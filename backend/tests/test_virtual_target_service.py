from __future__ import annotations

from app.services.virtual_target_service import build_virtual_target_schema


def test_build_virtual_target_schema_returns_canonical_concepts() -> None:
    profile = build_virtual_target_schema()

    assert profile.dataset_id == "virtual-target:canonical"
    assert profile.dataset_name == "canonical_glossary_erp.csv"
    assert profile.row_count == 0
    assert profile.columns
    assert any(column.name == "customer.id" for column in profile.columns)
    customer_id = next(column for column in profile.columns if column.name == "customer.id")
    assert customer_id.normalized_name
    assert customer_id.tokenized_name
    assert customer_id.detected_patterns == []