"""Tests Streamlit workspace review helpers for analysis and refinement flows."""

from __future__ import annotations

from types import SimpleNamespace

from streamlit_ui import workspace_review_views


def test_catalog_review_focus_sources_deduplicate_session_state_entries(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={"review_focus_sources": [" KUNNR ", "LAND1", "kunnr", ""]})
    monkeypatch.setattr(workspace_review_views, "st", fake_streamlit)

    assert workspace_review_views._catalog_review_focus_sources() == ["KUNNR", "LAND1"]


def test_filter_rows_for_catalog_review_focus_matches_sources_case_insensitively() -> None:
    assert workspace_review_views._filter_rows_for_catalog_review_focus(
        [
            {"source": "KUNNR", "target": "customer_id"},
            {"source": "LAND1", "target": "country_code"},
        ],
        ["kunnr"],
    ) == [{"source": "KUNNR", "target": "customer_id"}]


def test_catalog_review_focus_helpers_describe_multi_source_scope() -> None:
    assert workspace_review_views._catalog_review_focus_caption(["KUNNR", "LAND1"]) == (
        "Catalog diff focus is limiting Workspace Review to 2 changed source fields: KUNNR, LAND1."
    )
    assert workspace_review_views._effective_review_source_filter_label(
        "All",
        all_filter_option="All",
        focused_sources=["KUNNR", "LAND1"],
    ) == "Catalog diff focus (2 sources)"


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


def test_mapping_llm_proposal_confidence_ignores_generate_time_llm_validation() -> None:
    confidence = workspace_review_views._mapping_llm_proposal_confidence(
        {
            "source": "VKORG",
            "target": "sales_organization_id",
            "status": "accepted",
            "llm_recommendation": {"confidence": 0.86},
            "llm_decision_proposition": {"confidence": 0.86},
        },
        {"status": "accepted"},
        pending_proposals=[],
    )

    assert confidence is None


def test_mapping_llm_proposal_confidence_uses_refine_preview_when_present() -> None:
    confidence = workspace_review_views._mapping_llm_proposal_confidence(
        {
            "source": "VKORG",
            "target": "sales_organization_id",
            "status": "accepted",
        },
        {
            "status": "accepted",
            "llm_mapping_refinement": {
                "selected": {
                    "target": "sales_organization_id",
                    "llm_recommendation": {"confidence": 0.66},
                }
            },
        },
        pending_proposals=[],
    )

    assert confidence == 0.66


def test_llm_proposal_percent_label_hides_missing_values() -> None:
    assert workspace_review_views._llm_proposal_percent_label(None) == ""
    assert workspace_review_views._llm_proposal_percent_label("") == ""
    assert workspace_review_views._llm_proposal_percent_label(0.66) == "66%"


def test_selected_mapping_display_rows_leave_llm_proposal_blank_without_review_generated_state() -> None:
    rows = workspace_review_views._selected_mapping_display_rows(
        [
            {
                "source": "VKORG",
                "target": "sales_organization_id",
                "confidence": 0.86,
                "status": "accepted",
                "validator": "Knowledge match",
                "canonical_status": "shared_match",
                "canonical_status_label": "Shared canonical match",
                "shared_concepts": "sales.organization",
                "source_concepts": "sales.organization",
                "target_concepts": "sales.organization",
                "canonical_path": "VKORG -> sales.organization -> sales_organization_id",
                "llm_consulted": True,
                "llm_recommendation": {"confidence": 0.86},
            }
        ],
        {"VKORG": {"status": "accepted"}},
        [],
    )

    assert rows[0]["original_confidence"] == "86%"
    assert rows[0]["llm_proposal_confidence"] == ""


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


def test_guidance_generation_detail_uses_shared_llm_fallback_pattern() -> None:
    assert workspace_review_views._guidance_generation_detail(None) == ""
    assert workspace_review_views._guidance_generation_detail({"generation_metadata": {"used_llm": True}}) == "LLM"
    assert workspace_review_views._guidance_generation_detail({"generation_metadata": {"used_llm": False}}) == "Fallback"


