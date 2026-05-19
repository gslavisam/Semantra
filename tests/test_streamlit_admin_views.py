"""Tests admin and Canonical Console Streamlit helper behavior."""

from __future__ import annotations

from unittest.mock import patch

from streamlit_ui import admin_views


def test_section_label_appends_detail_only_when_present() -> None:
    assert admin_views._section_label("Overlay Summary", "customer-overlay") == "Overlay Summary · customer-overlay"
    assert admin_views._section_label("Canonical Glossary", "") == "Canonical Glossary"


def test_filter_canonical_concepts_matches_alias_and_display_name() -> None:
    concepts = [
        {
            "concept_id": "customer.id",
            "display_name": "Customer ID",
            "description": "Primary customer identifier",
            "entity": "customer",
            "attribute": "id",
            "source": "base_plus_active_overlay",
            "source_systems": ["SAP"],
            "business_domains": ["Customer"],
            "base_aliases": ["customer_id", "cust_id"],
            "active_overlay_aliases": ["legacy_customer_identifier"],
        },
        {
            "concept_id": "customer.phone",
            "display_name": "Customer Phone",
            "source_systems": ["CRM"],
            "business_domains": ["Customer"],
            "base_aliases": ["phone_number"],
            "active_overlay_aliases": [],
        },
    ]

    filtered = admin_views._filter_canonical_concepts(concepts, "legacy_customer")
    assert [item["concept_id"] for item in filtered] == ["customer.id"]

    filtered_by_name = admin_views._filter_canonical_concepts(concepts, "phone")
    assert [item["concept_id"] for item in filtered_by_name] == ["customer.phone"]

    filtered_by_source_system = admin_views._filter_canonical_concepts(concepts, "sap")
    assert [item["concept_id"] for item in filtered_by_source_system] == ["customer.id"]


def test_overlay_activation_block_reason_requires_validated_status() -> None:
    assert admin_views._overlay_activation_block_reason({"status": "validated"}) == ""
    assert admin_views._overlay_activation_block_reason({"status": "archived"}) == (
        "Only validated knowledge overlays can be activated. Current status: archived."
    )
    assert admin_views._overlay_activation_block_reason({"status": "active"}) == (
        "This knowledge overlay is already active."
    )


def test_overlay_archive_block_reason_requires_active_or_validated_status() -> None:
    assert admin_views._overlay_archive_block_reason({"status": "validated"}) == ""
    assert admin_views._overlay_archive_block_reason({"status": "active"}) == ""
    assert admin_views._overlay_archive_block_reason({"status": "archived"}) == "This knowledge overlay is already archived."


def test_bootstrap_canonical_console_state_loads_core_console_data() -> None:
    session_state: dict[str, object] = {}
    calls: list[tuple[str, str]] = []

    def fake_api_request(method: str, path: str):
        calls.append((method, path))
        responses = {
            ("POST", "/knowledge/reload"): {"mode": "overlay_active", "active_overlay_id": 1},
            ("GET", "/knowledge/overlays"): [{"overlay_id": 1, "name": "customer-overlay", "status": "active"}],
            ("GET", "/knowledge/audit"): [{"action": "stewardship"}],
            ("GET", "/knowledge/stewardship-items"): [{"item_type": "overlay_promotion", "item_key": "overlay_promotion_1_2", "status": "new"}],
            ("GET", "/knowledge/overlays/1"): {
                "version": {"overlay_id": 1, "name": "customer-overlay", "status": "active"},
                "entries": [],
            },
            ("GET", "/knowledge/canonical-concepts"): [{"concept_id": "customer.id"}],
        }
        return responses[(method, path)]

    with patch.object(admin_views.st, "session_state", session_state):
        admin_views._bootstrap_canonical_console_state(api_request=fake_api_request)

    assert session_state["debug_knowledge_runtime"] == {"mode": "overlay_active", "active_overlay_id": 1}
    assert session_state["debug_knowledge_overlays"] == [{"overlay_id": 1, "name": "customer-overlay", "status": "active"}]
    assert session_state["debug_knowledge_audit_logs"] == [{"action": "stewardship"}]
    assert session_state["debug_knowledge_stewardship_items"] == [
        {"item_type": "overlay_promotion", "item_key": "overlay_promotion_1_2", "status": "new"}
    ]
    assert session_state["debug_selected_overlay_version"] == "#1 | customer-overlay | active"
    assert session_state["debug_selected_knowledge_overlay"] == {
        "version": {"overlay_id": 1, "name": "customer-overlay", "status": "active"},
        "entries": [],
    }
    assert session_state["debug_canonical_concepts"] == [{"concept_id": "customer.id"}]
    assert session_state["debug_canonical_console_bootstrapped"] is True
    assert calls == [
        ("POST", "/knowledge/reload"),
        ("GET", "/knowledge/overlays"),
        ("GET", "/knowledge/audit"),
        ("GET", "/knowledge/stewardship-items"),
        ("GET", "/knowledge/overlays/1"),
        ("GET", "/knowledge/canonical-concepts"),
    ]


