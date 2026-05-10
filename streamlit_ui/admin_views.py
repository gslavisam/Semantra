from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _filter_canonical_concepts(concepts: list[dict] | None, query: str | None = None) -> list[dict]:
    items = concepts or []
    normalized_query = _normalized_text(query).lower()
    if not normalized_query:
        return list(items)

    filtered: list[dict] = []
    for concept in items:
        haystacks = [
            _normalized_text(concept.get("concept_id")),
            _normalized_text(concept.get("display_name")),
            _normalized_text(concept.get("description")),
            _normalized_text(concept.get("entity")),
            _normalized_text(concept.get("attribute")),
            _normalized_text(concept.get("source")),
            *(str(value or "") for value in concept.get("source_systems", [])),
            *(str(value or "") for value in concept.get("business_domains", [])),
            *(str(alias or "") for alias in concept.get("base_aliases", [])),
            *(str(alias or "") for alias in concept.get("active_overlay_aliases", [])),
        ]
        if any(normalized_query in value.lower() for value in haystacks if value):
            filtered.append(concept)
    return filtered


def _filter_canonical_concepts_by_scope(
    concepts: list[dict] | None,
    source_system: str | None = None,
    business_domain: str | None = None,
) -> list[dict]:
    items = concepts or []
    normalized_source_system = _normalized_text(source_system)
    normalized_business_domain = _normalized_text(business_domain)
    if not normalized_source_system and not normalized_business_domain:
        return list(items)

    filtered: list[dict] = []
    for concept in items:
        concept_source_systems = {
            _normalized_text(value)
            for value in concept.get("source_systems", [])
            if _normalized_text(value)
        }
        concept_business_domains = {
            _normalized_text(value)
            for value in concept.get("business_domains", [])
            if _normalized_text(value)
        }
        if normalized_source_system and normalized_source_system not in concept_source_systems:
            continue
        if normalized_business_domain and normalized_business_domain not in concept_business_domains:
            continue
        filtered.append(concept)
    return filtered


def _filter_canonical_concepts_by_focus(concepts: list[dict] | None, focus: str | None = None) -> list[dict]:
    items = concepts or []
    normalized_focus = _normalized_text(focus).lower() or "all"
    if normalized_focus == "all":
        return list(items)

    filtered: list[dict] = []
    for concept in items:
        source = _normalized_text(concept.get("source")).lower() or "base"
        usage_count = int(concept.get("usage_count", 0) or 0)
        field_context_count = int(concept.get("field_context_count", 0) or 0)
        overlay_count = int(concept.get("active_overlay_entry_count", 0) or 0)
        if normalized_focus == "active_overlay" and overlay_count > 0:
            filtered.append(concept)
        elif normalized_focus == "overlay_only" and source == "overlay_only":
            filtered.append(concept)
        elif normalized_focus == "in_use" and usage_count > 0:
            filtered.append(concept)
        elif normalized_focus == "with_context" and field_context_count > 0:
            filtered.append(concept)
        elif normalized_focus == "base_only" and source == "base":
            filtered.append(concept)
    return filtered


def _canonical_overlay_summary(runtime: dict | None, overlays: list[dict] | None) -> dict[str, object]:
    runtime_payload = runtime or {}
    overlay_rows = overlays or []
    entry_type_counts = runtime_payload.get("entry_type_counts") or {}
    status_counts: dict[str, int] = {}
    for overlay in overlay_rows:
        status = _normalized_text(overlay.get("status")).lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "mode": runtime_payload.get("mode") or "base_only",
        "active_overlay_name": runtime_payload.get("active_overlay_name") or "none",
        "active_entry_count": int(runtime_payload.get("active_entry_count", 0) or 0),
        "concept_alias_entries": int(entry_type_counts.get("concept_alias", 0) or 0),
        "total_versions": len(overlay_rows),
        "active_versions": int(status_counts.get("active", 0) or 0),
        "validated_versions": int(status_counts.get("validated", 0) or 0),
        "archived_versions": int(status_counts.get("archived", 0) or 0),
    }


def _overlay_activation_block_reason(overlay: dict | None) -> str:
    status = _normalized_text((overlay or {}).get("status")).lower() or "draft"
    if status == "validated":
        return ""
    if status == "active":
        return "This knowledge overlay is already active."
    return f"Only validated knowledge overlays can be activated. Current status: {status}."


def _overlay_archive_block_reason(overlay: dict | None) -> str:
    status = _normalized_text((overlay or {}).get("status")).lower() or "draft"
    if status in {"validated", "active"}:
        return ""
    if status == "archived":
        return "This knowledge overlay is already archived."
    return f"Only validated or active knowledge overlays can be archived. Current status: {status}."


def _canonical_concept_registry_rows(concepts: list[dict] | None) -> list[dict]:
    rows: list[dict] = []
    for concept in concepts or []:
        base_aliases = [str(alias).strip() for alias in concept.get("base_aliases", []) if str(alias).strip()]
        overlay_aliases = [str(alias).strip() for alias in concept.get("active_overlay_aliases", []) if str(alias).strip()]
        rows.append(
            {
                "concept_id": concept.get("concept_id"),
                "display_name": concept.get("display_name"),
                "entity": concept.get("entity") or "",
                "attribute": concept.get("attribute") or "",
                "data_type": concept.get("data_type") or "",
                "source": concept.get("source") or "base",
                "usage_count": concept.get("usage_count", 0),
                "field_context_count": concept.get("field_context_count", 0),
                "active_overlay_entry_count": concept.get("active_overlay_entry_count", 0),
                "source_systems": ", ".join(str(value).strip() for value in concept.get("source_systems", []) if str(value).strip()),
                "business_domains": ", ".join(str(value).strip() for value in concept.get("business_domains", []) if str(value).strip()),
                "base_aliases": ", ".join(base_aliases),
                "active_overlay_aliases": ", ".join(overlay_aliases),
            }
        )
    return rows


def _canonical_concept_option_label(concept: dict) -> str:
    concept_id = _normalized_text(concept.get("concept_id")) or "unknown"
    display_name = _normalized_text(concept.get("display_name")) or concept_id
    source = _normalized_text(concept.get("source")) or "base"
    usage_count = int(concept.get("usage_count", 0) or 0)
    return f"{concept_id} | {display_name} | source={source} | usage={usage_count}"


def _canonical_gap_candidate_key(index: int, candidate: dict) -> str:
    source = _normalized_text(candidate.get("source"))
    target = _normalized_text(candidate.get("target"))
    return f"canonical_gap_{source or 'unknown'}_{target or 'unknown'}".replace(" ", "_")


def _canonical_gap_console_state(
    candidate_key: str,
    console_states: dict[str, str] | None = None,
    stewardship_item: dict | None = None,
) -> str:
    stewardship_state = _canonical_gap_stewardship_status(stewardship_item)
    if stewardship_state in {"ignored", "approved", "rejected"}:
        return stewardship_state
    if stewardship_state in {"new", "needs_review", "ready_for_approval"}:
        return "active"
    state = _normalized_text((console_states or {}).get(candidate_key)) or "active"
    if state not in {"active", "ignored", "approved", "rejected"}:
        return "active"
    return state


def _canonical_gap_stewardship_status(stewardship_item: dict | None = None) -> str:
    state = _normalized_text((stewardship_item or {}).get("status"))
    if state not in {"new", "needs_review", "ready_for_approval", "approved", "rejected", "ignored", "promoted"}:
        return ""
    return state


def _canonical_gap_proposal_state(
    candidate_key: str,
    proposal_states: dict[str, str] | None = None,
    stewardship_item: dict | None = None,
) -> str:
    stewardship_state = _canonical_gap_stewardship_status(stewardship_item)
    if stewardship_state in {"new", "needs_review", "ready_for_approval"}:
        return stewardship_state
    state = _normalized_text((proposal_states or {}).get(candidate_key)) or "new"
    if state not in {"new", "needs_review", "ready_for_approval"}:
        return "new"
    return state


def _canonical_gap_proposal_state_label(state: str) -> str:
    return {
        "new": "New",
        "needs_review": "Needs review",
        "ready_for_approval": "Ready for approval",
        "approved": "Approved",
        "rejected": "Rejected",
        "ignored": "Ignored",
        "promoted": "Promoted",
        "active": "Active",
        "not_tracked": "Not tracked",
    }.get(state, state)


def _canonical_gap_proposal_state_map(records: list[dict] | None = None) -> dict[str, str]:
    states: dict[str, str] = {}
    for record in records or []:
        candidate_key = _normalized_text(record.get("candidate_key") or record.get("item_key"))
        if not candidate_key:
            continue
        proposal_state = _normalized_text(record.get("proposal_state") or record.get("status"))
        if proposal_state not in {"new", "needs_review", "ready_for_approval"}:
            continue
        states[candidate_key] = _canonical_gap_proposal_state(candidate_key, {candidate_key: proposal_state})
    return states


def _canonical_gap_stewardship_item_map(records: list[dict] | None = None) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for record in records or []:
        item_key = _normalized_text(record.get("item_key") or record.get("candidate_key"))
        item_type = _normalized_text(record.get("item_type")) or "canonical_gap"
        if not item_key or item_type != "canonical_gap":
            continue
        items[item_key] = record
    return items


def _overlay_promotion_item_key(entry: dict, overlay_version: dict | None = None) -> str:
    overlay_id = _normalized_text(entry.get("overlay_id") or entry.get("version_id") or (overlay_version or {}).get("overlay_id"))
    entry_id = _normalized_text(entry.get("entry_id"))
    alias = _normalized_text(entry.get("alias")) or "unknown"
    canonical_term = _normalized_text(entry.get("canonical_concept_id") or entry.get("canonical_term")) or "unknown"
    if overlay_id and entry_id:
        return f"overlay_promotion_{overlay_id}_{entry_id}".replace(" ", "_")
    return f"overlay_promotion_{overlay_id or canonical_term}_{alias}".replace(" ", "_")


def _overlay_promotion_item_map(records: list[dict] | None = None) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for record in records or []:
        item_key = _normalized_text(record.get("item_key"))
        if not item_key or _normalized_text(record.get("item_type")) != "overlay_promotion":
            continue
        items[item_key] = record
    return items


def _overlay_promotion_status(item: dict | None = None) -> str:
    status = _normalized_text((item or {}).get("status"))
    if status in {"new", "needs_review", "ready_for_approval", "promoted", "ignored", "rejected"}:
        return status
    return "not_tracked"


def _overlay_promotion_can_execute(item: dict | None = None) -> bool:
    return bool((item or {}).get("item_id")) and _overlay_promotion_status(item) == "ready_for_approval"


def _overlay_promotion_execution_request(changed_by: str | None, note: str | None = None) -> dict:
    payload = {"changed_by": _normalized_text(changed_by) or None}
    if _normalized_text(note):
        payload["note"] = _normalized_text(note)
    return payload


