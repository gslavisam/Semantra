from __future__ import annotations

from dataclasses import dataclass, field
import csv
from pathlib import Path
import re
from typing import Iterable

from openpyxl import load_workbook

from app.models.schema import ColumnProfile


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METADATA_DICT_PATH = PROJECT_ROOT / "metadata_dict" / "metadata_dict.csv"
DEFAULT_METADATA_WORKBOOK_PATH = PROJECT_ROOT / "metadata_dict" / "metadata_dictionary.xlsx"
DEFAULT_SAP_TABLES_PATH = PROJECT_ROOT / "metadata_dict" / "sap_tables_mostUsed.xlsx"
DEFAULT_QAD_TABLES_PATH = PROJECT_ROOT / "metadata_dict" / "qad_tables_mostUsed.xlsx"
DEFAULT_WORKDAY_ENTITIES_PATH = PROJECT_ROOT / "metadata_dict" / "WD_entities_mostUsed.xlsx"
MULTI_VALUE_FIELDS = ("Skracenice", "Alternativni nazivi")
ALIAS_FIELDS = (
    "Naziv (Engleski)",
    "Naziv (Srpski)",
    "snake_case",
    "camelCase",
    "PascalCase",
    "kebab-case",
    "UPPER_SNAKE",
    "lowercase",
    "SAP style",
    "Oracle/QAD style",
    "Salesforce style",
    "Odoo style",
    "MS Dynamics style",
)


