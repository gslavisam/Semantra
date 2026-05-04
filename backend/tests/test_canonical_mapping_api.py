from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import StaticLLMProvider
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()


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


def test_canonical_mapping_endpoint_can_use_llm_for_low_confidence_semantic_only_case() -> None:
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

    provider = StaticLLMProvider(
        '{"selected_target":"no_match","confidence":0.92,"reasoning":["LAND1 is a country key and the closed candidate set does not contain a reliable country concept match."]}'
    )
    with patch("app.api.routes.mapping.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/mapping/canonical",
            json={"source_dataset_id": upload_response.json()["dataset_id"]},
        )

    assert response.status_code == 200
    payload = response.json()
    land1 = next(item for item in payload["mappings"] if item["source"] == "LAND1")
    assert land1["method"] == "llm_validator_no_match"
    assert land1["target"] is None
    assert any("LLM validator rejected the available candidates" in line for line in land1["explanation"])


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")