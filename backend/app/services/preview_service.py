from __future__ import annotations

from app.models.mapping import MappingDecision, PreviewResponse, PreviewRow


def build_preview(rows: list[dict[str, object]], mapping_decisions: list[MappingDecision]) -> PreviewResponse:
    accepted = [decision for decision in mapping_decisions if decision.status != "rejected"]
    preview_rows: list[PreviewRow] = []

    for row in rows[:10]:
        projected = {}
        warnings: list[str] = []
        for decision in accepted:
            if decision.source not in row:
                warnings.append(f"Missing source column: {decision.source}")
                continue
            value = row.get(decision.source)
            projected[decision.target] = "" if value is None else value
        preview_rows.append(PreviewRow(values=projected, warnings=warnings))

    unresolved_targets = [decision.target for decision in mapping_decisions if decision.status == "needs_review"]
    return PreviewResponse(preview=preview_rows, unresolved_targets=unresolved_targets)