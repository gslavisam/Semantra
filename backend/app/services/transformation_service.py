from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.mapping import MappingDecision, TransformationPreviewResult, TransformationPreviewWarning


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
    code = (decision.transformation_code or "").strip()
    if not code:
        return f'df_target["{decision.target}"] = df_source["{decision.source}"]'
    if "df_target[" in code:
        return code
    return f'df_target["{decision.target}"] = {code}'


def sample_series_values(series: pd.Series) -> list[str]:
    return ["" if pd.isna(value) else str(value) for value in series.head(3).tolist()]


def semantic_dtype_label(series: pd.Series) -> str:
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
    if mode == "direct":
        return "direct"
    if status == "validated" and not warnings:
        return "safe"
    return "risky"


def build_transformed_target_frame(
    rows: list[dict[str, object]],
    mapping_decisions: list[MappingDecision],
) -> tuple[list[dict[str, Any]], list[TransformationPreviewResult]]:
    if not rows:
        return [], []

    df_source = pd.DataFrame(rows)
    df_target = pd.DataFrame(index=df_source.index)
    preview_results: list[TransformationPreviewResult] = []

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
        warnings: list[TransformationPreviewWarning] = []

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
            )
        )

    df_target = execution_locals["df_target"].where(pd.notnull(execution_locals["df_target"]), "")
    return df_target.to_dict(orient="records"), preview_results