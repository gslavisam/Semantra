from __future__ import annotations

from app.models.mapping import TargetSystem
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.utils.normalization import normalize_name, tokenize_name


def build_virtual_target_schema(target_system: TargetSystem = "canonical") -> SchemaProfile:
    if target_system != "canonical":
        raise ValueError(f"Unsupported virtual target system: {target_system}")

    columns = [
        _build_canonical_column(entry)
        for entry in metadata_knowledge_service.list_canonical_glossary_entries()
    ]

    return SchemaProfile(
        dataset_id="virtual-target:canonical",
        dataset_name=metadata_knowledge_service.canonical_glossary_path.name,
        row_count=0,
        columns=columns,
    )


def _build_canonical_column(entry) -> ColumnProfile:
    normalized_name = " ".join(
        part.strip()
        for part in (entry.display_name, entry.description)
        if str(part).strip()
    ) or entry.display_name
    detected_patterns, dtype = _canonical_pattern_and_dtype(entry)

    return ColumnProfile(
        name=entry.concept_id,
        normalized_name=normalize_name(normalized_name),
        dtype=dtype,
        null_ratio=0.0,
        unique_ratio=0.0,
        avg_length=0.0,
        non_null_count=0,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=detected_patterns,
        tokenized_name=tokenize_name(normalized_name),
    )


def _canonical_pattern_and_dtype(entry) -> tuple[list[str], str]:
    raw_data_type = str(getattr(entry, "data_type", "") or "").strip().lower()
    combined_text = " ".join(
        normalize_name(str(value))
        for value in (entry.concept_id, entry.display_name, entry.description, entry.attribute)
        if str(value).strip()
    )

    if "email" in combined_text:
        return ["email"], "string"
    if "phone" in combined_text or "mobile" in combined_text or "telephone" in combined_text:
        return ["phone"], "string"
    if "date" in raw_data_type or "date" in combined_text:
        return ["date"], "date"
    if raw_data_type in {"integer", "int", "bigint", "smallint"}:
        return [], "integer"
    if raw_data_type in {"float", "decimal", "double", "number", "numeric"}:
        return [], "float"
    return [], raw_data_type or "string"