def _overlay_promotion_entry_rows(
    entries: list[dict] | None,
    promotion_items: dict[str, dict] | None = None,
    overlay_version: dict | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for entry in entries or []:
        if _normalized_text(entry.get("entry_type")) and _normalized_text(entry.get("entry_type")) != "concept_alias":
            continue
        item = (promotion_items or {}).get(_overlay_promotion_item_key(entry, overlay_version)) or {}
        rows.append(
            {
                "alias": _normalized_text(entry.get("alias")),
                "canonical_term": _normalized_text(entry.get("canonical_term")),
                "canonical_concept_id": _normalized_text(entry.get("canonical_concept_id")),
                "source_system": _normalized_text(entry.get("source_system")),
                "promotion_status": _overlay_promotion_status(item),
                "owner": _normalized_text(item.get("owner")),
                "assignee": _normalized_text(item.get("assignee")),
                "review_note": _normalized_text(item.get("review_note")),
            }
        )
    return rows


def _overlay_promotion_items_for_concept(concept: dict | None, records: list[dict] | None = None) -> list[dict]:
    concept_id = _normalized_text((concept or {}).get("concept_id"))
    if not concept_id:
        return []
    items: list[dict] = []
    for record in records or []:
        if _normalized_text(record.get("item_type")) != "overlay_promotion":
            continue
        record_concept_id = _normalized_text(record.get("concept_id") or record.get("target"))
        if record_concept_id != concept_id:
            continue
        items.append(record)
    return items


def _overlay_promotion_rows_for_concept(concept: dict | None, records: list[dict] | None = None) -> list[dict]:
    rows: list[dict] = []
    for item in _overlay_promotion_items_for_concept(concept, records):
        rows.append(
            {
                "alias": _normalized_text(item.get("source")),
                "status": _overlay_promotion_status(item),
                "source_system": _normalized_text(item.get("source_system")),
                "business_domain": _normalized_text(item.get("business_domain")),
                "owner": _normalized_text(item.get("owner")),
                "assignee": _normalized_text(item.get("assignee")),
                "review_note": _normalized_text(item.get("review_note")),
            }
        )
    return rows


def _overlay_promotion_item_record_label(item: dict | None = None) -> str:
    alias = _normalized_text((item or {}).get("source")) or "unknown"
    source_system = _normalized_text((item or {}).get("source_system")) or "n/a"
    status = _overlay_promotion_status(item)
    return f"{alias} | source_system={source_system} | status={status}"


def _overlay_promotion_option_label(entry: dict, item: dict | None = None) -> str:
    alias = _normalized_text(entry.get("alias")) or "unknown"
    concept_id = _normalized_text(entry.get("canonical_concept_id")) or _normalized_text(entry.get("canonical_term")) or "unknown"
    status = _overlay_promotion_status(item)
    return f"{alias} -> {concept_id} | status={status}"


def _overlay_promotion_item_request(
    entry: dict,
    overlay_version: dict | None,
    *,
    status: str,
    owner: str | None = None,
    assignee: str | None = None,
    review_note: str | None = None,
    changed_by: str | None = None,
) -> dict:
    overlay_payload = {
        **entry,
        "overlay_id": entry.get("overlay_id") or entry.get("version_id") or (overlay_version or {}).get("overlay_id"),
        "overlay_name": (overlay_version or {}).get("name"),
        "overlay_status": (overlay_version or {}).get("status"),
    }
    alias = _normalized_text(entry.get("alias")) or None
    concept_id = _normalized_text(entry.get("canonical_concept_id")) or None
    return {
        "item_type": "overlay_promotion",
        "item_key": _overlay_promotion_item_key(entry, overlay_version),
        "title": f"Promote overlay alias '{alias or 'unknown'}'",
        "status": status,
        "concept_id": concept_id,
        "source": alias,
        "target": concept_id or _normalized_text(entry.get("canonical_term")) or None,
        "source_system": _normalized_text(entry.get("source_system")) or None,
        "business_domain": _normalized_text(entry.get("domain")) or None,
        "owner": _normalized_text(owner) or None,
        "assignee": _normalized_text(assignee) or None,
        "review_note": _normalized_text(review_note) or None,
        "overlay_entry_payload": overlay_payload,
        "created_by": _normalized_text(changed_by) or None,
        "changed_by": _normalized_text(changed_by) or None,
    }


def _canonical_gap_effective_status(
    candidate_key: str,
    console_states: dict[str, str] | None = None,
    proposal_states: dict[str, str] | None = None,
    stewardship_item: dict | None = None,
) -> str:
    stewardship_state = _canonical_gap_stewardship_status(stewardship_item)
    if stewardship_state:
        return stewardship_state
    console_state = _canonical_gap_console_state(candidate_key, console_states)
    if console_state != "active":
        return console_state
    return _canonical_gap_proposal_state(candidate_key, proposal_states)


def _canonical_gap_stewardship_item_request(
    candidate_key: str,
    candidate: dict,
    suggestion: dict | None = None,
    *,
    status: str,
    owner: str | None = None,
    assignee: str | None = None,
    review_note: str | None = None,
    changed_by: str | None = None,
) -> dict:
    return {
        "item_type": "canonical_gap",
        "item_key": candidate_key,
        "title": f"{_normalized_text(candidate.get('source')) or 'unknown'} -> {_normalized_text(candidate.get('target')) or 'unknown'}",
        "status": status,
        "concept_id": _normalized_text((suggestion or {}).get("concept_id")) or None,
        "source": _normalized_text(candidate.get("source")) or None,
        "target": _normalized_text(candidate.get("target")) or None,
        "owner": _normalized_text(owner) or None,
        "assignee": _normalized_text(assignee) or None,
        "review_note": _normalized_text(review_note) or None,
        "candidate_payload": candidate,
        "suggestion_payload": suggestion or {},
        "created_by": _normalized_text(changed_by) or None,
        "changed_by": _normalized_text(changed_by) or None,
    }


def _canonical_gap_repeat_summary_rows(
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None = None,
    console_states: dict[str, str] | None = None,
    proposal_states: dict[str, str] | None = None,
    stewardship_items: dict[str, dict] | None = None,
) -> list[dict]:
    observations: dict[str, dict[str, object]] = {}
    seen_candidate_keys: set[str] = set()

    for index, candidate in enumerate(candidates or []):
        candidate_key = _canonical_gap_candidate_key(index, candidate)
        seen_candidate_keys.add(candidate_key)
        stewardship_item = (stewardship_items or {}).get(candidate_key) or {}
        suggestion = (suggestions or {}).get(candidate_key) or {}
        observations[candidate_key] = {
            "source": _normalized_text(candidate.get("source") or stewardship_item.get("source")) or "unknown",
            "target": _normalized_text(candidate.get("target") or stewardship_item.get("target")) or "unknown",
            "concept_id": _normalized_text(suggestion.get("concept_id") or stewardship_item.get("concept_id")),
            "status": _canonical_gap_effective_status(
                candidate_key,
                console_states,
                proposal_states,
                stewardship_item,
            ),
            "current_queue": True,
            "updated_at": _normalized_text(stewardship_item.get("updated_at") or stewardship_item.get("created_at")),
        }

    for item_key, stewardship_item in (stewardship_items or {}).items():
        if item_key in seen_candidate_keys:
            continue
        observations[item_key] = {
            "source": _normalized_text(stewardship_item.get("source")) or "unknown",
            "target": _normalized_text(stewardship_item.get("target")) or "unknown",
            "concept_id": _normalized_text(stewardship_item.get("concept_id")),
            "status": _canonical_gap_stewardship_status(stewardship_item) or "not_tracked",
            "current_queue": False,
            "updated_at": _normalized_text(stewardship_item.get("updated_at") or stewardship_item.get("created_at")),
        }

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for observation in observations.values():
        target = _normalized_text(observation.get("target")) or "unknown"
        concept_id = _normalized_text(observation.get("concept_id"))
        group_key = (target.lower(), concept_id.lower())
        group = grouped.setdefault(
            group_key,
            {
                "target": target,
                "suggested_concept_id": concept_id,
                "observations": 0,
                "distinct_source_count": 0,
                "current_queue_count": 0,
                "new": 0,
                "needs_review": 0,
                "ready_for_approval": 0,
                "approved": 0,
                "ignored": 0,
                "rejected": 0,
                "promoted": 0,
                "source_examples": [],
                "latest_observed_at": "",
                "_source_keys": set(),
            },
        )
        group["observations"] = int(group["observations"]) + 1
        source = _normalized_text(observation.get("source")) or "unknown"
        source_key = source.lower()
        source_keys = group["_source_keys"]
        if isinstance(source_keys, set) and source_key not in source_keys:
            source_keys.add(source_key)
            group["distinct_source_count"] = int(group["distinct_source_count"]) + 1
            source_examples = group["source_examples"]
            if isinstance(source_examples, list) and len(source_examples) < 4:
                source_examples.append(source)
        if observation.get("current_queue"):
            group["current_queue_count"] = int(group["current_queue_count"]) + 1
        status = _normalized_text(observation.get("status"))
        if status in {"new", "needs_review", "ready_for_approval", "approved", "ignored", "rejected", "promoted"}:
            group[status] = int(group[status]) + 1
        updated_at = _normalized_text(observation.get("updated_at"))
        if updated_at and updated_at > _normalized_text(group.get("latest_observed_at")):
            group["latest_observed_at"] = updated_at

    rows: list[dict] = []
    for group in grouped.values():
        if int(group["observations"]) < 2:
            continue
        rows.append(
            {
                "target": group["target"],
                "suggested_concept_id": group["suggested_concept_id"],
                "observations": group["observations"],
                "distinct_source_count": group["distinct_source_count"],
                "current_queue_count": group["current_queue_count"],
                "ready_for_approval": group["ready_for_approval"],
                "needs_review": group["needs_review"],
                "new": group["new"],
                "ignored": group["ignored"],
                "rejected": group["rejected"],
                "approved": group["approved"],
                "promoted": group["promoted"],
                "source_examples": ", ".join(group["source_examples"]),
                "latest_observed_at": group["latest_observed_at"],
            }
        )

    return sorted(
        rows,
        key=lambda item: (
            -int(item.get("observations", 0) or 0),
            -int(item.get("distinct_source_count", 0) or 0),
            _normalized_text(item.get("target")).lower(),
            _normalized_text(item.get("suggested_concept_id")).lower(),
        ),
    )


def _knowledge_stewardship_status_update_request(
    status: str,
    changed_by: str | None,
    *,
    owner: str | None = None,
    assignee: str | None = None,
    review_note: str | None = None,
    note: str | None = None,
) -> dict:
    payload = {
        "status": status,
        "changed_by": _normalized_text(changed_by) or None,
        "owner": _normalized_text(owner) or None,
        "assignee": _normalized_text(assignee) or None,
        "review_note": _normalized_text(review_note) or None,
    }
    if _normalized_text(note):
        payload["note"] = _normalized_text(note)
    return payload


def _canonical_gap_queue_rows(
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None = None,
    console_states: dict[str, str] | None = None,
    proposal_states: dict[str, str] | None = None,
    stewardship_items: dict[str, dict] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    suggestion_map = suggestions or {}
    for index, candidate in enumerate(candidates or []):
        candidate_key = _canonical_gap_candidate_key(index, candidate)
        suggestion = suggestion_map.get(candidate_key) or {}
        stewardship_item = (stewardship_items or {}).get(candidate_key) or {}
        aliases = [str(alias).strip() for alias in suggestion.get("aliases", []) if str(alias).strip()]
        rows.append(
            {
                "source": candidate.get("source") or "",
                "target": candidate.get("target") or "",
                "confidence_pct": int(float(candidate.get("confidence", 0.0) or 0.0) * 100),
                "confidence_label": candidate.get("confidence_label") or "",
                "status": candidate.get("status") or "",
                "method": candidate.get("method") or "",
                "reason": candidate.get("reason") or "",
                "suggested_action": suggestion.get("action") or "pending",
                "suggested_concept": suggestion.get("concept_id") or "",
                "suggested_display_name": suggestion.get("display_name") or "",
                "alias_count": len(aliases),
                "reasoning_count": len(suggestion.get("reasoning") or []),
                "risk_count": len(suggestion.get("risk_notes") or []),
                "console_state": _canonical_gap_console_state(candidate_key, console_states, stewardship_item),
                "proposal_state": _canonical_gap_proposal_state(candidate_key, proposal_states, stewardship_item),
                "stewardship_status": _canonical_gap_effective_status(candidate_key, console_states, proposal_states, stewardship_item),
                "owner": stewardship_item.get("owner") or "",
                "assignee": stewardship_item.get("assignee") or "",
            }
        )
    return rows


def _canonical_gap_option_label(index: int, candidate: dict, suggestion: dict | None = None) -> str:
    source = _normalized_text(candidate.get("source")) or "unknown"
    target = _normalized_text(candidate.get("target")) or "unknown"
    confidence_pct = int(float(candidate.get("confidence", 0.0) or 0.0) * 100)
    action = _normalized_text((suggestion or {}).get("action")) or "pending"
    return f"{source} -> {target} | confidence={confidence_pct}% | action={action}"


def _canonical_gap_can_approve(
    suggestion: dict | None,
    console_state: str = "active",
    proposal_state: str = "new",
) -> bool:
    action = _normalized_text((suggestion or {}).get("action"))
    return bool(
        action
        and action != "no_action"
        and console_state == "active"
        and proposal_state == "ready_for_approval"
    )


def _canonical_gap_can_ignore(console_state: str) -> bool:
    return console_state == "active"


def _canonical_gap_can_restore(console_state: str) -> bool:
    return console_state == "ignored"


def _canonical_gap_can_reject(console_state: str) -> bool:
    return console_state == "active"


def _canonical_gap_rejection_request(
    candidate: dict,
    suggestion: dict | None,
    rejected_by: str | None,
    note: str | None,
    disposition: str = "rejected",
) -> dict:
    payload: dict[str, object] = {
        "candidate": candidate,
        "disposition": disposition,
        "rejected_by": _normalized_text(rejected_by) or "streamlit-admin-debug",
    }
    if suggestion:
        payload["suggestion"] = suggestion
    if _normalized_text(note):
        payload["note"] = _normalized_text(note)
    return payload


def _canonical_gap_related_audit_entries(audit_entries: list[dict] | None, candidate: dict | None) -> list[dict]:
    source = _normalized_text((candidate or {}).get("source"))
    target = _normalized_text((candidate or {}).get("target"))
    if not source or not target:
        return []

    needle = f"{source} -> {target}"
    rows: list[dict] = []
    for entry in audit_entries or []:
        message = _normalized_text(entry.get("message"))
        if needle not in message:
            continue
        rows.append(
            {
                "action": entry.get("action") or "",
                "overlay_name": entry.get("overlay_name") or "",
                "created_at": entry.get("created_at") or "",
                "message": message,
            }
        )
    return rows


def _canonical_gap_approval_request(candidate: dict, suggestion: dict, approved_by: str | None) -> dict:
    return {
        "candidate": candidate,
        "suggestion": suggestion,
        "approved_by": _normalized_text(approved_by) or "streamlit-admin-debug",
    }


def _canonical_gap_impact_preview_rows(
    selected_index: int,
    selected_candidate: dict,
    selected_suggestion: dict | None,
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None = None,
    console_states: dict[str, str] | None = None,
) -> list[dict]:
    action = _normalized_text((selected_suggestion or {}).get("action"))
    if action not in {"existing_concept_alias", "new_canonical_concept"}:
        return []

    selected_source = _normalized_text(selected_candidate.get("source")).lower()
    selected_target = _normalized_text(selected_candidate.get("target")).lower()
    suggested_concept_id = _normalized_text((selected_suggestion or {}).get("concept_id")).lower()
    alias_set = {
        _normalized_text(alias).lower()
        for alias in (selected_suggestion or {}).get("aliases", [])
        if _normalized_text(alias)
    }
    if selected_source:
        alias_set.add(selected_source)

    rows: list[dict] = []
    suggestion_map = suggestions or {}
    for index, candidate in enumerate(candidates or []):
        candidate_source = _normalized_text(candidate.get("source"))
        candidate_target = _normalized_text(candidate.get("target"))
        candidate_source_normalized = candidate_source.lower()
        candidate_target_normalized = candidate_target.lower()
        candidate_key = _canonical_gap_candidate_key(index, candidate)
        candidate_suggestion = suggestion_map.get(candidate_key) or {}

        impact_reasons: list[str] = []
        if index == selected_index:
            impact_reasons.append("selected gap under review")
        else:
            if selected_source and candidate_source_normalized == selected_source:
                impact_reasons.append("same source column")
            if alias_set and candidate_source_normalized in alias_set and candidate_source_normalized != selected_source:
                impact_reasons.append("source matches proposed alias")
            if selected_target and candidate_target_normalized == selected_target:
                impact_reasons.append("same target field")
            if suggested_concept_id and _normalized_text(candidate_suggestion.get("concept_id")).lower() == suggested_concept_id:
                impact_reasons.append("same suggested concept")

        if not impact_reasons:
            continue

        rows.append(
            {
                "source": candidate_source,
                "target": candidate_target,
                "confidence_pct": int(float(candidate.get("confidence", 0.0) or 0.0) * 100),
                "console_state": _canonical_gap_console_state(candidate_key, console_states),
                "impact_reason": " | ".join(dict.fromkeys(impact_reasons)),
            }
        )

    return rows


def _canonical_gap_pending_rows_for_concept(
    concept: dict | None,
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None = None,
    console_states: dict[str, str] | None = None,
    proposal_states: dict[str, str] | None = None,
    stewardship_items: dict[str, dict] | None = None,
) -> list[dict]:
    concept_id = _normalized_text((concept or {}).get("concept_id"))
    if not concept_id:
        return []

    rows: list[dict] = []
    suggestion_map = suggestions or {}
    for index, candidate in enumerate(candidates or []):
        candidate_key = _canonical_gap_candidate_key(index, candidate)
        suggestion = suggestion_map.get(candidate_key) or {}
        stewardship_item = (stewardship_items or {}).get(candidate_key) or {}
        if _normalized_text(suggestion.get("action")) != "existing_concept_alias":
            continue
        if _normalized_text(suggestion.get("concept_id")) != concept_id:
            continue

        console_state = _canonical_gap_console_state(candidate_key, console_states, stewardship_item)
        if console_state != "active":
            continue
        proposal_state = _canonical_gap_proposal_state(candidate_key, proposal_states, stewardship_item)

        reasoning = [str(item).strip() for item in suggestion.get("reasoning") or [] if str(item).strip()]
        risk_notes = [str(item).strip() for item in suggestion.get("risk_notes") or [] if str(item).strip()]
        aliases = [str(item).strip() for item in suggestion.get("aliases") or [] if str(item).strip()]
        rows.append(
            {
                "source": _normalized_text(candidate.get("source")),
                "target": _normalized_text(candidate.get("target")),
                "confidence_pct": int(float(candidate.get("confidence", 0.0) or 0.0) * 100),
                "suggested_action": _normalized_text(suggestion.get("action")) or "pending",
                "proposal_state": proposal_state,
                "aliases": ", ".join(aliases),
                "reasoning": " | ".join(reasoning),
                "risk_notes": " | ".join(risk_notes),
            }
        )

    order = {"ready_for_approval": 0, "needs_review": 1, "new": 2}
    rows.sort(
        key=lambda item: (
            order.get(_normalized_text(item.get("proposal_state")), 99),
            -int(item.get("confidence_pct", 0) or 0),
            item.get("source") or "",
        )
    )
    return rows


def _refresh_canonical_console_knowledge_state(*, api_request: Callable[..., Any]) -> None:
    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
    st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
    st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
        st.session_state.get("debug_knowledge_stewardship_items")
    )


def _bootstrap_active_overlay_detail(*, api_request: Callable[..., Any]) -> None:
    if st.session_state.get("debug_selected_knowledge_overlay") is not None:
        return

    runtime = st.session_state.get("debug_knowledge_runtime") or {}
    active_overlay_id = runtime.get("active_overlay_id")
    if active_overlay_id is None:
        return

    overlays = st.session_state.get("debug_knowledge_overlays") or []
    active_overlay = next(
        (item for item in overlays if item.get("overlay_id") == active_overlay_id),
        None,
    )
    if active_overlay is None:
        return

    st.session_state["debug_selected_overlay_version"] = (
        f"#{active_overlay['overlay_id']} | {active_overlay['name']} | {active_overlay['status']}"
    )
    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{active_overlay_id}")


def _ensure_canonical_concept_detail_loaded(*, api_request: Callable[..., Any], selected_concept_id: str | None) -> bool:
    normalized_selected_concept_id = _normalized_text(selected_concept_id)
    if not normalized_selected_concept_id:
        return False

    current_concept_id = _normalized_text(
        ((st.session_state.get("debug_canonical_concept_detail") or {}).get("concept") or {}).get("concept_id")
    )
    if current_concept_id == normalized_selected_concept_id:
        return False

    st.session_state["debug_canonical_concept_detail"] = api_request(
        "GET",
        f"/knowledge/canonical-concepts/{normalized_selected_concept_id}",
    )
    return True


def _preferred_canonical_concept_label(
    concepts: list[dict] | None,
    records: list[dict] | None = None,
    *,
    active_overlay_id: object | None = None,
    current_label: str | None = None,
) -> str | None:
    concept_items = concepts or []
    if not concept_items:
        return None

    labels_by_concept_id = {
        _normalized_text(item.get("concept_id")): _canonical_concept_option_label(item)
        for item in concept_items
        if _normalized_text(item.get("concept_id"))
    }
    if current_label in labels_by_concept_id.values():
        return current_label

    normalized_active_overlay_id = _normalized_text(active_overlay_id)
    promotion_concept_ids: set[str] = set()
    active_overlay_promotion_concept_ids: set[str] = set()
    for record in records or []:
        if _normalized_text(record.get("item_type")) != "overlay_promotion":
            continue
        record_concept_id = _normalized_text(record.get("concept_id") or record.get("target"))
        if not record_concept_id:
            continue
        promotion_concept_ids.add(record_concept_id)
        record_overlay_id = _normalized_text(((record.get("overlay_entry_payload") or {}).get("overlay_id")))
        if normalized_active_overlay_id and record_overlay_id == normalized_active_overlay_id:
            active_overlay_promotion_concept_ids.add(record_concept_id)

    def concept_rank(item: dict) -> tuple[int, int, int, str]:
        concept_id = _normalized_text(item.get("concept_id"))
        source = _normalized_text(item.get("source")).lower() or "base"
        active_overlay_entry_count = int(item.get("active_overlay_entry_count", 0) or 0)
        usage_count = int(item.get("usage_count", 0) or 0)
        return (
            0 if concept_id in active_overlay_promotion_concept_ids else 1,
            0 if concept_id in promotion_concept_ids else 1,
            0 if active_overlay_entry_count > 0 or source == "overlay_only" else 1,
            -usage_count,
        )

    preferred_concept = min(concept_items, key=concept_rank)
    return labels_by_concept_id.get(_normalized_text(preferred_concept.get("concept_id")))


def _bootstrap_canonical_console_state(*, api_request: Callable[..., Any]) -> None:
    if st.session_state.get("debug_canonical_console_manual_clear"):
        return
    if st.session_state.get("debug_canonical_console_bootstrapped"):
        return

    _refresh_canonical_console_knowledge_state(api_request=api_request)
    _bootstrap_active_overlay_detail(api_request=api_request)
    st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
    st.session_state["debug_canonical_console_bootstrapped"] = True


def _canonical_console_action_label(loaded: bool, noun: str) -> str:
    prefix = "Refresh" if loaded else "Load"
    return f"{prefix} {noun}"


def render_canonical_console_panel(
    *,
    api_request: Callable[..., Any],
    api_request_content: Callable[..., bytes],
    upload_file_to_request_files: Callable[[Any], dict | None],
) -> None:
    st.header("Canonical Console")
    st.caption(
        "Concept registry and review console for the active canonical model, including overlay aliases, usage, gap queue, and audit context."
    )

    try:
        _bootstrap_canonical_console_state(api_request=api_request)
    except httpx.HTTPError as error:
        st.session_state["last_action"] = {
            "level": "error",
            "message": f"Bootstrapping canonical console failed: {error}",
        }

    if "debug_knowledge_audit_logs" not in st.session_state:
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
        except httpx.HTTPError:
            st.session_state["debug_knowledge_audit_logs"] = []

    if "debug_knowledge_stewardship_items" not in st.session_state:
        try:
            st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
        except httpx.HTTPError:
            st.session_state["debug_knowledge_stewardship_items"] = []

    if "debug_canonical_gap_proposal_states" not in st.session_state:
        try:
            st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                st.session_state.get("debug_knowledge_stewardship_items")
            )
        except httpx.HTTPError:
            st.session_state["debug_canonical_gap_proposal_states"] = {}

    canonical_console_actions = st.columns(4)
    if canonical_console_actions[0].button(
        _canonical_console_action_label(st.session_state.get("debug_canonical_concepts") is not None, "canonical concept registry"),
        width="stretch",
        key="debug_load_canonical_concepts",
    ):
        try:
            st.session_state.pop("debug_canonical_console_manual_clear", None)
            st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            _bootstrap_active_overlay_detail(api_request=api_request)
            st.session_state["debug_canonical_console_bootstrapped"] = True
            st.session_state["last_action"] = {"level": "success", "message": "Loaded canonical concept registry."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Loading canonical concept registry failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[1].button(
        "Refresh overlay summary",
        width="stretch",
        key="canonical_console_refresh_overlay_summary",
    ):
        try:
            st.session_state.pop("debug_canonical_console_manual_clear", None)
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            _bootstrap_active_overlay_detail(api_request=api_request)
            if st.session_state.get("debug_canonical_concepts") is None:
                st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
            st.session_state["debug_canonical_console_bootstrapped"] = True
            st.session_state["last_action"] = {
                "level": "success",
                "message": "Refreshed overlay summary and knowledge audit state.",
            }
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Refreshing overlay summary failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[2].button(
        _canonical_console_action_label(st.session_state.get("debug_knowledge_audit_logs") is not None, "knowledge audit log"),
        width="stretch",
        key="canonical_console_load_audit",
    ):
        try:
            st.session_state.pop("debug_canonical_console_manual_clear", None)
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Loading knowledge audit log failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[3].button(
        "Clear canonical console state",
        width="stretch",
        key="debug_clear_canonical_concepts",
    ):
        for key in (
            "debug_canonical_concepts",
            "debug_selected_canonical_concept_label",
            "debug_canonical_concept_detail",
            "debug_selected_canonical_gap_label",
            "debug_canonical_gap_console_states",
            "debug_knowledge_audit_logs",
            "debug_knowledge_runtime",
            "debug_knowledge_overlays",
            "debug_selected_knowledge_overlay",
            "debug_knowledge_validation",
            "debug_knowledge_created",
            "debug_canonical_glossary_import",
            "canonical_glossary_export_bytes",
            "debug_canonical_console_bootstrapped",
        ):
            st.session_state.pop(key, None)
        st.session_state["debug_canonical_console_manual_clear"] = True
        st.session_state["last_action"] = {"level": "info", "message": "Cleared canonical console state."}
        st.rerun()

    overlay_summary = _canonical_overlay_summary(
        st.session_state.get("debug_knowledge_runtime"),
        st.session_state.get("debug_knowledge_overlays"),
    )
    st.subheader("Overlay Summary")
    overlay_summary_columns = st.columns(5)
    overlay_summary_columns[0].metric("Active overlay", str(overlay_summary.get("active_overlay_name") or "none"))
    overlay_summary_columns[1].metric("Active entries", int(overlay_summary.get("active_entry_count", 0) or 0))
    overlay_summary_columns[2].metric("Concept aliases", int(overlay_summary.get("concept_alias_entries", 0) or 0))
    overlay_summary_columns[3].metric("Versions", int(overlay_summary.get("total_versions", 0) or 0))
    overlay_summary_columns[4].metric("Validated", int(overlay_summary.get("validated_versions", 0) or 0))
    st.caption(
        f"Mode={overlay_summary.get('mode') or 'base_only'} | "
        f"active_versions={overlay_summary.get('active_versions', 0)} | "
        f"archived_versions={overlay_summary.get('archived_versions', 0)}"
    )

    st.subheader("Overlay Management")
    overlay_action_columns = st.columns(4)
    if overlay_action_columns[0].button(
        _canonical_console_action_label(st.session_state.get("debug_knowledge_overlays") is not None, "knowledge overlays"),
        width="stretch",
        key="canonical_console_load_knowledge_overlays",
    ):
        try:
            st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
            _bootstrap_active_overlay_detail(api_request=api_request)
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge overlay versions."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge overlays failed: {error}"}
        st.rerun()

    if overlay_action_columns[1].button(
        "Reload knowledge",
        width="stretch",
        key="canonical_console_reload_knowledge",
    ):
        try:
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {"level": "success", "message": "Reloaded active knowledge overlay into runtime."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Knowledge reload failed: {error}"}
        st.rerun()

    if overlay_action_columns[2].button(
        _canonical_console_action_label(st.session_state.get("debug_knowledge_runtime") is not None, "active knowledge status"),
        width="stretch",
        key="canonical_console_load_knowledge_runtime",
    ):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded active knowledge runtime status."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge runtime status failed: {error}"}
        st.rerun()

    if overlay_action_columns[3].button(
        "Load overlay audit log",
        width="stretch",
        key="canonical_console_load_overlay_audit",
    ):
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge audit log failed: {error}"}
        st.rerun()

    knowledge_upload = st.file_uploader(
        "Knowledge overlay CSV",
        type=["csv"],
        key="knowledge_overlay_file",
        help="Upload CSV entries for abbreviations, synonyms, field aliases, or concept aliases.",
    )
    knowledge_overlay_name = st.text_input(
        "Overlay version name",
        value="",
        key="knowledge_overlay_name",
        placeholder="Example: customer-domain-overlay-v1",
    )
    knowledge_overlay_created_by = st.text_input(
        "Created by",
        value="",
        key="knowledge_overlay_created_by",
        placeholder="Example: data-governance-team",
    )
    knowledge_upload_columns = st.columns(2)
    if knowledge_upload_columns[0].button(
        "Validate knowledge CSV",
        width="stretch",
        key="canonical_console_validate_knowledge_overlay",
        disabled=knowledge_upload is None,
    ):
        try:
            st.session_state["debug_knowledge_validation"] = api_request(
                "POST",
                "/knowledge/overlays/validate",
                files=upload_file_to_request_files(knowledge_upload),
            )
            st.session_state["last_action"] = {"level": "success", "message": "Validated knowledge overlay CSV."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Knowledge CSV validation failed: {error}"}
        st.rerun()

    if knowledge_upload_columns[1].button(
        "Save overlay version",
        width="stretch",
        key="canonical_console_save_knowledge_overlay",
        disabled=knowledge_upload is None,
    ):
        try:
            created = api_request(
                "POST",
                "/knowledge/overlays",
                files=upload_file_to_request_files(knowledge_upload),
                data={
                    key: value
                    for key, value in {
                        "name": knowledge_overlay_name.strip(),
                        "created_by": knowledge_overlay_created_by.strip(),
                    }.items()
                    if value
                }
                or None,
            )
            st.session_state["debug_knowledge_created"] = created
            st.session_state["debug_knowledge_validation"] = created.get("validation")
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Saved knowledge overlay version '{created['version']['name']}' with {created['saved_entry_count']} entries.",
            }
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Saving knowledge overlay failed: {error}"}
        st.rerun()

    knowledge_validation = st.session_state.get("debug_knowledge_validation")
    if knowledge_validation:
        st.caption(
            f"Validation summary: total={knowledge_validation.get('total_rows', 0)} | "
            f"valid={knowledge_validation.get('valid_rows', 0)} | invalid={knowledge_validation.get('invalid_rows', 0)} | "
            f"duplicates={knowledge_validation.get('duplicate_rows', 0)} | conflicts={knowledge_validation.get('conflicts', 0)}"
        )

    knowledge_overlays = st.session_state.get("debug_knowledge_overlays")
    if knowledge_overlays:
        st.dataframe(knowledge_overlays, width="stretch", hide_index=True)
        overlay_options = {
            f"#{item['overlay_id']} | {item['name']} | {item['status']}": item["overlay_id"]
            for item in knowledge_overlays
        }
        if overlay_options:
            selected_overlay_label = st.selectbox(
                "Overlay version",
                list(overlay_options.keys()),
                key="debug_selected_overlay_version",
            )
            selected_overlay_id = overlay_options[selected_overlay_label]
            selected_overlay = next(
                (item for item in knowledge_overlays if item.get("overlay_id") == selected_overlay_id),
                None,
            )
            activation_block_reason = _overlay_activation_block_reason(selected_overlay)
            archive_block_reason = _overlay_archive_block_reason(selected_overlay)
            overlay_columns = st.columns(4)
            if overlay_columns[0].button("Load details", width="stretch", key="canonical_console_load_overlay_details"):
                try:
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded knowledge overlay details for version #{selected_overlay_id}.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Loading overlay details failed: {error}"}
                st.rerun()

            if overlay_columns[1].button(
                "Activate selected overlay",
                width="stretch",
                key="canonical_console_activate_overlay",
                disabled=bool(activation_block_reason),
            ):
                try:
                    activated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/activate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Activated knowledge overlay '{activated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay activation failed: {error}"}
                st.rerun()
            if activation_block_reason:
                st.caption(activation_block_reason)

            if overlay_columns[2].button("Deactivate selected overlay", width="stretch", key="canonical_console_deactivate_overlay"):
                try:
                    deactivated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/deactivate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Deactivated knowledge overlay '{deactivated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay deactivation failed: {error}"}
                st.rerun()

            if overlay_columns[3].button(
                "Archive selected overlay",
                width="stretch",
                key="canonical_console_archive_overlay",
                disabled=bool(archive_block_reason),
            ):
                try:
                    archived = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/archive")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Archived knowledge overlay '{archived['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay archive failed: {error}"}
                st.rerun()
            if archive_block_reason:
                st.caption(archive_block_reason)

            if st.button("Rollback active overlay", width="stretch", key="canonical_console_rollback_overlay"):
                try:
                    runtime = api_request("POST", "/knowledge/overlays/rollback")
                    st.session_state["debug_knowledge_runtime"] = runtime
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    active_overlay_id = runtime.get("active_overlay_id")
                    st.session_state["debug_selected_knowledge_overlay"] = (
                        api_request("GET", f"/knowledge/overlays/{active_overlay_id}") if active_overlay_id else None
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            f"Rolled back to knowledge overlay '{runtime['active_overlay_name']}'."
                            if active_overlay_id
                            else "Rolled back to base-only knowledge mode."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay rollback failed: {error}"}
                st.rerun()

    selected_overlay = st.session_state.get("debug_selected_knowledge_overlay")
    if selected_overlay:
        version = selected_overlay.get("version", {})
        overlay_entry_counts: dict[str, int] = {}
        for entry in selected_overlay.get("entries", []):
            entry_type = str(entry.get("entry_type") or "")
            if not entry_type:
                continue
            overlay_entry_counts[entry_type] = overlay_entry_counts.get(entry_type, 0) + 1
        st.caption(
            f"Overlay detail: #{version.get('overlay_id')} | {version.get('name')} | status={version.get('status')} | created_by={version.get('created_by') or 'n/a'} | source={version.get('source_filename') or 'n/a'}"
        )
        if overlay_entry_counts:
            st.caption(
                "Overlay entry summary: "
                + " | ".join(f"{entry_type}={count}" for entry_type, count in sorted(overlay_entry_counts.items()))
            )
        entries = selected_overlay.get("entries", [])
        if entries:
            st.dataframe(entries, width="stretch", hide_index=True)
        else:
            st.info("This overlay version does not contain any saved entries.")

        overlay_promotion_items = _overlay_promotion_item_map(st.session_state.get("debug_knowledge_stewardship_items"))
        promotable_entries = [
            entry
            for entry in entries
            if _normalized_text(entry.get("entry_type")) == "concept_alias" and entry.get("entry_id") is not None
        ]
        if promotable_entries:
            st.write("**Overlay promotion candidates**")
            st.caption(
                "Track which active overlay aliases should be promoted into the stable canonical glossary later. "
                "This does not write to the base glossary; it creates a durable stewardship candidate."
            )
            promotion_rows = _overlay_promotion_entry_rows(promotable_entries, overlay_promotion_items, version)
            promotion_metrics = st.columns(4)
            promotion_metrics[0].metric("Promotable aliases", len(promotable_entries))
            promotion_metrics[1].metric(
                "Tracked",
                sum(1 for row in promotion_rows if row.get("promotion_status") != "not_tracked"),
            )
            promotion_metrics[2].metric(
                "Ready",
                sum(1 for row in promotion_rows if row.get("promotion_status") == "ready_for_approval"),
            )
            promotion_metrics[3].metric(
                "Promoted",
                sum(1 for row in promotion_rows if row.get("promotion_status") == "promoted"),
            )
            st.dataframe(promotion_rows, width="stretch", hide_index=True)

            promotion_options = {
                _overlay_promotion_option_label(
                    entry,
                    overlay_promotion_items.get(_overlay_promotion_item_key(entry, version)),
                ): entry
                for entry in promotable_entries
            }
            selected_promotion_label = st.selectbox(
                "Overlay promotion detail",
                list(promotion_options.keys()),
                key="debug_selected_overlay_promotion_label",
            )
            selected_promotion_entry = promotion_options[selected_promotion_label]
            selected_promotion_key = _overlay_promotion_item_key(selected_promotion_entry, version)
            selected_promotion_item = overlay_promotion_items.get(selected_promotion_key) or {}
            selected_promotion_item_id = selected_promotion_item.get("item_id")
            selected_promotion_status = _overlay_promotion_status(selected_promotion_item)

            st.caption(
                f"Promotion status: {_canonical_gap_proposal_state_label(selected_promotion_status)} | "
                f"alias={_normalized_text(selected_promotion_entry.get('alias')) or 'n/a'} | "
                f"concept={_normalized_text(selected_promotion_entry.get('canonical_concept_id')) or _normalized_text(selected_promotion_entry.get('canonical_term')) or 'n/a'}"
            )
            if selected_promotion_entry.get("note"):
                st.caption(f"Overlay note: {_normalized_text(selected_promotion_entry.get('note'))}")

            promotion_owner_columns = st.columns(2)
            promotion_owner = promotion_owner_columns[0].text_input(
                "Promotion owner",
                value=_normalized_text(selected_promotion_item.get("owner")),
                key=f"debug_overlay_promotion_owner_{selected_promotion_key}",
                placeholder="Example: master-data-governance",
            )
            promotion_assignee = promotion_owner_columns[1].text_input(
                "Promotion assignee",
                value=_normalized_text(selected_promotion_item.get("assignee")),
                key=f"debug_overlay_promotion_assignee_{selected_promotion_key}",
                placeholder="Example: canonical-model-owner",
            )
            promotion_review_note = st.text_input(
                "Promotion review note",
                value=_normalized_text(selected_promotion_item.get("review_note")),
                key=f"debug_overlay_promotion_review_note_{selected_promotion_key}",
                placeholder="Why should this overlay alias be promoted to the stable glossary?",
            )
            promotion_status_options = ["new", "needs_review", "ready_for_approval", "ignored", "rejected"]
            if selected_promotion_status == "promoted":
                promotion_status_options.append("promoted")
            promotion_status = st.selectbox(
                "Promotion status",
                options=promotion_status_options,
                index=promotion_status_options.index(selected_promotion_status) if selected_promotion_status in promotion_status_options else 0,
                key=f"debug_overlay_promotion_status_{selected_promotion_key}",
                format_func=_canonical_gap_proposal_state_label,
            )
            promotion_save_disabled = _normalized_text(version.get("status")) != "active" and not selected_promotion_item_id
            promotion_action_columns = st.columns(2)
            if promotion_action_columns[0].button(
                "Save promotion candidate",
                width="stretch",
                key=f"debug_save_overlay_promotion_{selected_promotion_key}",
                disabled=promotion_save_disabled or selected_promotion_status == "promoted",
            ):
                try:
                    api_request(
                        "POST",
                        "/knowledge/stewardship-items",
                        json=_overlay_promotion_item_request(
                            selected_promotion_entry,
                            version,
                            status=promotion_status,
                            owner=promotion_owner,
                            assignee=promotion_assignee,
                            review_note=promotion_review_note,
                            changed_by=st.session_state.get("admin_token"),
                        ),
                    )
                    st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                    st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                        st.session_state.get("debug_knowledge_stewardship_items")
                    )
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    st.session_state["last_action"] = {
                        "level": "info",
                        "message": "Saved durable overlay promotion candidate for the selected alias.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Saving overlay promotion candidate failed: {error}",
                    }
                st.rerun()
            if promotion_action_columns[1].button(
                "Promote to stable glossary",
                width="stretch",
                key=f"debug_execute_overlay_promotion_{selected_promotion_key}",
                disabled=not _overlay_promotion_can_execute(selected_promotion_item),
            ):
                try:
                    promotion_result = api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_promotion_item_id}/promote-to-glossary",
                        json=_overlay_promotion_execution_request(
                            st.session_state.get("admin_token"),
                            note="Promoted from Canonical Console overlay detail.",
                        ),
                    )
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["debug_selected_knowledge_overlay"] = api_request(
                        "GET",
                        f"/knowledge/overlays/{version.get('overlay_id')}",
                    )
                    if st.session_state.get("debug_canonical_concepts") is not None:
                        st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
                    promoted_concept_id = _normalized_text((promotion_result.get("glossary_entry") or {}).get("concept_id"))
                    if promoted_concept_id and promoted_concept_id == _normalized_text(
                        ((st.session_state.get("debug_canonical_concept_detail") or {}).get("concept") or {}).get("concept_id")
                    ):
                        st.session_state["debug_canonical_concept_detail"] = api_request(
                            "GET",
                            f"/knowledge/canonical-concepts/{promoted_concept_id}",
                        )
                    st.session_state["canonical_glossary_export_bytes"] = api_request_content(
                        "GET",
                        "/knowledge/canonical-glossary/export",
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            "Promoted selected overlay alias into the stable canonical glossary."
                            if promotion_result.get("alias_added", True)
                            else "Selected overlay alias was already present in the stable canonical glossary; stewardship item marked as promoted."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Stable glossary promotion failed: {error}",
                    }
                st.rerun()
            if selected_promotion_status == "ready_for_approval":
                st.caption("Promotion execution writes the alias into the base canonical glossary and then marks the stewardship item as promoted.")
            elif selected_promotion_status == "promoted":
                st.caption("This alias has already been promoted to the stable canonical glossary.")
            if _normalized_text(version.get("status")) != "active" and not selected_promotion_item_id:
                st.caption("Activate this overlay before creating a new promotion candidate. Existing candidates can still be reviewed.")

    st.subheader("Canonical Glossary")
    canonical_glossary_upload = st.file_uploader(
        "Canonical glossary CSV",
        type=["csv"],
        key="canonical_glossary_file",
        help="Import or export the canonical business concept glossary as CSV.",
    )
    canonical_glossary_columns = st.columns(2)
    if canonical_glossary_columns[0].button(
        "Load canonical glossary export",
        width="stretch",
        key="canonical_console_export_canonical_glossary",
    ):
        try:
            st.session_state["canonical_glossary_export_bytes"] = api_request_content("GET", "/knowledge/canonical-glossary/export")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded canonical glossary export."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Canonical glossary export failed: {error}"}
        st.rerun()

    if canonical_glossary_columns[1].button(
        "Import canonical glossary",
        width="stretch",
        key="canonical_console_import_canonical_glossary",
        disabled=canonical_glossary_upload is None,
    ):
        try:
            st.session_state["debug_canonical_glossary_import"] = api_request(
                "POST",
                "/knowledge/canonical-glossary/import",
                files=upload_file_to_request_files(canonical_glossary_upload),
            )
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            if st.session_state.get("debug_canonical_concepts") is not None:
                st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
            st.session_state["last_action"] = {"level": "success", "message": "Imported canonical glossary CSV."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Canonical glossary import failed: {error}"}
        st.rerun()

    canonical_glossary_export_bytes = st.session_state.get("canonical_glossary_export_bytes")
    if canonical_glossary_export_bytes:
        st.download_button(
            "Download canonical glossary CSV",
            data=canonical_glossary_export_bytes,
            file_name="canonical_glossary.csv",
            mime="text/csv",
            width="stretch",
        )

    canonical_glossary_import = st.session_state.get("debug_canonical_glossary_import")
    if canonical_glossary_import:
        st.caption(
            "Canonical glossary import: "
            f"rows={canonical_glossary_import.get('imported_row_count', 0)}, "
            f"concepts={canonical_glossary_import.get('canonical_concept_count', 0)}."
        )

    canonical_concepts = st.session_state.get("debug_canonical_concepts") or []
    if canonical_concepts:
        available_source_systems = sorted(
            {
                _normalized_text(value)
                for concept in canonical_concepts
                for value in concept.get("source_systems", [])
                if _normalized_text(value)
            }
        )
        available_business_domains = sorted(
            {
                _normalized_text(value)
                for concept in canonical_concepts
                for value in concept.get("business_domains", [])
                if _normalized_text(value)
            }
        )
        filter_columns = st.columns(4)
        concept_query = filter_columns[0].text_input(
            "Canonical concept search",
            value=st.session_state.get("debug_canonical_concept_query", ""),
            key="debug_canonical_concept_query",
            placeholder="Search by concept id, display name, alias, source system, domain, entity, or source",
        )
        concept_focus = filter_columns[1].selectbox(
            "Concept focus",
            options=["all", "active_overlay", "overlay_only", "in_use", "with_context", "base_only"],
            index=0,
            key="debug_canonical_concept_focus",
            format_func=lambda value: {
                "all": "All concepts",
                "active_overlay": "With active overlay aliases",
                "overlay_only": "Overlay-only concepts",
                "in_use": "Used in catalog",
                "with_context": "With field contexts",
                "base_only": "Base-only concepts",
            }.get(value, value),
        )
        concept_source_system = filter_columns[2].selectbox(
            "Source system",
            options=[""] + available_source_systems,
            key="debug_canonical_concept_source_system",
            format_func=lambda value: value or "All source systems",
        )
        concept_business_domain = filter_columns[3].selectbox(
            "Business domain",
            options=[""] + available_business_domains,
            key="debug_canonical_concept_business_domain",
            format_func=lambda value: value or "All business domains",
        )
        filtered_concepts = _filter_canonical_concepts_by_scope(
            _filter_canonical_concepts_by_focus(
                _filter_canonical_concepts(canonical_concepts, concept_query),
                concept_focus,
            ),
            concept_source_system,
            concept_business_domain,
        )
        st.dataframe(_canonical_concept_registry_rows(filtered_concepts), width="stretch", hide_index=True)

        if filtered_concepts:
            concept_options = {_canonical_concept_option_label(item): item["concept_id"] for item in filtered_concepts}
            preferred_concept_label = _preferred_canonical_concept_label(
                filtered_concepts,
                st.session_state.get("debug_knowledge_stewardship_items"),
                active_overlay_id=(st.session_state.get("debug_knowledge_runtime") or {}).get("active_overlay_id"),
                current_label=st.session_state.get("debug_selected_canonical_concept_label"),
            )
            if preferred_concept_label and st.session_state.get("debug_selected_canonical_concept_label") != preferred_concept_label:
                st.session_state["debug_selected_canonical_concept_label"] = preferred_concept_label
            selected_concept_label = st.selectbox(
                "Canonical concept detail",
                list(concept_options.keys()),
                key="debug_selected_canonical_concept_label",
            )
            selected_concept_id = concept_options[selected_concept_label]
            try:
                _ensure_canonical_concept_detail_loaded(
                    api_request=api_request,
                    selected_concept_id=selected_concept_id,
                )
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading canonical concept detail failed: {error}",
                }

            if st.button(
                _canonical_console_action_label(
                    _normalized_text(
                        ((st.session_state.get("debug_canonical_concept_detail") or {}).get("concept") or {}).get("concept_id")
                    )
                    == _normalized_text(selected_concept_id),
                    "canonical concept detail",
                ),
                width="stretch",
                key="debug_load_canonical_concept_detail",
            ):
                try:
                    st.session_state["debug_canonical_concept_detail"] = api_request(
                        "GET",
                        f"/knowledge/canonical-concepts/{selected_concept_id}",
                    )
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded canonical concept detail for {selected_concept_id}.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Loading canonical concept detail failed: {error}",
                    }
                st.rerun()
        else:
            st.info("No canonical concepts match the current search.")

    canonical_concept_detail = st.session_state.get("debug_canonical_concept_detail")
    if canonical_concept_detail:
        concept = canonical_concept_detail.get("concept") or {}
        concept_pending_rows = _canonical_gap_pending_rows_for_concept(
            concept,
            st.session_state.get("canonical_gap_candidates"),
            st.session_state.get("canonical_gap_suggestions"),
            st.session_state.get("debug_canonical_gap_console_states"),
            st.session_state.get("debug_canonical_gap_proposal_states"),
            _canonical_gap_stewardship_item_map(st.session_state.get("debug_knowledge_stewardship_items")),
        )
        concept_overlay_promotion_items = _overlay_promotion_items_for_concept(
            concept,
            st.session_state.get("debug_knowledge_stewardship_items"),
        )
        concept_overlay_promotion_rows = _overlay_promotion_rows_for_concept(
            concept,
            st.session_state.get("debug_knowledge_stewardship_items"),
        )
        summary_columns = st.columns(5)
        summary_columns[0].metric("Usage", int(concept.get("usage_count", 0) or 0))
        summary_columns[1].metric("Field contexts", int(concept.get("field_context_count", 0) or 0))
        summary_columns[2].metric("Active overlay aliases", int(concept.get("active_overlay_entry_count", 0) or 0))
        summary_columns[3].metric("Pending proposals", len(concept_pending_rows))
        summary_columns[4].metric("Overlay promotions", len(concept_overlay_promotion_items))
        st.caption(
            f"{concept.get('concept_id') or 'unknown'} | {concept.get('display_name') or 'n/a'} | "
            f"entity={concept.get('entity') or '-'} | attribute={concept.get('attribute') or '-'} | "
            f"source={concept.get('source') or 'base'}"
        )
        if concept.get("description"):
            st.write(concept.get("description"))
        if concept.get("base_aliases") or concept.get("active_overlay_aliases"):
            st.caption(
                "Aliases: "
                + " | ".join(
                    part
                    for part in [
                        (
                            "base=" + ", ".join(concept.get("base_aliases") or [])
                            if concept.get("base_aliases")
                            else ""
                        ),
                        (
                            "active_overlay=" + ", ".join(concept.get("active_overlay_aliases") or [])
                            if concept.get("active_overlay_aliases")
                            else ""
                        ),
                    ]
                    if part
                )
            )
        if concept.get("source_systems") or concept.get("business_domains"):
            st.caption(
                "Discovery facets: "
                + " | ".join(
                    part
                    for part in [
                        (
                            "source_systems=" + ", ".join(concept.get("source_systems") or [])
                            if concept.get("source_systems")
                            else ""
                        ),
                        (
                            "business_domains=" + ", ".join(concept.get("business_domains") or [])
                            if concept.get("business_domains")
                            else ""
                        ),
                    ]
                    if part
                )
            )
        st.caption(f"Alias count: {int(concept.get('alias_count', 0) or 0)}")

        if concept_pending_rows:
            st.write("**Pending queue proposals for this concept**")
            st.caption(
                "Current active gap suggestions that would extend this concept through the console approve flow."
            )
            st.dataframe(concept_pending_rows, width="stretch", hide_index=True)
        else:
            st.caption("No active queue proposals currently target this concept.")

        if concept_overlay_promotion_items:
            st.write("**Overlay promotion stewardship**")
            st.caption(
                "Durable overlay alias candidates already linked to this canonical concept, including execution-ready items."
            )
            st.dataframe(concept_overlay_promotion_rows, width="stretch", hide_index=True)
            concept_promotion_options = {
                _overlay_promotion_item_record_label(item): item for item in concept_overlay_promotion_items
            }
            selected_concept_promotion_label = st.selectbox(
                "Concept overlay promotion detail",
                list(concept_promotion_options.keys()),
                key=f"debug_concept_overlay_promotion_{_normalized_text(concept.get('concept_id')) or 'unknown'}",
            )
            selected_concept_promotion_item = concept_promotion_options[selected_concept_promotion_label]
            st.caption(
                f"Promotion status: {_canonical_gap_proposal_state_label(_overlay_promotion_status(selected_concept_promotion_item))} | "
                f"alias={_normalized_text(selected_concept_promotion_item.get('source')) or 'n/a'} | "
                f"source_system={_normalized_text(selected_concept_promotion_item.get('source_system')) or 'n/a'} | "
                f"business_domain={_normalized_text(selected_concept_promotion_item.get('business_domain')) or 'n/a'}"
            )
            if _normalized_text(selected_concept_promotion_item.get("review_note")):
                st.caption(f"Review note: {_normalized_text(selected_concept_promotion_item.get('review_note'))}")
            if st.button(
                "Promote selected concept candidate",
                width="stretch",
                key=f"debug_execute_concept_overlay_promotion_{selected_concept_promotion_item.get('item_id')}",
                disabled=not _overlay_promotion_can_execute(selected_concept_promotion_item),
            ):
                try:
                    promotion_result = api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_concept_promotion_item.get('item_id')}/promote-to-glossary",
                        json=_overlay_promotion_execution_request(
                            st.session_state.get("admin_token"),
                            note="Promoted from Canonical Console concept detail.",
                        ),
                    )
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["debug_canonical_concept_detail"] = api_request(
                        "GET",
                        f"/knowledge/canonical-concepts/{_normalized_text(concept.get('concept_id'))}",
                    )
                    st.session_state["canonical_glossary_export_bytes"] = api_request_content(
                        "GET",
                        "/knowledge/canonical-glossary/export",
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            "Promoted selected concept-linked overlay alias into the stable canonical glossary."
                            if promotion_result.get("alias_added", True) or promotion_result.get("concept_created", False)
                            else "Selected concept-linked overlay alias was already present in the stable canonical glossary; stewardship item marked as promoted."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Concept-linked stable glossary promotion failed: {error}",
                    }
                st.rerun()
            if _overlay_promotion_status(selected_concept_promotion_item) == "ready_for_approval":
                st.caption("This concept-linked promotion item can now write into the stable canonical glossary.")
            elif _overlay_promotion_status(selected_concept_promotion_item) == "promoted":
                st.caption("This concept-linked overlay alias has already been promoted.")
        else:
            st.caption("No overlay promotion stewardship items currently target this concept.")

        if canonical_concept_detail.get("field_contexts"):
            st.write("**Field contexts**")
            st.dataframe(canonical_concept_detail.get("field_contexts"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("active_overlay_entries"):
            st.write("**Active overlay entries**")
            st.dataframe(canonical_concept_detail.get("active_overlay_entries"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("integrations"):
            st.write("**Catalog usage**")
            st.dataframe(canonical_concept_detail.get("integrations"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("audit_entries"):
            st.write("**Knowledge audit references**")
            st.dataframe(canonical_concept_detail.get("audit_entries"), width="stretch", hide_index=True)

    st.write("**Canonical gap review queue**")
    st.caption(
        "Mirror of the Review tab canonical gap state. Console can approve, ignore, or reject cached suggestions while showing direct audit context for the selected gap."
    )
    canonical_gap_candidates = st.session_state.get("canonical_gap_candidates") or []
    canonical_gap_suggestions = st.session_state.get("canonical_gap_suggestions") or {}
    canonical_gap_console_states = st.session_state.setdefault("debug_canonical_gap_console_states", {})
    canonical_gap_proposal_states = st.session_state.setdefault("debug_canonical_gap_proposal_states", {})
    canonical_gap_stewardship_items = _canonical_gap_stewardship_item_map(
        st.session_state.get("debug_knowledge_stewardship_items")
    )
    if canonical_gap_candidates:
        repeated_gap_rows = _canonical_gap_repeat_summary_rows(
            canonical_gap_candidates,
            canonical_gap_suggestions,
            canonical_gap_console_states,
            canonical_gap_proposal_states,
            canonical_gap_stewardship_items,
        )
        queue_columns = st.columns(5)
        queue_columns[0].metric("Candidates", len(canonical_gap_candidates))
        queue_columns[1].metric(
            "Ignored",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_console_state(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                    canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                )
                == "ignored"
            ),
        )
        queue_columns[2].metric(
            "Rejected",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_console_state(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                    canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                )
                == "rejected"
            ),
        )
        queue_columns[3].metric(
            "With suggestion",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, candidate))
            ),
        )
        queue_columns[4].metric(
            "Ready for approval",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_can_approve(
                    canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, candidate)),
                    _canonical_gap_console_state(
                        _canonical_gap_candidate_key(index, candidate),
                        canonical_gap_console_states,
                        canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                    ),
                    _canonical_gap_proposal_state(
                        _canonical_gap_candidate_key(index, candidate),
                        canonical_gap_proposal_states,
                        canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                    ),
                )
            ),
        )
        if repeated_gap_rows:
            st.write("**Repeated gap signals**")
            st.caption(
                "Aggregated target and suggested-concept patterns seen across the current queue and durable stewardship history. "
                "Use this to spot glossary or overlay work that can eliminate multiple gap reviews at once."
            )
            st.dataframe(repeated_gap_rows, width="stretch", hide_index=True)
        available_stewardship_statuses = sorted(
            {
                _canonical_gap_effective_status(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                    canonical_gap_proposal_states,
                    canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                )
                for index, candidate in enumerate(canonical_gap_candidates)
            },
            key=lambda value: {
                "new": 0,
                "needs_review": 1,
                "ready_for_approval": 2,
                "approved": 3,
                "rejected": 4,
                "ignored": 5,
                "promoted": 6,
                "active": 7,
            }.get(value, 99),
        )
        available_owners = sorted(
            {
                _normalized_text(item.get("owner"))
                for item in canonical_gap_stewardship_items.values()
                if _normalized_text(item.get("owner"))
            }
        )
        available_assignees = sorted(
            {
                _normalized_text(item.get("assignee"))
                for item in canonical_gap_stewardship_items.values()
                if _normalized_text(item.get("assignee"))
            }
        )
        queue_filter_columns = st.columns(3)
        queue_status_filter = queue_filter_columns[0].selectbox(
            "Stewardship status",
            options=[""] + available_stewardship_statuses,
            key="debug_canonical_gap_status_filter",
            format_func=lambda value: _canonical_gap_proposal_state_label(value) if value else "All statuses",
        )
        queue_owner_filter = queue_filter_columns[1].selectbox(
            "Owner",
            options=[""] + available_owners,
            key="debug_canonical_gap_owner_filter",
            format_func=lambda value: value or "All owners",
        )
        queue_assignee_filter = queue_filter_columns[2].selectbox(
            "Assignee",
            options=[""] + available_assignees,
            key="debug_canonical_gap_assignee_filter",
            format_func=lambda value: value or "All assignees",
        )
        visible_gap_indices = [
            index
            for index, candidate in enumerate(canonical_gap_candidates)
            if (
                (not queue_status_filter)
                or _canonical_gap_effective_status(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                    canonical_gap_proposal_states,
                    canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)),
                )
                == queue_status_filter
            )
            and (
                (not queue_owner_filter)
                or _normalized_text(
                    (canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)) or {}).get("owner")
                )
                == queue_owner_filter
            )
            and (
                (not queue_assignee_filter)
                or _normalized_text(
                    (canonical_gap_stewardship_items.get(_canonical_gap_candidate_key(index, candidate)) or {}).get("assignee")
                )
                == queue_assignee_filter
            )
        ]
        st.dataframe(
            _canonical_gap_queue_rows(
                [canonical_gap_candidates[index] for index in visible_gap_indices],
                canonical_gap_suggestions,
                canonical_gap_console_states,
                canonical_gap_proposal_states,
                canonical_gap_stewardship_items,
            ),
            width="stretch",
            hide_index=True,
        )

        gap_options = {
            _canonical_gap_option_label(index, canonical_gap_candidates[index], canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, canonical_gap_candidates[index]))): index
            for index in visible_gap_indices
        }
        if not gap_options:
            st.info("No canonical gaps match current stewardship filters.")
            return
        selected_gap_label = st.selectbox(
            "Canonical gap queue detail",
            list(gap_options.keys()),
            key="debug_selected_canonical_gap_label",
        )
        selected_gap_index = gap_options[selected_gap_label]
        selected_candidate = canonical_gap_candidates[selected_gap_index]
        selected_candidate_key = _canonical_gap_candidate_key(selected_gap_index, selected_candidate)
        selected_suggestion = canonical_gap_suggestions.get(selected_candidate_key) or {}
        selected_stewardship_item = canonical_gap_stewardship_items.get(selected_candidate_key) or {}
        selected_stewardship_item_id = selected_stewardship_item.get("item_id")
        selected_console_state = _canonical_gap_console_state(
            selected_candidate_key,
            canonical_gap_console_states,
            selected_stewardship_item,
        )
        selected_proposal_state = _canonical_gap_proposal_state(
            selected_candidate_key,
            canonical_gap_proposal_states,
            selected_stewardship_item,
        )
        selected_effective_status = _canonical_gap_effective_status(
            selected_candidate_key,
            canonical_gap_console_states,
            canonical_gap_proposal_states,
            selected_stewardship_item,
        )

        detail_columns = st.columns([3, 3, 2])
        detail_columns[0].markdown(f"**Source:** {_normalized_text(selected_candidate.get('source')) or 'n/a'}")
        detail_columns[1].markdown(f"**Target:** {_normalized_text(selected_candidate.get('target')) or 'n/a'}")
        detail_columns[2].metric("Confidence", f"{int(float(selected_candidate.get('confidence', 0.0) or 0.0) * 100)}%")
        st.caption(f"Console state: {selected_console_state}")
        st.caption(f"Proposal triage: {_canonical_gap_proposal_state_label(selected_proposal_state)}")
        st.caption(f"Stewardship status: {_canonical_gap_proposal_state_label(selected_effective_status)}")
        if selected_candidate.get("reason"):
            st.caption(selected_candidate.get("reason"))
        if selected_candidate.get("explanation"):
            st.caption("Signals: " + " | ".join(selected_candidate.get("explanation") or []))

        stewardship_columns = st.columns(2)
        stewardship_owner = stewardship_columns[0].text_input(
            "Owner",
            value=_normalized_text(selected_stewardship_item.get("owner")),
            key=f"debug_stewardship_owner_{selected_gap_index}",
            placeholder="Example: data-governance",
        )
        stewardship_assignee = stewardship_columns[1].text_input(
            "Assignee",
            value=_normalized_text(selected_stewardship_item.get("assignee")),
            key=f"debug_stewardship_assignee_{selected_gap_index}",
            placeholder="Example: analyst-on-duty",
        )

        review_note = st.text_input(
            "Review note",
            value=_normalized_text(selected_stewardship_item.get("review_note")),
            key=f"debug_review_note_{selected_gap_index}",
            placeholder="Why is this gap being ignored, rejected, or ready for approval?",
        )

        save_stewardship_disabled = (
            bool(selected_stewardship_item_id)
            and _normalized_text(selected_stewardship_item.get("owner")) == _normalized_text(stewardship_owner)
            and _normalized_text(selected_stewardship_item.get("assignee")) == _normalized_text(stewardship_assignee)
            and _normalized_text(selected_stewardship_item.get("review_note")) == _normalized_text(review_note)
            and _canonical_gap_stewardship_status(selected_stewardship_item) == selected_effective_status
        )
        if st.button(
            "Save stewardship fields",
            width="stretch",
            key=f"debug_save_stewardship_item_{selected_gap_index}",
            disabled=save_stewardship_disabled,
        ):
            try:
                api_request(
                    "POST",
                    "/knowledge/stewardship-items",
                    json=_canonical_gap_stewardship_item_request(
                        selected_candidate_key,
                        selected_candidate,
                        selected_suggestion or None,
                        status=selected_effective_status,
                        owner=stewardship_owner,
                        assignee=stewardship_assignee,
                        review_note=review_note,
                        changed_by=st.session_state.get("admin_token"),
                    ),
                )
                st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                    st.session_state.get("debug_knowledge_stewardship_items")
                )
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": "Saved durable stewardship owner, assignee, and review note for the selected canonical gap.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Saving stewardship fields failed: {error}",
                }
            st.rerun()

        triage_columns = st.columns([2, 1])
        triage_selection = triage_columns[0].selectbox(
            "Proposal triage",
            options=["new", "needs_review", "ready_for_approval"],
            index=["new", "needs_review", "ready_for_approval"].index(selected_proposal_state),
            key=f"debug_proposal_state_{selected_gap_index}",
            format_func=_canonical_gap_proposal_state_label,
        )
        if triage_columns[1].button(
            "Update triage",
            width="stretch",
            key=f"debug_update_proposal_state_{selected_gap_index}",
            disabled=triage_selection == selected_proposal_state,
        ):
            try:
                if selected_stewardship_item_id:
                    api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_stewardship_item_id}/status",
                        json=_knowledge_stewardship_status_update_request(
                            triage_selection,
                            st.session_state.get("admin_token"),
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                        ),
                    )
                else:
                    api_request(
                        "POST",
                        "/knowledge/stewardship-items",
                        json=_canonical_gap_stewardship_item_request(
                            selected_candidate_key,
                            selected_candidate,
                            selected_suggestion or None,
                            status=triage_selection,
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                            changed_by=st.session_state.get("admin_token"),
                        ),
                    )
                st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                    st.session_state.get("debug_knowledge_stewardship_items")
                )
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": (
                        f"Updated proposal triage to '{_canonical_gap_proposal_state_label(triage_selection)}' for "
                        f"{_normalized_text(selected_candidate.get('source')) or 'selected gap'}."
                    ),
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Updating proposal triage failed: {error}",
                }
            st.rerun()

        state_action_columns = st.columns(3)
        if state_action_columns[0].button(
            "Ignore with audit",
            width="stretch",
            key=f"debug_ignore_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_ignore(selected_console_state),
        ):
            try:
                api_request(
                    "POST",
                    "/knowledge/canonical-gaps/reject",
                    json=_canonical_gap_rejection_request(
                        selected_candidate,
                        selected_suggestion or None,
                        st.session_state.get("admin_token"),
                        review_note,
                        disposition="ignored",
                    ),
                )
                canonical_gap_console_states[selected_candidate_key] = "ignored"
                if selected_stewardship_item_id:
                    api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_stewardship_item_id}/status",
                        json=_knowledge_stewardship_status_update_request(
                            "ignored",
                            st.session_state.get("admin_token"),
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                            note=review_note,
                        ),
                    )
                else:
                    api_request(
                        "POST",
                        "/knowledge/stewardship-items",
                        json=_canonical_gap_stewardship_item_request(
                            selected_candidate_key,
                            selected_candidate,
                            selected_suggestion or None,
                            status="ignored",
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                            changed_by=st.session_state.get("admin_token"),
                        ),
                    )
                st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                    st.session_state.get("debug_knowledge_stewardship_items")
                )
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": "Ignored canonical gap suggestion and persisted an audit entry.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Canonical gap ignore failed: {error}",
                }
            st.rerun()

        if state_action_columns[1].button(
            "Restore to queue",
            width="stretch",
            key=f"debug_restore_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_restore(selected_console_state),
        ):
            canonical_gap_console_states.pop(selected_candidate_key, None)
            if selected_stewardship_item_id:
                try:
                    api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_stewardship_item_id}/status",
                        json=_knowledge_stewardship_status_update_request(
                            "needs_review",
                            st.session_state.get("admin_token"),
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                        ),
                    )
                    st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                    st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                        st.session_state.get("debug_knowledge_stewardship_items")
                    )
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Restoring stewardship status failed: {error}",
                    }
                    st.rerun()
            st.session_state["last_action"] = {
                "level": "info",
                "message": "Restored canonical gap to the active console queue. Existing ignore audit entries remain in history.",
            }
            st.rerun()

        if state_action_columns[2].button(
            "Reject with audit",
            width="stretch",
            key=f"debug_reject_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_reject(selected_console_state),
        ):
            try:
                api_request(
                    "POST",
                    "/knowledge/canonical-gaps/reject",
                    json=_canonical_gap_rejection_request(
                        selected_candidate,
                        selected_suggestion or None,
                        st.session_state.get("admin_token"),
                        review_note,
                    ),
                )
                canonical_gap_console_states[selected_candidate_key] = "rejected"
                if selected_stewardship_item_id:
                    api_request(
                        "POST",
                        f"/knowledge/stewardship-items/{selected_stewardship_item_id}/status",
                        json=_knowledge_stewardship_status_update_request(
                            "rejected",
                            st.session_state.get("admin_token"),
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                            note=review_note,
                        ),
                    )
                else:
                    api_request(
                        "POST",
                        "/knowledge/stewardship-items",
                        json=_canonical_gap_stewardship_item_request(
                            selected_candidate_key,
                            selected_candidate,
                            selected_suggestion or None,
                            status="rejected",
                            owner=stewardship_owner,
                            assignee=stewardship_assignee,
                            review_note=review_note,
                            changed_by=st.session_state.get("admin_token"),
                        ),
                    )
                st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                    st.session_state.get("debug_knowledge_stewardship_items")
                )
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": "Rejected canonical gap suggestion and persisted an audit entry.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Canonical gap rejection failed: {error}",
                }
            st.rerun()

        related_gap_audit_entries = _canonical_gap_related_audit_entries(
            st.session_state.get("debug_knowledge_audit_logs"),
            selected_candidate,
        )
        if related_gap_audit_entries:
            st.write("**Gap audit references**")
            st.dataframe(related_gap_audit_entries, width="stretch", hide_index=True)

        if selected_suggestion:
            st.write(
                f"Action: **{selected_suggestion.get('action', 'no_action')}** | "
                f"Concept: **{selected_suggestion.get('concept_id') or 'n/a'}** - {selected_suggestion.get('display_name') or 'n/a'}"
            )
            if selected_suggestion.get("aliases"):
                st.caption("Aliases: " + ", ".join(selected_suggestion.get("aliases") or []))
            for line in selected_suggestion.get("reasoning") or []:
                st.caption(f"Reason: {line}")
            for line in selected_suggestion.get("risk_notes") or []:
                st.caption(f"Risk: {line}")

            impact_preview_rows = _canonical_gap_impact_preview_rows(
                selected_gap_index,
                selected_candidate,
                selected_suggestion,
                canonical_gap_candidates,
                canonical_gap_suggestions,
                canonical_gap_console_states,
            )
            suggested_concept_id = _normalized_text(selected_suggestion.get("concept_id"))
            suggested_concept_summary = next(
                (
                    concept
                    for concept in st.session_state.get("debug_canonical_concepts") or []
                    if _normalized_text(concept.get("concept_id")) == suggested_concept_id
                ),
                None,
            )
            if impact_preview_rows or suggested_concept_summary:
                st.write("**Impact preview**")
                impact_metrics = st.columns(3)
                impact_metrics[0].metric("Potential queue rows", len(impact_preview_rows))
                impact_metrics[1].metric("Additional rows", max(0, len(impact_preview_rows) - 1))
                impact_metrics[2].metric(
                    "Saved usages",
                    int((suggested_concept_summary or {}).get("usage_count", 0) or 0),
                )
                if suggested_concept_summary and (
                    suggested_concept_summary.get("source_systems") or suggested_concept_summary.get("business_domains")
                ):
                    st.caption(
                        "Concept facets: "
                        + " | ".join(
                            part
                            for part in [
                                (
                                    "source_systems=" + ", ".join(suggested_concept_summary.get("source_systems") or [])
                                    if suggested_concept_summary.get("source_systems")
                                    else ""
                                ),
                                (
                                    "business_domains=" + ", ".join(suggested_concept_summary.get("business_domains") or [])
                                    if suggested_concept_summary.get("business_domains")
                                    else ""
                                ),
                            ]
                            if part
                        )
                    )
                if impact_preview_rows:
                    st.dataframe(impact_preview_rows, width="stretch", hide_index=True)
                else:
                    st.caption("No additional current queue rows match this proposed concept/alias pattern yet.")

            approve_ready = _canonical_gap_can_approve(
                selected_suggestion,
                selected_console_state,
                selected_proposal_state,
            )
            if st.button(
                "Approve from console",
                width="stretch",
                key=f"debug_approve_canonical_gap_{selected_gap_index}",
                disabled=not approve_ready,
            ):
                try:
                    response = api_request(
                        "POST",
                        "/knowledge/canonical-gaps/approve",
                        json=_canonical_gap_approval_request(
                            selected_candidate,
                            selected_suggestion,
                            st.session_state.get("admin_token"),
                        ),
                    )
                    canonical_gap_console_states[selected_candidate_key] = "approved"
                    if selected_stewardship_item_id:
                        api_request(
                            "POST",
                            f"/knowledge/stewardship-items/{selected_stewardship_item_id}/status",
                            json=_knowledge_stewardship_status_update_request(
                                "approved",
                                st.session_state.get("admin_token"),
                                owner=stewardship_owner,
                                assignee=stewardship_assignee,
                                review_note=review_note,
                            ),
                        )
                    else:
                        api_request(
                            "POST",
                            "/knowledge/stewardship-items",
                            json=_canonical_gap_stewardship_item_request(
                                selected_candidate_key,
                                selected_candidate,
                                selected_suggestion,
                                status="approved",
                                owner=stewardship_owner,
                                assignee=stewardship_assignee,
                                review_note=review_note,
                                changed_by=st.session_state.get("admin_token"),
                            ),
                        )
                    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    st.session_state["debug_knowledge_stewardship_items"] = api_request("GET", "/knowledge/stewardship-items")
                    st.session_state["debug_canonical_gap_proposal_states"] = _canonical_gap_proposal_state_map(
                        st.session_state.get("debug_knowledge_stewardship_items")
                    )
                    if st.session_state.get("debug_canonical_concepts") is not None:
                        st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
                    approved_concept_id = _normalized_text(selected_suggestion.get("concept_id"))
                    if approved_concept_id:
                        st.session_state["debug_canonical_concept_detail"] = api_request(
                            "GET",
                            f"/knowledge/canonical-concepts/{approved_concept_id}",
                        )
                    if st.session_state.get("debug_knowledge_overlays") is not None:
                        st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            f"Approved canonical gap into overlay '{response.get('overlay_name')}'. "
                            "Regenerate mapping to see the canonical path filled."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Canonical gap approval failed: {error}",
                    }
                st.rerun()
            elif selected_console_state == "ignored":
                st.caption("This gap is currently ignored in the console. Restore it to the active queue before approving.")
            elif selected_console_state == "approved":
                st.caption("This gap was already approved from the console in this session.")
            elif selected_console_state == "rejected":
                st.caption("This gap was rejected from the console and the decision was persisted to the audit log.")
            elif selected_proposal_state != "ready_for_approval":
                st.caption(
                    "Move proposal triage to 'Ready for approval' before approving from the console."
                )
            elif not approve_ready:
                st.caption("This suggestion is not approve-ready. Generate a usable non-`no_action` suggestion from the Review tab first.")
        else:
            if selected_console_state == "rejected":
                st.caption("This gap was rejected without a cached suggestion payload. The audit decision is persisted.")
            elif selected_console_state == "ignored":
                st.caption("This gap was ignored with audit. Restore it locally if you want to reconsider it in the queue.")
            else:
                st.info("No cached LLM suggestion for this gap yet. Generate it from the Review tab.")
    else:
        st.info("Canonical gap review queue is empty. Use the Review tab to find high-confidence gaps first.")


