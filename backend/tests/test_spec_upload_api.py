"""API tests for schema-spec upload parsing and validation flows."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()


def test_spec_detect_endpoint_returns_hint_for_spec_file() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                    "NAME1,Customer name,VARCHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] == {
        "name_col": "Column",
        "description_col": "Description",
        "type_col": "Type",
        "sample_values_col": None,
        "confidence": 1.0,
    }


def test_spec_detect_endpoint_returns_no_hint_for_data_file() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.csv",
                csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_upload_endpoint_returns_dataset_handle() -> None:
    response = client.post(
        "/upload/spec",
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                    "ERDAT,Created on,DATE\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"]
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["KUNNR", "ERDAT"]
    assert payload["schema_profile"]["columns"][0]["normalized_name"] == "kunnr"
    assert payload["schema_profile"]["columns"][0]["description"] == "Customer number"
    assert payload["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["preview_rows"] == []


def test_spec_upload_endpoint_accepts_manual_sample_values_column() -> None:
    response = client.post(
        "/upload/spec",
        data={
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
        },
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
                    "AKONT,Reconciliation account,CHAR,160000|170000\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_profile"]["columns"][0]["name"] == "AKONT"
    assert payload["schema_profile"]["columns"][0]["description"] == "Reconciliation account"
    assert payload["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["schema_profile"]["columns"][0]["sample_values"] == ["160000", "170000"]


def test_spec_upload_endpoint_returns_400_for_unknown_name_col() -> None:
    response = client.post(
        "/upload/spec",
        data={"name_col": "MissingColumn"},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown spec name column: MissingColumn"


def test_upload_handle_endpoint_returns_dataset_handle_for_row_data() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"]
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["cust_id", "phone"]
    assert payload["preview_rows"][0]["cust_id"] == "1"


def test_upload_handle_metadata_endpoint_enriches_existing_dataset_handle() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("KUNNR,ERDAT\n1,2024-01-01\n2,2024-01-02\n"),
                "text/csv",
            )
        },
    )

    response = client.post(
        "/upload/handle/metadata",
        data={"dataset_id": upload_response.json()["dataset_id"]},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type,Sample Values\n"
                    "KUNNR,Customer number,CHAR,1000|2000\n"
                    "ERDAT,Created on,DATS,20240101\n"
                    "UNUSED,Unused,CHAR,XX\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_columns"] == 2
    assert payload["unmatched_columns"] == ["UNUSED"]
    assert payload["dataset"]["dataset_id"] == upload_response.json()["dataset_id"]
    assert payload["dataset"]["preview_rows"][0]["KUNNR"] == "1"
    assert payload["dataset"]["schema_profile"]["columns"][0]["description"] == "Customer number"
    assert payload["dataset"]["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["dataset"]["schema_profile"]["columns"][0]["sample_values"] == ["1000", "2000"]


def test_upload_handle_metadata_endpoint_returns_400_when_no_columns_match() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("KUNNR,ERDAT\n1,2024-01-01\n"),
                "text/csv",
            )
        },
    )

    response = client.post(
        "/upload/handle/metadata",
        data={"dataset_id": upload_response.json()["dataset_id"]},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "LAND1,Country,CHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Companion metadata did not match any existing dataset columns."


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")