from __future__ import annotations

from streamlit_ui import admin_views


def test_filter_canonical_concepts_matches_alias_and_display_name() -> None:
    concepts = [
        {
            "concept_id": "customer.id",
            "display_name": "Customer ID",
            "description": "Primary customer identifier",
            "entity": "customer",
            "attribute": "id",
            "source": "base_plus_active_overlay",
            "base_aliases": ["customer_id", "cust_id"],
            "active_overlay_aliases": ["legacy_customer_identifier"],
        },
        {
            "concept_id": "customer.phone",
            "display_name": "Customer Phone",
            "base_aliases": ["phone_number"],
            "active_overlay_aliases": [],
        },
    ]

    filtered = admin_views._filter_canonical_concepts(concepts, "legacy_customer")
    assert [item["concept_id"] for item in filtered] == ["customer.id"]

    filtered_by_name = admin_views._filter_canonical_concepts(concepts, "phone")
    assert [item["concept_id"] for item in filtered_by_name] == ["customer.phone"]


def test_canonical_concept_registry_rows_flattens_alias_columns() -> None:
    rows = admin_views._canonical_concept_registry_rows(
        [
            {
                "concept_id": "customer.id",
                "display_name": "Customer ID",
                "entity": "customer",
                "attribute": "id",
                "data_type": "string",
                "source": "base_plus_active_overlay",
                "usage_count": 3,
                "field_context_count": 2,
                "active_overlay_entry_count": 1,
                "base_aliases": ["customer_id", "cust_id"],
                "active_overlay_aliases": ["legacy_customer_identifier"],
            }
        ]
    )

    assert rows == [
        {
            "concept_id": "customer.id",
            "display_name": "Customer ID",
            "entity": "customer",
            "attribute": "id",
            "data_type": "string",
            "source": "base_plus_active_overlay",
            "usage_count": 3,
            "field_context_count": 2,
            "active_overlay_entry_count": 1,
            "base_aliases": "customer_id, cust_id",
            "active_overlay_aliases": "legacy_customer_identifier",
        }
    ]


def test_filter_canonical_concepts_by_focus_matches_overlay_and_usage_states() -> None:
    concepts = [
        {
            "concept_id": "customer.id",
            "source": "base_plus_active_overlay",
            "usage_count": 3,
            "field_context_count": 1,
            "active_overlay_entry_count": 2,
        },
        {
            "concept_id": "customer.shadow_id",
            "source": "overlay_only",
            "usage_count": 0,
            "field_context_count": 0,
            "active_overlay_entry_count": 1,
        },
        {
            "concept_id": "customer.phone",
            "source": "base",
            "usage_count": 0,
            "field_context_count": 2,
            "active_overlay_entry_count": 0,
        },
    ]

    assert [item["concept_id"] for item in admin_views._filter_canonical_concepts_by_focus(concepts, "active_overlay")] == [
        "customer.id",
        "customer.shadow_id",
    ]
    assert [item["concept_id"] for item in admin_views._filter_canonical_concepts_by_focus(concepts, "overlay_only")] == [
        "customer.shadow_id",
    ]
    assert [item["concept_id"] for item in admin_views._filter_canonical_concepts_by_focus(concepts, "in_use")] == [
        "customer.id",
    ]
    assert [item["concept_id"] for item in admin_views._filter_canonical_concepts_by_focus(concepts, "with_context")] == [
        "customer.id",
        "customer.phone",
    ]


def test_canonical_overlay_summary_aggregates_runtime_and_overlay_versions() -> None:
    summary = admin_views._canonical_overlay_summary(
        {
            "mode": "overlay_active",
            "active_overlay_name": "customer-domain-overlay-v2",
            "active_entry_count": 7,
            "entry_type_counts": {"concept_alias": 4, "synonym": 3},
        },
        [
            {"overlay_id": 1, "status": "active"},
            {"overlay_id": 2, "status": "validated"},
            {"overlay_id": 3, "status": "archived"},
        ],
    )

    assert summary == {
        "mode": "overlay_active",
        "active_overlay_name": "customer-domain-overlay-v2",
        "active_entry_count": 7,
        "concept_alias_entries": 4,
        "total_versions": 3,
        "active_versions": 1,
        "validated_versions": 1,
        "archived_versions": 1,
    }


def test_canonical_gap_queue_rows_merge_candidate_and_suggestion_state() -> None:
    candidates = [
        {
            "source": "LEGACY_CUSTOMER_ID",
            "target": "customer_id",
            "confidence": 0.91,
            "confidence_label": "high_confidence",
            "status": "accepted",
            "method": "multi_signal_heuristic",
            "reason": "Missing canonical path.",
        }
    ]
    suggestions = {
        "canonical_gap_0_LEGACY_CUSTOMER_ID_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
            "display_name": "Customer ID",
            "aliases": ["legacy_customer_id"],
            "reasoning": ["Alias matches known customer identifier semantics."],
            "risk_notes": ["Check overlap with account identifiers."],
        }
    }

    rows = admin_views._canonical_gap_queue_rows(
        candidates,
        suggestions,
        {"canonical_gap_0_LEGACY_CUSTOMER_ID_customer_id": "ignored"},
    )

    assert rows == [
        {
            "source": "LEGACY_CUSTOMER_ID",
            "target": "customer_id",
            "confidence_pct": 91,
            "confidence_label": "high_confidence",
            "status": "accepted",
            "method": "multi_signal_heuristic",
            "reason": "Missing canonical path.",
            "suggested_action": "existing_concept_alias",
            "suggested_concept": "customer.id",
            "suggested_display_name": "Customer ID",
            "alias_count": 1,
            "reasoning_count": 1,
            "risk_count": 1,
            "console_state": "ignored",
        }
    ]