def _normalize_alias(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return " ".join(token for token in cleaned.split() if token)


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class KnowledgeFieldContext:
    system: str
    object_name: str
    field_name: str
    category: str = ""
    object_description: str = ""
    field_description: str = ""
    note: str = ""


@dataclass(frozen=True)
class KnowledgeConcept:
    concept_id: str
    domain: str
    canonical_name: str
    aliases: frozenset[str]
    contexts: tuple[KnowledgeFieldContext, ...] = ()
    context_terms: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ConceptMatch:
    concept_id: str
    strength: float
    matched_aliases: tuple[str, ...] = ()
    contexts: tuple[KnowledgeFieldContext, ...] = ()


class MetadataKnowledgeService:
    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = csv_path or DEFAULT_METADATA_DICT_PATH
        self.metadata_workbook_path = DEFAULT_METADATA_WORKBOOK_PATH
        self.sap_tables_path = DEFAULT_SAP_TABLES_PATH
        self.qad_tables_path = DEFAULT_QAD_TABLES_PATH
        self.workday_entities_path = DEFAULT_WORKDAY_ENTITIES_PATH
        self._concepts_by_id: dict[str, KnowledgeConcept] = {}
        self._alias_to_concepts: dict[str, set[str]] = {}
        self._field_alias_to_contexts: dict[str, list[tuple[str, KnowledgeFieldContext]]] = {}
        self._load()

    @property
    def is_available(self) -> bool:
        return bool(self._concepts_by_id)

    @property
    def concept_count(self) -> int:
        return len(self._concepts_by_id)

    def expand_semantic_tokens(self, profile: ColumnProfile) -> set[str]:
        tokens = set(profile.tokenized_name)
        for match in self.match_concepts(profile):
            concept = self._concepts_by_id.get(match.concept_id)
            if not concept:
                continue
            tokens.add(match.concept_id)
            for alias in concept.aliases:
                tokens.update(alias.split())
            tokens.update(concept.context_terms)
        return tokens

    def knowledge_alignment(self, source: ColumnProfile, target: ColumnProfile) -> float:
        source_matches = {match.concept_id: match for match in self.match_concepts(source)}
        target_matches = {match.concept_id: match for match in self.match_concepts(target)}
        shared = set(source_matches) & set(target_matches)
        if not shared:
            return 0.0

        candidate_scores: list[float] = []
        for concept_id in shared:
            source_match = source_matches[concept_id]
            target_match = target_matches[concept_id]
            base_score = min(source_match.strength, target_match.strength)
            if source_match.contexts and target_match.contexts:
                base_score = min(1.0, base_score + 0.15)
            elif source_match.contexts or target_match.contexts:
                base_score = min(1.0, base_score + 0.05)
            candidate_scores.append(base_score)
        return round(max(candidate_scores), 4)

    def explain_alignment(self, source: ColumnProfile, target: ColumnProfile) -> list[str]:
        source_matches = {match.concept_id: match for match in self.match_concepts(source)}
        target_matches = {match.concept_id: match for match in self.match_concepts(target)}
        shared = set(source_matches) & set(target_matches)
        explanations: list[str] = []
        for concept_id in sorted(shared):
            concept = self._concepts_by_id.get(concept_id)
            if concept is None:
                continue
            explanations.append(
                f"Internal metadata dictionary aligns both fields to concept '{concept.canonical_name}' in domain '{concept.domain}'."
            )
            source_contexts = source_matches[concept_id].contexts
            target_contexts = target_matches[concept_id].contexts
            if source_contexts or target_contexts:
                source_label = ", ".join(self._format_context(context) for context in source_contexts[:2]) or "no explicit source context"
                target_label = ", ".join(self._format_context(context) for context in target_contexts[:2]) or "no explicit target context"
                explanations.append(f"Context prior: source {source_label}; target {target_label}.")
        return explanations

    def describe_profile(self, profile: ColumnProfile) -> list[str]:
        descriptions: list[str] = []
        for match in self.match_concepts(profile):
            concept = self._concepts_by_id.get(match.concept_id)
            if concept is None:
                continue
            prefix = f"{profile.name} matches internal concept '{concept.canonical_name}'"
            if match.contexts:
                context_details = ", ".join(self._format_context(context) for context in match.contexts[:3])
                descriptions.append(f"{prefix} via {context_details}.")
            else:
                descriptions.append(f"{prefix} via curated aliases and multilingual metadata.")
        return descriptions

    def match_concepts(self, profile: ColumnProfile) -> list[ConceptMatch]:
        normalized_name = _normalize_alias(profile.name)
        normalized_profile_name = _normalize_alias(profile.normalized_name)
        profile_tokens = {token for token in normalized_profile_name.split() if token}

        strengths: dict[str, float] = {}
        matched_aliases: dict[str, set[str]] = {}
        matched_contexts: dict[str, list[KnowledgeFieldContext]] = {}
        for candidate_name in {normalized_name, normalized_profile_name}:
            for concept_id in self._alias_to_concepts.get(candidate_name, set()):
                strengths[concept_id] = max(strengths.get(concept_id, 0.0), 1.0)
                matched_aliases.setdefault(concept_id, set()).add(candidate_name)
            for concept_id, context in self._field_alias_to_contexts.get(candidate_name, []):
                strengths[concept_id] = max(strengths.get(concept_id, 0.0), 1.0)
                matched_aliases.setdefault(concept_id, set()).add(candidate_name)
                matched_contexts.setdefault(concept_id, []).append(context)

        for alias, concept_ids in self._alias_to_concepts.items():
            alias_tokens = set(alias.split())
            if len(alias_tokens) < 2:
                continue
            if alias_tokens.issubset(profile_tokens):
                for concept_id in concept_ids:
                    strengths[concept_id] = max(strengths.get(concept_id, 0.0), 0.7)
                    matched_aliases.setdefault(concept_id, set()).add(alias)

        return [
            ConceptMatch(
                concept_id=concept_id,
                strength=strength,
                matched_aliases=tuple(sorted(matched_aliases.get(concept_id, set()))),
                contexts=tuple(self._unique_contexts(matched_contexts.get(concept_id, []))),
            )
            for concept_id, strength in sorted(strengths.items())
        ]

    def _load(self) -> None:
        if not self.csv_path.exists():
            return

        for encoding in ("utf-8-sig", "utf-8", "cp1250", "cp1252", "latin-1"):
            try:
                with self.csv_path.open("r", encoding=encoding, newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        self._register_csv_row(row)
                self._load_workbook_contexts()
                return
            except UnicodeDecodeError:
                self._concepts_by_id.clear()
                self._alias_to_concepts.clear()
                self._field_alias_to_contexts.clear()

    def _register_csv_row(self, row: dict[str, object]) -> None:
        concept_id = _normalize_alias(str(row.get("Naziv (Engleski)", "")))
        if not concept_id:
            return
        domain = str(row.get("Kategorija/Domen") or "general").strip()
        canonical_name = str(row.get("Naziv (Engleski)") or concept_id).strip()
        aliases = self._extract_aliases(row, ALIAS_FIELDS, MULTI_VALUE_FIELDS)
        self._register_concept(concept_id, domain, canonical_name, aliases=aliases)

    def _load_workbook_contexts(self) -> None:
        sap_descriptions = self._load_sap_table_descriptions()
        qad_descriptions = self._load_qad_table_descriptions()
        workday_entities, workday_fields = self._load_workday_entity_descriptions()
        self._load_metadata_mapping_sheet(sap_descriptions, qad_descriptions, workday_entities, workday_fields)

    def _load_sap_table_descriptions(self) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        if not self.sap_tables_path.exists():
            return descriptions
        workbook = load_workbook(self.sap_tables_path, read_only=True, data_only=True)
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            header = [value for value in next(worksheet.iter_rows(min_row=4, max_row=4, values_only=True), ())]
            if not header or header[0] != "Table":
                continue
            for row in worksheet.iter_rows(min_row=5, values_only=True):
                table_name = _normalize_alias(str(row[0] or ""))
                if not table_name:
                    continue
                description = " ".join(
                    part.strip()
                    for part in (str(row[1] or "").strip(), str(row[4] or "").strip(), sheet_name.replace("_", " "))
                    if part and part.strip()
                )
                descriptions[table_name] = description
        return descriptions

    def _load_qad_table_descriptions(self) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        if not self.qad_tables_path.exists():
            return descriptions
        workbook = load_workbook(self.qad_tables_path, read_only=True, data_only=True)
        worksheet = workbook["Core Tables Catalog"] if "Core Tables Catalog" in workbook.sheetnames else None
        if worksheet is None:
            return descriptions
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            table_name = _normalize_alias(str(row[0] or ""))
            if not table_name:
                continue
            description = " ".join(
                part.strip()
                for part in (
                    str(row[2] or "").strip(),
                    str(row[3] or "").strip(),
                    str(row[4] or "").strip(),
                    str(row[5] or "").strip(),
                )
                if part and part.strip()
            )
            descriptions[table_name] = description
        return descriptions

    def _load_workday_entity_descriptions(self) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
        entity_descriptions: dict[str, str] = {}
        field_descriptions: dict[tuple[str, str], str] = {}
        if not self.workday_entities_path.exists():
            return entity_descriptions, field_descriptions
        workbook = load_workbook(self.workday_entities_path, read_only=True, data_only=True)

        if "Entities" in workbook.sheetnames:
            worksheet = workbook["Entities"]
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                entity_name = _normalize_alias(str(row[1] or ""))
                if not entity_name:
                    continue
                entity_descriptions[entity_name] = " ".join(
                    part.strip()
                    for part in (
                        str(row[2] or "").strip(),
                        str(row[3] or "").strip(),
                        str(row[7] or "").strip(),
                    )
                    if part and part.strip()
                )

        for sheet_name in workbook.sheetnames:
            if not sheet_name.endswith("_Fields"):
                continue
            entity_name = _normalize_alias(sheet_name.replace("_Fields", "").replace("_", " "))
            worksheet = workbook[sheet_name]
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                field_name = _normalize_alias(str(row[1] or ""))
                if not field_name:
                    continue
                description = str(row[4] or "").strip()
                if description:
                    field_descriptions[(entity_name, field_name)] = description
        return entity_descriptions, field_descriptions

    def _load_metadata_mapping_sheet(
        self,
        sap_descriptions: dict[str, str],
        qad_descriptions: dict[str, str],
        workday_entities: dict[str, str],
        workday_fields: dict[tuple[str, str], str],
    ) -> None:
        if not self.metadata_workbook_path.exists():
            return
        workbook = load_workbook(self.metadata_workbook_path, read_only=True, data_only=True)
        if "Metadata_Mapping" not in workbook.sheetnames:
            return
        worksheet = workbook["Metadata_Mapping"]
        headers = [str(value or "") for value in next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True))]
        for row_values in worksheet.iter_rows(min_row=2, values_only=True):
            row = {headers[index]: row_values[index] for index in range(min(len(headers), len(row_values)))}
            concept_id = _normalize_alias(str(row.get("Naziv (EN)", "")))
            if not concept_id:
                continue
            category = str(row.get("Kategorija") or "general").strip()
            canonical_name = str(row.get("Naziv (EN)") or concept_id).strip()
            aliases = self._extract_aliases(row, ("Naziv (EN)", "Naziv (SR)", "SAP polje", "QAD polje", "Workday polje"), ())
            contexts: list[KnowledgeFieldContext] = []

            sap_table = str(row.get("SAP tabela") or "").strip()
            sap_field = str(row.get("SAP polje") or "").strip()
            if sap_table and sap_field:
                context = KnowledgeFieldContext(
                    system="SAP",
                    object_name=sap_table,
                    field_name=sap_field,
                    category=category,
                    object_description=sap_descriptions.get(_normalize_alias(sap_table), ""),
                    field_description=str(row.get("Napomena") or "").strip(),
                    note=str(row.get("Napomena") or "").strip(),
                )
                contexts.append(context)
                self._register_field_context(sap_field, concept_id, context)
                aliases.add(_normalize_alias(f"{sap_table} {sap_field}"))

            qad_table = str(row.get("QAD tabela") or "").strip()
            qad_field = str(row.get("QAD polje") or "").strip()
            if qad_table and qad_field:
                context = KnowledgeFieldContext(
                    system="QAD",
                    object_name=qad_table,
                    field_name=qad_field,
                    category=category,
                    object_description=qad_descriptions.get(_normalize_alias(qad_table), ""),
                    field_description=str(row.get("Napomena") or "").strip(),
                    note=str(row.get("Napomena") or "").strip(),
                )
                contexts.append(context)
                self._register_field_context(qad_field, concept_id, context)
                aliases.add(_normalize_alias(f"{qad_table} {qad_field}"))

            workday_entity = str(row.get("Workday entitet") or "").strip()
            workday_field = str(row.get("Workday polje") or "").strip()
            if workday_entity and workday_field:
                normalized_entity = _normalize_alias(workday_entity)
                normalized_field = _normalize_alias(workday_field)
                context = KnowledgeFieldContext(
                    system="Workday",
                    object_name=workday_entity,
                    field_name=workday_field,
                    category=category,
                    object_description=workday_entities.get(normalized_entity, ""),
                    field_description=workday_fields.get((normalized_entity, normalized_field), str(row.get("Napomena") or "").strip()),
                    note=str(row.get("Napomena") or "").strip(),
                )
                contexts.append(context)
                self._register_field_context(workday_field, concept_id, context)
                aliases.add(_normalize_alias(f"{workday_entity} {workday_field}"))

            self._register_concept(concept_id, category, canonical_name, aliases=aliases, contexts=contexts)

    def _extract_aliases(
        self,
        row: dict[str, object],
        single_value_fields: Iterable[str],
        multi_value_fields: Iterable[str],
    ) -> set[str]:
        aliases: set[str] = set()
        for field_name in single_value_fields:
            value = str(row.get(field_name) or "").strip()
            normalized = _normalize_alias(value)
            if normalized:
                aliases.add(normalized)
        for field_name in multi_value_fields:
            for value in _split_values(str(row.get(field_name) or "")):
                normalized = _normalize_alias(value)
                if normalized:
                    aliases.add(normalized)
        return aliases

    def _register_field_context(self, alias: str, concept_id: str, context: KnowledgeFieldContext) -> None:
        normalized_alias = _normalize_alias(alias)
        if not normalized_alias:
            return
        self._field_alias_to_contexts.setdefault(normalized_alias, []).append((concept_id, context))

    def _register_concept(
        self,
        concept_id: str,
        domain: str,
        canonical_name: str,
        aliases: Iterable[str] = (),
        contexts: Iterable[KnowledgeFieldContext] = (),
    ) -> None:
        existing = self._concepts_by_id.get(concept_id)
        merged_aliases = set(existing.aliases if existing else ())
        merged_aliases.update(alias for alias in aliases if alias)
        merged_contexts = list(existing.contexts if existing else ())
        merged_contexts.extend(list(contexts))
        unique_contexts = tuple(self._unique_contexts(merged_contexts))
        merged_context_terms = set(existing.context_terms if existing else ())
        merged_context_terms.update(self._context_terms(unique_contexts))
        concept = KnowledgeConcept(
            concept_id=concept_id,
            domain=(existing.domain if existing and existing.domain else domain) or "general",
            canonical_name=(existing.canonical_name if existing and existing.canonical_name else canonical_name) or concept_id,
            aliases=frozenset(merged_aliases),
            contexts=unique_contexts,
            context_terms=frozenset(merged_context_terms),
        )
        self._concepts_by_id[concept_id] = concept
        for alias in concept.aliases:
            self._alias_to_concepts.setdefault(alias, set()).add(concept_id)

    def _context_terms(self, contexts: Iterable[KnowledgeFieldContext]) -> set[str]:
        tokens: set[str] = set()
        for context in contexts:
            for text in (
                context.object_name,
                context.field_name,
                context.category,
                context.object_description,
                context.field_description,
                context.note,
            ):
                normalized = _normalize_alias(text)
                if not normalized:
                    continue
                tokens.update(normalized.split())
        return tokens

    def _unique_contexts(self, contexts: Iterable[KnowledgeFieldContext]) -> list[KnowledgeFieldContext]:
        seen: set[tuple[str, str, str, str, str, str, str]] = set()
        unique_contexts: list[KnowledgeFieldContext] = []
        for context in contexts:
            marker = (
                context.system,
                context.object_name,
                context.field_name,
                context.category,
                context.object_description,
                context.field_description,
                context.note,
            )
            if marker in seen:
                continue
            seen.add(marker)
            unique_contexts.append(context)
        return unique_contexts

    def _format_context(self, context: KnowledgeFieldContext) -> str:
        location = f"{context.object_name}.{context.field_name}" if context.object_name and context.field_name else context.field_name or context.object_name
        if context.object_description:
            return f"{context.system} {location} ({context.object_description})"
        return f"{context.system} {location}"


metadata_knowledge_service = MetadataKnowledgeService()