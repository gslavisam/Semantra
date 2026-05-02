from app.services.knowledge_overlay_service import knowledge_overlay_validation_service


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def test_validate_csv_payload_returns_normalized_valid_preview() -> None:
    result = knowledge_overlay_validation_service.validate_csv_payload(
        csv_bytes(
            "entry_type,canonical_term,alias,domain,source_system,note\n"
            "field_alias,customer id,KUNNR,master_data,SAP,Customer number\n"
            "abbreviation,customer,cust,general,,Common abbreviation\n"
        ),
        filename="knowledge_overlay.csv",
    )

    assert result.total_rows == 2
    assert result.valid_rows == 2
    assert result.invalid_rows == 0
    assert result.duplicate_rows == 0
    assert result.conflicts == 0
    assert result.normalized_preview[0].normalized_canonical_term == "customer id"
    assert result.normalized_preview[0].normalized_alias == "kunnr"
    assert result.normalized_preview[0].status == "valid"


def test_validate_csv_payload_marks_duplicates_and_missing_fields() -> None:
    result = knowledge_overlay_validation_service.validate_csv_payload(
        csv_bytes(
            "entry_type,canonical_term,alias,domain,source_system,note\n"
            "abbreviation,customer,cust,general,,Common abbreviation\n"
            "abbreviation,customer,cust,general,,Duplicate abbreviation\n"
            "synonym,,buyer,sales,,Missing canonical\n"
        ),
        filename="knowledge_overlay.csv",
    )

    assert result.total_rows == 3
    assert result.valid_rows == 1
    assert result.invalid_rows == 2
    assert result.duplicate_rows == 1
    duplicate_row = result.normalized_preview[1]
    missing_row = result.normalized_preview[2]
    assert any(issue.code == "duplicate_upload_entry" for issue in duplicate_row.issues)
    assert any(issue.code == "missing_canonical_term" for issue in missing_row.issues)


def test_validate_csv_payload_reports_conflict_against_base_dictionary() -> None:
    result = knowledge_overlay_validation_service.validate_csv_payload(
        csv_bytes(
            "entry_type,canonical_term,alias,domain,source_system,note\n"
            "field_alias,vendor id,KUNNR,master_data,SAP,Intentional conflict with base knowledge\n"
        ),
        filename="knowledge_overlay.csv",
    )

    assert result.total_rows == 1
    assert result.valid_rows == 1
    assert result.invalid_rows == 0
    assert result.conflicts == 1
    assert any(issue.code == "conflict_existing_alias" for issue in result.normalized_preview[0].issues)