def test_bootstrap_canonical_console_state_respects_manual_clear() -> None:
    session_state: dict[str, object] = {"debug_canonical_console_manual_clear": True}

    with patch.object(admin_views.st, "session_state", session_state):
        admin_views._bootstrap_canonical_console_state(api_request=lambda method, path: None)

    assert session_state == {"debug_canonical_console_manual_clear": True}


def test_ensure_canonical_concept_detail_loaded_fetches_missing_detail() -> None:
    session_state: dict[str, object] = {}
    calls: list[tuple[str, str]] = []

    def fake_api_request(method: str, path: str):
        calls.append((method, path))
        return {"concept": {"concept_id": "customer.id", "display_name": "Customer ID"}}

    with patch.object(admin_views.st, "session_state", session_state):
        changed = admin_views._ensure_canonical_concept_detail_loaded(
            api_request=fake_api_request,
            selected_concept_id="customer.id",
        )

    assert changed is True
    assert session_state["debug_canonical_concept_detail"] == {
        "concept": {"concept_id": "customer.id", "display_name": "Customer ID"}
    }
    assert calls == [("GET", "/knowledge/canonical-concepts/customer.id")]


def test_ensure_canonical_concept_detail_loaded_skips_matching_detail() -> None:
    session_state: dict[str, object] = {
        "debug_canonical_concept_detail": {"concept": {"concept_id": "customer.id", "display_name": "Customer ID"}}
    }

    with patch.object(admin_views.st, "session_state", session_state):
        changed = admin_views._ensure_canonical_concept_detail_loaded(
            api_request=lambda method, path: None,
            selected_concept_id="customer.id",
        )

    assert changed is False
    assert session_state["debug_canonical_concept_detail"] == {
        "concept": {"concept_id": "customer.id", "display_name": "Customer ID"}
    }


def test_preferred_canonical_concept_label_prefers_active_overlay_promotion_concept() -> None:
    concepts = [
        {
            "concept_id": "absence.balance",
            "display_name": "Absence Balance",
            "source": "base",
            "usage_count": 0,
            "active_overlay_entry_count": 0,
        },
        {
            "concept_id": "customer.shadow_id",
            "display_name": "Customer Shadow ID",
            "source": "overlay_only",
            "usage_count": 0,
            "active_overlay_entry_count": 1,
        },
    ]
    records = [
        {
            "item_type": "overlay_promotion",
            "concept_id": "customer.shadow_id",
            "status": "promoted",
            "overlay_entry_payload": {"overlay_id": 283},
        }
    ]

    preferred = admin_views._preferred_canonical_concept_label(
        concepts,
        records,
        active_overlay_id=283,
        current_label=None,
    )

    assert preferred == "customer.shadow_id | Customer Shadow ID | source=overlay_only | usage=0"


