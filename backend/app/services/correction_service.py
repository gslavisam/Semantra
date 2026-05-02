from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

from app.models.mapping import (
    CorrectionRuleCandidate,
    ReusableCorrectionRule,
    ReusableCorrectionRulePromotionRequest,
    UserCorrectionEntry,
)
from app.services.persistence_service import persistence_service


def _correction_signature(
    source: str,
    suggested_target: str | None,
    corrected_target: str | None,
    status: str,
) -> tuple[str, str | None, str | None, str]:
    return (source, suggested_target, corrected_target, status)


def _build_recommendation(
    source: str,
    suggested_target: str | None,
    corrected_target: str | None,
    status: str,
) -> str:
    if status == "rejected":
        return f"Reject target '{suggested_target}' by default for source '{source}' unless new evidence appears."
    if status == "accepted":
        return f"Prefer target '{corrected_target}' by default for source '{source}'."
    return f"Promote override rule for source '{source}': use '{corrected_target}' instead of '{suggested_target}'."


class UserCorrectionStore:
    def __init__(self) -> None:
        self._entries: list[UserCorrectionEntry] = []
        self._lock = Lock()
        self._feedback_enabled = True

    def append(self, entry: UserCorrectionEntry | dict) -> None:
        if isinstance(entry, dict):
            entry = UserCorrectionEntry.model_validate(entry)
        saved_entry = persistence_service.save_user_correction(entry)
        with self._lock:
            self._entries.append(saved_entry)

    def list_entries(self) -> list[UserCorrectionEntry]:
        with self._lock:
            if self._entries:
                return list(self._entries)
        persisted = persistence_service.list_user_corrections()
        with self._lock:
            self._entries = list(persisted)
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
        persistence_service.clear_user_corrections()

    def list_reusable_rules(self) -> list[ReusableCorrectionRule]:
        return persistence_service.list_reusable_correction_rules()

    def clear_reusable_rules(self) -> None:
        persistence_service.clear_reusable_correction_rules()

    def promote_reusable_rule(
        self,
        request: ReusableCorrectionRulePromotionRequest | dict,
    ) -> ReusableCorrectionRule:
        payload = request if isinstance(request, ReusableCorrectionRulePromotionRequest) else ReusableCorrectionRulePromotionRequest.model_validate(request)
        grouped = self._group_corrections()
        occurrence_count = grouped.get(
            _correction_signature(payload.source, payload.suggested_target, payload.corrected_target, payload.status),
            0,
        )
        if occurrence_count < 2:
            raise ValueError("Reusable correction rules require at least two matching corrections.")

        return persistence_service.save_reusable_correction_rule(
            ReusableCorrectionRule(
                source=payload.source,
                suggested_target=payload.suggested_target,
                corrected_target=payload.corrected_target,
                status=payload.status,
                occurrence_count=max(payload.occurrence_count, occurrence_count),
                created_by=payload.created_by,
                note=payload.note,
                active=True,
            )
        )

    def get_feedback_adjustment(self, source: str, target: str) -> float:
        return self.describe_feedback(source, target)["strength"]

    def describe_feedback(self, source: str, target: str) -> dict[str, int | float]:
        if not self._feedback_enabled:
            return {
                "strength": 0.0,
                "accepted_matches": 0,
                "overridden_matches": 0,
                "rejected_targets": 0,
                "overridden_away": 0,
                "promoted_preferred_rules": 0,
                "promoted_rejected_rules": 0,
                "promoted_overridden_away_rules": 0,
            }

        accepted_matches = 0
        overridden_matches = 0
        rejected_targets = 0
        overridden_away = 0
        promoted_preferred_rules = 0
        promoted_rejected_rules = 0
        promoted_overridden_away_rules = 0

        for entry in self.list_entries():
            if entry.source != source:
                continue
            if entry.corrected_target == target:
                if entry.status == "accepted":
                    accepted_matches += 1
                elif entry.status == "overridden":
                    overridden_matches += 1
            if entry.suggested_target == target:
                if entry.status == "rejected":
                    rejected_targets += 1
                elif entry.status == "overridden" and entry.corrected_target != target:
                    overridden_away += 1

        for rule in self.list_reusable_rules():
            if rule.source != source:
                continue
            if rule.corrected_target == target and rule.status in {"accepted", "overridden"}:
                promoted_preferred_rules += 1
            if rule.suggested_target == target:
                if rule.status == "rejected":
                    promoted_rejected_rules += 1
                elif rule.status == "overridden" and rule.corrected_target != target:
                    promoted_overridden_away_rules += 1

        boost = min(0.2, (0.06 * accepted_matches) + (0.05 * overridden_matches))
        penalty = min(0.2, (0.06 * rejected_targets) + (0.05 * overridden_away))
        rule_boost = min(0.3, 0.18 * promoted_preferred_rules)
        rule_penalty = min(0.3, 0.18 * (promoted_rejected_rules + promoted_overridden_away_rules))
        strength = round(boost + rule_boost - penalty - rule_penalty, 4)
        return {
            "strength": strength,
            "accepted_matches": accepted_matches,
            "overridden_matches": overridden_matches,
            "rejected_targets": rejected_targets,
            "overridden_away": overridden_away,
            "promoted_preferred_rules": promoted_preferred_rules,
            "promoted_rejected_rules": promoted_rejected_rules,
            "promoted_overridden_away_rules": promoted_overridden_away_rules,
        }

    @contextmanager
    def feedback_disabled(self):
        with self._lock:
            previous = self._feedback_enabled
            self._feedback_enabled = False
        try:
            yield
        finally:
            with self._lock:
                self._feedback_enabled = previous

    def _group_corrections(self) -> dict[tuple[str, str | None, str | None, str], int]:
        grouped: dict[tuple[str, str | None, str | None, str], int] = {}
        for entry in self.list_entries():
            key = _correction_signature(entry.source, entry.suggested_target, entry.corrected_target, entry.status)
            grouped[key] = grouped.get(key, 0) + 1
        return grouped

    def suggest_reusable_rules(self, min_occurrences: int = 2) -> list[CorrectionRuleCandidate]:
        grouped = self._group_corrections()
        promoted_rule_map = {
            _correction_signature(rule.source, rule.suggested_target, rule.corrected_target, rule.status): rule
            for rule in self.list_reusable_rules()
        }

        candidates: list[CorrectionRuleCandidate] = []
        for (source, suggested_target, corrected_target, status), occurrence_count in grouped.items():
            if occurrence_count < min_occurrences:
                continue
            promoted_rule = promoted_rule_map.get((source, suggested_target, corrected_target, status))
            candidates.append(
                CorrectionRuleCandidate(
                    source=source,
                    suggested_target=suggested_target,
                    corrected_target=corrected_target,
                    status=status,
                    occurrence_count=occurrence_count,
                    recommendation=_build_recommendation(source, suggested_target, corrected_target, status),
                    already_promoted=promoted_rule is not None,
                    promoted_rule_id=promoted_rule.rule_id if promoted_rule is not None else None,
                )
            )

        return sorted(candidates, key=lambda item: (item.occurrence_count, item.source), reverse=True)


correction_store = UserCorrectionStore()