def test_guidance_generation_message_helpers_use_shared_copy_pattern() -> None:
    assert workspace_review_views._guidance_generation_success_message(
        "review queue plan",
        "the current review set",
    ) == "Generated review queue plan for the current review set."
    assert workspace_review_views._guidance_generation_error_message("Review queue plan", "boom") == (
        "Review queue plan generation failed: boom"
    )


def test_guidance_generation_metadata_caption_uses_llm_fallback_pattern() -> None:
    assert workspace_review_views._guidance_generation_metadata_caption(None) == ""
    assert workspace_review_views._guidance_generation_metadata_caption(
        {"generation_metadata": {"used_llm": True, "fallback_used": False}}
    ) == "LLM"
    assert workspace_review_views._guidance_generation_metadata_caption(
        {"generation_metadata": {"used_llm": False, "fallback_used": True}}
    ) == "Fallback with fallback contract"


def test_guidance_output_heading_preserves_section_title() -> None:
    assert workspace_review_views._guidance_output_heading("Key matches") == "Key matches"
    assert workspace_review_views._guidance_output_heading(" Risks ") == "Risks"


def test_selected_mapping_display_rows_formats_original_and_llm_proposal_confidence() -> None:
    rows = workspace_review_views._selected_mapping_display_rows(
        [
            {
                "source": "segment_label",
                "target": "customer_segment",
                "confidence": 0.61,
                "status": "accepted",
                "validator": "Manual review",
                "canonical_status": "source_only_match",
                "canonical_status_label": "Source-only canonical match",
                "shared_concepts": "",
                "source_concepts": "customer.segment",
                "target_concepts": "",
                "canonical_path": "segment_label -> customer.segment -> customer_segment",
                "llm_consulted": True,
            }
        ],
        {
            "segment_label": {
                "status": "accepted",
                "llm_proposal_confidence": 0.8,
                "llm_proposal_target": "customer_segment",
                "llm_proposal_status": "accepted",
            }
        },
    )

    assert rows == [
        {
            "source": "segment_label",
            "target": "customer_segment",
            "original_confidence": "61%",
            "llm_proposal_confidence": "80%",
            "status": "accepted",
            "validator": "Manual review",
            "canonical_status": "Source-only canonical match",
            "shared_concepts": "",
            "source_concepts": "customer.segment",
            "target_concepts": "",
            "canonical_path": "segment_label -> customer.segment -> customer_segment",
            "llm_consulted": "yes",
        }
    ]


def test_selected_mapping_display_rows_uses_pending_generated_llm_proposal_confidence() -> None:
    rows = workspace_review_views._selected_mapping_display_rows(
        [
            {
                "source": "segment_label",
                "target": "customer_segment",
                "confidence": 0.61,
                "status": "needs_review",
                "validator": "Manual review",
                "canonical_status": "source_only_match",
                "canonical_status_label": "Source-only canonical match",
                "shared_concepts": "",
                "source_concepts": "customer.segment",
                "target_concepts": "",
                "canonical_path": "segment_label -> customer.segment -> customer_segment",
                "llm_consulted": True,
            }
        ],
        {},
        [
            {
                "source": "segment_label",
                "current_target": "customer_segment",
                "current_status": "needs_review",
                "confidence": 0.8,
                "proposal_type": "accept_current",
            }
        ],
    )

    assert rows == [
        {
            "source": "segment_label",
            "target": "customer_segment",
            "original_confidence": "61%",
            "llm_proposal_confidence": "80%",
            "status": "needs_review",
            "validator": "Manual review",
            "canonical_status": "Source-only canonical match",
            "shared_concepts": "",
            "source_concepts": "customer.segment",
            "target_concepts": "",
            "canonical_path": "segment_label -> customer.segment -> customer_segment",
            "llm_consulted": "yes",
        }
    ]


def test_canonical_gap_triage_copy_helpers_state_read_only_and_unlock_roles() -> None:
    assert workspace_review_views._canonical_gap_triage_intro_caption() == (
        "Generate one bounded gap queue summary for the current canonical-gap queue before reviewing candidates one by one. "
        "This is a read-only guidance surface and does not change candidate decisions or approval state."
    )
    assert workspace_review_views._canonical_gap_triage_unlock_message() == (
        "Run 'Find canonical gaps' first to unlock the queue-level summary."
    )


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


