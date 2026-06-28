"""Transformation authoring, preview classification, and warning generation logic."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.mapping import (
    MappingDecision,
    TransformationPreviewResult,
    TransformationPreviewWarning,
    TransformationSpec,
    TransformationSpecFieldRule,
)
from app.models.schema import ColumnProfile
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.utils.normalization import normalize_name, tokenize_name


SAFE_BUILTINS = {
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "str": str,
}


def build_transformation_warning(
    *,
    code: str,
    message: str,
    source: str,
    target: str,
    stage: str = "preview",
    severity: str = "warning",
    fallback_applied: bool = False,
    details: dict[str, Any] | None = None,
) -> TransformationPreviewWarning:
    """Build one structured transformation warning for preview and code-generation surfaces."""

    return TransformationPreviewWarning(
        code=code,
        message=message,
        source=source,
        target=target,
        stage=stage,
        severity=severity,
        fallback_applied=fallback_applied,
        details=details or {},
    )


def build_transformation_statement(decision: MappingDecision) -> str:
    """Normalize a mapping decision into an executable Pandas assignment statement."""

    code = (decision.transformation_code or "").strip()
    if not code:
        return f'df_target["{decision.target}"] = df_source["{decision.source}"]'
    if "df_target[" in code:
        return code
    return f'df_target["{decision.target}"] = {code}'


def _lightweight_column_profile(column_name: str) -> ColumnProfile:
    return ColumnProfile(
        name=column_name,
        normalized_name=normalize_name(column_name),
        description="",
        declared_type="",
        dtype="string",
        null_ratio=0.0,
        unique_ratio=0.0,
        avg_length=0.0,
        non_null_count=0,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=[],
        tokenized_name=tokenize_name(column_name),
    )


def build_mapping_privacy_warnings(
    decision: MappingDecision,
    *,
    stage: str = "preview",
) -> list[TransformationPreviewWarning]:
    """Emit a warning when a mapping pair shares privacy-tagged canonical meaning."""

    privacy_concepts = metadata_knowledge_service.canonical_privacy_concepts_for_mapping(
        _lightweight_column_profile(decision.source),
        _lightweight_column_profile(decision.target),
    )
    if not privacy_concepts:
        return []

    concept_labels: list[str] = []
    for concept in privacy_concepts[:3]:
        tags: list[str] = []
        if concept.get("is_pii"):
            tags.append("PII")
        if concept.get("is_gdpr_special_category"):
            tags.append("GDPR special")
        pii_categories = concept.get("pii_categories") or []
        if pii_categories:
            tags.append("tags=" + ", ".join(str(value) for value in pii_categories))
        data_subject_types = concept.get("data_subject_types") or []
        if data_subject_types:
            tags.append("subjects=" + ", ".join(str(value) for value in data_subject_types))
        concept_labels.append(f"{concept.get('concept_id')} ({'; '.join(tags)})")

    overflow = len(privacy_concepts) - len(concept_labels)
    overflow_suffix = f" (+{overflow} more)" if overflow > 0 else ""
    return [
        build_transformation_warning(
            code="privacy_classification",
            message=(
                "Shared privacy-tagged canonical concept detected for this mapping: "
                + "; ".join(concept_labels)
                + overflow_suffix
                + ". Review masking, minimization, and downstream handling before production use."
            ),
            source=decision.source,
            target=decision.target,
            stage=stage,
            details={"privacy_concepts": privacy_concepts},
        )
    ]


def sample_series_values(series: pd.Series) -> list[str]:
    """Return a short stringified sample from a Pandas series for preview readouts."""

    return ["" if pd.isna(value) else str(value) for value in series.head(3).tolist()]


def semantic_dtype_label(series: pd.Series) -> str:
    """Collapse a Pandas dtype into a coarse semantic label for preview comparisons."""

    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_string_dtype(series) or pd.api.types.infer_dtype(series, skipna=True) in {"string", "unicode", "empty"}:
        return "string"
    return str(series.dtype)


def classify_transformation_preview(mode: str, status: str, warnings: list[TransformationPreviewWarning]) -> str:
    """Classify a transformation preview as direct, safe, or risky for UI display."""

    if mode == "direct":
        return "direct"
    if status == "validated" and not warnings:
        return "safe"
    return "risky"


def build_transformed_target_frame(
    rows: list[dict[str, object]],
    mapping_decisions: list[MappingDecision],
    transformation_spec: TransformationSpec | None = None,
) -> tuple[list[dict[str, Any]], list[TransformationPreviewResult]]:
    """Apply mapping decisions to preview rows and collect transformation preview results."""

    if not rows:
        return [], []

    df_source = pd.DataFrame(rows)
    df_target = pd.DataFrame(index=df_source.index)
    preview_results: list[TransformationPreviewResult] = []
    spec_lookup = {
        str(rule.target_field or "").strip(): rule
        for rule in (transformation_spec.field_rules if transformation_spec else [])
        if str(rule.target_field or "").strip()
    }

    execution_globals = {
        "__builtins__": SAFE_BUILTINS,
        "pd": pd,
    }
    execution_locals = {
        "df_source": df_source,
        "df_target": df_target,
    }

    for decision in mapping_decisions:
        if decision.source not in df_source.columns:
            preview_results.append(
                TransformationPreviewResult(
                    source=decision.source,
                    target=decision.target,
                    mode="custom" if (decision.transformation_code or "").strip() else "direct",
                    status="fallback",
                    classification="risky",
                    spec_rule=(spec_lookup.get(decision.target) or TransformationSpecFieldRule(target_field="", rule="")).rule if transformation_spec else "",
                    spec_source_fields=(
                        (spec_lookup.get(decision.target) or TransformationSpecFieldRule(target_field="", rule="")).source_fields
                        if transformation_spec
                        else []
                    ),
                    warnings=[
                        build_transformation_warning(
                            code="missing_source_column",
                            message=f"Missing source column: {decision.source}",
                            source=decision.source,
                            target=decision.target,
                            severity="error",
                            fallback_applied=True,
                            details={"missing_column": decision.source},
                        )
                    ],
                )
            )
            continue

        source_series = execution_locals["df_source"][decision.source].copy()
        custom_code = (decision.transformation_code or "").strip()
        mode = "custom" if custom_code else "direct"
        status = "direct" if not custom_code else "validated"
        warnings: list[TransformationPreviewWarning] = build_mapping_privacy_warnings(decision, stage="preview")

        if not custom_code:
            execution_locals["df_target"][decision.target] = source_series
        else:
            statement = build_transformation_statement(decision)
            try:
                compile(statement, f"<transformation:{decision.source}->{decision.target}>", "exec")
            except SyntaxError as error:
                warnings.append(
                    build_transformation_warning(
                        code="syntax_error",
                        message=(
                            f"Transformation syntax error for {decision.source} -> {decision.target}: {error.msg}. "
                            "Fell back to direct mapping."
                        ),
                        source=decision.source,
                        target=decision.target,
                        severity="error",
                        fallback_applied=True,
                        details={
                            "syntax_message": error.msg,
                            "line": error.lineno,
                            "column": error.offset,
                            "statement": statement,
                        },
                    )
                )
                execution_locals["df_target"][decision.target] = source_series
                status = "fallback"
            else:
                try:
                    exec(statement, execution_globals, execution_locals)
                    if decision.target not in execution_locals["df_target"].columns:
                        raise KeyError(f"Transformation did not populate target column '{decision.target}'")
                    result_series = execution_locals["df_target"][decision.target]
                    if len(result_series) != len(df_source.index):
                        warnings.append(
                            build_transformation_warning(
                                code="row_count_mismatch",
                                message=(
                                    f"Transformation produced {len(result_series)} rows for {decision.source} -> {decision.target} "
                                    f"but preview expected {len(df_source.index)}. Fell back to direct mapping."
                                ),
                                source=decision.source,
                                target=decision.target,
                                severity="error",
                                fallback_applied=True,
                                details={
                                    "produced_row_count": len(result_series),
                                    "expected_row_count": len(df_source.index),
                                },
                            )
                        )
                        execution_locals["df_target"][decision.target] = source_series
                        status = "fallback"
                    else:
                        if result_series.isna().sum() > source_series.isna().sum():
                            warnings.append(
                                build_transformation_warning(
                                    code="null_expansion",
                                    message=(
                                        f"Transformation increased null values for {decision.source} -> {decision.target}."
                                    ),
                                    source=decision.source,
                                    target=decision.target,
                                    details={
                                        "source_null_count": int(source_series.isna().sum()),
                                        "result_null_count": int(result_series.isna().sum()),
                                    },
                                )
                            )
                        if semantic_dtype_label(source_series) != semantic_dtype_label(result_series):
                            warnings.append(
                                build_transformation_warning(
                                    code="type_coercion",
                                    message=(
                                        f"Transformation changed dtype from {source_series.dtype} to {result_series.dtype} for "
                                        f"{decision.source} -> {decision.target}."
                                    ),
                                    source=decision.source,
                                    target=decision.target,
                                    details={
                                        "source_dtype": str(source_series.dtype),
                                        "result_dtype": str(result_series.dtype),
                                        "source_semantic_dtype": semantic_dtype_label(source_series),
                                        "result_semantic_dtype": semantic_dtype_label(result_series),
                                    },
                                )
                            )
                except Exception as error:
                    warnings.append(
                        build_transformation_warning(
                            code="runtime_error",
                            message=(
                                f"Transformation failed for {decision.source} -> {decision.target}: {error}. Fell back to direct mapping."
                            ),
                            source=decision.source,
                            target=decision.target,
                            severity="error",
                            fallback_applied=True,
                            details={
                                "exception_type": error.__class__.__name__,
                                "statement": statement,
                            },
                        )
                    )
                    execution_locals["df_target"][decision.target] = source_series
                    status = "fallback"

        after_series = execution_locals["df_target"][decision.target]
        preview_results.append(
            TransformationPreviewResult(
                source=decision.source,
                target=decision.target,
                mode=mode,
                status=status,
                classification=classify_transformation_preview(mode, status, warnings),
                before_samples=sample_series_values(source_series),
                after_samples=sample_series_values(after_series),
                warnings=warnings,
                spec_rule=(spec_lookup.get(decision.target) or TransformationSpecFieldRule(target_field="", rule="")).rule if transformation_spec else "",
                spec_source_fields=(
                    (spec_lookup.get(decision.target) or TransformationSpecFieldRule(target_field="", rule="")).source_fields
                    if transformation_spec
                    else []
                ),
            )
        )

    df_target = execution_locals["df_target"].where(pd.notnull(execution_locals["df_target"]), "")
    return df_target.to_dict(orient="records"), preview_results