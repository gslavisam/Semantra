"""Prioritize QuickBooks post-promotion review queue by module volume and field frequency.

Reads quickbooks_tables_fields_classification.csv, collects post-promotion review rows,
sorts by module volume and field frequency to guide steward review priority.

Output: prioritized review queue, priority summary by module.

Usage:
    python support/quickbooks/prioritize_quickbooks_review_queue.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import Counter, defaultdict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_tables_fields_classification.csv"
PRIORITY_QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_priority_review_queue.csv"
PRIORITY_SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "quickbooks" / "quickbooks_priority_review_summary.csv"


def main() -> None:
    if not CLASSIFICATION_PATH.exists():
        print(f"Error: {CLASSIFICATION_PATH} not found. Run generate_quickbooks_tables_inventory.py first.")
        return

    rows = read_classification_csv(CLASSIFICATION_PATH)
    print(f"Read {len(rows)} rows from classification CSV.")

    # Collect review-needing rows (weak candidates, unmapped)
    review_rows = [
        row for row in rows
        if row.get("classification_bucket", "") in {"weak_canonical_candidate", "unmapped"}
    ]
    print(f"Review candidates: {len(review_rows)}")

    # Module-level aggregation
    module_counts: dict[str, int] = defaultdict(int)
    module_field_freq: dict[str, Counter[str]] = defaultdict(Counter)
    for row in review_rows:
        module = row.get("qb_module", "UNKNOWN")
        field = row.get("qb_field", "")
        module_counts[module] += 1
        module_field_freq[module][field] += 1

    # Sort by module volume (descending)
    sorted_modules = sorted(module_counts.items(), key=lambda x: -x[1])

    # Build prioritized queue: append rows grouped by module (high-volume first)
    prioritized = []
    for module, _count in sorted_modules:
        module_rows = [r for r in review_rows if r.get("qb_module", "UNKNOWN") == module]
        # Sort within module by field frequency (high-freq first)
        field_freq = module_field_freq.get(module, Counter())
        module_rows.sort(key=lambda r: -field_freq.get(r.get("qb_field", ""), 0))
        prioritized.extend(module_rows)

    write_csv(PRIORITY_QUEUE_PATH, prioritized, get_fieldnames(rows))
    write_summary_csv(PRIORITY_SUMMARY_PATH, sorted_modules, module_field_freq)

    print(f"Wrote: {PRIORITY_QUEUE_PATH}")
    print(f"Wrote: {PRIORITY_SUMMARY_PATH}")
    print(f"\nModule review priority:")
    for module, count in sorted_modules:
        print(f"  {module}: {count} rows")


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
    module_counts: list[tuple[str, int]],
    module_field_freq: dict[str, Counter[str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    for module, count in module_counts:
        field_freq = module_field_freq.get(module, Counter())
        top_fields = ", ".join([f"{field}({freq})" for field, freq in field_freq.most_common(5)])
        rows.append({
            "module": module,
            "review_row_count": str(count),
            "top_5_fields_by_freq": top_fields,
        })

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["module", "review_row_count", "top_5_fields_by_freq"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
