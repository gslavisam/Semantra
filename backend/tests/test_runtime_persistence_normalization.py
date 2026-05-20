"""Focused tests for canonical runtime sync and normalized governance/discovery repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.models.knowledge import KnowledgeStewardshipItemCreateRequest
import app.services.metadata_knowledge_service as metadata_knowledge_service_module
from app.services.catalog_repository import CatalogRepository
from app.services.knowledge_runtime_repository import KnowledgeRuntimeRepository
from app.services.mapping_governance_repository import MappingGovernanceRepository
from app.services.persistence_service import SQLitePersistenceService
from app.services.stewardship_repository import StewardshipRepository


def test_canonical_authoring_sync_updates_only_canonical_runtime_snapshot(tmp_path, monkeypatch) -> None:
    persistence = SQLitePersistenceService(str(tmp_path / "runtime.sqlite3"))
    runtime_repository = KnowledgeRuntimeRepository(storage=persistence)
    monkeypatch.setattr(metadata_knowledge_service_module, "knowledge_runtime_repository", runtime_repository)

    service = metadata_knowledge_service_module.MetadataKnowledgeService()
    service.canonical_glossary_path = tmp_path / "canonical_glossary.csv"
    knowledge_before, _canonical_before, _contexts_before = runtime_repository.load_runtime_snapshot()

    import_payload = (
        "concept_id,entity,attribute,display_name,description,data_type,aliases\n"
        'loyalty.id,loyalty,id,Loyalty ID,Identifier for a loyalty profile,string,"loyalty id, loyalty identifier"\n'
    ).encode("utf-8")

    with patch.object(
        runtime_repository,
        "replace_runtime_snapshot",
        side_effect=AssertionError("full runtime replace should not run"),
    ), patch.object(runtime_repository, "sync_canonical_runtime", wraps=runtime_repository.sync_canonical_runtime) as sync_spy, patch.object(
        service,
        "_load",
        side_effect=AssertionError("full metadata reseed should not run"),
    ):
        response = service.import_canonical_glossary_csv(import_payload, filename="canonical_glossary.csv")

    knowledge_after, canonical_after, _contexts_after = runtime_repository.load_runtime_snapshot()

    assert response.imported_row_count == 1
    assert service.runtime_source == "canonical_authoring_sync"
    assert sync_spy.called is True
    assert len(knowledge_after) == len(knowledge_before)
    assert any(row["concept_id"] == "loyalty.id" for row in canonical_after)


def test_stewardship_repository_filters_normalized_queue_rows(tmp_path) -> None:
    persistence = SQLitePersistenceService(str(tmp_path / "stewardship.sqlite3"))
    repository = StewardshipRepository(storage=persistence)

    repository.upsert_item(
        KnowledgeStewardshipItemCreateRequest(
            item_type="canonical_gap",
            item_key="canonical_gap_customer_id_customer.id",
            title="customer_id -> customer.id",
            status="ready_for_approval",
            concept_id="customer.id",
            source="customer_id",
            target="customer.id",
            owner="governance",
            assignee="steward-1",
            created_by="tester",
            changed_by="tester",
        )
    )
    repository.upsert_item(
        KnowledgeStewardshipItemCreateRequest(
            item_type="overlay_promotion",
            item_key="overlay_promotion_1_1",
            title="legacy_customer_identifier",
            status="new",
            concept_id="customer.id",
            source="legacy_customer_identifier",
            target="customer.id",
            owner="governance",
            assignee="steward-2",
            created_by="tester",
            changed_by="tester",
        )
    )

    ready_items = repository.list_items(item_type="canonical_gap", status="ready_for_approval")
    by_key = repository.get_item_by_key("canonical_gap", "canonical_gap_customer_id_customer.id")

    assert len(ready_items) == 1
    assert ready_items[0].item_key == "canonical_gap_customer_id_customer.id"
    assert by_key is not None
    assert by_key.assignee == "steward-1"


def test_catalog_repository_reads_mapping_set_projection_after_governance_update(tmp_path) -> None:
    persistence = SQLitePersistenceService(str(tmp_path / "catalog.sqlite3"))
    governance_repository = MappingGovernanceRepository(storage=persistence)
    catalog_repository = CatalogRepository(storage=persistence)

    saved = governance_repository.save_mapping_set(
        "customer-master",
        [
            {"source": "customer_id", "target": "customer_id", "status": "accepted"},
            {"source": "customer_name", "target": "customer_name", "status": "accepted"},
        ],
        source_dataset_id="source-1",
        target_dataset_id="target-1",
        status="draft",
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        interface_type="batch",
        description="Customer master sync",
        canonical_concepts=["customer.id"],
        unmatched_sources=["legacy_customer_identifier"],
        created_by="tester",
        owner="qa-owner",
        assignee="qa-reviewer",
        review_note="Initial governance draft",
    )
    governance_repository.update_mapping_set_status(
        saved.mapping_set_id,
        "approved",
        owner="qa-owner",
        assignee="qa-reviewer",
        review_note="Approved for reuse",
    )

    catalog_rows = catalog_repository.list_integrations(status="approved", source_system="SAP")
    detail = catalog_repository.get_integration_detail("Customer Master Sync")
    concept_rows = catalog_repository.list_concept_usage_records("customer.id", status="approved")

    assert len(catalog_rows) == 1
    assert catalog_rows[0].integration_name == "Customer Master Sync"
    assert catalog_rows[0].status == "approved"
    assert detail.latest_approved_version is not None
    assert detail.latest_approved_version.status == "approved"
    assert detail.latest_approved_version.owner == "qa-owner"
    assert detail.latest_approved_version.assignee == "qa-reviewer"
    assert len(concept_rows) == 1
    assert concept_rows[0].mapping_set_id == saved.mapping_set_id
    assert concept_rows[0].source_system == "SAP"
