"""Enrich QuickBooks canonical field contexts into the main enrichment file.

Reads quickbooks_materialized_canonical_contexts.csv and merges high-confidence
field contexts into metadata_dict/canonical_field_context_enrichment.csv, avoiding
duplicates and preserving existing entries.

This enables runtime field context lookups for QB entities without modifying the
canonical layer directly.

Output: Updated canonical_field_context_enrichment.csv with QB contexts

Usage:
    python support/quickbooks/enrich_canonical_field_contexts_with_qb.py
"""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATERIALIZED_CONTEXTS_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_materialized_canonical_contexts.csv"
ENRICHMENT_PATH = PROJECT_ROOT / "metadata_dict" / "canonical_field_context_enrichment.csv"
ENRICHMENT_BACKUP_PATH = ENRICHMENT_PATH.with_stem(f"{ENRICHMENT_PATH.stem}_backup_qb_merge")


def main() -> None:
    if not MATERIALIZED_CONTEXTS_PATH.exists():
        print(f"Error: {MATERIALIZED_CONTEXTS_PATH} not found. Run materialize_quickbooks_canonical_contexts.py first.")
        return

    # Read existing enrichment
    existing_rows = []
    fieldnames_from_existing = []
    if ENRICHMENT_PATH.exists():
        with ENRICHMENT_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames_from_existing = reader.fieldnames or []
            for row in reader:
                existing_rows.append(row)
        print(f"Read {len(existing_rows)} existing enrichment entries from {ENRICHMENT_PATH.name}")
    else:
        # Use QB materialized structure as base
        fieldnames_from_existing = ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"]

    # Build dedup key set from existing
    existing_keys = set()
    for row in existing_rows:
        key = (row.get("concept_id", ""), row.get("system", ""), row.get("object_name", ""), row.get("field_name", ""))
        existing_keys.add(key)

    # Read QB materialized contexts
    qb_rows = []
    with MATERIALIZED_CONTEXTS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            qb_rows.append(row)
    print(f"Read {len(qb_rows)} QB materialized contexts from {MATERIALIZED_CONTEXTS_PATH.name}")

    # Enrich QB rows with confidence metadata
    qb_enriched = []
    for row in qb_rows:
        key = (row.get("concept_id", ""), row.get("system", ""), row.get("object_name", ""), row.get("field_name", ""))
        if key in existing_keys:
            print(f"Skipping duplicate QB context: {key}")
            continue

        # Add confidence metadata based on source bucket
        note = row.get("note", "")
        if "direct_alias_match" in note:
            confidence = "high"
            reason = "direct_field_to_canonical_match"
        elif "description_alias_match" in note:
            confidence = "medium"
            reason = "field_description_to_canonical_match"
        else:
            confidence = "medium"
            reason = "materialized_context"

        # Add QB-specific metadata
        row["note"] = f"source=qb_materialized_contexts; confidence={confidence}; reason={reason}; {note}"
        qb_enriched.append(row)

    # Combine and write
    merged_rows = existing_rows + qb_enriched
    write_enrichment_csv(ENRICHMENT_PATH, merged_rows, fieldnames_from_existing)

    print(f"\nMerged {len(qb_enriched)} new QB contexts into enrichment.")
    print(f"Total entries: {len(merged_rows)}")
    print(f"Wrote: {ENRICHMENT_PATH}")


def write_enrichment_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
