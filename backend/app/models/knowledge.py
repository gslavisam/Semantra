from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


KnowledgeOverlayVersionStatus = Literal["draft", "validated", "active", "archived"]
KnowledgeOverlayEntryType = Literal["abbreviation", "synonym", "field_alias", "concept_alias"]
KnowledgeOverlayIssueSeverity = Literal["error", "warning"]
KnowledgeOverlayRowStatus = Literal["valid", "invalid"]
KnowledgeOverlayMode = Literal["base_only", "overlay_active"]
KnowledgeAuditAction = Literal["create", "activate", "deactivate", "archive", "rollback"]


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


class KnowledgeAuditEntry(BaseModel):
    audit_id: int | None = None
    overlay_id: int | None = None
    overlay_name: str | None = None
    action: KnowledgeAuditAction
    message: str
    created_at: str | None = None