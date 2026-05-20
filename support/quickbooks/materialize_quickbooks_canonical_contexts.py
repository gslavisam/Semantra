"""Materialize high-confidence QuickBooks canonical field contexts.

Reads quickbooks_tables_fields_classification.csv, extracts direct_alias_match and
description_alias_match rows with high canonical confidence, and materializes durable
field context records that can be loaded into the runtime without widening global aliases.

Output: materialized contexts CSV, materialization summary.

Usage:
    python support/quickbooks/materialize_quickbooks_canonical_contexts.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_tables_fields_classification.csv"
REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_materialized_canonical_contexts.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_materialized_canonical_contexts_summary.csv"


def main() -> None:
    if not CLASSIFICATION_PATH.exists():
        print(f"Error: {CLASSIFICATION_PATH} not found. Run generate_quickbooks_tables_inventory.py first.")
        return

    rows = read_classification_csv(CLASSIFICATION_PATH)
    print(f"Read {len(rows)} rows from classification CSV.")

    materialized = []
    context_counts = Counter()

    for row in rows:
        bucket = row.get("classification_bucket", "")
        table = row.get("qb_table", "")
        field = row.get("qb_field", "")
        description = row.get("qb_description", "")
        module = row.get("qb_module", "")
        concept_id = ""

        # Material only high-confidence hits
        if bucket == "direct_alias_match":
            concept_id = row.get("direct_field_canonical_concept_id", "").strip()
            if concept_id:
                materialized.append({
                    "concept_id": concept_id,
                    "system": "QuickBooks",
                    "object_name": table,
                    "field_name": field,
                    "category": module or "General",
                    "object_description": "",
                    "field_description": description,
                    "note": "Materialized from direct_alias_match; QBO table-field context only.",
                })
                context_counts["direct_alias_match"] += 1
        elif bucket == "description_alias_match":
            concept_id = row.get("description_canonical_concept_id", "").strip()
            if concept_id:
                materialized.append({
                    "concept_id": concept_id,
                    "system": "QuickBooks",
                    "object_name": table,
                    "field_name": field,
                    "category": module or "General",
                    "object_description": "",
                    "field_description": description,
                    "note": "Materialized from description_alias_match; context from QBO field description.",
                })
                context_counts["description_alias_match"] += 1

    write_csv(REPORT_PATH, materialized, [
        "concept_id",
        "system",
        "object_name",
        "field_name",
        "category",
        "object_description",
        "field_description",
        "note",
    ])
    write_summary_csv(SUMMARY_PATH, len(rows), context_counts)

    print(f"Materialized {sum(context_counts.values())} field contexts:")
    for bucket, count in sorted(context_counts.items()):
        print(f"  {bucket}: {count}")
    print(f"Wrote: {REPORT_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def read_classification_csv(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(
    path: Path,
    total_rows: int,
    context_counts: Counter[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    for bucket, count in sorted(context_counts.items()):
        rows.append({
            "source_bucket": bucket,
            "context_count": str(count),
            "percentage_of_total": f"{100 * count / total_rows:.1f}%" if total_rows else "0%",
        })

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_bucket", "context_count", "percentage_of_total"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
