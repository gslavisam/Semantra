"""Enrich Workday promoted aliases into the canonical glossary.

Reads promoted WD aliases from wave-1 and wave-2, merges unique entries into
metadata_dict/canonical_glossary_erp.csv.

Output: Updated canonical_glossary_erp.csv

Usage:
    python support/workday/enrich_canonical_glossary_with_wd.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMOTED_W1_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_promoted_canonical_aliases.csv"
PROMOTED_W2_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_wave2_promoted_canonical_expansions.csv"
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
        print(f"Read {len(existing_glossary)} existing glossary entries")
    else:
        glossary_fieldnames = ["concept_id", "domain", "canonical_name", "aliases", "entity", "attribute", "note"]

    # Collect WD promoted concept info
    wd_concepts: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"aliases": [], "tables": []})

    # Wave-1
    if PROMOTED_W1_PATH.exists():
        with PROMOTED_W1_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                concept_id = row.get("direct_field_canonical_concept_id", "").strip()
                wd_field = row.get("wd_column", "").strip()
                wd_table = row.get("wd_table", "").strip()
                if concept_id and wd_field:
                    if wd_field not in wd_concepts[concept_id]["aliases"]:
                        wd_concepts[concept_id]["aliases"].append(wd_field)
                    if wd_table not in wd_concepts[concept_id]["tables"]:
                        wd_concepts[concept_id]["tables"].append(wd_table)
        print(f"Processed {len(wd_concepts)} unique WD concepts from wave-1")

    # Wave-2
    if PROMOTED_W2_PATH.exists():
        with PROMOTED_W2_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                concept_id = row.get("top_canonical_concept_id", "").strip() or row.get("top_knowledge_concept_id", "").strip()
                wd_field = row.get("wd_column", "").strip()
                wd_table = row.get("wd_table", "").strip()
                if concept_id and wd_field:
                    if wd_field not in wd_concepts[concept_id]["aliases"]:
                        wd_concepts[concept_id]["aliases"].append(wd_field)
                    if wd_table not in wd_concepts[concept_id]["tables"]:
                        wd_concepts[concept_id]["tables"].append(wd_table)
        print(f"Updated WD concepts from wave-2; total unique: {len(wd_concepts)}")

    # Enrich glossary
    additions = 0
    for concept_id, info in sorted(wd_concepts.items()):
        if concept_id not in existing_glossary:
            aliases = info["aliases"]
            tables = info["tables"]
            new_row = {
                "concept_id": concept_id,
                "domain": "Human Capital Management",
                "canonical_name": concept_id,
                "aliases": ";".join(aliases),
                "entity": ";".join(tables),
                "attribute": "",
                "note": f"Auto-promoted from Workday HRDH wave-1/wave-2; fields: {', '.join(aliases)}; tables: {', '.join(tables)}",
            }
            existing_glossary[concept_id] = new_row
            additions += 1
        else:
            row = existing_glossary[concept_id]
            current_aliases = row.get("aliases", "").split(";") if row.get("aliases") else []
            new_aliases = info["aliases"]
            combined_aliases = list(set(current_aliases + new_aliases))
            row["aliases"] = ";".join(sorted(combined_aliases))

    glossary_rows = list(existing_glossary.values())
    write_glossary_csv(GLOSSARY_PATH, glossary_rows, glossary_fieldnames)
    print(f"Added {additions} new WD concepts to glossary")
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
