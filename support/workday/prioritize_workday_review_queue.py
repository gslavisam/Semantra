"""Prioritize Workday post-promotion review queue by table volume.

Reads workday_datahub_classification.csv, collects post-promotion review rows,
sorts by table volume to guide steward review priority.

Output: prioritized review queue, priority summary by table.

Usage:
    python support/workday/prioritize_workday_review_queue.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import Counter, defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_datahub_classification.csv"
PRIORITY_QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_priority_review_queue.csv"
PRIORITY_SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_priority_review_summary.csv"


def main() -> None:
    if not CLASSIFICATION_PATH.exists():
        print(f"Error: {CLASSIFICATION_PATH} not found.")
        return

    rows = read_classification_csv(CLASSIFICATION_PATH)
    print(f"Read {len(rows)} rows from classification CSV.")

    # Collect review-needing rows
    review_rows = [
        row for row in rows
        if row.get("classification_bucket", "") in {"weak_canonical_candidate", "knowledge_only", "unmapped"}
    ]
    print(f"Review candidates: {len(review_rows)}")

    # Table-level aggregation
    table_counts: dict[str, int] = defaultdict(int)
    for row in review_rows:
        table = row.get("wd_table", "UNKNOWN")
        table_counts[table] += 1

    # Sort by volume (descending)
    sorted_tables = sorted(table_counts.items(), key=lambda x: -x[1])

    # Build prioritized queue
    prioritized = []
    for table, _count in sorted_tables:
        table_rows = [r for r in review_rows if r.get("wd_table", "UNKNOWN") == table]
        prioritized.extend(table_rows)

    write_csv(PRIORITY_QUEUE_PATH, prioritized, get_fieldnames(rows))
    write_summary_csv(PRIORITY_SUMMARY_PATH, sorted_tables)

    print(f"Wrote: {PRIORITY_QUEUE_PATH}")
    print(f"Wrote: {PRIORITY_SUMMARY_PATH}")
    print(f"\nTable review priority:")
    for table, count in sorted_tables[:10]:
        print(f"  {table}: {count} rows")


def read_classification_csv(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def get_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    return list(rows[0].keys()) if rows else []


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(
    path: Path,
    table_counts: list[tuple[str, int]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "table": table,
            "review_row_count": str(count),
        }
        for table, count in table_counts
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["table", "review_row_count"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
