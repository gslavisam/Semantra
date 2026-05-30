"""Models for canonical concepts, overlays, stewardship, and knowledge runtime status."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


KnowledgeOverlayVersionStatus = Literal["draft", "validated", "active", "archived"]
KnowledgeOverlayEntryType = Literal["abbreviation", "synonym", "field_alias", "concept_alias"]
KnowledgeOverlayIssueSeverity = Literal["error", "warning"]
KnowledgeOverlayRowStatus = Literal["valid", "invalid"]
KnowledgeOverlayMode = Literal["base_only", "overlay_active"]
KnowledgeRuntimeSource = Literal["sqlite_cache", "source_files", "canonical_authoring_sync"]
KnowledgeSeedState = Literal["current", "drifted", "missing"]
KnowledgeAuditAction = Literal["create", "activate", "deactivate", "archive", "rollback", "reseed", "reject", "ignore", "triage", "stewardship"]
CanonicalConceptSource = Literal["base", "overlay_only", "base_plus_active_overlay"]
KnowledgeConceptSource = Literal["base_registry", "derived_runtime", "generated_runtime"]
KnowledgeStewardshipItemType = Literal["canonical_gap", "overlay_promotion", "concept_governance"]
KnowledgeStewardshipStatus = Literal["new", "needs_review", "ready_for_approval", "approved", "rejected", "ignored", "promoted"]


class CanonicalPrivacyMetadata(BaseModel):
    """Privacy tags attached to one canonical concept."""

    is_pii: bool = False
    is_gdpr_special_category: bool = False
    pii_categories: list[str] = Field(default_factory=list)
    data_subject_types: list[str] = Field(default_factory=list)


class KnowledgeOverlayVersion(BaseModel):
    """Metadata describing one persisted knowledge overlay version."""

    overlay_id: int | None = None
    name: str
    status: KnowledgeOverlayVersionStatus = "draft"
    scope: str = "global"
    created_by: str | None = None
    source_filename: str | None = None
    created_at: str | None = None
    activated_at: str | None = None


class KnowledgeOverlayEntry(BaseModel):
    """One normalized alias or concept entry belonging to a knowledge overlay version."""

    entry_id: int | None = None
    version_id: int | None = None
    entry_type: KnowledgeOverlayEntryType
    canonical_term: str
    canonical_concept_id: str | None = None
    alias: str
    domain: str | None = None
    source_system: str | None = None
    note: str | None = None
    normalized_canonical_term: str
    normalized_alias: str


class KnowledgeOverlayValidationIssue(BaseModel):
    """One validation issue produced while checking an uploaded overlay row."""

    row_number: int
    severity: KnowledgeOverlayIssueSeverity
    code: str
    message: str


class KnowledgeOverlayValidationPreviewRow(BaseModel):
    """Normalized preview of one uploaded overlay row together with its issues."""

    row_number: int
    status: KnowledgeOverlayRowStatus = "valid"
    entry_type: str | None = None
    canonical_term: str | None = None
    canonical_concept_id: str | None = None
    alias: str | None = None
    domain: str | None = None
    source_system: str | None = None
    note: str | None = None
    normalized_canonical_term: str | None = None
    normalized_alias: str | None = None
    issues: list[KnowledgeOverlayValidationIssue] = Field(default_factory=list)


class KnowledgeOverlayValidationResult(BaseModel):
    """Summary and normalized preview produced when validating an overlay upload."""

    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    conflicts: int = 0
    warnings: int = 0
    normalized_preview: list[KnowledgeOverlayValidationPreviewRow] = Field(default_factory=list)


class KnowledgeOverlayCreateResponse(BaseModel):
    """Response returned after successfully creating a knowledge overlay version."""

    version: KnowledgeOverlayVersion
    saved_entry_count: int = 0
    validation: KnowledgeOverlayValidationResult


class KnowledgeOverlayVersionEntriesResponse(BaseModel):
    """Overlay version detail response including its persisted entries."""

    version: KnowledgeOverlayVersion
    entries: list[KnowledgeOverlayEntry] = Field(default_factory=list)


class KnowledgeRuntimeStatus(BaseModel):
    """Runtime status snapshot for the active knowledge base and overlay state."""

    mode: KnowledgeOverlayMode = "base_only"
    runtime_source: KnowledgeRuntimeSource = "source_files"
    source_hash_state: KnowledgeSeedState = "missing"
    seeded_at: str | None = None
    seeded_concept_count: int = 0
    seeded_canonical_concept_count: int = 0
    active_overlay_id: int | None = None
    active_overlay_name: str | None = None
    active_entry_count: int = 0
    entry_type_counts: dict[str, int] = Field(default_factory=dict)
    concept_count: int = 0
    canonical_concept_count: int = 0


class CanonicalGlossaryEntry(BaseModel):
    """One canonical glossary concept entry with aliases and descriptive metadata."""

    concept_id: str
    entity: str
    attribute: str
    display_name: str
    description: str = ""
    data_type: str = ""
    aliases: list[str] = Field(default_factory=list)
    privacy: CanonicalPrivacyMetadata = Field(default_factory=CanonicalPrivacyMetadata)


class CanonicalGlossaryImportResponse(BaseModel):
    """Summary returned after importing a canonical glossary file."""

    imported_row_count: int = 0
    canonical_concept_count: int = 0
    source_filename: str | None = None


class KnowledgeRegistryImportResponse(BaseModel):
    """Summary returned after importing the base knowledge registry CSV."""

    imported_row_count: int = 0
    knowledge_concept_count: int = 0
    source_filename: str | None = None


class KnowledgeConceptBaseRecord(BaseModel):
    """Editable base-registry fields for one knowledge concept."""

    domain: str = ""
    english_name: str = ""
    serbian_name: str = ""
    abbreviations: str = ""
    alternative_names: str = ""
    data_type: str = ""
    typical_length: str = ""
    example_value: str = ""


class KnowledgeConceptUpdateRequest(BaseModel):
    """Request payload used to update the editable base-registry fields of one knowledge concept."""

    domain: str = ""
    serbian_name: str = ""
    abbreviations: str = ""
    alternative_names: str = ""
    data_type: str = ""
    typical_length: str = ""
    example_value: str = ""
    changed_by: str | None = None


class KnowledgeConceptPromotionRequest(BaseModel):
    """Request payload used to promote one or more knowledge concepts into the stable canonical glossary."""

    concept_ids: list[str] = Field(default_factory=list)
    target_concept_id: str | None = None
    changed_by: str | None = None
    note: str | None = None


class KnowledgeConceptPromotionResult(BaseModel):
    """Outcome for one knowledge concept promotion attempt."""

    knowledge_concept_id: str
    target_concept_id: str | None = None
    status: str = "skipped"
    alias_count: int = 0
    aliases_added: int = 0
    concept_created: bool = False
    message: str = ""


class KnowledgeConceptPromotionResponse(BaseModel):
    """Batch response for knowledge-to-canonical promotion attempts."""

    promoted_count: int = 0
    skipped_count: int = 0
    results: list[KnowledgeConceptPromotionResult] = Field(default_factory=list)


class CanonicalGlossaryPromotionRequest(BaseModel):
    """Request metadata for promoting a stewardship item into the glossary."""

    changed_by: str | None = None
    note: str | None = None


class CanonicalGlossaryPromotionResponse(BaseModel):
    """Response returned after promoting an overlay stewardship item into the glossary."""

    item: KnowledgeStewardshipItemDetail
    glossary_entry: CanonicalGlossaryEntry
    alias_added: bool = False
    concept_created: bool = False


class KnowledgeAuditEntry(BaseModel):
    """Audit log entry for glossary, overlay, and stewardship actions."""

    audit_id: int | None = None
    overlay_id: int | None = None
    overlay_name: str | None = None
    action: KnowledgeAuditAction
    message: str
    created_at: str | None = None


class CanonicalConceptFieldContext(BaseModel):
    """Field-level business context attached to one canonical concept."""

    system: str = ""
    object_name: str = ""
    field_name: str = ""
    category: str = ""
    object_description: str = ""
    field_description: str = ""
    note: str = ""


class CanonicalConceptUsageRecord(BaseModel):
    """One mapping-set usage record showing where a canonical concept appears."""

    concept_id: str
    mapping_set_id: int
    name: str
    integration_name: str
    version: int = 1
    status: str = "draft"
    artifact_type: str = "standard"
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    owner: str | None = None
    created_at: str | None = None


class CanonicalConceptOverlayEntry(BaseModel):
    """Overlay entry detail attached to a canonical concept detail response."""

    entry_id: int | None = None
    overlay_id: int
    overlay_name: str
    canonical_term: str
    alias: str
    source_system: str | None = None
    note: str | None = None


class CanonicalConceptSummary(BaseModel):
    """Summary view of a canonical concept enriched with usage and overlay metadata."""

    concept_id: str
    entity: str = ""
    attribute: str = ""
    display_name: str
    description: str = ""
    data_type: str = ""
    source: CanonicalConceptSource = "base"
    base_aliases: list[str] = Field(default_factory=list)
    active_overlay_aliases: list[str] = Field(default_factory=list)
    alias_count: int = 0
    field_context_count: int = 0
    usage_count: int = 0
    active_overlay_entry_count: int = 0
    source_systems: list[str] = Field(default_factory=list)
    business_domains: list[str] = Field(default_factory=list)
    privacy: CanonicalPrivacyMetadata = Field(default_factory=CanonicalPrivacyMetadata)


class CanonicalConceptDetailResponse(BaseModel):
    """Detail response for one canonical concept, including contexts, usage, and audits."""

    concept: CanonicalConceptSummary
    field_contexts: list[CanonicalConceptFieldContext] = Field(default_factory=list)
    active_overlay_entries: list[CanonicalConceptOverlayEntry] = Field(default_factory=list)
    integrations: list[CanonicalConceptUsageRecord] = Field(default_factory=list)
    audit_entries: list[KnowledgeAuditEntry] = Field(default_factory=list)


class KnowledgeConceptFieldContext(BaseModel):
    """Field-level context attached to one runtime knowledge concept."""

    system: str = ""
    object_name: str = ""
    field_name: str = ""
    category: str = ""
    object_description: str = ""
    field_description: str = ""
    note: str = ""


class KnowledgeConceptSummary(BaseModel):
    """Summary view of one runtime knowledge concept."""

    concept_id: str
    domain: str = ""
    canonical_name: str
    source: KnowledgeConceptSource = "base_registry"
    editable: bool = False
    alias_count: int = 0
    field_context_count: int = 0
    linked_canonical_concept_count: int = 0
    source_systems: list[str] = Field(default_factory=list)
    linked_canonical_concepts: list[str] = Field(default_factory=list)
    linked_privacy: CanonicalPrivacyMetadata = Field(default_factory=CanonicalPrivacyMetadata)
    aliases: list[str] = Field(default_factory=list)


class KnowledgeConceptDetailResponse(BaseModel):
    """Detail response for one runtime knowledge concept."""

    concept: KnowledgeConceptSummary
    field_contexts: list[KnowledgeConceptFieldContext] = Field(default_factory=list)
    base_record: KnowledgeConceptBaseRecord | None = None


class KnowledgeStewardshipItemRecord(BaseModel):
    """Persisted stewardship item for queue workflows or concept governance metadata."""

    item_id: int
    item_type: KnowledgeStewardshipItemType = "canonical_gap"
    item_key: str
    title: str
    status: KnowledgeStewardshipStatus = "new"
    concept_id: str | None = None
    source: str | None = None
    target: str | None = None
    source_system: str | None = None
    business_domain: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None
    created_by: str | None = None
    changed_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeStewardshipItemDetail(KnowledgeStewardshipItemRecord):
    """Expanded stewardship item including serialized candidate and suggestion payloads."""

    candidate_payload: dict[str, Any] = Field(default_factory=dict)
    suggestion_payload: dict[str, Any] = Field(default_factory=dict)
    overlay_entry_payload: dict[str, Any] = Field(default_factory=dict)


class KnowledgeStewardshipItemCreateRequest(BaseModel):
    """Request payload used to create or upsert a stewardship item."""

    item_type: KnowledgeStewardshipItemType = "canonical_gap"
    item_key: str
    title: str
    status: KnowledgeStewardshipStatus = "new"
    concept_id: str | None = None
    source: str | None = None
    target: str | None = None
    source_system: str | None = None
    business_domain: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None
    candidate_payload: dict[str, Any] = Field(default_factory=dict)
    suggestion_payload: dict[str, Any] = Field(default_factory=dict)
    overlay_entry_payload: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    changed_by: str | None = None


class KnowledgeStewardshipItemStatusUpdateRequest(BaseModel):
    """Request payload used to change stewardship status or assignment metadata."""

    status: KnowledgeStewardshipStatus
    changed_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class SourceFieldHintRecord(BaseModel):
    """Persisted business-meaning hint for one source field within a workspace scope."""

    hint_id: int | None = None
    source_system: str
    business_domain: str | None = None
    integration_name: str | None = None
    source_field: str
    meaning_hint: str = ""
    negative_hint: str = ""
    sample_values: list[str] = Field(default_factory=list)
    active: bool = True
    created_by: str | None = None
    changed_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SourceFieldHintUpsertRequest(BaseModel):
    """Request payload used to create or update a persistent source-field hint."""

    source_system: str
    business_domain: str | None = None
    integration_name: str | None = None
    source_field: str
    meaning_hint: str = ""
    negative_hint: str = ""
    sample_values: list[str] = Field(default_factory=list)
    active: bool = True
    created_by: str | None = None
    changed_by: str | None = None