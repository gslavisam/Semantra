from __future__ import annotations

import httpx
from typing import Any


def mapping_set_workspace_block_reason(status: str | None, *, action_label: str) -> str:
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "approved":
        return ""
    current_status = normalized_status or "draft"
    return f"Only approved mapping sets can be {action_label}. Current status: {current_status}."


def mapping_output_block_reason(mapping_decisions: list[dict[str, Any]], *, action_label: str) -> str:
    blocked_statuses = sorted(
        {
            (str(item.get("status") or "").strip().lower() or "needs_review")
            for item in mapping_decisions
            if (str(item.get("status") or "").strip().lower() or "needs_review") != "accepted"
        }
    )
    if not blocked_statuses:
        return ""
    return (
        f"{action_label} is blocked until all active mapping decisions are accepted. "
        f"Review statuses: {', '.join(blocked_statuses)}."
    )


def mapping_benchmark_block_reason(mapping_decisions: list[dict[str, Any]]) -> str:
    return mapping_output_block_reason(
        mapping_decisions,
        action_label="Saving current mapping as benchmark",
    )


def api_error_message(error: httpx.HTTPError, *, default_prefix: str) -> str:
    response = getattr(error, "response", None)
    if response is not None and response.status_code in {403, 409}:
        try:
            detail = str(response.json().get("detail") or "").strip()
        except Exception:
            detail = ""
        if detail:
            return detail
    return f"{default_prefix}: {error}"