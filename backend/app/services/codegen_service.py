from __future__ import annotations

from app.models.mapping import GeneratedArtifact, MappingDecision


def generate_pandas_code(mapping_decisions: list[MappingDecision]) -> GeneratedArtifact:
    lines = [
        "import pandas as pd",
        "",
        "df_target = pd.DataFrame()",
    ]
    warnings: list[str] = []

    for decision in mapping_decisions:
        if decision.status == "rejected":
            warnings.append(f"Skipped rejected mapping: {decision.source} -> {decision.target}")
            continue
        lines.append(f'df_target["{decision.target}"] = df_source["{decision.source}"]')

    return GeneratedArtifact(code="\n".join(lines), warnings=warnings)