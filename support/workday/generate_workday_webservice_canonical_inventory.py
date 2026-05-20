"""Classify Workday webservice inventory against canonical business concepts.

Reads hr_wd_webservice_inventory.csv generated from hr_wd.xml, classifies each
entity-field row against current canonical and knowledge layers, and outputs
reports that match SAP/QB pipeline conventions.

Usage:
    python support/workday/generate_workday_webservice_canonical_inventory.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from app.models.schema import ColumnProfile
from app.services.metadata_knowledge_service import metadata_knowledge_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "hr_wd_webservice_inventory.csv"
OUTPUT_DIR = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday"
CLASSIFICATION_OUTPUT_PATH = OUTPUT_DIR / "workday_webservice_classification.csv"
GAP_CANDIDATES_PATH = OUTPUT_DIR / "workday_webservice_gap_candidates.csv"
SUMMARY_PATH = OUTPUT_DIR / "workday_webservice_summary.csv"


def main() -> None:
    if not INPUT_PATH.exists():
        print(f"Error: {INPUT_PATH} not found. Run generate_workday_webservice_inventory.py first.")
        return

    metadata_knowledge_service.refresh()
    print("Knowledge/canonical runtime refreshed")

    rows = read_csv(INPUT_PATH)
    print(f"Loaded {len(rows)} Workday webservice rows")

    classified_rows: list[dict[str, str]] = []
    bucket_counts: Counter[str] = Counter()

    for row in rows:
        classified = classify_row(row)
        classified_rows.append(classified)
        bucket_counts[classified["classification_bucket"]] += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(classified_rows[0].keys()) if classified_rows else []
    write_csv(CLASSIFICATION_OUTPUT_PATH, classified_rows, fieldnames)

    gap_candidates = [
        row for row in classified_rows
        if row["classification_bucket"] in {"knowledge_only", "unmapped"}
    ]
    write_csv(GAP_CANDIDATES_PATH, gap_candidates, fieldnames)

    summary_rows = [
        {
            "bucket": bucket,
            "count": str(count),
            "percentage": f"{100 * count / len(classified_rows):.1f}%" if classified_rows else "0%",
        }
        for bucket, count in sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    write_summary_csv(SUMMARY_PATH, summary_rows)

    print("\nWorkday webservice classification:")
    for bucket, count in sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {bucket}: {count}")
    print(f"\nWrote: {CLASSIFICATION_OUTPUT_PATH}")
    print(f"Wrote: {GAP_CANDIDATES_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def classify_row(row: dict[str, str]) -> dict[str, str]:
    entity = str(row.get("wd_entity") or "").strip()
    field = str(row.get("wd_field") or "").strip()
    wd_type = str(row.get("wd_type") or "").strip()
    description = str(row.get("wd_description") or "").strip()

    profile = ColumnProfile(
        name=field,
        normalized_name=field.lower().replace("_", ""),
        description=f"{entity} {field} {wd_type} {description}".strip(),
        declared_type=wd_type,
        dtype="object",
        null_ratio=0.5,
        unique_ratio=0.5,
        non_null_count=0,
    )

    knowledge_matches = metadata_knowledge_service.match_concepts(
        profile,
        prefer_metadata_text=True,
    )
    top_knowledge = knowledge_matches[0] if knowledge_matches else None

    canonical_matches = metadata_knowledge_service.match_canonical_concepts(
        profile,
        prefer_metadata_text=True,
    )
    top_canonical = canonical_matches[0] if canonical_matches else None

    direct_field_canonical = ""
    description_canonical = ""

    try:
        resolved_field = metadata_knowledge_service.resolve_canonical_concept_id(field)
        if resolved_field:
            direct_field_canonical = resolved_field
    except Exception:
        pass

    if not direct_field_canonical and description:
        try:
            resolved_desc = metadata_knowledge_service.resolve_canonical_concept_id(description)
            if resolved_desc:
                description_canonical = resolved_desc
        except Exception:
            pass

    bucket = classify_bucket(
        bool(direct_field_canonical),
        bool(description_canonical),
        top_canonical,
        top_knowledge,
    )

    return {
        "wd_entity": entity,
        "wd_field": field,
        "wd_type": wd_type,
        "wd_description": description,
        "classification_bucket": bucket,
        "direct_field_canonical_concept_id": direct_field_canonical,
        "description_canonical_concept_id": description_canonical,
        "top_canonical_concept_id": top_canonical.concept_id if top_canonical else "",
        "top_canonical_strength": f"{top_canonical.strength:.3f}" if top_canonical else "",
        "top_knowledge_concept_id": top_knowledge.concept_id if top_knowledge else "",
        "top_knowledge_strength": f"{top_knowledge.strength:.3f}" if top_knowledge else "",
    }


def classify_bucket(
    has_direct_field: bool,
    has_description: bool,
    top_canonical,
    top_knowledge,
) -> str:
    if has_direct_field:
        return "direct_alias_match"
    if has_description:
        return "description_alias_match"
    if top_canonical and top_canonical.strength >= 0.75:
        return "strong_canonical_candidate"
    if top_canonical:
        return "weak_canonical_candidate"
    if top_knowledge:
        return "knowledge_only"
    return "unmapped"


def read_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
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


def write_summary_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", "count", "percentage"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
