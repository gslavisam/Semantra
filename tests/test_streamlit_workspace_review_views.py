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


def test_review_attention_summary_rows_groups_unmatched_and_low_confidence_patterns() -> None:
    rows = workspace_review_views._review_attention_summary_rows(
        [
            {
                "source": "LAND1",
                "target": "",
                "confidence_label": "low_confidence",
                "canonical_status": "no_match",
                "canonical_status_label": "No canonical match",
                "shared_concepts": "",
                "source_concepts": "",
                "target_concepts": "",
            },
            {
                "source": "REGIO",
                "target": "",
                "confidence_label": "low_confidence",
                "canonical_status": "no_match",
                "canonical_status_label": "No canonical match",
                "shared_concepts": "",
                "source_concepts": "",
                "target_concepts": "",
            },
            {
                "source": "KUNNR",
                "target": "customer_id",
                "confidence_label": "low_confidence",
                "canonical_status": "source_only_match",
                "canonical_status_label": "Source-only canonical match",
                "shared_concepts": "",
                "source_concepts": "customer.id",
                "target_concepts": "",
            },
            {
                "source": "ALT_KUNNR",
                "target": "customer_id",
                "confidence_label": "low_confidence",
                "canonical_status": "source_only_match",
                "canonical_status_label": "Source-only canonical match",
                "shared_concepts": "",
                "source_concepts": "customer.id",
                "target_concepts": "",
            },
            {
                "source": "NAME1",
                "target": "customer_name",
                "confidence_label": "high_confidence",
                "canonical_status": "shared_match",
                "canonical_status_label": "Shared canonical match",
                "shared_concepts": "customer.name",
                "source_concepts": "customer.name",
                "target_concepts": "customer.name",
            },
        ]
    )

    assert rows == [
        {
            "issue_type": "unmatched",
            "focus": "No canonical match",
            "canonical_status": "No canonical match",
            "count": 2,
            "source_examples": "LAND1, REGIO",
            "follow_up": "Check missing glossary coverage or absent viable target candidates.",
        },
        {
            "issue_type": "low_confidence",
            "focus": "customer_id",
            "canonical_status": "Source-only canonical match",
            "count": 2,
            "source_examples": "KUNNR, ALT_KUNNR",
            "follow_up": "Check glossary/knowledge coverage before forcing target decisions.",
        },
    ]