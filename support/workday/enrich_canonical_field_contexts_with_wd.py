"""Enrich Workday canonical field contexts into the main enrichment file.

Reads workday_materialized_canonical_contexts.csv and merges field contexts
into metadata_dict/canonical_field_context_enrichment.csv, avoiding duplicates.

Output: Updated canonical_field_context_enrichment.csv

Usage:
    python support/workday/enrich_canonical_field_contexts_with_wd.py
"""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATERIALIZED_CONTEXTS_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_materialized_canonical_contexts.csv"
ENRICHMENT_PATH = PROJECT_ROOT / "metadata_dict" / "canonical_field_context_enrichment.csv"


def main() -> None:
    if not MATERIALIZED_CONTEXTS_PATH.exists():
        print(f"Error: {MATERIALIZED_CONTEXTS_PATH} not found.")
        return

    # Read existing enrichment
    existing_rows = []
    fieldnames = []
    if ENRICHMENT_PATH.exists():
        with ENRICHMENT_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            for row in reader:
                existing_rows.append(row)
        print(f"Read {len(existing_rows)} existing enrichment entries")
    else:
        fieldnames = ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"]

    # Build dedup key set
    existing_keys = set()
    for row in existing_rows:
        key = (row.get("concept_id", ""), row.get("system", ""), row.get("object_name", ""), row.get("field_name", ""))
        existing_keys.add(key)

    # Read WD materialized contexts
    wd_rows = []
    with MATERIALIZED_CONTEXTS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            wd_rows.append(row)
    print(f"Read {len(wd_rows)} WD materialized contexts")

    # Enrich with confidence metadata
    wd_enriched = []
    for row in wd_rows:
        key = (row.get("concept_id", ""), row.get("system", ""), row.get("object_name", ""), row.get("field_name", ""))
        if key in existing_keys:
            continue

        note = row.get("note", "")
        if "direct_alias_match" in note:
            confidence = "high"
        elif "knowledge_only" in note:
            confidence = "medium"
        elif "weak_canonical_candidate" in note:
            confidence = "low"
        else:
            confidence = "medium"

        row["note"] = f"source=wd_datahub_materialized; confidence={confidence}; {note}"
        wd_enriched.append(row)

    merged_rows = existing_rows + wd_enriched
    write_csv(ENRICHMENT_PATH, merged_rows, fieldnames)

    print(f"Merged {len(wd_enriched)} new WD contexts into enrichment")
    print(f"Total entries: {len(merged_rows)}")
    print(f"Wrote: {ENRICHMENT_PATH}")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