def test_build_llm_decision_proposal_creates_safe_accept_current_proposal() -> None:
    proposal = workspace_review_views._build_llm_decision_proposal(
        {
            "source": "annual_spend_usd",
            "target": "annual_revenue_usd",
            "status": "needs_review",
            "signals": {"knowledge": 0.4, "canonical": 0.0},
            "explanation": ["Context prior: finance glossary supports this mapping."],
            "llm_recommendation": {"confidence": 0.91, "reasoning": ["Business semantics align."]},
            "llm_decision_proposition": {
                "proposition_type": "confirm",
                "summary": "LLM supports the current target.",
            },
        },
        {"target": "annual_revenue_usd", "status": "needs_review"},
    )

    assert proposal == {
        "source": "annual_spend_usd",
        "current_target": "annual_revenue_usd",
        "current_status": "needs_review",
        "proposal_type": "accept_current",
        "proposed_target": "annual_revenue_usd",
        "proposed_status": "accepted",
        "summary": "LLM supports the current target.",
        "confidence": 0.91,
        "reasoning": ["Business semantics align."],
        "origin": "mapping_validation",
        "knowledge_supported": True,
        "canonical_supported": False,
        "safe_to_apply": True,
        "safe_reason": "Eligible for safe apply.",
    }


def test_build_llm_decision_proposal_marks_unsupported_switch_as_not_safe() -> None:
    proposal = workspace_review_views._build_llm_decision_proposal(
        {
            "source": "op_type",
            "target": "operation_label",
            "status": "needs_review",
            "signals": {"knowledge": 0.0, "canonical": 0.0},
            "explanation": [],
            "llm_recommendation": {"confidence": 0.9, "reasoning": ["Another candidate is semantically closer."]},
            "llm_decision_proposition": {
                "proposition_type": "challenge",
                "proposed_target": "operation_type_code",
                "summary": "LLM prefers operation_type_code.",
            },
        },
        {"target": "operation_label", "status": "needs_review"},
    )

    assert proposal is not None
    assert proposal["proposal_type"] == "switch_target"
    assert proposal["proposed_target"] == "operation_type_code"
    assert proposal["safe_to_apply"] is False
    assert proposal["safe_reason"] == "Switch proposals need knowledge or canonical support for batch-safe apply."


def test_llm_decision_proposals_for_filtered_rows_can_use_live_fill() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_refine(source: str, *, candidate_targets: list[str], **_: object) -> dict:
        calls.append((source, list(candidate_targets)))
        return {
            "selected": {
                "target": "operation_type_code",
                "llm_recommendation": {
                    "confidence": 0.92,
                    "reasoning": ["Target naming and semantics are closer."],
                },
                "llm_decision_proposition": {
                    "summary": "Refine favors operation_type_code.",
                },
            }
        }

    proposals = workspace_review_views._llm_decision_proposals_for_filtered_rows(
        [{"source": "op_type", "status": "needs_review"}],
        {
            "ranked_mappings": [
                {
                    "source": "op_type",
                    "candidates": [
                        {
                            "target": "operation_label",
                            "signals": {"knowledge": 0.4, "canonical": 0.0},
                            "explanation": ["Context prior: operation taxonomy context."],
                        },
                        {
                            "target": "operation_type_code",
                            "signals": {"knowledge": 0.5, "canonical": 0.0},
                            "explanation": ["Context prior: operation taxonomy context."],
                        },
                    ],
                }
            ],
            "mappings": [{"source": "op_type", "target": "operation_label"}],
        },
        {"op_type": {"target": "operation_label", "status": "needs_review"}},
        include_live_llm_fill=True,
        request_llm_mapping_refinement=_fake_refine,
        llm_runtime_available=True,
    )

    assert calls == [("op_type", ["operation_label", "operation_type_code"])]
    assert len(proposals) == 1
    assert proposals[0]["proposal_type"] == "switch_target"
    assert proposals[0]["proposed_target"] == "operation_type_code"


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