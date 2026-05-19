"""API tests for canonical-only mapping and related governance behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.knowledge import SourceFieldHintRecord
from app.models.mapping import AutoMappingResponse, MappingCandidate, SourceMappingResult
from app.services.llm_service import StaticLLMProvider
from app.services.persistence_service import persistence_service
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()
    persistence_service.clear_source_field_hints()


def test_canonical_mapping_endpoint_maps_source_to_canonical_concept() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("sold_to_party\nC001\nC002\n"),
                "text/csv",
            )
        },
    )
    assert upload_response.status_code == 200

    response = client.post(
        "/mapping/canonical",
        json={"source_dataset_id": upload_response.json()["dataset_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mappings"]
    assert payload["mappings"][0]["source"] == "sold_to_party"
    assert payload["mappings"][0]["target"] == "customer.id"
    assert payload["mappings"][0]["canonical_details"]["shared_concepts"][0]["concept_id"] == "customer.id"
    assert payload["canonical_coverage"]["source"]["matched_columns"] == 1
    assert payload["canonical_coverage"]["target"]["matched_columns"] > 0


def test_canonical_mapping_endpoint_returns_404_for_unknown_source_dataset() -> None:
    response = client.post(
        "/mapping/canonical",
        json={"source_dataset_id": "missing-dataset-id"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "'Unknown dataset_id: missing-dataset-id'"


def test_canonical_mapping_endpoint_land1_resolves_correctly_via_knowledge_bridge() -> None:
    fixture_path = Path(__file__).parents[2] / "ui_fixtures" / "source_schema_spec.csv"
    upload_response = client.post(
        "/upload/spec",
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "text/csv",
            )
        },
    )
    assert upload_response.status_code == 200

    # LLM is present but LAND1 should now be resolved confidently via the KC→CC bridge
    # (bridge maps KC "country" → CC "address.country"), so LLM validator is NOT needed.
    provider = StaticLLMProvider(
        '{"selected_target":"no_match","confidence":0.92,"reasoning":["LLM says no_match for everything"]}'
    )
    with patch("app.api.routes.mapping.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/mapping/canonical",
            json={"source_dataset_id": upload_response.json()["dataset_id"]},
        )

    assert response.status_code == 200
    payload = response.json()
    land1 = next(item for item in payload["mappings"] if item["source"] == "LAND1")
    # LAND1 now reaches an address canonical concept via the KC→CC alias bridge,
    # so it should have a definitive match (not LLM-rejected null).
    assert land1["target"] is not None
    assert land1["method"] != "llm_validator_no_match"


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def test_canonical_mapping_endpoint_applies_persistent_source_field_hint() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("tipOpe\nSALE\nRETURN\n"),
                "text/csv",
            )
        },
    )
    assert upload_response.status_code == 200

    save_hint_response = client.post(
        "/mapping/source-field-hints",
        json={
            "source_system": "Senior HR",
            "business_domain": "HR",
            "source_field": "tipOpe",
            "meaning_hint": "Operation type / transaction type",
            "negative_hint": "Not contact name",
            "sample_values": ["SALE", "RETURN", "STORNO"],
        },
    )
    assert save_hint_response.status_code == 200

    list_response = client.get(
        "/mapping/source-field-hints",
        params={"source_system": "Senior HR", "business_domain": "HR"},
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["source_field"] == "tipOpe"

    captured: dict[str, object] = {}

    def fake_apply_source_field_hints(source_schema, **kwargs):
        captured["hint_scope"] = kwargs
        enriched_schema = source_schema.model_copy(
            update={
                "columns": [
                    source_schema.columns[0].model_copy(
                        update={
                            "description": "Persistent field hint: Operation type / transaction type Not: Not contact name",
                            "sample_values": ["SALE", "RETURN", "STORNO"],
                            "distinct_sample_values": ["SALE", "RETURN", "STORNO"],
                        }
                    )
                ]
            }
        )
        return enriched_schema, [
            SourceFieldHintRecord(
                source_system="Senior HR",
                business_domain="HR",
                source_field="tipOpe",
                meaning_hint="Operation type / transaction type",
                negative_hint="Not contact name",
                sample_values=["SALE", "RETURN", "STORNO"],
            )
        ]

    def fake_generate_mapping_candidates(source_schema, target_schema, **kwargs):
        captured["source_description"] = source_schema.columns[0].description
        captured["source_sample_values"] = list(source_schema.columns[0].sample_values)
        captured["description_priority"] = kwargs.get("description_priority")
        return AutoMappingResponse()

    with patch("app.api.routes.mapping.apply_source_field_hints", side_effect=fake_apply_source_field_hints):
        with patch("app.api.routes.mapping.generate_mapping_candidates", side_effect=fake_generate_mapping_candidates):
            response = client.post(
                "/mapping/canonical",
                json={
                    "source_dataset_id": upload_response.json()["dataset_id"],
                    "source_system": "Senior HR",
                    "business_domain": "HR",
                    "candidate_pool_size": 5,
                },
            )

    assert response.status_code == 200
    assert captured["hint_scope"] == {
        "source_system": "Senior HR",
        "business_domain": "HR",
        "integration_name": None,
    }
    assert "Persistent field hint: Operation type / transaction type" in str(captured["source_description"])
    assert "STORNO" in list(captured["source_sample_values"])
    assert captured["description_priority"] is True


def test_mapping_refine_endpoint_uses_transient_manual_hints_and_closed_candidate_set() -> None:
    source_upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("tipOpe\nSALE\nRETURN\n"),
                "text/csv",
            )
        },
    )
    assert source_upload_response.status_code == 200

    target_upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "target.csv",
                csv_bytes("employee_type,employee_name\nSALE,Ana\nRETURN,Marko\n"),
                "text/csv",
            )
        },
    )
    assert target_upload_response.status_code == 200

    captured: dict[str, object] = {}

    def fake_refine_mapping_for_source(source_column, target_columns, **kwargs):
        captured["source_description"] = source_column.description
        captured["source_sample_values"] = list(source_column.sample_values)
        captured["candidate_target_names"] = kwargs.get("candidate_target_names")
        captured["description_priority"] = kwargs.get("description_priority")
        return SourceMappingResult(
            source=source_column.name,
            selected=MappingCandidate(
                source=source_column.name,
                target="employee_type",
                confidence=0.88,
                confidence_label="high_confidence",
                status="needs_review",
                method="llm_validated",
                signals={"llm": 0.88},
                explanation=["LLM validator re-ranked this candidate within the closed candidate set."],
                llm_consulted=True,
                llm_recommendation={
                    "selected_target": "employee_type",
                    "confidence": 0.88,
                    "reasoning": ["Business meaning points to operation type."],
                },
            ),
            candidates=[],
        )

    with patch("app.api.routes.mapping.refine_mapping_for_source", side_effect=fake_refine_mapping_for_source):
        response = client.post(
            "/mapping/refine",
            json={
                "source_dataset_id": source_upload_response.json()["dataset_id"],
                "target_dataset_id": target_upload_response.json()["dataset_id"],
                "source_field": "tipOpe",
                "candidate_targets": ["employee_type"],
                "meaning_hint": "Operation type / transaction type",
                "negative_hint": "Not employee name",
                "sample_values": ["SALE", "RETURN", "STORNO"],
                "refinement_instruction": "Prefer operation type semantics over person-related fields.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "tipOpe"
    assert payload["selected"]["target"] == "employee_type"
    assert "Persistent field hint: Operation type / transaction type" in str(captured["source_description"])
    assert "Not: Not employee name" in str(captured["source_description"])
    assert "LLM refinement instruction: Prefer operation type semantics over person-related fields." in str(captured["source_description"])
    assert "STORNO" in list(captured["source_sample_values"])
    assert captured["candidate_target_names"] == ["employee_type"]
    assert captured["description_priority"] is True


def test_mapping_target_fields_endpoint_returns_virtual_canonical_targets() -> None:
    response = client.get(
        "/mapping/target-fields",
        params={"target_system": "canonical"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert "customer.id" in payload


def test_codegen_endpoint_allows_needs_review_when_explicitly_enabled() -> None:
    response = client.post(
        "/mapping/codegen",
        json={
            "mapping_decisions": [
                {"source": "matnr", "target": "material.number", "status": "needs_review"}
            ],
            "mode": "pandas",
            "allow_unaccepted": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "python-pandas"
    assert "material.number" in payload["code"]