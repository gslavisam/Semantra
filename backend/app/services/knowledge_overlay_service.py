from __future__ import annotations

import csv
from io import StringIO

from app.models.knowledge import (
    KnowledgeOverlayEntry,
    KnowledgeOverlayValidationIssue,
    KnowledgeOverlayValidationPreviewRow,
    KnowledgeOverlayValidationResult,
)
from app.services.metadata_knowledge_service import _normalize_alias, metadata_knowledge_service


REQUIRED_HEADERS = ("entry_type", "canonical_term", "alias")
OPTIONAL_HEADERS = ("domain", "source_system", "note")
ALLOWED_ENTRY_TYPES = {"abbreviation", "synonym", "field_alias", "concept_alias"}
SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "cp1250", "cp1252", "latin-1")


class KnowledgeOverlayValidationService:
    def validate_csv_payload(self, payload: bytes, filename: str | None = None) -> KnowledgeOverlayValidationResult:
        if filename and not filename.lower().endswith(".csv"):
            raise ValueError("Knowledge overlay upload currently supports CSV files only.")

        decoded = self._decode_payload(payload)
        reader = csv.DictReader(StringIO(decoded))
        if not reader.fieldnames:
            raise ValueError("Knowledge overlay CSV must include a header row.")

        missing_headers = [header for header in REQUIRED_HEADERS if header not in reader.fieldnames]
        if missing_headers:
            missing_label = ", ".join(missing_headers)
            raise ValueError(f"Knowledge overlay CSV is missing required columns: {missing_label}.")

        seen_entries: set[tuple[str, str, str, str, str]] = set()
        preview_rows: list[KnowledgeOverlayValidationPreviewRow] = []

        for row_number, row in enumerate(reader, start=2):
            preview_rows.append(self._validate_row(row, row_number, seen_entries))

        return KnowledgeOverlayValidationResult(
            total_rows=len(preview_rows),
            valid_rows=sum(1 for row in preview_rows if row.status == "valid"),
            invalid_rows=sum(1 for row in preview_rows if row.status == "invalid"),
            duplicate_rows=sum(1 for row in preview_rows if any(issue.code == "duplicate_upload_entry" for issue in row.issues)),
            conflicts=sum(1 for row in preview_rows if any(issue.code == "conflict_existing_alias" for issue in row.issues)),
            warnings=sum(1 for row in preview_rows for issue in row.issues if issue.severity == "warning"),
            normalized_preview=preview_rows,
        )

    def _validate_row(
        self,
        row: dict[str, object],
        row_number: int,
        seen_entries: set[tuple[str, str, str, str, str]],
    ) -> KnowledgeOverlayValidationPreviewRow:
        entry_type = str(row.get("entry_type") or "").strip()
        canonical_term = str(row.get("canonical_term") or "").strip()
        alias = str(row.get("alias") or "").strip()
        domain = str(row.get("domain") or "").strip() or None
        source_system = str(row.get("source_system") or "").strip() or None
        note = str(row.get("note") or "").strip() or None

        normalized_canonical_term = _normalize_alias(canonical_term)
        normalized_alias = _normalize_alias(alias)
        canonical_concept_id = None

        issues: list[KnowledgeOverlayValidationIssue] = []
        if not entry_type:
            issues.append(self._issue(row_number, "error", "missing_entry_type", "entry_type is required."))
        elif entry_type not in ALLOWED_ENTRY_TYPES:
            allowed = ", ".join(sorted(ALLOWED_ENTRY_TYPES))
            issues.append(
                self._issue(
                    row_number,
                    "error",
                    "invalid_entry_type",
                    f"entry_type must be one of: {allowed}.",
                )
            )

        if not canonical_term:
            issues.append(self._issue(row_number, "error", "missing_canonical_term", "canonical_term is required."))
        elif not normalized_canonical_term:
            issues.append(
                self._issue(
                    row_number,
                    "error",
                    "invalid_canonical_term",
                    "canonical_term must contain at least one alphanumeric character.",
                )
            )

        if entry_type == "concept_alias" and canonical_term:
            canonical_concept_id = metadata_knowledge_service.resolve_canonical_concept_id(canonical_term)
            if canonical_concept_id is None:
                issues.append(
                    self._issue(
                        row_number,
                        "error",
                        "unknown_canonical_concept",
                        f"canonical_term '{canonical_term}' does not match any canonical business concept.",
                    )
                )

        if not alias:
            issues.append(self._issue(row_number, "error", "missing_alias", "alias is required."))
        elif not normalized_alias:
            issues.append(
                self._issue(
                    row_number,
                    "error",
                    "invalid_alias",
                    "alias must contain at least one alphanumeric character.",
                )
            )

        if normalized_canonical_term and normalized_alias and normalized_canonical_term == normalized_alias:
            issues.append(
                self._issue(
                    row_number,
                    "warning",
                    "canonical_matches_alias",
                    "canonical_term and alias normalize to the same value; this entry may not add useful signal.",
                )
            )

        dedupe_key = (
            entry_type,
            normalized_canonical_term,
            normalized_alias,
            _normalize_alias(domain or ""),
            _normalize_alias(source_system or ""),
        )
        if all(dedupe_key[:3]):
            if dedupe_key in seen_entries:
                issues.append(
                    self._issue(
                        row_number,
                        "error",
                        "duplicate_upload_entry",
                        "This normalized knowledge entry appears more than once in the uploaded CSV.",
                    )
                )
            else:
                seen_entries.add(dedupe_key)

        if normalized_alias:
            existing_concepts = metadata_knowledge_service.concepts_for_alias(normalized_alias)
            if existing_concepts and normalized_canonical_term and normalized_canonical_term not in existing_concepts:
                existing_label = ", ".join(existing_concepts)
                issues.append(
                    self._issue(
                        row_number,
                        "warning",
                        "conflict_existing_alias",
                        f"Alias '{alias}' already matches base knowledge concept(s): {existing_label}.",
                    )
                )

        status = "invalid" if any(issue.severity == "error" for issue in issues) else "valid"
        return KnowledgeOverlayValidationPreviewRow(
            row_number=row_number,
            status=status,
            entry_type=entry_type or None,
            canonical_term=canonical_term or None,
            canonical_concept_id=canonical_concept_id,
            alias=alias or None,
            domain=domain,
            source_system=source_system,
            note=note,
            normalized_canonical_term=normalized_canonical_term or None,
            normalized_alias=normalized_alias or None,
            issues=issues,
        )

    def build_entry(self, preview_row: KnowledgeOverlayValidationPreviewRow) -> KnowledgeOverlayEntry:
        if preview_row.status != "valid":
            raise ValueError("Cannot build a knowledge overlay entry from an invalid preview row.")

        return KnowledgeOverlayEntry(
            entry_type=preview_row.entry_type,
            canonical_term=preview_row.canonical_term,
            canonical_concept_id=preview_row.canonical_concept_id,
            alias=preview_row.alias,
            domain=preview_row.domain,
            source_system=preview_row.source_system,
            note=preview_row.note,
            normalized_canonical_term=preview_row.normalized_canonical_term,
            normalized_alias=preview_row.normalized_alias,
        )

    def _decode_payload(self, payload: bytes) -> str:
        for encoding in SUPPORTED_ENCODINGS:
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Knowledge overlay CSV could not be decoded with supported encodings.")

    def _issue(self, row_number: int, severity: str, code: str, message: str) -> KnowledgeOverlayValidationIssue:
        return KnowledgeOverlayValidationIssue(row_number=row_number, severity=severity, code=code, message=message)


knowledge_overlay_validation_service = KnowledgeOverlayValidationService()