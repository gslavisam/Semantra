"""Starter artifact code generation for Pandas, PySpark, and dbt outputs."""

from __future__ import annotations

import re

from app.models.mapping import GeneratedArtifact, MappingDecision
from app.services.dbt_codegen_profile import current_dbt_codegen_profile, dbt_identifier, dbt_source_relation
from app.services.transformation_service import (
    build_mapping_privacy_warnings,
    build_transformation_statement,
    build_transformation_warning,
)


def generate_pandas_code(mapping_decisions: list[MappingDecision]) -> GeneratedArtifact:
    """Generate a Pandas starter artifact from reviewed mapping decisions."""

    lines = [
        "import pandas as pd",
        "",
        "df_target = pd.DataFrame()",
    ]
    warnings = []

    for decision in mapping_decisions:
        if decision.status == "rejected":
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped rejected mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status},
                )
            )
            continue

        statement = build_transformation_statement(decision)
        try:
            compile(statement, f"<codegen:{decision.source}->{decision.target}>", "exec")
        except SyntaxError as error:
            warnings.append(
                build_transformation_warning(
                    code="syntax_error",
                    message=(
                        f"Code generation detected invalid transformation syntax for {decision.source} -> {decision.target}: "
                        f"{error.msg}. Direct mapping was emitted instead."
                    ),
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
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
            statement = f'df_target["{decision.target}"] = df_source["{decision.source}"]'

        warnings.extend(build_mapping_privacy_warnings(decision, stage="codegen"))
        lines.extend(statement.splitlines())

    return GeneratedArtifact(code="\n".join(lines), warnings=warnings)


def _pyspark_column_expression(decision: MappingDecision) -> tuple[str, list]:
    warnings = []
    custom_code = (decision.transformation_code or "").strip()
    if not custom_code:
        return f'F.col("{decision.source}").alias("{decision.target}")', warnings

    statement = build_transformation_statement(decision)
    simple_direct_patterns = [
        rf'^df_target\["{re.escape(decision.target)}"\]\s*=\s*df_source\["{re.escape(decision.source)}"\]\s*$',
        rf'^df_source\["{re.escape(decision.source)}"\]\s*$',
    ]
    if any(re.match(pattern, statement) for pattern in simple_direct_patterns):
        return f'F.col("{decision.source}").alias("{decision.target}")', warnings

    warnings.append(
        build_transformation_warning(
            code="untranslated_custom_transformation",
            message=(
                f"PySpark code generation could not translate custom transformation for {decision.source} -> {decision.target}. "
                "Direct mapping was emitted instead."
            ),
            source=decision.source,
            target=decision.target,
            stage="codegen",
            fallback_applied=True,
            details={"statement": statement, "requested_runtime": "python-pyspark"},
        )
    )
    return f'F.col("{decision.source}").alias("{decision.target}")', warnings


def generate_pyspark_code(mapping_decisions: list[MappingDecision]) -> GeneratedArtifact:
    """Generate a PySpark starter artifact from reviewed mapping decisions."""

    lines = [
        "from pyspark.sql import functions as F",
        "",
        "df_target = df_source.select(",
    ]
    warnings = []
    select_lines: list[str] = []

    for decision in mapping_decisions:
        if decision.status == "rejected":
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped rejected mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status},
                )
            )
            continue

        warnings.extend(build_mapping_privacy_warnings(decision, stage="codegen"))
        expression, decision_warnings = _pyspark_column_expression(decision)
        warnings.extend(decision_warnings)
        select_lines.append(f"    {expression},")

    if select_lines:
        lines.extend(select_lines)
    lines.append(")")

    return GeneratedArtifact(language="python-pyspark", code="\n".join(lines), warnings=warnings)


def _dbt_select_expression(decision: MappingDecision) -> tuple[str, list]:
    warnings = []
    custom_code = (decision.transformation_code or "").strip()
    profile = current_dbt_codegen_profile()
    source_ref = f"{profile.source_cte_name}.{dbt_identifier(decision.source, profile)}"
    target_ref = dbt_identifier(decision.target, profile)
    if not custom_code:
        return f"{source_ref} as {target_ref}", warnings

    statement = build_transformation_statement(decision)
    simple_direct_patterns = [
        rf'^df_target\["{re.escape(decision.target)}"\]\s*=\s*df_source\["{re.escape(decision.source)}"\]\s*$',
        rf'^df_source\["{re.escape(decision.source)}"\]\s*$',
    ]
    if any(re.match(pattern, statement) for pattern in simple_direct_patterns):
        return f"{source_ref} as {target_ref}", warnings

    warnings.append(
        build_transformation_warning(
            code="untranslated_custom_transformation",
            message=(
                f"dbt code generation could not translate custom transformation for {decision.source} -> {decision.target}. "
                "Direct column mapping was emitted instead."
            ),
            source=decision.source,
            target=decision.target,
            stage="codegen",
            fallback_applied=True,
            details={"statement": statement, "requested_runtime": "sql-dbt"},
        )
    )
    return f"{source_ref} as {target_ref}", warnings


def generate_dbt_code(mapping_decisions: list[MappingDecision]) -> GeneratedArtifact:
    """Generate a dbt starter model from reviewed mapping decisions."""

    profile = current_dbt_codegen_profile()
    lines = [
        f"{{{{ config(materialized='{profile.materialization}') }}}}",
        "",
        f"with {profile.source_cte_name} as (",
        "    select *",
        f"    from {dbt_source_relation(profile)}",
        ")",
        "",
        "select",
    ]
    warnings = []
    select_lines: list[str] = []

    for decision in mapping_decisions:
        if decision.status == "rejected":
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped rejected mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status},
                )
            )
            continue

        warnings.extend(build_mapping_privacy_warnings(decision, stage="codegen"))
        expression, decision_warnings = _dbt_select_expression(decision)
        warnings.extend(decision_warnings)
        select_lines.append(f"    {expression},")

    if select_lines:
        select_lines[-1] = select_lines[-1].rstrip(",")
        lines.extend(select_lines)
    else:
        lines.append("    *")
    lines.append(f"from {profile.source_cte_name}")

    return GeneratedArtifact(language="sql-dbt", code="\n".join(lines), warnings=warnings)