def test_preferred_canonical_concept_label_preserves_valid_current_selection() -> None:
    concepts = [
        {
            "concept_id": "absence.balance",
            "display_name": "Absence Balance",
            "source": "base",
            "usage_count": 0,
            "active_overlay_entry_count": 0,
        },
        {
            "concept_id": "customer.shadow_id",
            "display_name": "Customer Shadow ID",
            "source": "overlay_only",
            "usage_count": 0,
            "active_overlay_entry_count": 1,
        },
    ]

    preferred = admin_views._preferred_canonical_concept_label(
        concepts,
        [],
        active_overlay_id=283,
        current_label="absence.balance | Absence Balance | source=base | usage=0",
    )

    assert preferred == "absence.balance | Absence Balance | source=base | usage=0"


def test_canonical_console_action_label_reflects_loaded_state() -> None:
    assert admin_views._canonical_console_action_label(False, "canonical concept registry") == "Load canonical concept registry"
    assert admin_views._canonical_console_action_label(True, "canonical concept registry") == "Refresh canonical concept registry"


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
                "source_systems": ["SAP", "CRM"],
                "business_domains": ["Customer"],
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
            "source_systems": "SAP, CRM",
            "business_domains": "Customer",
            "base_aliases": "customer_id, cust_id",
            "active_overlay_aliases": "legacy_customer_identifier",
        }
    ]


def test_filter_canonical_concepts_by_scope_matches_source_system_and_business_domain() -> None:
    concepts = [
        {
            "concept_id": "customer.id",
            "source_systems": ["SAP", "CRM"],
            "business_domains": ["Customer"],
        },
        {
            "concept_id": "vendor.id",
            "source_systems": ["SAP"],
            "business_domains": ["Vendor"],
        },
        {
            "concept_id": "material.id",
            "source_systems": ["MES"],
            "business_domains": ["Manufacturing"],
        },
    ]

    assert [
        item["concept_id"]
        for item in admin_views._filter_canonical_concepts_by_scope(concepts, "SAP", None)
    ] == ["customer.id", "vendor.id"]
    assert [
        item["concept_id"]
        for item in admin_views._filter_canonical_concepts_by_scope(concepts, None, "Customer")
    ] == ["customer.id"]
    assert [
        item["concept_id"]
        for item in admin_views._filter_canonical_concepts_by_scope(concepts, "SAP", "Vendor")
    ] == ["vendor.id"]


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
            "runtime_source": "sqlite_cache",
            "source_hash_state": "current",
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
        "runtime_source": "sqlite_cache",
        "source_hash_state": "current",
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
        "canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {
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
        {"canonical_gap_LEGACY_CUSTOMER_ID_customer_id": "ignored"},
        {"canonical_gap_LEGACY_CUSTOMER_ID_customer_id": "needs_review"},
        None,
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
            "proposal_state": "needs_review",
            "stewardship_status": "ignored",
            "owner": "",
            "assignee": "",
        }
    ]
def test_overlay_promotion_item_map_filters_overlay_items() -> None:
    assert admin_views._overlay_promotion_item_map(
        [
            {"item_type": "overlay_promotion", "item_key": "overlay_promotion_2_10", "status": "new"},
            {"item_type": "canonical_gap", "item_key": "canonical_gap_A_B", "status": "needs_review"},
        ]
    ) == {
        "overlay_promotion_2_10": {"item_type": "overlay_promotion", "item_key": "overlay_promotion_2_10", "status": "new"}
    }


def test_overlay_promotion_entry_rows_merge_status_and_assignment() -> None:
    rows = admin_views._overlay_promotion_entry_rows(
        [
            {
                "entry_id": 10,
                "version_id": 2,
                "entry_type": "concept_alias",
                "canonical_term": "Customer ID",
                "canonical_concept_id": "customer.id",
                "alias": "legacy_customer_identifier",
                "source_system": "LegacyERP",
            }
        ],
        {
            "overlay_promotion_2_10": {
                "item_id": 5,
                "item_type": "overlay_promotion",
                "item_key": "overlay_promotion_2_10",
                "status": "ready_for_approval",
                "owner": "master-data-governance",
                "assignee": "canonical-model-owner",
                "review_note": "Looks stable across integrations.",
            }
        },
    )

    assert rows == [
        {
            "alias": "legacy_customer_identifier",
            "canonical_term": "Customer ID",
            "canonical_concept_id": "customer.id",
            "source_system": "LegacyERP",
            "promotion_status": "ready_for_approval",
            "owner": "master-data-governance",
            "assignee": "canonical-model-owner",
            "review_note": "Looks stable across integrations.",
        }
    ]


