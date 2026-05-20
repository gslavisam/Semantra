"""Materialize high-confidence SAP canonical contexts into the enrichment CSV.

This script turns the current SAP inventory classification into durable canonical
field-context rows without broadening the global canonical alias registry.

It uses only high-confidence rows:
- direct_alias_match
- description_alias_match

Outputs under knowledge_sources/generated/runtime/sap/:
    - sap_materialized_canonical_contexts.csv
    - sap_materialized_canonical_contexts_summary.csv
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from app.services.metadata_knowledge_service import metadata_knowledge_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_materialized_canonical_contexts.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_materialized_canonical_contexts_summary.csv"
CONTEXT_HEADERS = ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"]
REPORT_HEADERS = [
    "sap_module",
    "sap_table",
    "sap_field",
    "sap_description",
    "classification_bucket",
    "canonical_concept_id",
    "context_added",
    "status",
]


def main() -> None:
    classification_rows = list(read_csv(CLASSIFICATION_PATH))
    context_path = metadata_knowledge_service.canonical_glossary_path.parent / "canonical_field_context_enrichment.csv"
    context_rows = list(read_csv(context_path))
    existing_context_keys = {
        (row["concept_id"], row["system"], row["object_name"], row["field_name"])
        for row in context_rows
    }

    report_rows: list[dict[str, str]] = []
    for row in classification_rows:
        bucket = row.get("classification_bucket", "").strip()
        if bucket not in {"direct_alias_match", "description_alias_match"}:
            continue
        concept_id = canonical_concept_id_for_row(row)
        if not concept_id:
            continue

        context_key = (concept_id, "SAP", row.get("sap_table", "").strip(), row.get("sap_field", "").strip())
        context_added = context_key not in existing_context_keys
        if context_added:
            context_rows.append(
                {
                    "concept_id": concept_id,
                    "system": "SAP",
                    "object_name": row.get("sap_table", "").strip(),
                    "field_name": row.get("sap_field", "").strip(),
                    "category": concept_id.split(".", 1)[0] if "." in concept_id else "general",
                    "object_description": row.get("sap_table_description", "").strip(),
                    "field_description": row.get("sap_description", "").strip(),
                    "note": (
                        "source=sap_full_inventory_classification; confidence=high; "
                        f"reason={bucket}; module={row.get('sap_module', '').strip() or 'UNKNOWN'}; mode=context_only"
                    ),
                }
            )
            existing_context_keys.add(context_key)

        report_rows.append(
            {
                "sap_module": row.get("sap_module", ""),
                "sap_table": row.get("sap_table", ""),
                "sap_field": row.get("sap_field", ""),
                "sap_description": row.get("sap_description", ""),
                "classification_bucket": bucket,
                "canonical_concept_id": concept_id,
                "context_added": str(context_added).lower(),
                "status": "added" if context_added else "already_present",
            }
        )

    write_csv(context_path, context_rows, CONTEXT_HEADERS)
    write_csv(REPORT_PATH, report_rows, REPORT_HEADERS)
    write_summary(report_rows, len(classification_rows))
    metadata_knowledge_service.refresh()

    print(f"Processed classification rows: {len(classification_rows)}")
    print(f"Materialized context rows: {sum(1 for row in report_rows if row['context_added'] == 'true')}")
    print(f"Canonical context file rows: {len(context_rows)}")
    print(f"Wrote: {REPORT_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def canonical_concept_id_for_row(row: dict[str, str]) -> str:
    bucket = row.get("classification_bucket", "").strip()
    if bucket == "direct_alias_match":
        return (
            row.get("direct_field_canonical_concept_id", "").strip()
            or row.get("top_canonical_concept_id", "").strip()
        )
    if bucket == "description_alias_match":
        return row.get("description_canonical_concept_id", "").strip()
    return ""


def write_summary(report_rows: list[dict[str, str]], total_rows: int) -> None:
    rows: list[dict[str, str]] = []
    for scope, counts in (
        ("classification_bucket", Counter(row["classification_bucket"] for row in report_rows)),
        ("status", Counter(row["status"] for row in report_rows)),
    ):
        for label, count in sorted(counts.items()):
            rows.append(
                {
                    "scope": scope,
                    "label": label,
                    "row_count": str(count),
                    "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000",
                }
            )
    write_csv(SUMMARY_PATH, rows, ["scope", "label", "row_count", "ratio"])


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()