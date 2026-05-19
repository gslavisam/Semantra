"""Advisory preview generation for active mapping and transformation decisions."""

from __future__ import annotations

from app.models.mapping import MappingDecision, PreviewResponse, PreviewRow
from app.services.transformation_service import build_transformed_target_frame


def build_preview(rows: list[dict[str, object]], mapping_decisions: list[MappingDecision]) -> PreviewResponse:
    """Build an advisory preview of target rows from the current mapping decisions."""

    accepted = [decision for decision in mapping_decisions if decision.status != "rejected"]
    if not accepted:
        return PreviewResponse(preview=[], unresolved_targets=[], transformation_previews=[])

    transformed_rows, transformation_previews = build_transformed_target_frame(rows[:10], accepted)
    warnings_by_source: dict[str | None, list[str]] = {}
    for transformation_preview in transformation_previews:
        for warning in transformation_preview.warnings:
            warnings_by_source.setdefault(warning.source, []).append(warning.message)

    preview_rows: list[PreviewRow] = []

    for index, row in enumerate(rows[:10]):
        projected = transformed_rows[index] if index < len(transformed_rows) else {}
        warnings: list[str] = []
        for decision in accepted:
            if decision.source not in row:
                warnings.append(f"Missing source column: {decision.source}")
        for source_name, source_warnings in warnings_by_source.items():
            if source_name is None or source_name in row:
                warnings.extend(source_warnings)
        preview_rows.append(PreviewRow(values=projected, warnings=warnings))

    unresolved_targets = [decision.target for decision in mapping_decisions if decision.status == "needs_review"]
    return PreviewResponse(
        preview=preview_rows,
        unresolved_targets=unresolved_targets,
        transformation_previews=transformation_previews,
    )