def test_canonical_gap_option_label_reflects_pending_state() -> None:
    label = admin_views._canonical_gap_option_label(
        0,
        {
            "source": "MATERIAL_NUMBER",
            "target": "material_id",
            "confidence": 0.88,
        },
        None,
    )

    assert label == "MATERIAL_NUMBER -> material_id | confidence=88% | action=pending"


def test_canonical_gap_can_approve_rejects_no_action() -> None:
    assert admin_views._canonical_gap_can_approve({"action": "existing_concept_alias"}) is True
    assert admin_views._canonical_gap_can_approve({"action": "new_canonical_concept"}) is True
    assert admin_views._canonical_gap_can_approve({"action": "existing_concept_alias"}, "ignored") is False
    assert admin_views._canonical_gap_can_approve({"action": "existing_concept_alias"}, "approved") is False
    assert admin_views._canonical_gap_can_approve({"action": "no_action"}) is False
    assert admin_views._canonical_gap_can_approve(None) is False


def test_canonical_gap_console_state_defaults_to_active() -> None:
    assert admin_views._canonical_gap_console_state("canonical_gap_0_X_Y", None) == "active"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_0_X_Y",
        {"canonical_gap_0_X_Y": "ignored"},
    ) == "ignored"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_0_X_Y",
        {"canonical_gap_0_X_Y": "approved"},
    ) == "approved"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_0_X_Y",
        {"canonical_gap_0_X_Y": "rejected"},
    ) == "rejected"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_0_X_Y",
        {"canonical_gap_0_X_Y": "weird"},
    ) == "active"


def test_canonical_gap_console_ignore_restore_helpers() -> None:
    assert admin_views._canonical_gap_can_ignore("active") is True
    assert admin_views._canonical_gap_can_ignore("ignored") is False
    assert admin_views._canonical_gap_can_restore("ignored") is True
    assert admin_views._canonical_gap_can_restore("active") is False
    assert admin_views._canonical_gap_can_reject("active") is True
    assert admin_views._canonical_gap_can_reject("ignored") is False
    assert admin_views._canonical_gap_can_reject("rejected") is False


def test_canonical_gap_rejection_request_uses_fallback_actor_and_optional_note() -> None:
    payload = admin_views._canonical_gap_rejection_request(
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        {"action": "existing_concept_alias", "concept_id": "customer.id"},
        None,
        " Duplicate concept under governance review. ",
    )

    assert payload == {
        "candidate": {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        "suggestion": {"action": "existing_concept_alias", "concept_id": "customer.id"},
        "disposition": "rejected",
        "rejected_by": "streamlit-admin-debug",
        "note": "Duplicate concept under governance review.",
    }


def test_canonical_gap_rejection_request_supports_ignored_disposition() -> None:
    payload = admin_views._canonical_gap_rejection_request(
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        None,
        "reviewer-1",
        None,
        disposition="ignored",
    )

    assert payload == {
        "candidate": {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        "disposition": "ignored",
        "rejected_by": "reviewer-1",
    }


def test_canonical_gap_related_audit_entries_filters_by_selected_candidate() -> None:
    audit_entries = [
        {
            "action": "ignore",
            "created_at": "2026-05-10T10:00:00Z",
            "message": "Ignored canonical gap suggestion for LEGACY_CUSTOMER_ID -> customer_id. Disposition=ignored.",
            "overlay_name": None,
        },
        {
            "action": "reject",
            "created_at": "2026-05-10T11:00:00Z",
            "message": "Rejected canonical gap suggestion for MATERIAL_NUMBER -> material_id. Disposition=rejected.",
            "overlay_name": None,
        },
    ]

    rows = admin_views._canonical_gap_related_audit_entries(
        audit_entries,
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
    )

    assert rows == [
        {
            "action": "ignore",
            "overlay_name": "",
            "created_at": "2026-05-10T10:00:00Z",
            "message": "Ignored canonical gap suggestion for LEGACY_CUSTOMER_ID -> customer_id. Disposition=ignored.",
        }
    ]


def test_canonical_gap_approval_request_uses_fallback_actor() -> None:
    payload = admin_views._canonical_gap_approval_request(
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        {"action": "existing_concept_alias", "concept_id": "customer.id"},
        None,
    )

    assert payload == {
        "candidate": {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        "suggestion": {"action": "existing_concept_alias", "concept_id": "customer.id"},
        "approved_by": "streamlit-admin-debug",
    }