def test_overlay_promotion_item_request_builds_stewardship_payload() -> None:
    payload = admin_views._overlay_promotion_item_request(
        {
            "entry_id": 10,
            "version_id": 2,
            "entry_type": "concept_alias",
            "canonical_term": "Customer ID",
            "canonical_concept_id": "customer.id",
            "alias": "legacy_customer_identifier",
            "domain": "master_data",
            "source_system": "LegacyERP",
            "note": "Candidate for promotion",
        },
        {"overlay_id": 2, "name": "overlay-v2", "status": "active"},
        status="new",
        owner="master-data-governance",
        assignee="canonical-model-owner",
        review_note="Stable alias across current integrations.",
        changed_by="reviewer-1",
    )

    assert payload == {
        "item_type": "overlay_promotion",
        "item_key": "overlay_promotion_2_10",
        "title": "Promote overlay alias 'legacy_customer_identifier'",
        "status": "new",
        "concept_id": "customer.id",
        "source": "legacy_customer_identifier",
        "target": "customer.id",
        "source_system": "LegacyERP",
        "business_domain": "master_data",
        "owner": "master-data-governance",
        "assignee": "canonical-model-owner",
        "review_note": "Stable alias across current integrations.",
        "overlay_entry_payload": {
            "entry_id": 10,
            "version_id": 2,
            "entry_type": "concept_alias",
            "canonical_term": "Customer ID",
            "canonical_concept_id": "customer.id",
            "alias": "legacy_customer_identifier",
            "domain": "master_data",
            "source_system": "LegacyERP",
            "note": "Candidate for promotion",
            "overlay_id": 2,
            "overlay_name": "overlay-v2",
            "overlay_status": "active",
        },
        "created_by": "reviewer-1",
        "changed_by": "reviewer-1",
    }


def test_overlay_promotion_can_execute_requires_saved_ready_item() -> None:
    assert admin_views._overlay_promotion_can_execute({"item_id": 5, "status": "ready_for_approval"}) is True
    assert admin_views._overlay_promotion_can_execute({"item_id": 5, "status": "new"}) is False
    assert admin_views._overlay_promotion_can_execute({"status": "ready_for_approval"}) is False
    assert admin_views._overlay_promotion_can_execute({"item_id": 5, "status": "promoted"}) is False


def test_overlay_promotion_execution_request_uses_actor_and_optional_note() -> None:
    assert admin_views._overlay_promotion_execution_request(" reviewer-1 ", " Promote via console. ") == {
        "changed_by": "reviewer-1",
        "note": "Promote via console.",
    }
    assert admin_views._overlay_promotion_execution_request(None) == {"changed_by": None}


def test_overlay_promotion_rows_for_concept_filter_matching_items() -> None:
    concept = {"concept_id": "customer.id"}
    rows = admin_views._overlay_promotion_rows_for_concept(
        concept,
        [
            {
                "item_id": 11,
                "item_type": "overlay_promotion",
                "concept_id": "customer.id",
                "source": "legacy_customer_identifier",
                "status": "ready_for_approval",
                "source_system": "LegacyERP",
                "business_domain": "master_data",
                "owner": "data-governance",
                "assignee": "analyst-1",
                "review_note": "Stable alias.",
            },
            {
                "item_id": 12,
                "item_type": "overlay_promotion",
                "concept_id": "material.id",
                "source": "material_number",
                "status": "new",
            },
            {
                "item_id": 13,
                "item_type": "canonical_gap",
                "concept_id": "customer.id",
                "source": "KUNNR",
                "status": "ready_for_approval",
            },
        ],
    )

    assert rows == [
        {
            "alias": "legacy_customer_identifier",
            "status": "ready_for_approval",
            "source_system": "LegacyERP",
            "business_domain": "master_data",
            "owner": "data-governance",
            "assignee": "analyst-1",
            "review_note": "Stable alias.",
        }
    ]


