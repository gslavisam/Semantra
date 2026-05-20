"""Enrich QuickBooks promoted aliases into the canonical glossary.

Reads promoted QB aliases from wave-1 and wave-2, extracts canonical concept IDs,
and merges unique entries into metadata_dict/canonical_glossary_erp.csv.

This enriches the canonical layer with QB-sourced canonical concepts without
modifying existing canonical entries (only adds new or updates with QB context).

Output: Updated canonical_glossary_erp.csv with QB promoted aliases

Usage:
    python support/quickbooks/enrich_canonical_glossary_with_qb.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMOTED_W1_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_promoted_canonical_aliases.csv"
PROMOTED_W2_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_wave2_promoted_canonical_expansions.csv"
GLOSSARY_PATH = PROJECT_ROOT / "metadata_dict" / "canonical_glossary_erp.csv"


def main() -> None:
    # Read existing glossary
    existing_glossary = {}
    glossary_fieldnames = []
    if GLOSSARY_PATH.exists():
        with GLOSSARY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            glossary_fieldnames = reader.fieldnames or []
            for row in reader:
                concept_id = row.get("concept_id", "").strip()
                if concept_id:
                    existing_glossary[concept_id] = row
        print(f"Read {len(existing_glossary)} existing glossary entries from {GLOSSARY_PATH.name}")
    else:
        glossary_fieldnames = ["concept_id", "domain", "canonical_name", "aliases", "entity", "attribute", "note"]

    # Collect QB promoted concept info
    qb_concepts: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"aliases": [], "fields": [], "qb_tables": []})

    # Process wave-1
    if PROMOTED_W1_PATH.exists():
        with PROMOTED_W1_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                concept_id = row.get("direct_field_canonical_concept_id", "").strip() or row.get("description_canonical_concept_id", "").strip()
                qb_field = row.get("qb_field", "").strip()
                qb_table = row.get("qb_table", "").strip()
                if concept_id and qb_field:
                    if qb_field not in qb_concepts[concept_id]["aliases"]:
                        qb_concepts[concept_id]["aliases"].append(qb_field)
                    if qb_table not in qb_concepts[concept_id]["qb_tables"]:
                        qb_concepts[concept_id]["qb_tables"].append(qb_table)
        print(f"Processed {len(qb_concepts)} unique QB concepts from wave-1")

    # Process wave-2
    if PROMOTED_W2_PATH.exists():
        with PROMOTED_W2_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                concept_id = row.get("top_canonical_concept_id", "").strip()
                qb_field = row.get("qb_field", "").strip()
                qb_table = row.get("qb_table", "").strip()
                if concept_id and qb_field:
                    if qb_field not in qb_concepts[concept_id]["aliases"]:
                        qb_concepts[concept_id]["aliases"].append(qb_field)
                    if qb_table not in qb_concepts[concept_id]["qb_tables"]:
                        qb_concepts[concept_id]["qb_tables"].append(qb_table)
        print(f"Updated QB concepts from wave-2; total unique: {len(qb_concepts)}")

    # Enrich glossary with QB-sourced concepts
    additions = 0
    for concept_id, info in sorted(qb_concepts.items()):
        if concept_id not in existing_glossary:
            # New concept - add with QB context
            aliases = info["aliases"]
            qb_tables = info["qb_tables"]
            new_row = {
                "concept_id": concept_id,
                "domain": "QuickBooks",
                "canonical_name": concept_id,  # Use ID as canonical term for now
                "aliases": ";".join(aliases),
                "entity": ";".join(qb_tables),
                "attribute": "",
                "note": f"Auto-promoted from QuickBooks wave-1/wave-2 mappings; fields: {', '.join(aliases)}; QB tables: {', '.join(qb_tables)}",
            }
            existing_glossary[concept_id] = new_row
            additions += 1
        else:
            # Existing concept - add QB aliases if not present
            row = existing_glossary[concept_id]
            current_aliases = row.get("aliases", "").split(";") if row.get("aliases") else []
            new_aliases = info["aliases"]
            combined_aliases = list(set(current_aliases + new_aliases))
            row["aliases"] = ";".join(sorted(combined_aliases))
            # Append QB context to note
            row["note"] = (row.get("note", "") or "") + f"; QB enrichment: fields={', '.join(new_aliases)}"

    # Write updated glossary
    glossary_rows = list(existing_glossary.values())
    write_glossary_csv(GLOSSARY_PATH, glossary_rows, glossary_fieldnames)
    print(f"\nAdded {additions} new QB concepts to glossary")
    print(f"Total glossary entries: {len(glossary_rows)}")
    print(f"Wrote: {GLOSSARY_PATH}")


def write_glossary_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
