"""Apply the safest SAP P2 auto-alias candidates to canonical artifacts.

Input:
- knowledge_sources/generated/runtime/sap/batches/sap_p2_auto_alias_candidates.csv

Updates:
- metadata_dict/canonical_glossary_erp.csv (aliases only)
- metadata_dict/canonical_field_context_enrichment.csv (SAP context rows)

Output:
- knowledge_sources/generated/runtime/sap/batches/sap_p2_auto_alias_apply_report.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.services.metadata_knowledge_service import CANONICAL_GLOSSARY_HEADERS, metadata_knowledge_service
from app.utils.knowledge_text import filter_canonical_aliases, normalize_canonical_alias_text, split_csv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "batches" / "sap_p2_auto_alias_candidates.csv"
GLOSSARY_PATH = PROJECT_ROOT / "metadata_dict" / "canonical_glossary_erp.csv"
CONTEXT_PATH = PROJECT_ROOT / "metadata_dict" / "canonical_field_context_enrichment.csv"
REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "batches" / "sap_p2_auto_alias_apply_report.csv"

CONTEXT_HEADERS = ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"]
REPORT_HEADERS = [
    "sap_module",
    "sap_table",
    "sap_field",
    "sap_description",
    "concept_id",
    "alias_added",
    "context_added",
    "status",
]


def main() -> None:
    metadata_knowledge_service.refresh()

    candidates = list(read_csv(CANDIDATES_PATH))
    glossary_rows = load_glossary_rows(GLOSSARY_PATH)
    glossary_by_concept = {row["concept_id"]: row for row in glossary_rows}

    context_rows = list(read_csv(CONTEXT_PATH))
    existing_context_keys = {
        (
            row.get("concept_id", "").strip(),
            row.get("system", "").strip(),
            row.get("object_name", "").strip(),
            row.get("field_name", "").strip(),
        )
        for row in context_rows
    }

    report_rows: list[dict[str, str]] = []
    for row in candidates:
        concept_id = (row.get("top_canonical_concept_id") or "").strip()
        alias = normalize_canonical_alias_text((row.get("sap_field") or "").strip())

        if not concept_id or not alias:
            report_rows.append(build_report(row, concept_id, False, False, "skipped_missing_concept_or_alias"))
            continue

        glossary_row = glossary_by_concept.get(concept_id)
        if glossary_row is None:
            report_rows.append(build_report(row, concept_id, False, False, "skipped_missing_concept"))
            continue

        existing_aliases = {
            normalized
            for normalized in (
                normalize_canonical_alias_text(value)
                for value in split_csv_values(glossary_row.get("aliases") or "")
            )
            if normalized
        }
        alias_added = alias not in existing_aliases
        if alias_added:
            existing_aliases.add(alias)
            glossary_row["aliases"] = ", ".join(sorted(filter_canonical_aliases(existing_aliases)))

        sap_table = (row.get("sap_table") or "").strip()
        sap_field = (row.get("sap_field") or "").strip()
        context_key = (concept_id, "SAP", sap_table, sap_field)
        context_added = context_key not in existing_context_keys
        if context_added:
            concept = metadata_knowledge_service._canonical_concepts_by_id.get(concept_id)
            context_rows.append(
                {
                    "concept_id": concept_id,
                    "system": "SAP",
                    "object_name": sap_table,
                    "field_name": sap_field,
                    "category": concept.entity if concept is not None else concept_id.split(".", 1)[0],
                    "object_description": "",
                    "field_description": (row.get("sap_description") or "").strip(),
                    "note": (
                        "source=sap_p2_auto_alias_candidates; confidence=high; "
                        f"reason=single_top_canonical_candidate; module={(row.get('sap_module') or '').strip() or 'UNKNOWN'}"
                    ),
                }
            )
            existing_context_keys.add(context_key)

        status = "applied" if alias_added or context_added else "already_present"
        report_rows.append(build_report(row, concept_id, alias_added, context_added, status))

    write_glossary_rows(GLOSSARY_PATH, glossary_rows)
    write_csv(CONTEXT_PATH, context_rows, CONTEXT_HEADERS)
    write_csv(REPORT_PATH, report_rows, REPORT_HEADERS)

    alias_adds = sum(1 for row in report_rows if row["alias_added"] == "true")
    context_adds = sum(1 for row in report_rows if row["context_added"] == "true")
    print(f"Candidates processed: {len(candidates)}")
    print(f"Alias additions: {alias_adds}")
    print(f"Context additions: {context_adds}")
    print(f"Wrote: {REPORT_PATH}")


def build_report(row: dict[str, str], concept_id: str, alias_added: bool, context_added: bool, status: str) -> dict[str, str]:
    return {
        "sap_module": row.get("sap_module", ""),
        "sap_table": row.get("sap_table", ""),
        "sap_field": row.get("sap_field", ""),
        "sap_description": row.get("sap_description", ""),
        "concept_id": concept_id,
        "alias_added": str(alias_added).lower(),
        "context_added": str(context_added).lower(),
        "status": status,
    }


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_glossary_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{header: str(row.get(header) or "").strip() for header in CANONICAL_GLOSSARY_HEADERS} for row in reader]


def write_glossary_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_GLOSSARY_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
