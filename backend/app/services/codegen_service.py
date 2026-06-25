"""Starter artifact code generation for Pandas, PySpark, and dbt outputs."""

from __future__ import annotations

import re

from app.models.mapping import GeneratedArtifact, MappingDecision, TransformationSpec
from app.services.transformation_spec_service import is_runtime_active_mapping, summarize_transformation_spec
from app.services.dbt_codegen_profile import current_dbt_codegen_profile, dbt_identifier, dbt_source_relation
from app.services.transformation_service import (
    build_mapping_privacy_warnings,
    build_transformation_statement,
    build_transformation_warning,
)


def _rhs_from_pandas_code(code: str, target: str) -> str:
    """Strip a df_target assignment prefix and return the right-hand expression."""
    stripped = code.strip()
    m = re.match(r'^df_target\[".+?"\]\s*=\s*(.+)$', stripped, re.DOTALL)
    return m.group(1).strip() if m else stripped


def _try_translate_pandas_to_pyspark(custom_code: str, source: str, target: str) -> str | None:
    """Translate known Pandas template patterns to PySpark F.* expressions.

    Returns the PySpark column expression string (without trailing comma) or None when
    the pattern is not recognised and a fallback is needed.
    """
    rhs = _rhs_from_pandas_code(custom_code, target)
    src = re.escape(source)

    # Direct column reference
    if re.fullmatch(rf'df_source\["{src}"\]', rhs):
        return f'F.col("{source}").alias("{target}")'

    # str.strip()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.strip\(\)', rhs):
        return f'F.trim(F.col("{source}").cast("string")).alias("{target}")'

    # str.lower()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.lower\(\)', rhs):
        return f'F.lower(F.col("{source}").cast("string")).alias("{target}")'

    # str.upper()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.upper\(\)', rhs):
        return f'F.upper(F.col("{source}").cast("string")).alias("{target}")'

    # str.title() -> initcap
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.title\(\)', rhs):
        return f'F.initcap(F.col("{source}").cast("string")).alias("{target}")'

    # Add prefix: .apply(lambda v: "PREFIX" + v if pd.notna(v) else v)
    m = re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.apply\(lambda v:\s*"(.+?)"\s*\+\s*v\s+if\s+pd\.notna\(v\)\s+else\s+v\)',
        rhs,
    )
    if m:
        prefix = m.group(1).replace('"', '\\"')
        return f'F.concat(F.lit("{prefix}"), F.col("{source}").cast("string")).alias("{target}")'

    # Add suffix: .apply(lambda v: v + "SUFFIX" if pd.notna(v) else v)
    m = re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.apply\(lambda v:\s*v\s*\+\s*"(.+?)"\s+if\s+pd\.notna\(v\)\s+else\s+v\)',
        rhs,
    )
    if m:
        suffix = m.group(1).replace('"', '\\"')
        return f'F.concat(F.col("{source}").cast("string"), F.lit("{suffix}")).alias("{target}")'

    # Digits only: str.replace(r"\D+", "", regex=True)
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.replace\(r"\\\\D\\+",\s*"",\s*regex=True\)', rhs):
        return f'F.regexp_replace(F.col("{source}").cast("string"), r"\\D+", "").alias("{target}")'

    # Email local-part: .str.split("@").str[0].str.replace(".", " ", regex=False).str.title()
    if re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.str\.split\("@"\)\.str\[0\]\.str\.replace\("\.",\s*" ",\s*regex=False\)\.str\.title\(\)',
        rhs,
    ):
        return (
            f'F.initcap(F.regexp_replace(F.split(F.col("{source}").cast("string"), "@").getItem(0), r"\\.", " "))'
            f'.alias("{target}")'
        )

    return None


def _try_translate_pandas_to_dbt_sql(
    custom_code: str,
    source: str,
    target: str,
    source_ref: str,
    target_ref: str,
) -> str | None:
    """Translate known Pandas template patterns to dbt SQL column expressions.

    Returns a SQL expression fragment (e.g. ``TRIM(stage.col) as tgt``) or None.
    """
    rhs = _rhs_from_pandas_code(custom_code, target)
    src = re.escape(source)

    # Direct column reference
    if re.fullmatch(rf'df_source\["{src}"\]', rhs):
        return f"{source_ref} as {target_ref}"

    # str.strip()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.strip\(\)', rhs):
        return f"TRIM(CAST({source_ref} AS VARCHAR)) as {target_ref}"

    # str.lower()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.lower\(\)', rhs):
        return f"LOWER(CAST({source_ref} AS VARCHAR)) as {target_ref}"

    # str.upper()
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.upper\(\)', rhs):
        return f"UPPER(CAST({source_ref} AS VARCHAR)) as {target_ref}"

    # str.title() -> INITCAP
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.title\(\)', rhs):
        return f"INITCAP(CAST({source_ref} AS VARCHAR)) as {target_ref}"

    # Add prefix
    m = re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.apply\(lambda v:\s*"(.+?)"\s*\+\s*v\s+if\s+pd\.notna\(v\)\s+else\s+v\)',
        rhs,
    )
    if m:
        prefix = m.group(1).replace("'", "''")
        return f"CONCAT('{prefix}', CAST({source_ref} AS VARCHAR)) as {target_ref}"

    # Add suffix
    m = re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.apply\(lambda v:\s*v\s*\+\s*"(.+?)"\s+if\s+pd\.notna\(v\)\s+else\s+v\)',
        rhs,
    )
    if m:
        suffix = m.group(1).replace("'", "''")
        return f"CONCAT(CAST({source_ref} AS VARCHAR), '{suffix}') as {target_ref}"

    # Digits only
    if re.fullmatch(rf'df_source\["{src}"\]\.astype\(str\)\.str\.replace\(r"\\\\D\\+",\s*"",\s*regex=True\)', rhs):
        return f"REGEXP_REPLACE(CAST({source_ref} AS VARCHAR), '\\D+', '') as {target_ref}"

    # Email local-part
    if re.fullmatch(
        rf'df_source\["{src}"\]\.astype\(str\)\.str\.split\("@"\)\.str\[0\]\.str\.replace\("\.",\s*" ",\s*regex=False\)\.str\.title\(\)',
        rhs,
    ):
        return f"INITCAP(REPLACE(SPLIT_PART(CAST({source_ref} AS VARCHAR), '@', 1), '.', ' ')) as {target_ref}"

    return None