def test_overlay_promotion_rows_for_concept_returns_empty_without_concept_id() -> None:
    assert admin_views._overlay_promotion_rows_for_concept({}, [{"item_type": "overlay_promotion", "concept_id": "customer.id"}]) == []


def test_canonical_gap_console_state_defaults_to_active() -> None:
    assert admin_views._canonical_gap_console_state("canonical_gap_X_Y", None) == "active"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_X_Y",
        {"canonical_gap_X_Y": "ignored"},
    ) == "ignored"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_X_Y",
        {"canonical_gap_X_Y": "approved"},
    ) == "approved"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_X_Y",
        {"canonical_gap_X_Y": "rejected"},
    ) == "rejected"
    assert admin_views._canonical_gap_console_state(
        "canonical_gap_X_Y",
        {"canonical_gap_X_Y": "weird"},
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


def test_canonical_gap_impact_preview_rows_identifies_selected_and_related_queue_rows() -> None:
    candidates = [
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id", "confidence": 0.91},
        {"source": "legacy_customer_id", "target": "customer_id", "confidence": 0.87},
        {"source": "KUNNR", "target": "customer_id", "confidence": 0.82},
        {"source": "LEGACY_CUSTOMER_ID", "target": "account_id", "confidence": 0.63},
    ]
    suggestions = {
        "canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
            "aliases": ["legacy_customer_id"],
        },
        "canonical_gap_legacy_customer_id_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
        },
        "canonical_gap_KUNNR_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
        },
    }

    rows = admin_views._canonical_gap_impact_preview_rows(
        0,
        candidates[0],
        suggestions["canonical_gap_LEGACY_CUSTOMER_ID_customer_id"],
        candidates,
        suggestions,
        {"canonical_gap_KUNNR_customer_id": "ignored"},
    )

    assert rows == [
        {
            "source": "LEGACY_CUSTOMER_ID",
            "target": "customer_id",
            "confidence_pct": 91,
            "console_state": "active",
            "impact_reason": "selected gap under review",
        },
        {
            "source": "legacy_customer_id",
            "target": "customer_id",
            "confidence_pct": 87,
            "console_state": "active",
            "impact_reason": "same source column | same target field | same suggested concept",
        },
        {
            "source": "KUNNR",
            "target": "customer_id",
            "confidence_pct": 82,
            "console_state": "ignored",
            "impact_reason": "same target field | same suggested concept",
        },
        {
            "source": "LEGACY_CUSTOMER_ID",
            "target": "account_id",
            "confidence_pct": 63,
            "console_state": "active",
            "impact_reason": "same source column",
        },
    ]


