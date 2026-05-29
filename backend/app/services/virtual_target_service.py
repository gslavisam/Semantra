"""Virtual canonical target schema builders for canonical-first and target-aware mapping mode."""

from __future__ import annotations

from app.models.mapping import TargetIntentOption, TargetProjectionMode, TargetSystem
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.utils.normalization import normalize_name, tokenize_name


_TARGET_INTENT_OPTIONS: dict[str, TargetIntentOption] = {
    "canonical": TargetIntentOption(
        target_system="canonical",
        label="Canonical only",
        description="Canonical-first mapping with no system-specific projection bias.",
        projection_mode="canonical_only",
        artifact_type="canonical-only",
        target_profile="canonical_core",
    ),
    "sap": TargetIntentOption(
        target_system="sap",
        label="SAP",
        description="Canonical-first mapping with SAP-oriented target aliases and explainability hints.",
        projection_mode="target_aware_canonical",
        artifact_type="canonical-only",
        target_profile="sap_customer_master",
    ),
}

_TARGET_PROFILE_ALIASES: dict[str, dict[str, list[str]]] = {
    "sap": {
        "customer.id": ["kunnr", "customer number", "sold-to party"],
        "customer.name": ["name1", "customer name", "sold-to party name"],
        "address.country": ["land1", "country key"],
        "address.city": ["ort01", "city"],
    },
}


def list_supported_target_intents() -> list[TargetIntentOption]:
    """Return the supported target-intent options for canonical-first mapping flows."""

    return [option.model_copy() for option in _TARGET_INTENT_OPTIONS.values()]


def get_target_intent_option(target_system: TargetSystem = "canonical") -> TargetIntentOption:
    """Return one supported target-intent option."""

    return _TARGET_INTENT_OPTIONS[str(target_system)]


def build_virtual_target_schema(target_system: TargetSystem = "canonical") -> SchemaProfile:
    """Build a virtual target schema from the canonical glossary for canonical-first mapping mode."""

    if str(target_system) not in _TARGET_INTENT_OPTIONS:
        raise ValueError(f"Unsupported virtual target system: {target_system}")

    target_option = get_target_intent_option(target_system)

    columns = [
        _build_canonical_column(entry, target_system=target_system)
        for entry in metadata_knowledge_service.list_canonical_glossary_entries()
    ]

    return SchemaProfile(
        dataset_id=f"virtual-target:{target_system}",
        dataset_name=(
            metadata_knowledge_service.canonical_glossary_path.name
            if target_system == "canonical"
            else f"{metadata_knowledge_service.canonical_glossary_path.name} [{target_option.label}]"
        ),
        row_count=0,
        columns=columns,
    )


def target_intent_projection_mode(target_system: TargetSystem = "canonical") -> TargetProjectionMode:
    """Return the projection mode for one supported target-intent option."""

    return get_target_intent_option(target_system).projection_mode


def target_intent_profile(target_system: TargetSystem = "canonical") -> str | None:
    """Return the target profile identifier for one supported target-intent option."""

    return get_target_intent_option(target_system).target_profile


def _build_canonical_column(entry, *, target_system: TargetSystem) -> ColumnProfile:
    base_name = " ".join(
        part.strip()
        for part in (entry.display_name, entry.description)
        if str(part).strip()
    ) or entry.display_name
    target_option = get_target_intent_option(target_system)
    profile_aliases = _TARGET_PROFILE_ALIASES.get(str(target_system), {}).get(entry.concept_id, [])
    profile_hint = (
        f"{base_name} {target_option.label} aliases {' '.join(profile_aliases)}"
        if profile_aliases
        else base_name
    )
    detected_patterns, dtype = _canonical_pattern_and_dtype(entry)
    description = str(entry.description or "").strip()
    if profile_aliases:
        description = (
            f"{description}. " if description else ""
        ) + f"Target intent {target_option.label} aliases: {', '.join(profile_aliases)}."

    return ColumnProfile(
        name=entry.concept_id,
        normalized_name=normalize_name(profile_hint),
        description=description,
        dtype=dtype,
        null_ratio=0.0,
        unique_ratio=0.0,
        avg_length=0.0,
        non_null_count=0,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=detected_patterns,
        tokenized_name=tokenize_name(profile_hint),
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