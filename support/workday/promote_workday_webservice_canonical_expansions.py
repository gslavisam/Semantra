"""Wave-2 Workday webservice canonical expansion.

Reads workday_webservice_classification.csv and promotes additional candidates:
- knowledge_only with a top knowledge concept
- weak_canonical_candidate with top canonical strength >= 0.50

Usage:
    python support/workday/promote_workday_webservice_canonical_expansions.py [--dry-run]
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_classification.csv"
PROMOTED_REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_wave2_promoted_canonical_expansions.csv"
REVIEW_QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_wave2_review_queue.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_webservice_wave2_promotion_summary.csv"


def main(dry_run: bool = False) -> None:
    if not CLASSIFICATION_PATH.exists():
        print(f"Error: {CLASSIFICATION_PATH} not found. Run generate_workday_webservice_canonical_inventory.py first.")
        return

    rows = read_classification_csv(CLASSIFICATION_PATH)
    print(f"Read {len(rows)} rows from classification CSV.")

    promoted: list[dict[str, str]] = []
    review_queue: list[dict[str, str]] = []
    promotion_counts: Counter[str] = Counter()
    non_promotion_counts: Counter[str] = Counter()

    for row in rows:
        bucket = row.get("classification_bucket", "")
        top_canonical_strength = safe_float(row.get("top_canonical_strength", "0"))
        top_knowledge_concept = row.get("top_knowledge_concept_id", "").strip()

        if bucket == "knowledge_only" and top_knowledge_concept:
            promoted.append(row)
            promotion_counts["knowledge_only"] += 1
        elif bucket == "weak_canonical_candidate" and top_canonical_strength >= 0.50:
            promoted.append(row)
            promotion_counts["weak_canonical_candidate"] += 1
        else:
            review_queue.append(row)
            non_promotion_counts[bucket] += 1

    if not dry_run:
        write_csv(PROMOTED_REPORT_PATH, promoted, get_fieldnames(rows))
        write_csv(REVIEW_QUEUE_PATH, review_queue, get_fieldnames(rows))
        write_summary_csv(SUMMARY_PATH, len(rows), promotion_counts, non_promotion_counts)

    print(f"Wave-2 promoted {sum(promotion_counts.values())} rows:")
    for bucket, count in sorted(promotion_counts.items()):
        print(f"  {bucket}: {count}")
    print(f"Review queue: {sum(non_promotion_counts.values())} rows:")
    for bucket, count in sorted(non_promotion_counts.items()):
        print(f"  {bucket}: {count}")

    if not dry_run:
        print(f"Wrote: {PROMOTED_REPORT_PATH}")
        print(f"Wrote: {REVIEW_QUEUE_PATH}")
        print(f"Wrote: {SUMMARY_PATH}")


def read_classification_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def get_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    return list(rows[0].keys()) if rows else []


def safe_float(value: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(
    path: Path,
    total_rows: int,
    promoted_counts: Counter[str],
    review_counts: Counter[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for bucket, count in sorted(promoted_counts.items()):
        rows.append(
            {
                "wave": "2",
                "action": "promoted",
                "bucket": bucket,
                "row_count": str(count),
                "percentage": f"{100 * count / total_rows:.1f}%" if total_rows else "0%",
            }
        )

    for bucket, count in sorted(review_counts.items()):
        rows.append(
            {
                "wave": "2",
                "action": "review_queue",
                "bucket": bucket,
                "row_count": str(count),
                "percentage": f"{100 * count / total_rows:.1f}%" if total_rows else "0%",
            }
        )

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["wave", "action", "bucket", "row_count", "percentage"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wave-2 promotion for Workday webservice canonical candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
