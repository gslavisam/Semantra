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
    assert payload["schema_profile"]["columns"][0]["normalized_name"] == "Customer number"
    assert payload["preview_rows"] == []


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


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")