def test_canonical_gap_repeat_summary_rows_aggregates_current_and_durable_gap_patterns() -> None:
    candidates = [
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        {"source": "legacy_customer_id", "target": "customer_id"},
        {"source": "KUNNR", "target": "customer_id"},
    ]
    suggestions = {
        "canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {"concept_id": "customer.id"},
        "canonical_gap_legacy_customer_id_customer_id": {"concept_id": "customer.id"},
    }
    stewardship_items = admin_views._canonical_gap_stewardship_item_map(
        [
            {
                "item_type": "canonical_gap",
                "item_key": "canonical_gap_LEGACY_CUSTOMER_ID_customer_id",
                "source": "LEGACY_CUSTOMER_ID",
                "target": "customer_id",
                "concept_id": "customer.id",
                "status": "ready_for_approval",
                "updated_at": "2026-05-10T10:00:00Z",
            },
            {
                "item_type": "canonical_gap",
                "item_key": "canonical_gap_legacy_customer_id_customer_id",
                "source": "legacy_customer_id",
                "target": "customer_id",
                "concept_id": "customer.id",
                "status": "needs_review",
                "updated_at": "2026-05-10T11:00:00Z",
            },
            {
                "item_type": "canonical_gap",
                "item_key": "canonical_gap_KUNNR_customer_id",
                "source": "KUNNR",
                "target": "customer_id",
                "concept_id": "customer.id",
                "status": "ignored",
                "updated_at": "2026-05-10T12:00:00Z",
            },
        ]
    )

    rows = admin_views._canonical_gap_repeat_summary_rows(
        candidates,
        suggestions,
        {},
        {},
        stewardship_items,
    )

    assert rows == [
        {
            "target": "customer_id",
            "suggested_concept_id": "customer.id",
            "observations": 3,
            "distinct_source_count": 2,
            "current_queue_count": 3,
            "ready_for_approval": 1,
            "needs_review": 1,
            "new": 0,
            "ignored": 1,
            "rejected": 0,
            "approved": 0,
            "promoted": 0,
            "source_examples": "LEGACY_CUSTOMER_ID, KUNNR",
            "latest_observed_at": "2026-05-10T12:00:00Z",
        }
    ]


def test_canonical_gap_impact_preview_rows_skips_no_action_suggestions() -> None:
    rows = admin_views._canonical_gap_impact_preview_rows(
        0,
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id"},
        {"action": "no_action"},
        [{"source": "LEGACY_CUSTOMER_ID", "target": "customer_id", "confidence": 0.91}],
    )

    assert rows == []


def test_canonical_gap_pending_rows_for_concept_filters_active_alias_proposals() -> None:
    concept = {"concept_id": "customer.id"}
    candidates = [
        {"source": "LEGACY_CUSTOMER_ID", "target": "customer_id", "confidence": 0.91},
        {"source": "KUNNR", "target": "customer_id", "confidence": 0.82},
        {"source": "MATERIAL_NUMBER", "target": "material_id", "confidence": 0.88},
    ]
    suggestions = {
        "canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
            "aliases": ["legacy_customer_id"],
            "reasoning": ["Alias matches customer identifier semantics."],
            "risk_notes": ["Check duplicate account concepts."],
        },
        "canonical_gap_KUNNR_customer_id": {
            "action": "existing_concept_alias",
            "concept_id": "customer.id",
            "aliases": ["kunnr"],
        },
        "canonical_gap_MATERIAL_NUMBER_material_id": {
            "action": "new_canonical_concept",
            "concept_id": "material.id",
            "aliases": ["material_number"],
        },
    }

    rows = admin_views._canonical_gap_pending_rows_for_concept(
        concept,
        candidates,
        suggestions,
        {"canonical_gap_KUNNR_customer_id": "ignored"},
        {"canonical_gap_LEGACY_CUSTOMER_ID_customer_id": "ready_for_approval"},
        {
            "canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {
                "item_id": 3,
                "item_type": "canonical_gap",
                "item_key": "canonical_gap_LEGACY_CUSTOMER_ID_customer_id",
                "status": "ready_for_approval",
            }
        },
    )

    assert rows == [
        {
            "source": "LEGACY_CUSTOMER_ID",
            "target": "customer_id",
            "confidence_pct": 91,
            "suggested_action": "existing_concept_alias",
            "proposal_state": "ready_for_approval",
            "aliases": "legacy_customer_id",
            "reasoning": "Alias matches customer identifier semantics.",
            "risk_notes": "Check duplicate account concepts.",
        }
    ]


def test_canonical_gap_pending_rows_for_concept_returns_empty_without_concept_id() -> None:
    rows = admin_views._canonical_gap_pending_rows_for_concept(
        {},
        [{"source": "LEGACY_CUSTOMER_ID", "target": "customer_id", "confidence": 0.91}],
        {"canonical_gap_LEGACY_CUSTOMER_ID_customer_id": {"action": "existing_concept_alias", "concept_id": "customer.id"}},
    )

    assert rows == []