"""Generate QuickBooks knowledge overlay from promotion waves.

Reads promoted QB aliases from wave-1 and wave-2, converts them into knowledge
overlay format compatible with the runtime, and produces a durable overlay file.

This overlay is auto-loaded by metadata_knowledge_service during refresh().

Output: qb_knowledge_overlay.csv in knowledge_sources/generated/overlays/

Usage:
    python support/quickbooks/generate_qb_knowledge_overlay.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMOTED_W1_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_promoted_canonical_aliases.csv"
PROMOTED_W2_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_wave2_promoted_canonical_expansions.csv"
OVERLAY_OUTPUT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "overlays" / "qb_knowledge_overlay.csv"


def main() -> None:
    overlay_rows = []

    # Wave-1 promotions (direct + description matches)
    if PROMOTED_W1_PATH.exists():
        w1_rows = read_promoted_csv(PROMOTED_W1_PATH)
        print(f"Read {len(w1_rows)} wave-1 promoted rows from {PROMOTED_W1_PATH.name}")
        overlay_rows.extend(convert_to_overlay(w1_rows, "QuickBooks", "Wave-1 Direct/Description"))
    else:
        print(f"Warning: {PROMOTED_W1_PATH} not found, skipping wave-1")

    # Wave-2 promotions (strong candidates + knowledge_only)
    if PROMOTED_W2_PATH.exists():
        w2_rows = read_promoted_csv(PROMOTED_W2_PATH)
        print(f"Read {len(w2_rows)} wave-2 promoted rows from {PROMOTED_W2_PATH.name}")
        overlay_rows.extend(convert_to_overlay(w2_rows, "QuickBooks", "Wave-2 Strong/Knowledge"))
    else:
        print(f"Warning: {PROMOTED_W2_PATH} not found, skipping wave-2")

    # Deduplicate by (canonical_concept_id, alias) to avoid redundant entries
    seen = set()
    deduped = []
    for row in overlay_rows:
        key = (row["canonical_concept_id"], row["alias"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    write_overlay_csv(OVERLAY_OUTPUT_PATH, deduped)
    print(f"\nWrote {len(deduped)} overlay entries to {OVERLAY_OUTPUT_PATH.name}")


def read_promoted_csv(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def convert_to_overlay(
    promoted_rows: list[dict[str, str]],
    source_system: str,
    wave_label: str,
) -> list[dict[str, str]]:
    overlay_rows = []

    for row in promoted_rows:
        # Extract canonical concept info
        concept_id = (
            row.get("direct_field_canonical_concept_id", "").strip()
            or row.get("description_canonical_concept_id", "").strip()
            or row.get("top_canonical_concept_id", "").strip()
        )
        if not concept_id:
            continue

        # Extract QB field info
        qb_table = row.get("qb_table", "").strip()
        qb_field = row.get("qb_field", "").strip()
        qb_description = row.get("qb_description", "").strip()
        qb_module = row.get("qb_module", "").strip()

        if not qb_field:
            continue

        # Map module to domain for better categorization
        domain = map_module_to_domain(qb_module)

        # Create overlay entry
        overlay_rows.append({
            "entry_type": "concept_alias",
            "canonical_term": qb_field,  # Use QB field as display term
            "canonical_concept_id": concept_id,
            "alias": qb_field,
            "domain": domain,
            "source_system": source_system,
            "note": f"{wave_label}: {qb_table}.{qb_field} - {qb_description[:80]}" if qb_description else f"{wave_label}: {qb_table}.{qb_field}",
        })

    return overlay_rows


def map_module_to_domain(module: str) -> str:
    """Map QB module codes to business domains."""
    mapping = {
        "AR": "Accounts Receivable",
        "AP": "Accounts Payable",
        "GL": "General Ledger",
        "INV": "Inventory",
        "PAY": "Payroll",
        "RPT": "Reporting",
    }
    return mapping.get(module, "General")


def write_overlay_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["entry_type", "canonical_term", "canonical_concept_id", "alias", "domain", "source_system", "note"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
