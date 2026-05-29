"""Tests virtual canonical target schema generation for canonical-first target-intent mode."""

from __future__ import annotations

from app.services.virtual_target_service import build_virtual_target_schema, list_supported_target_intents


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


def test_build_virtual_target_schema_supports_sap_profile_aliases() -> None:
    profile = build_virtual_target_schema("sap")

    assert profile.dataset_id == "virtual-target:sap"
    customer_id = next(column for column in profile.columns if column.name == "customer.id")
    assert "kunnr" in customer_id.normalized_name
    assert "kunnr" in customer_id.tokenized_name
    assert "Target intent SAP aliases" in customer_id.description


def test_list_supported_target_intents_returns_canonical_and_system_profiles() -> None:
    options = list_supported_target_intents()

    assert [option.target_system for option in options] == ["canonical", "sap"]
    assert options[1].projection_mode == "target_aware_canonical"