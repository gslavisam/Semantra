from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.mapping import MappingDecision


SAFE_BUILTINS = {
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "str": str,
}


def build_transformation_statement(decision: MappingDecision) -> str:
    code = (decision.transformation_code or "").strip()
    if not code:
        return f'df_target["{decision.target}"] = df_source["{decision.source}"]'
    if "df_target[" in code:
        return code
    return f'df_target["{decision.target}"] = {code}'


def build_transformed_target_frame(
    rows: list[dict[str, object]],
    mapping_decisions: list[MappingDecision],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not rows:
        return [], []

    df_source = pd.DataFrame(rows)
    df_target = pd.DataFrame(index=df_source.index)
    warnings: list[str] = []

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
            continue
        statement = build_transformation_statement(decision)
        try:
            exec(statement, execution_globals, execution_locals)
        except Exception as error:
            warnings.append(
                f"Transformation failed for {decision.source} -> {decision.target}: {error}. Fell back to direct mapping."
            )
            execution_locals["df_target"][decision.target] = execution_locals["df_source"][decision.source]

    df_target = execution_locals["df_target"].where(pd.notnull(execution_locals["df_target"]), "")
    return df_target.to_dict(orient="records"), warnings