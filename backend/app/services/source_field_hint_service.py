from __future__ import annotations

from app.models.knowledge import SourceFieldHintRecord
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.persistence_service import persistence_service


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def _specificity_tuple(hint: SourceFieldHintRecord) -> tuple[int, int, str]:
    return (
        1 if str(hint.integration_name or "").strip() else 0,
        1 if str(hint.business_domain or "").strip() else 0,
        str(hint.updated_at or hint.created_at or ""),
    )


def _merge_hint_description(existing_description: str, hint: SourceFieldHintRecord) -> str:
    parts: list[str] = []
    if str(existing_description or "").strip():
        parts.append(str(existing_description).strip())
    if str(hint.meaning_hint or "").strip():
        parts.append(f"Persistent field hint: {str(hint.meaning_hint).strip()}")
    if str(hint.negative_hint or "").strip():
        parts.append(f"Not: {str(hint.negative_hint).strip()}")
    return " ".join(parts).strip()


def _merge_sample_values(column: ColumnProfile, hint: SourceFieldHintRecord) -> tuple[list[str], list[str]]:
    sample_values: list[str] = []
    for value in [*(column.sample_values or []), *(hint.sample_values or [])]:
        text = str(value or "").strip()
        if text and text not in sample_values:
            sample_values.append(text)

    distinct_sample_values: list[str] = []
    for value in [*(column.distinct_sample_values or []), *sample_values]:
        text = str(value or "").strip()
        if text and text not in distinct_sample_values:
            distinct_sample_values.append(text)

    return sample_values, distinct_sample_values


def apply_source_field_hints(
    schema_profile: SchemaProfile,
    *,
    source_system: str | None,
    business_domain: str | None = None,
    integration_name: str | None = None,
) -> tuple[SchemaProfile, list[SourceFieldHintRecord]]:
    normalized_source_system = _normalized_text(source_system)
    if not normalized_source_system:
        return schema_profile, []

    normalized_business_domain = _normalized_text(business_domain)
    normalized_integration_name = _normalized_text(integration_name)
    candidate_hints = persistence_service.list_source_field_hints(
        source_system=source_system,
        active_only=True,
    )

    selected_hints_by_field: dict[str, SourceFieldHintRecord] = {}
    for hint in candidate_hints:
        if _normalized_text(hint.integration_name) and _normalized_text(hint.integration_name) != normalized_integration_name:
            continue
        if _normalized_text(hint.business_domain) and _normalized_text(hint.business_domain) != normalized_business_domain:
            continue

        field_key = _normalized_text(hint.source_field)
        existing = selected_hints_by_field.get(field_key)
        if existing is None or _specificity_tuple(hint) > _specificity_tuple(existing):
            selected_hints_by_field[field_key] = hint

    if not selected_hints_by_field:
        return schema_profile, []

    applied_hints: list[SourceFieldHintRecord] = []
    enriched_columns: list[ColumnProfile] = []
    for column in schema_profile.columns:
        hint = selected_hints_by_field.get(_normalized_text(column.name))
        if hint is None:
            enriched_columns.append(column)
            continue

        sample_values, distinct_sample_values = _merge_sample_values(column, hint)
        enriched_columns.append(
            column.model_copy(
                update={
                    "description": _merge_hint_description(column.description, hint),
                    "sample_values": sample_values,
                    "distinct_sample_values": distinct_sample_values,
                }
            )
        )
        applied_hints.append(hint)

    return schema_profile.model_copy(update={"columns": enriched_columns}), applied_hints


def apply_inline_source_field_hint(
    column: ColumnProfile,
    *,
    meaning_hint: str = "",
    negative_hint: str = "",
    sample_values: list[str] | None = None,
    refinement_instruction: str = "",
) -> ColumnProfile:
    if (
        not str(meaning_hint or "").strip()
        and not str(negative_hint or "").strip()
        and not list(sample_values or [])
        and not str(refinement_instruction or "").strip()
    ):
        return column

    transient_hint = SourceFieldHintRecord(
        source_system="transient_manual_hint",
        source_field=column.name,
        meaning_hint=str(meaning_hint or "").strip(),
        negative_hint=str(negative_hint or "").strip(),
        sample_values=[str(value or "").strip() for value in list(sample_values or []) if str(value or "").strip()],
    )
    merged_sample_values, merged_distinct_sample_values = _merge_sample_values(column, transient_hint)
    merged_description = _merge_hint_description(column.description, transient_hint)
    if str(refinement_instruction or "").strip():
        instruction_text = str(refinement_instruction).strip()
        merged_description = (
            f"{merged_description} LLM refinement instruction: {instruction_text}".strip()
            if merged_description
            else f"LLM refinement instruction: {instruction_text}"
        )
    return column.model_copy(
        update={
            "description": merged_description,
            "sample_values": merged_sample_values,
            "distinct_sample_values": merged_distinct_sample_values,
        }
    )