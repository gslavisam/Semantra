from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


KnowledgeOverlayVersionStatus = Literal["draft", "validated", "active", "archived"]
KnowledgeOverlayEntryType = Literal["abbreviation", "synonym", "field_alias", "concept_alias"]
KnowledgeOverlayIssueSeverity = Literal["error", "warning"]
KnowledgeOverlayRowStatus = Literal["valid", "invalid"]
KnowledgeOverlayMode = Literal["base_only", "overlay_active"]
KnowledgeAuditAction = Literal["create", "activate", "deactivate", "archive", "rollback", "reseed", "reject", "ignore", "triage", "stewardship"]
CanonicalConceptSource = Literal["base", "overlay_only", "base_plus_active_overlay"]
KnowledgeStewardshipItemType = Literal["canonical_gap", "overlay_promotion"]
KnowledgeStewardshipStatus = Literal["new", "needs_review", "ready_for_approval", "approved", "rejected", "ignored", "promoted"]


class KnowledgeOverlayVersion(BaseModel):
    overlay_id: int | None = None
    name: str
    status: KnowledgeOverlayVersionStatus = "draft"
    scope: str = "global"
    created_by: str | None = None
    source_filename: str | None = None
    created_at: str | None = None
    activated_at: str | None = None


class KnowledgeOverlayEntry(BaseModel):
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
    row_number: int
    severity: KnowledgeOverlayIssueSeverity
    code: str
    message: str


class KnowledgeOverlayValidationPreviewRow(BaseModel):
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
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    conflicts: int = 0
    warnings: int = 0
    normalized_preview: list[KnowledgeOverlayValidationPreviewRow] = Field(default_factory=list)


class KnowledgeOverlayCreateResponse(BaseModel):
    version: KnowledgeOverlayVersion
    saved_entry_count: int = 0
    validation: KnowledgeOverlayValidationResult


class KnowledgeOverlayVersionEntriesResponse(BaseModel):
    version: KnowledgeOverlayVersion
    entries: list[KnowledgeOverlayEntry] = Field(default_factory=list)


class KnowledgeRuntimeStatus(BaseModel):
    mode: KnowledgeOverlayMode = "base_only"
    active_overlay_id: int | None = None
    active_overlay_name: str | None = None
    active_entry_count: int = 0
    entry_type_counts: dict[str, int] = Field(default_factory=dict)
    concept_count: int = 0
    canonical_concept_count: int = 0


class CanonicalGlossaryEntry(BaseModel):
    concept_id: str
    entity: str
    attribute: str
    display_name: str
    description: str = ""
    data_type: str = ""
    aliases: list[str] = Field(default_factory=list)


class CanonicalGlossaryImportResponse(BaseModel):
    imported_row_count: int = 0
    canonical_concept_count: int = 0
    source_filename: str | None = None


class CanonicalGlossaryPromotionRequest(BaseModel):
    changed_by: str | None = None
    note: str | None = None


class CanonicalGlossaryPromotionResponse(BaseModel):
    item: KnowledgeStewardshipItemDetail
    glossary_entry: CanonicalGlossaryEntry
    alias_added: bool = False
    concept_created: bool = False


class KnowledgeAuditEntry(BaseModel):
    audit_id: int | None = None
    overlay_id: int | None = None
    overlay_name: str | None = None
    action: KnowledgeAuditAction
    message: str
    created_at: str | None = None


class CanonicalConceptFieldContext(BaseModel):
    system: str = ""
    object_name: str = ""
    field_name: str = ""
    category: str = ""
    object_description: str = ""
    field_description: str = ""
    note: str = ""


class CanonicalConceptUsageRecord(BaseModel):
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
    entry_id: int | None = None
    overlay_id: int
    overlay_name: str
    canonical_term: str
    alias: str
    source_system: str | None = None
    note: str | None = None


class CanonicalConceptSummary(BaseModel):
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


class CanonicalConceptDetailResponse(BaseModel):
    concept: CanonicalConceptSummary
    field_contexts: list[CanonicalConceptFieldContext] = Field(default_factory=list)
    active_overlay_entries: list[CanonicalConceptOverlayEntry] = Field(default_factory=list)
    integrations: list[CanonicalConceptUsageRecord] = Field(default_factory=list)
    audit_entries: list[KnowledgeAuditEntry] = Field(default_factory=list)


class KnowledgeStewardshipItemRecord(BaseModel):
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
    candidate_payload: dict[str, Any] = Field(default_factory=dict)
    suggestion_payload: dict[str, Any] = Field(default_factory=dict)
    overlay_entry_payload: dict[str, Any] = Field(default_factory=dict)


class KnowledgeStewardshipItemCreateRequest(BaseModel):
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
    status: KnowledgeStewardshipStatus
    changed_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class SourceFieldHintRecord(BaseModel):
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