"""Generate Workday webservice knowledge overlay from promotion waves.

Reads wave-1 and wave-2 Workday webservice promoted rows and converts them to
knowledge overlay format compatible with runtime import/API.

Primary output:
- knowledge_sources/generated/overlays/wd_webservice_knowledge_overlay.csv

Convenience sync output (for legacy runtime file-based loading):
- metadata_dict/wd_hr_knowledge_overlay.csv

Usage:
    python support/workday/generate_wd_webservice_knowledge_overlay.py
"""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMOTED_W1_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_promoted_canonical_aliases.csv"
PROMOTED_W2_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_wave2_promoted_canonical_expansions.csv"
OVERLAY_OUTPUT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "overlays" / "wd_webservice_knowledge_overlay.csv"
METADATA_DICT_SYNC_PATH = PROJECT_ROOT / "metadata_dict" / "wd_hr_knowledge_overlay.csv"


def main() -> None:
    overlay_rows: list[dict[str, str]] = []

    if PROMOTED_W1_PATH.exists():
        w1_rows = read_promoted_csv(PROMOTED_W1_PATH)
        print(f"Read {len(w1_rows)} wave-1 promoted rows from {PROMOTED_W1_PATH.name}")
        overlay_rows.extend(convert_to_overlay(w1_rows, "Workday_Webservice", "Wave-1 Direct/Description"))
    else:
        print(f"Warning: {PROMOTED_W1_PATH} not found, skipping wave-1")

    if PROMOTED_W2_PATH.exists():
        w2_rows = read_promoted_csv(PROMOTED_W2_PATH)
        print(f"Read {len(w2_rows)} wave-2 promoted rows from {PROMOTED_W2_PATH.name}")
        overlay_rows.extend(convert_to_overlay(w2_rows, "Workday_Webservice", "Wave-2 Strong/Knowledge"))
    else:
        print(f"Warning: {PROMOTED_W2_PATH} not found, skipping wave-2")

    deduped = dedupe_overlay_rows(overlay_rows)

    write_overlay_csv(OVERLAY_OUTPUT_PATH, deduped)
    print(f"Wrote {len(deduped)} entries to {OVERLAY_OUTPUT_PATH.name}")

    write_overlay_csv(METADATA_DICT_SYNC_PATH, deduped)
    print(f"Synced {len(deduped)} entries to {METADATA_DICT_SYNC_PATH.name}")


def read_promoted_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
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
    overlay_rows: list[dict[str, str]] = []

    for row in promoted_rows:
        concept_id = (
            row.get("direct_field_canonical_concept_id", "").strip()
            or row.get("description_canonical_concept_id", "").strip()
            or row.get("top_canonical_concept_id", "").strip()
            or row.get("top_knowledge_concept_id", "").strip()
        )
        if not concept_id:
            continue

        wd_entity = row.get("wd_entity", "").strip()
        wd_field = row.get("wd_field", "").strip()
        wd_type = row.get("wd_type", "").strip()
        wd_description = row.get("wd_description", "").strip()

        if not wd_field:
            continue

        note = f"{wave_label}: {wd_entity}.{wd_field} ({wd_type})"
        if wd_description:
            note = f"{note} - {wd_description[:120]}"

        overlay_rows.append(
            {
                "entry_type": "concept_alias",
                "canonical_term": wd_field,
                "canonical_concept_id": concept_id,
                "alias": wd_field,
                "domain": "Human Capital Management",
                "source_system": source_system,
                "note": note,
            }
        )

    return overlay_rows


def dedupe_overlay_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []

    for row in rows:
        key = (row["canonical_concept_id"], row["alias"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def write_overlay_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_type",
        "canonical_term",
        "canonical_concept_id",
        "alias",
        "domain",
        "source_system",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
