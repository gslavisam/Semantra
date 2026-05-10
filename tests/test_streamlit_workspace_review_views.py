from __future__ import annotations

from streamlit_ui import workspace_review_views


def test_canonical_gap_approval_block_reason_requires_ready_for_approval() -> None:
    assert workspace_review_views._canonical_gap_approval_block_reason(
        {"action": "existing_concept_alias"},
        "needs_review",
    ) == (
        "Move proposal triage to 'Ready for approval' before approving and persisting this canonical gap. "
        "Current state: needs_review."
    )


def test_canonical_gap_approval_block_reason_rejects_no_action() -> None:
    assert workspace_review_views._canonical_gap_approval_block_reason(
        {"action": "no_action"},
        "ready_for_approval",
    ) == "Generate a usable non-'no_action' canonical gap suggestion before approving."


def test_canonical_gap_approval_block_reason_allows_ready_state_with_real_suggestion() -> None:
    assert workspace_review_views._canonical_gap_approval_block_reason(
        {"action": "new_canonical_concept"},
        "ready_for_approval",
    ) == ""