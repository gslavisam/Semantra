"""Build a prioritized SAP review queue from the current full inventory classification."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
PRIORITY_QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_priority_review_queue.csv"
PRIORITY_SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_priority_review_summary.csv"

REASON_PRIORITY = {
    "knowledge_only": 1,
    "strong_canonical_candidate": 2,
    "weak_canonical_candidate": 3,
    "unmapped": 4,
    "description_alias_match": 5,
}


def main() -> None:
    rows = list(read_csv(CLASSIFICATION_PATH))
    review_rows = [row for row in rows if row["classification_bucket"] != "direct_alias_match"]
    module_counts = Counter(row["sap_module"] or "UNKNOWN" for row in review_rows)
    module_rank = {module: index + 1 for index, (module, _count) in enumerate(module_counts.most_common())}

    prioritized_rows = []
    for row in review_rows:
        module = row["sap_module"] or "UNKNOWN"
        reason = row["classification_bucket"]
        priority_rank = module_rank.get(module, 99) * 10 + REASON_PRIORITY.get(reason, 9)
        prioritized_rows.append(
            {
                "priority_rank": str(priority_rank),
                "priority_tier": priority_tier(reason, module_rank.get(module, 99)),
                "sap_module": module,
                "sap_table": row["sap_table"],
                "sap_field": row["sap_field"],
                "sap_description": row["sap_description"],
                "classification_bucket": reason,
                "top_canonical_concept_id": row["top_canonical_concept_id"],
                "top_canonical_matches": row["top_canonical_matches"],
                "top_knowledge_concept_id": row["top_knowledge_concept_id"],
                "top_knowledge_matches": row["top_knowledge_matches"],
                "suggested_action": suggested_action(reason),
            }
        )
    prioritized_rows.sort(key=lambda row: (int(row["priority_rank"]), row["sap_module"], row["sap_table"], row["sap_field"]))

    write_csv(
        PRIORITY_QUEUE_PATH,
        prioritized_rows,
        [
            "priority_rank",
            "priority_tier",
            "sap_module",
            "sap_table",
            "sap_field",
            "sap_description",
            "classification_bucket",
            "top_canonical_concept_id",
            "top_canonical_matches",
            "top_knowledge_concept_id",
            "top_knowledge_matches",
            "suggested_action",
        ],
    )

    summary_rows = []
    for module, _count in module_counts.most_common():
        module_rows = [row for row in prioritized_rows if row["sap_module"] == module]
        module_total = len(module_rows)
        reason_counts = Counter(row["classification_bucket"] for row in module_rows)
        for reason, count in sorted(reason_counts.items(), key=lambda item: (REASON_PRIORITY.get(item[0], 9), item[0])):
            summary_rows.append(
                {
                    "sap_module": module,
                    "module_total": str(module_total),
                    "classification_bucket": reason,
                    "row_count": str(count),
                    "ratio": f"{(count / module_total):.4f}" if module_total else "0.0000",
                }
            )
    write_csv(PRIORITY_SUMMARY_PATH, summary_rows, ["sap_module", "module_total", "classification_bucket", "row_count", "ratio"])

    print(f"Prioritized review rows: {len(prioritized_rows)}")
    print(f"Wrote: {PRIORITY_QUEUE_PATH}")
    print(f"Wrote: {PRIORITY_SUMMARY_PATH}")


def priority_tier(reason: str, module_rank: int) -> str:
    if reason == "knowledge_only" and module_rank <= 4:
        return "P1"
    if reason == "strong_canonical_candidate" and module_rank <= 4:
        return "P2"
    if reason == "weak_canonical_candidate" and module_rank <= 4:
        return "P3"
    if reason == "knowledge_only":
        return "P3"
    if reason == "strong_canonical_candidate":
        return "P4"
    if reason == "unmapped" and module_rank <= 4:
        return "P4"
    return "P5"


def suggested_action(reason: str) -> str:
    if reason == "knowledge_only":
        return "promote_new_canonical_concept_or_attach_to_existing"
    if reason == "strong_canonical_candidate":
        return "promote_existing_canonical_alias_after_quick_review"
    if reason == "weak_canonical_candidate":
        return "disambiguate_canonical_target_before_promotion"
    if reason == "description_alias_match":
        return "review_description_conflict_then_promote"
    return "knowledge_ingest_or_leave_vendor_specific"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()