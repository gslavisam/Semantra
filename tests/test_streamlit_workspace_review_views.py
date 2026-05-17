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


def test_section_label_appends_detail_only_when_present() -> None:
    assert workspace_review_views._section_label("Manual Review", "5 items") == "Manual Review · 5 items"
    assert workspace_review_views._section_label("Selected Mapping", "") == "Selected Mapping"


def test_manual_review_open_item_count_counts_non_accepted_or_unmapped_rows() -> None:
    count = workspace_review_views._manual_review_open_item_count(
        {
            "ranked_mappings": [
                {"source": "KUNNR", "candidates": [{"target": "customer_id"}]},
                {"source": "LAND1", "candidates": [{"target": "country_code"}]},
                {"source": "REGIO", "candidates": []},
            ]
        },
        {
            "KUNNR": {"target": "customer_id", "status": "accepted"},
            "LAND1": {"target": "country_code", "status": "needs_review"},
            "REGIO": {"target": "", "status": "accepted"},
        },
        selected_target_options=lambda ranked: [candidate.get("target", "") for candidate in ranked.get("candidates", [])],
    )

    assert count == 2


def test_review_plan_request_payload_preserves_filters_and_rows() -> None:
    payload = workspace_review_views._review_plan_request_payload(
        [{"source": "LAND1"}],
        [{"issue_type": "unmatched"}],
        status_filter="needs_review",
        confidence_filter="low_confidence",
        source_filter="All",
    )

    assert payload == {
        "filtered_rows": [{"source": "LAND1"}],
        "attention_summary_rows": [{"issue_type": "unmatched"}],
        "filters": {
            "status": "needs_review",
            "confidence_label": "low_confidence",
            "source": "All",
        },
    }


def test_review_plan_cluster_rows_flattens_cluster_examples() -> None:
    rows = workspace_review_views._review_plan_cluster_rows(
        {
            "clusters": [
                {
                    "priority": "high",
                    "issue_type": "unmatched",
                    "focus": "No canonical match",
                    "canonical_status": "No canonical match",
                    "count": 2,
                    "source_examples": ["LAND1", "REGIO"],
                    "recommended_follow_up": "Check glossary coverage.",
                }
            ]
        }
    )

    assert rows == [
        {
            "priority": "high",
            "issue_type": "unmatched",
            "focus": "No canonical match",
            "canonical_status": "No canonical match",
            "count": 2,
            "source_examples": "LAND1, REGIO",
            "recommended_follow_up": "Check glossary coverage.",
        }
    ]


def test_canonical_gap_triage_payload_preserves_candidates_and_states() -> None:
    payload = workspace_review_views._canonical_gap_triage_payload(
        [{"source": "ALT_KUNNR"}],
        {"canonical_gap_ALT_KUNNR_customer_shadow_id": {"action": "existing_concept_alias"}},
        {"canonical_gap_ALT_KUNNR_customer_shadow_id": "ready_for_approval"},
    )

    assert payload == {
        "candidates": [{"source": "ALT_KUNNR"}],
        "suggestions": {"canonical_gap_ALT_KUNNR_customer_shadow_id": {"action": "existing_concept_alias"}},
        "proposal_states": {"canonical_gap_ALT_KUNNR_customer_shadow_id": "ready_for_approval"},
    }


def test_canonical_gap_triage_group_rows_flattens_source_examples() -> None:
    rows = workspace_review_views._canonical_gap_triage_group_rows(
        {
            "groups": [
                {
                    "priority": "high",
                    "focus": "customer.shadow_id",
                    "count": 2,
                    "suggestion_action": "existing_concept_alias",
                    "proposal_state": "ready_for_approval",
                    "source_examples": ["ALT_KUNNR", "LEGACY_KUNNR"],
                    "recommended_follow_up": "Approve this alias family before generating new suggestions.",
                }
            ]
        }
    )

    assert rows == [
        {
            "priority": "high",
            "focus": "customer.shadow_id",
            "count": 2,
            "suggestion_action": "existing_concept_alias",
            "proposal_state": "ready_for_approval",
            "source_examples": "ALT_KUNNR, LEGACY_KUNNR",
            "recommended_follow_up": "Approve this alias family before generating new suggestions.",
        }
    ]