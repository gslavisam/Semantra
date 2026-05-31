"""Structured transformation spec normalization and summary helpers."""

from __future__ import annotations

from typing import Any

from app.models.mapping import MappingDecision, TransformationSpec, TransformationSpecSummary


def _decision_target(item: MappingDecision | dict[str, Any]) -> str:
    if isinstance(item, dict):
        return str(item.get("target") or "").strip()
    return str(item.target or "").strip()


def transformation_spec_target_fields(mapping_decisions: list[MappingDecision] | list[dict[str, Any]]) -> list[str]:
    """Return ordered unique target fields from the active mapping decisions."""

    targets: list[str] = []
    seen_targets: set[str] = set()
    for item in mapping_decisions:
        target = _decision_target(item)
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)
        targets.append(target)
    return targets


def normalize_transformation_spec(
    spec: TransformationSpec | None,
    mapping_decisions: list[MappingDecision] | list[dict[str, Any]],
) -> TransformationSpec:
    """Align a transformation spec to the active target set and drop invalid field rules."""

    allowed_targets = transformation_spec_target_fields(mapping_decisions)
    target_lookup = set(allowed_targets)
    base_spec = spec or TransformationSpec()
    field_rules = []
    seen_targets: set[str] = set()
    for item in base_spec.field_rules:
        target_field = str(item.target_field or "").strip()
        rule = str(item.rule or "").strip()
        if not target_field or not rule or target_field not in target_lookup or target_field in seen_targets:
            continue
        seen_targets.add(target_field)
        field_rules.append({"target_field": target_field, "rule": rule})
    return TransformationSpec(
        target_grain=str(base_spec.target_grain or "").strip(),
        global_rules=str(base_spec.global_rules or "").strip(),
        defaults=str(base_spec.defaults or "").strip(),
        examples=str(base_spec.examples or "").strip(),
        target_fields=allowed_targets,
        field_rules=field_rules,
    )


def summarize_transformation_spec(
    spec: TransformationSpec | None,
    mapping_decisions: list[MappingDecision] | list[dict[str, Any]],
) -> TransformationSpecSummary:
    """Return a compact validation summary for a structured transformation spec."""

    normalized = normalize_transformation_spec(spec, mapping_decisions)
    described_lookup = {
        str(item.target_field or "").strip()
        for item in normalized.field_rules
        if str(item.target_field or "").strip() and str(item.rule or "").strip()
    }
    missing_fields = [target for target in normalized.target_fields if target not in described_lookup]

    if not normalized.target_fields:
        return TransformationSpecSummary(
            state="invalid",
            title="No active target fields",
            message="Add at least one active mapping decision before drafting a transformation spec.",
            target_count=0,
            described_count=0,
            missing_fields=[],
        )
    if not normalized.target_grain:
        return TransformationSpecSummary(
            state="incomplete",
            title="Missing target grain",
            message="Describe the target grain before using this transformation design as a governed output contract.",
            target_count=len(normalized.target_fields),
            described_count=len(described_lookup),
            missing_fields=missing_fields,
        )
    if not described_lookup and not normalized.global_rules and not normalized.defaults:
        return TransformationSpecSummary(
            state="incomplete",
            title="Add transformation rules",
            message="Define at least one field rule, global rule, or default behavior before this spec is ready.",
            target_count=len(normalized.target_fields),
            described_count=0,
            missing_fields=missing_fields,
        )
    if missing_fields and not normalized.defaults:
        return TransformationSpecSummary(
            state="incomplete",
            title="Field coverage is incomplete",
            message="Add explicit rules for the remaining target fields or define default behavior.",
            target_count=len(normalized.target_fields),
            described_count=len(described_lookup),
            missing_fields=missing_fields,
        )
    return TransformationSpecSummary(
        state="ready",
        title="Ready for next output step",
        message=(
            f"Structured spec covers {len(described_lookup)} of {len(normalized.target_fields)} target field(s)"
            + (" with explicit defaults for the rest." if missing_fields else ".")
        ),
        target_count=len(normalized.target_fields),
        described_count=len(described_lookup),
        missing_fields=missing_fields,
    )