"""Generate Workday knowledge overlay from promotion waves.

Reads promoted Workday aliases from wave-1 and wave-2, converts them into knowledge
overlay format compatible with the runtime, and produces a durable overlay file.

Output: wd_datahub_knowledge_overlay.csv in knowledge_sources/generated/overlays/

Usage:
    python support/workday/generate_wd_knowledge_overlay.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMOTED_W1_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_promoted_canonical_aliases.csv"
PROMOTED_W2_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_wave2_promoted_canonical_expansions.csv"
OVERLAY_OUTPUT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "overlays" / "wd_datahub_knowledge_overlay.csv"
METADATA_DICT_SYNC_PATH = PROJECT_ROOT / "metadata_dict" / "wd_datahub_knowledge_overlay.csv"


def main() -> None:
    overlay_rows = []

    # Wave-1 promotions
    if PROMOTED_W1_PATH.exists():
        w1_rows = read_promoted_csv(PROMOTED_W1_PATH)
        print(f"Read {len(w1_rows)} wave-1 promoted rows")
        overlay_rows.extend(convert_to_overlay(w1_rows, "Workday_HRDH", "Wave-1 Direct"))
    else:
        print(f"Warning: {PROMOTED_W1_PATH} not found")

    # Wave-2 promotions
    if PROMOTED_W2_PATH.exists():
        w2_rows = read_promoted_csv(PROMOTED_W2_PATH)
        print(f"Read {len(w2_rows)} wave-2 promoted rows")
        overlay_rows.extend(convert_to_overlay(w2_rows, "Workday_HRDH", "Wave-2 Knowledge/Weak"))
    else:
        print(f"Warning: {PROMOTED_W2_PATH} not found")

    # Deduplicate
    seen = set()
    deduped = []
    for row in overlay_rows:
        key = (row["canonical_concept_id"], row["alias"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    write_overlay_csv(OVERLAY_OUTPUT_PATH, deduped)
    print(f"\nWrote {len(deduped)} overlay entries to {OVERLAY_OUTPUT_PATH.name}")

    write_overlay_csv(METADATA_DICT_SYNC_PATH, deduped)
    print(f"Synced {len(deduped)} overlay entries to {METADATA_DICT_SYNC_PATH.name}")


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
        # Extract canonical concept
        concept_id = (
            row.get("direct_field_canonical_concept_id", "").strip()
            or row.get("top_canonical_concept_id", "").strip()
        )
        if not concept_id:
            continue

        # Extract WD field
        wd_field = row.get("wd_column", "").strip()
        wd_table = row.get("wd_table", "").strip()
        wd_type = row.get("wd_type", "").strip()

        if not wd_field:
            continue

        overlay_rows.append({
            "entry_type": "concept_alias",
            "canonical_term": wd_field,
            "canonical_concept_id": concept_id,
            "alias": wd_field,
            "domain": "Human Capital Management",
            "source_system": source_system,
            "note": f"{wave_label}: {wd_table}.{wd_field} ({wd_type})",
        })

    return overlay_rows


def write_overlay_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["entry_type", "canonical_term", "canonical_concept_id", "alias", "domain", "source_system", "note"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
