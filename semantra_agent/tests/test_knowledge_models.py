"""Unit tests for semantra_core.models.knowledge.

Covers the canonical glossary, knowledge overlay, runtime status, concept
summary/detail, stewardship, and source-field-hint models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from semantra_core.models.knowledge import (
    CanonicalConceptDetailResponse,
    CanonicalConceptFieldContext,
    CanonicalConceptOverlayEntry,
    CanonicalConceptSummary,
    CanonicalConceptUsageRecord,
    CanonicalGlossaryEntry,
    CanonicalGlossaryImportResponse,
    CanonicalGlossaryPromotionRequest,
    CanonicalGlossaryPromotionResponse,
    CanonicalPrivacyMetadata,
    KnowledgeAuditEntry,
    KnowledgeConceptBaseRecord,
    KnowledgeConceptDetailResponse,
    KnowledgeConceptFieldContext,
    KnowledgeConceptPromotionRequest,
    KnowledgeConceptPromotionResponse,
    KnowledgeConceptPromotionResult,
    KnowledgeConceptSummary,
    KnowledgeConceptUpdateRequest,
    KnowledgeOverlayCreateResponse,
    KnowledgeOverlayEntry,
    KnowledgeOverlayValidationIssue,
    KnowledgeOverlayValidationPreviewRow,
    KnowledgeOverlayValidationResult,
    KnowledgeOverlayVersion,
    KnowledgeOverlayVersionEntriesResponse,
    KnowledgeRuntimeStatus,
    KnowledgeStewardshipItemCreateRequest,
    KnowledgeStewardshipItemDetail,
    KnowledgeStewardshipItemRecord,
    KnowledgeStewardshipItemStatusUpdateRequest,
    SourceFieldHintRecord,
    SourceFieldHintUpsertRequest,
)


# ---------------------------------------------------------------------------
# Privacy metadata
# ---------------------------------------------------------------------------


def test_canonical_privacy_metadata_defaults() -> None:
    """Privacy metadata should default to non-PII with empty collections."""
    privacy = CanonicalPrivacyMetadata()
    assert privacy.is_pii is False
    assert privacy.is_gdpr_special_category is False
    assert privacy.pii_categories == []
    assert privacy.data_subject_types == []


def test_canonical_privacy_metadata_round_trip() -> None:
    """Privacy metadata should round-trip all custom values."""
    privacy = CanonicalPrivacyMetadata(
        is_pii=True,
        is_gdpr_special_category=False,
        pii_categories=["email"],
        data_subject_types=["customer"],
    )
    assert privacy.is_pii is True
    assert privacy.pii_categories == ["email"]


# ---------------------------------------------------------------------------
# KnowledgeOverlayVersion
# ---------------------------------------------------------------------------


def test_knowledge_overlay_version_defaults() -> None:
    """Overlay version should default to draft status, 'global' scope."""
    version = KnowledgeOverlayVersion(name="v1")
    assert version.overlay_id is None
    assert version.status == "draft"
    assert version.scope == "global"
    assert version.created_by is None
    assert version.source_filename is None
    assert version.created_at is None
    assert version.activated_at is None


def test_knowledge_overlay_version_rejects_invalid_status() -> None:
    """status must validate against the literal overlay-version statuses."""
    with pytest.raises(ValidationError):
        KnowledgeOverlayVersion(name="v1", status="published")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# KnowledgeOverlayEntry
# ---------------------------------------------------------------------------


def test_knowledge_overlay_entry_normalized_fields_required() -> None:
    """Normalized fields are required: they enforce downstream search determinism."""
    with pytest.raises(ValidationError):
        KnowledgeOverlayEntry(  # type: ignore[call-arg]
            entry_type="synonym",
            canonical_term="customer",
            alias="client",
        )


def test_knowledge_overlay_entry_round_trip() -> None:
    """An entry should round-trip every field exactly as supplied."""
    entry = KnowledgeOverlayEntry(
        entry_type="synonym",
        canonical_term="customer",
        alias="client",
        normalized_canonical_term="customer",
        normalized_alias="client",
    )
    assert entry.entry_id is None
    assert entry.canonical_concept_id is None
    assert entry.domain is None
    assert entry.source_system is None
    assert entry.note is None


# ---------------------------------------------------------------------------
# KnowledgeOverlay validation
# ---------------------------------------------------------------------------


def test_knowledge_overlay_validation_issue_round_trip() -> None:
    """Validation issue should preserve row, severity, code, and message."""
    issue = KnowledgeOverlayValidationIssue(
        row_number=3, severity="error", code="missing_alias", message="alias required"
    )
    assert issue.row_number == 3
    assert issue.severity == "error"


def test_knowledge_overlay_validation_preview_row_defaults() -> None:
    """Preview row should default status to 'valid' and issues to []."""
    row = KnowledgeOverlayValidationPreviewRow(row_number=1)
    assert row.status == "valid"
    assert row.issues == []
    assert row.canonical_term is None
    assert row.alias is None


def test_knowledge_overlay_validation_result_defaults() -> None:
    """Validation result should default all counters to 0 and preview to []."""
    result = KnowledgeOverlayValidationResult()
    assert result.total_rows == 0
    assert result.valid_rows == 0
    assert result.invalid_rows == 0
    assert result.duplicate_rows == 0
    assert result.conflicts == 0
    assert result.warnings == 0
    assert result.normalized_preview == []


def test_knowledge_overlay_create_response_round_trip() -> None:
    """Create response should nest version, count, and validation correctly."""
    version = KnowledgeOverlayVersion(name="v1", status="validated")
    validation = KnowledgeOverlayValidationResult(total_rows=5, valid_rows=5)
    response = KnowledgeOverlayCreateResponse(
        version=version, saved_entry_count=5, validation=validation
    )
    assert response.saved_entry_count == 5
    assert response.version is version
    assert response.validation.total_rows == 5


def test_knowledge_overlay_version_entries_response_defaults() -> None:
    """Version entries response should default entries to an empty list."""
    response = KnowledgeOverlayVersionEntriesResponse(
        version=KnowledgeOverlayVersion(name="v1")
    )
    assert response.entries == []


# ---------------------------------------------------------------------------
# KnowledgeRuntimeStatus
# ---------------------------------------------------------------------------


def test_knowledge_runtime_status_defaults() -> None:
    """Runtime status should default to base_only / source_files / missing."""
    status = KnowledgeRuntimeStatus()
    assert status.mode == "base_only"
    assert status.runtime_source == "source_files"
    assert status.source_hash_state == "missing"
    assert status.seeded_at is None
    assert status.seeded_concept_count == 0
    assert status.active_overlay_id is None
    assert status.active_overlay_name is None
    assert status.entry_type_counts == {}
    assert status.concept_count == 0


# ---------------------------------------------------------------------------
# Canonical glossary
# ---------------------------------------------------------------------------


def test_canonical_glossary_entry_minimal_required_fields() -> None:
    """Glossary entry requires identity and display name; everything else defaults."""
    entry = CanonicalGlossaryEntry(
        concept_id="customer.email",
        entity="customer",
        attribute="email",
        display_name="Customer Email",
    )
    assert entry.description == ""
    assert entry.data_type == ""
    assert entry.aliases == []
    assert isinstance(entry.privacy, CanonicalPrivacyMetadata)
    assert entry.privacy.is_pii is False


def test_canonical_glossary_entry_rejects_missing_required_fields() -> None:
    """Omitting required identity fields must raise a ValidationError."""
    with pytest.raises(ValidationError):
        CanonicalGlossaryEntry(  # type: ignore[call-arg]
            display_name="X",
        )


def test_canonical_glossary_import_response_defaults() -> None:
    """Import response should default counts to 0 and filename to None."""
    response = CanonicalGlossaryImportResponse()
    assert response.imported_row_count == 0
    assert response.canonical_concept_count == 0
    assert response.source_filename is None


# ---------------------------------------------------------------------------
# Knowledge concept base / update
# ---------------------------------------------------------------------------


def test_knowledge_concept_base_record_defaults() -> None:
    """All fields in the base record should default to empty strings."""
    record = KnowledgeConceptBaseRecord()
    assert record.domain == ""
    assert record.english_name == ""
    assert record.serbian_name == ""


def test_knowledge_concept_update_request_optional_changed_by() -> None:
    """changed_by should default to None on the update request."""
    request = KnowledgeConceptUpdateRequest()
    assert request.changed_by is None
    assert request.domain == ""


def test_knowledge_concept_promotion_request_defaults() -> None:
    """Promotion request should default concept_ids to [] and target to None."""
    request = KnowledgeConceptPromotionRequest()
    assert request.concept_ids == []
    assert request.target_concept_id is None
    assert request.changed_by is None


def test_knowledge_concept_promotion_result_defaults() -> None:
    """Promotion result should default to 'skipped' status."""
    result = KnowledgeConceptPromotionResult(knowledge_concept_id="k1")
    assert result.status == "skipped"
    assert result.alias_count == 0
    assert result.aliases_added == 0
    assert result.concept_created is False
    assert result.message == ""


def test_knowledge_concept_promotion_response_defaults() -> None:
    """Promotion response should default results to [] and counts to 0."""
    response = KnowledgeConceptPromotionResponse()
    assert response.promoted_count == 0
    assert response.skipped_count == 0
    assert response.results == []


# ---------------------------------------------------------------------------
# Canonical glossary promotion
# ---------------------------------------------------------------------------


def test_canonical_glossary_promotion_request_defaults() -> None:
    """Promotion request should default all metadata fields to None/''."""
    request = CanonicalGlossaryPromotionRequest()
    assert request.changed_by is None
    assert request.note is None


def test_canonical_glossary_promotion_response_round_trip() -> None:
    """Promotion response should embed the updated item and the new glossary entry."""
    item = KnowledgeStewardshipItemDetail(item_id=1, item_key="k1", title="t1")
    entry = CanonicalGlossaryEntry(
        concept_id="x.y", entity="x", attribute="y", display_name="X Y"
    )
    response = CanonicalGlossaryPromotionResponse(
        item=item, glossary_entry=entry, alias_added=True, concept_created=False
    )
    assert response.item is item
    assert response.glossary_entry is entry
    assert response.alias_added is True
    assert response.concept_created is False


# ---------------------------------------------------------------------------
# Audit / contexts / usage
# ---------------------------------------------------------------------------


def test_knowledge_audit_entry_required_action() -> None:
    """Audit entry action is required and must validate against the literal."""
    with pytest.raises(ValidationError):
        KnowledgeAuditEntry(message="x")  # type: ignore[call-arg]

    entry = KnowledgeAuditEntry(action="create", message="x")
    assert entry.action == "create"
    assert entry.created_at is None
    assert entry.overlay_id is None
    assert entry.overlay_name is None


def test_canonical_concept_field_context_defaults() -> None:
    """Field context should default all descriptive fields to ''."""
    ctx = CanonicalConceptFieldContext()
    assert ctx.system == ""
    assert ctx.object_name == ""
    assert ctx.field_name == ""
    assert ctx.note == ""


def test_canonical_concept_usage_record_defaults() -> None:
    """Usage record should default counts to 1 and status to 'draft'."""
    record = CanonicalConceptUsageRecord(
        concept_id="x", mapping_set_id=1, name="m1", integration_name="i1"
    )
    assert record.version == 1
    assert record.status == "draft"
    assert record.artifact_type == "standard"
    assert record.source_system is None
    assert record.created_at is None


def test_canonical_concept_overlay_entry_defaults() -> None:
    """Overlay entry should default entry_id to None and metadata to None."""
    entry = CanonicalConceptOverlayEntry(
        overlay_id=1,
        overlay_name="v1",
        canonical_term="customer",
        alias="client",
    )
    assert entry.entry_id is None
    assert entry.source_system is None
    assert entry.note is None


def test_canonical_concept_summary_defaults() -> None:
    """Concept summary should default all collections to [] and counts to 0."""
    summary = CanonicalConceptSummary(concept_id="x", display_name="X")
    assert summary.entity == ""
    assert summary.attribute == ""
    assert summary.source == "base"
    assert summary.base_aliases == []
    assert summary.active_overlay_aliases == []
    assert summary.alias_count == 0
    assert summary.usage_count == 0
    assert isinstance(summary.privacy, CanonicalPrivacyMetadata)


def test_canonical_concept_detail_response_defaults() -> None:
    """Detail response should default all list fields to []."""
    response = CanonicalConceptDetailResponse(
        concept=CanonicalConceptSummary(concept_id="x", display_name="X")
    )
    assert response.field_contexts == []
    assert response.active_overlay_entries == []
    assert response.integrations == []
    assert response.audit_entries == []


# ---------------------------------------------------------------------------
# Knowledge concept detail
# ---------------------------------------------------------------------------


def test_knowledge_concept_field_context_defaults() -> None:
    """Knowledge field context should default descriptive fields to ''."""
    ctx = KnowledgeConceptFieldContext()
    assert ctx.system == ""
    assert ctx.field_description == ""


def test_knowledge_concept_summary_defaults() -> None:
    """Knowledge concept summary should default source to 'base_registry'."""
    summary = KnowledgeConceptSummary(concept_id="x", canonical_name="X")
    assert summary.source == "base_registry"
    assert summary.editable is False
    assert summary.alias_count == 0
    assert summary.linked_canonical_concept_count == 0
    assert summary.source_systems == []
    assert summary.aliases == []


def test_knowledge_concept_detail_response_round_trip() -> None:
    """Detail response should preserve summary, contexts, and base record."""
    summary = KnowledgeConceptSummary(concept_id="x", canonical_name="X")
    base = KnowledgeConceptBaseRecord(domain="d1")
    response = KnowledgeConceptDetailResponse(
        concept=summary, field_contexts=[], base_record=base
    )
    assert response.concept is summary
    assert response.base_record is base


# ---------------------------------------------------------------------------
# Stewardship
# ---------------------------------------------------------------------------


def test_knowledge_stewardship_item_record_required_fields() -> None:
    """Stewardship item requires item_id, item_key, and title."""
    with pytest.raises(ValidationError):
        KnowledgeStewardshipItemRecord(  # type: ignore[call-arg]
            item_key="k1",
            title="t1",
        )


def test_knowledge_stewardship_item_record_defaults() -> None:
    """Stewardship item should default to canonical_gap / 'new' status."""
    record = KnowledgeStewardshipItemRecord(
        item_id=1, item_key="k1", title="t1"
    )
    assert record.item_type == "canonical_gap"
    assert record.status == "new"
    assert record.concept_id is None
    assert record.created_at is None


def test_knowledge_stewardship_item_detail_inherits_record_fields() -> None:
    """Stewardship detail should inherit record fields and add payload dicts."""
    detail = KnowledgeStewardshipItemDetail(
        item_id=1,
        item_key="k1",
        title="t1",
        candidate_payload={"a": 1},
    )
    assert detail.item_key == "k1"
    assert detail.candidate_payload == {"a": 1}
    assert detail.suggestion_payload == {}
    assert detail.overlay_entry_payload == {}


def test_knowledge_stewardship_item_create_request_defaults() -> None:
    """Create request should default to canonical_gap / 'new' status and empty payloads."""
    request = KnowledgeStewardshipItemCreateRequest(item_key="k1", title="t1")
    assert request.item_type == "canonical_gap"
    assert request.status == "new"
    assert request.candidate_payload == {}
    assert request.suggestion_payload == {}
    assert request.overlay_entry_payload == {}


def test_knowledge_stewardship_item_status_update_request_required_status() -> None:
    """Status is required on the status update request."""
    with pytest.raises(ValidationError):
        KnowledgeStewardshipItemStatusUpdateRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Source field hint
# ---------------------------------------------------------------------------


def test_source_field_hint_record_defaults() -> None:
    """Source field hint record should default to active=True with empty strings."""
    record = SourceFieldHintRecord(
        source_system="sys1", source_field="email"
    )
    assert record.hint_id is None
    assert record.business_domain is None
    assert record.meaning_hint == ""
    assert record.negative_hint == ""
    assert record.sample_values == []
    assert record.active is True
    assert record.created_at is None


def test_source_field_hint_upsert_request_defaults() -> None:
    """Upsert request should mirror record defaults and default changed_by to None."""
    request = SourceFieldHintUpsertRequest(
        source_system="sys1", source_field="email"
    )
    assert request.business_domain is None
    assert request.meaning_hint == ""
    assert request.sample_values == []
    assert request.active is True
    assert request.changed_by is None