def generate_pandas_code(
    mapping_decisions: list[MappingDecision],
    transformation_spec: TransformationSpec | None = None,
) -> GeneratedArtifact:
    """Generate a Pandas starter artifact from reviewed mapping decisions."""

    lines = [
        "import pandas as pd",
        "",
        "df_target = pd.DataFrame()",
    ]
    warnings = []

    for decision in mapping_decisions:
        if decision.status == "rejected" or not is_runtime_active_mapping(decision):
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped inactive mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status, "resolution_type": decision.resolution_type},
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

    return GeneratedArtifact(
        code="\n".join(lines),
        warnings=warnings,
        transformation_spec_summary=summarize_transformation_spec(transformation_spec, mapping_decisions)
        if transformation_spec
        else None,
    )


def _pyspark_column_expression(decision: MappingDecision) -> tuple[str, list]:
    warnings = []
    custom_code = (decision.transformation_code or "").strip()
    if not custom_code:
        return f'F.col("{decision.source}").alias("{decision.target}")', warnings

    # Try static pattern-based translation first
    translated = _try_translate_pandas_to_pyspark(custom_code, decision.source, decision.target)
    if translated is not None:
        return translated, warnings

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
                f"PySpark code generation could not automatically translate the custom transformation for "
                f"{decision.source} -> {decision.target}. Direct mapping was emitted; "
                "use LLM Refine to produce a full PySpark equivalent."
            ),
            source=decision.source,
            target=decision.target,
            stage="codegen",
            fallback_applied=True,
            details={"statement": statement, "requested_runtime": "python-pyspark"},
        )
    )
    return f'F.col("{decision.source}").alias("{decision.target}")', warnings


def generate_pyspark_code(
    mapping_decisions: list[MappingDecision],
    transformation_spec: TransformationSpec | None = None,
) -> GeneratedArtifact:
    """Generate a PySpark starter artifact from reviewed mapping decisions."""

    lines = [
        "from pyspark.sql import functions as F",
        "",
        "df_target = df_source.select(",
    ]
    warnings = []
    select_lines: list[str] = []

    for decision in mapping_decisions:
        if decision.status == "rejected" or not is_runtime_active_mapping(decision):
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped inactive mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status, "resolution_type": decision.resolution_type},
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

    return GeneratedArtifact(
        language="python-pyspark",
        code="\n".join(lines),
        warnings=warnings,
        transformation_spec_summary=summarize_transformation_spec(transformation_spec, mapping_decisions)
        if transformation_spec
        else None,
    )


def _dbt_select_expression(decision: MappingDecision) -> tuple[str, list]:
    warnings = []
    custom_code = (decision.transformation_code or "").strip()
    profile = current_dbt_codegen_profile()
    source_ref = f"{profile.source_cte_name}.{dbt_identifier(decision.source, profile)}"
    target_ref = dbt_identifier(decision.target, profile)
    if not custom_code:
        return f"{source_ref} as {target_ref}", warnings

    # Try static pattern-based translation first
    translated = _try_translate_pandas_to_dbt_sql(custom_code, decision.source, decision.target, source_ref, target_ref)
    if translated is not None:
        return translated, warnings

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
                f"dbt code generation could not automatically translate the custom transformation for "
                f"{decision.source} -> {decision.target}. Direct column mapping was emitted; "
                "use LLM Refine to produce a full dbt SQL equivalent."
            ),
            source=decision.source,
            target=decision.target,
            stage="codegen",
            fallback_applied=True,
            details={"statement": statement, "requested_runtime": "sql-dbt"},
        )
    )
    return f"{source_ref} as {target_ref}", warnings


def generate_dbt_code(
    mapping_decisions: list[MappingDecision],
    transformation_spec: TransformationSpec | None = None,
) -> GeneratedArtifact:
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
        if decision.status == "rejected" or not is_runtime_active_mapping(decision):
            warnings.append(
                build_transformation_warning(
                    code="skipped_rejected_mapping",
                    message=f"Skipped inactive mapping: {decision.source} -> {decision.target}",
                    source=decision.source,
                    target=decision.target,
                    stage="codegen",
                    details={"decision_status": decision.status, "resolution_type": decision.resolution_type},
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

    return GeneratedArtifact(
        language="sql-dbt",
        code="\n".join(lines),
        warnings=warnings,
        transformation_spec_summary=summarize_transformation_spec(transformation_spec, mapping_decisions)
        if transformation_spec
        else None,
    )