from __future__ import annotations

from types import SimpleNamespace

from streamlit_ui import catalog_views


def test_build_catalog_reuse_mapping_response_creates_workspace_shape() -> None:
    mapping_response = catalog_views._build_catalog_reuse_mapping_response(
        {
            "name": "customer-master",
            "version": 3,
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id", "customer.name"],
            "unmatched_sources": ["LAND1"],
            "mapping_decisions": [
                {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
                {"source": "NAME1", "target": "customer.name", "status": "accepted"},
                {"source": "LAND1", "target": "", "status": "needs_review"},
            ],
        }
    )

    assert [item["source"] for item in mapping_response["ranked_mappings"]] == ["KUNNR", "NAME1", "LAND1"]
    assert mapping_response["mappings"][0]["canonical_details"]["shared_concepts"][0]["concept_id"] == "customer.id"
    assert mapping_response["canonical_coverage"]["source"]["unmatched_columns"] == ["LAND1"]


def test_apply_mapping_set_detail_to_workspace_sets_editor_state(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._apply_mapping_set_detail_to_workspace(
        {
            "name": "customer-master",
            "version": 2,
            "owner": "governance-team",
            "assignee": "analyst-1",
            "review_note": "Ready for reuse",
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {
                    "source": "KUNNR",
                    "target": "customer.id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["KUNNR"]',
                }
            ],
        }
    )

    assert fake_streamlit.session_state["mapping_response"]["ranked_mappings"][0]["source"] == "KUNNR"
    assert fake_streamlit.session_state["mapping_editor_state"]["KUNNR"]["target"] == "customer.id"
    assert fake_streamlit.session_state["manual_transform_KUNNR"] == 'df_target["customer_id"] = df_source["KUNNR"]'
    assert fake_streamlit.session_state["mapping_set_owner"] == "governance-team"


def test_mapping_set_reuse_block_reason_requires_approved_status() -> None:
    assert catalog_views._mapping_set_reuse_block_reason("approved") == ""
    assert (
        catalog_views._mapping_set_reuse_block_reason("review")
        == "Only approved mapping set versions can be reused in Workspace. Current status: review."
    )