def render_admin_debug_tab(
    *,
    admin_token_required: Callable[[], bool],
    api_request: Callable[..., Any],
    api_request_content: Callable[..., bytes],
    upload_file_to_request_files: Callable[[Any], dict | None],
    knowledge_debug_rows: Callable[[dict], list[dict]],
) -> None:
    st.header("Admin / Debug")
    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for observability and evaluation admin endpoints.")
        return
    if not token_required:
        st.info("Backend currently exposes these admin/debug endpoints without an admin token.")

    action_columns = st.columns(4)
    if action_columns[0].button("Load runtime config", width="stretch", key="debug_load_runtime_config"):
        try:
            st.session_state["debug_runtime_config"] = api_request("GET", "/observability/config")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded runtime config snapshot."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading runtime config failed: {error}"}
        st.rerun()

    if action_columns[1].button("Load decision logs", width="stretch", key="debug_load_decision_logs"):
        try:
            st.session_state["debug_decision_logs"] = api_request("GET", "/observability/decision-logs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded decision logs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading decision logs failed: {error}"}
        st.rerun()

    if action_columns[2].button("Load saved corrections", width="stretch", key="debug_load_corrections"):
        try:
            st.session_state["debug_corrections"] = api_request("GET", "/observability/corrections")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded saved corrections."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading corrections failed: {error}"}
        st.rerun()

    if action_columns[3].button("Load benchmark runs", width="stretch", key="debug_load_benchmark_runs"):
        try:
            st.session_state["debug_runs"] = api_request("GET", "/evaluation/runs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded evaluation runs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading evaluation runs failed: {error}"}
        st.rerun()

    st.subheader("Knowledge Governance Debug")
    knowledge_debug_columns = st.columns(2)
    if knowledge_debug_columns[0].button("Load active knowledge status", width="stretch", key="debug_load_knowledge_runtime"):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded active knowledge runtime status."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge runtime status failed: {error}"}
        st.rerun()

    if knowledge_debug_columns[1].button("Load knowledge audit log", width="stretch", key="debug_load_knowledge_audit"):
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge audit log failed: {error}"}
        st.rerun()
    st.info("Canonical Console tab now owns overlay summary, overlay lifecycle controls, and canonical glossary authoring UI.")

    knowledge_runtime = st.session_state.get("debug_knowledge_runtime")
    if knowledge_runtime:
        st.caption(
            "Knowledge mode: "
            + str(knowledge_runtime.get("mode") or "base_only")
            + " | active overlay: "
            + str(knowledge_runtime.get("active_overlay_name") or "none")
            + f" | active_entry_count={knowledge_runtime.get('active_entry_count', 0)}"
            + f" | concept_count={knowledge_runtime.get('concept_count', 0)}"
        )
        entry_type_counts = knowledge_runtime.get("entry_type_counts") or {}
        if entry_type_counts:
            st.caption(
                "Active overlay breakdown: "
                + " | ".join(f"{entry_type}={count}" for entry_type, count in sorted(entry_type_counts.items()))
            )

    knowledge_audit_logs = st.session_state.get("debug_knowledge_audit_logs")
    if knowledge_audit_logs:
        st.subheader("Knowledge Audit Log")
        st.dataframe(knowledge_audit_logs, width="stretch", hide_index=True)

    runtime_config = st.session_state.get("debug_runtime_config")
    if runtime_config:
        st.subheader("Runtime Config")
        st.json(runtime_config)

    mapping_response = st.session_state.get("mapping_response")
    if mapping_response:
        canonical_coverage = mapping_response.get("canonical_coverage") or {}
        source_coverage = canonical_coverage.get("source") or {}
        target_coverage = canonical_coverage.get("target") or {}
        project_coverage = canonical_coverage.get("project") or {}
        if source_coverage or target_coverage or project_coverage:
            st.subheader("Canonical Coverage")
            st.dataframe(
                [
                    {
                        "dataset": "source",
                        "coverage_ratio": source_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": source_coverage.get("matched_columns", 0),
                        "total_columns": source_coverage.get("total_columns", 0),
                        "unmatched_columns": " | ".join(source_coverage.get("unmatched_columns", [])),
                    },
                    {
                        "dataset": "target",
                        "coverage_ratio": target_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": target_coverage.get("matched_columns", 0),
                        "total_columns": target_coverage.get("total_columns", 0),
                        "unmatched_columns": " | ".join(target_coverage.get("unmatched_columns", [])),
                    },
                    {
                        "dataset": "project",
                        "coverage_ratio": project_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": project_coverage.get("matched_columns", 0),
                        "total_columns": project_coverage.get("total_columns", 0),
                        "unmatched_columns": "shared=" + " | ".join(project_coverage.get("shared_concepts", [])),
                    },
                ],
                width="stretch",
                hide_index=True,
            )
        knowledge_rows = knowledge_debug_rows(mapping_response)
        if knowledge_rows:
            st.subheader("Knowledge and Canonical Match Insights")
            st.dataframe(
                [
                    {
                        "source": row["source"],
                        "target": row["target"],
                        "knowledge_signal": row["knowledge_signal"],
                        "canonical_signal": row["canonical_signal"],
                        "confidence": row["confidence"],
                        "validator": row["validator"],
                    }
                    for row in knowledge_rows
                ],
                width="stretch",
                hide_index=True,
            )
            for row in knowledge_rows:
                with st.expander(f"Knowledge details: {row['source']} -> {row['target']}"):
                    for line in row["knowledge_explanations"]:
                        st.caption(line)
                    for line in row["canonical_explanations"]:
                        st.caption(line)

    decision_logs = st.session_state.get("debug_decision_logs")
    if decision_logs:
        st.subheader("Decision Logs")
        st.dataframe(decision_logs, width="stretch", hide_index=True)

    corrections = st.session_state.get("debug_corrections")
    if corrections:
        st.subheader("Saved Corrections")
        st.dataframe(corrections, width="stretch", hide_index=True)

    runs = st.session_state.get("debug_runs")
    if runs:
        st.subheader("Evaluation Runs")
        st.dataframe(runs, width="stretch", hide_index=True)