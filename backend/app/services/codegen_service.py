from __future__ import annotations

from app.models.mapping import GeneratedArtifact, MappingDecision
from app.services.transformation_service import build_transformation_statement, build_transformation_warning


def generate_pandas_code(mapping_decisions: list[MappingDecision]) -> GeneratedArtifact:
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

        lines.extend(statement.splitlines())

    return GeneratedArtifact(code="\n".join(lines), warnings=warnings)