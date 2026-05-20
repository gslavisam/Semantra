"""Build module-based SAP P1/P2 review batches from the priority queue.

This script is non-destructive: it does not modify canonical glossary or contexts.
It materializes actionable batch files for focused stewardship rounds.

Outputs under knowledge_sources/generated/runtime/sap/batches/:
- sap_p1_p2_module_batch_summary.csv
- sap_p2_auto_alias_candidates.csv
- sap_p1_attach_candidates.csv
- modules/<module>_p1_batch.csv
- modules/<module>_p2_batch.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_priority_review_queue.csv"
OUTPUT_DIR = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "batches"
MODULE_DIR = OUTPUT_DIR / "modules"


QUEUE_FIELDS = [
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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SAP module-level P1/P2 review batches.")
    parser.add_argument(
        "--max-modules",
        type=int,
        default=0,
        help="Optional cap of modules by volume; 0 means all modules.",
    )
    parser.add_argument(
        "--min-p2-auto-strength",
        type=float,
        default=0.80,
        help="Minimum top canonical strength to include a row in P2 auto alias candidate list.",
    )
    parser.add_argument(
        "--min-p1-attach-strength",
        type=float,
        default=0.90,
        help="Minimum top knowledge strength to include a row in P1 attach candidate list.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MODULE_DIR.mkdir(parents=True, exist_ok=True)

    rows = list(read_csv(QUEUE_PATH))
    p1_rows = [row for row in rows if row.get("priority_tier") == "P1"]
    p2_rows = [row for row in rows if row.get("priority_tier") == "P2"]

    module_rows = defaultdict(list)
    for row in p1_rows + p2_rows:
        module_rows[row.get("sap_module") or "UNKNOWN"].append(row)

    ordered_modules = sorted(module_rows.keys(), key=lambda mod: len(module_rows[mod]), reverse=True)
    if args.max_modules > 0:
        ordered_modules = ordered_modules[: args.max_modules]

    summary_rows: list[dict[str, str]] = []
    auto_p2_rows: list[dict[str, str]] = []
    auto_p1_rows: list[dict[str, str]] = []

    for module in ordered_modules:
        module_subset = module_rows[module]
        p1_subset = [row for row in module_subset if row.get("priority_tier") == "P1"]
        p2_subset = [row for row in module_subset if row.get("priority_tier") == "P2"]

        p1_path = MODULE_DIR / f"{sanitize_module(module)}_p1_batch.csv"
        p2_path = MODULE_DIR / f"{sanitize_module(module)}_p2_batch.csv"
        write_csv(p1_path, p1_subset, QUEUE_FIELDS)
        write_csv(p2_path, p2_subset, QUEUE_FIELDS)

        classification_counts = Counter(row.get("classification_bucket", "") for row in module_subset)
        summary_rows.append(
            {
                "sap_module": module,
                "p1_rows": str(len(p1_subset)),
                "p2_rows": str(len(p2_subset)),
                "p1_p2_total": str(len(module_subset)),
                "knowledge_only": str(classification_counts.get("knowledge_only", 0)),
                "strong_canonical_candidate": str(classification_counts.get("strong_canonical_candidate", 0)),
                "p1_file": str(p1_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "p2_file": str(p2_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            }
        )

        auto_p2_rows.extend(build_auto_p2_candidates(p2_subset, args.min_p2_auto_strength))
        auto_p1_rows.extend(build_auto_p1_candidates(p1_subset, args.min_p1_attach_strength))

    write_csv(OUTPUT_DIR / "sap_p1_p2_module_batch_summary.csv", summary_rows, [
        "sap_module",
        "p1_rows",
        "p2_rows",
        "p1_p2_total",
        "knowledge_only",
        "strong_canonical_candidate",
        "p1_file",
        "p2_file",
    ])
    write_csv(OUTPUT_DIR / "sap_p2_auto_alias_candidates.csv", auto_p2_rows, [
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "top_canonical_concept_id",
        "top_canonical_strength",
        "top_canonical_matches",
        "candidate_reason",
    ])
    write_csv(OUTPUT_DIR / "sap_p1_attach_candidates.csv", auto_p1_rows, [
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "top_knowledge_concept_id",
        "top_knowledge_strength",
        "top_knowledge_matches",
        "candidate_reason",
    ])

    print(f"P1 rows: {len(p1_rows)}")
    print(f"P2 rows: {len(p2_rows)}")
    print(f"Modules exported: {len(ordered_modules)}")
    print(f"Auto P2 alias candidates: {len(auto_p2_rows)}")
    print(f"Auto P1 attach candidates: {len(auto_p1_rows)}")
    print(f"Wrote: {OUTPUT_DIR / 'sap_p1_p2_module_batch_summary.csv'}")


def build_auto_p2_candidates(rows: list[dict[str, str]], min_strength: float) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in rows:
        concept_id = (row.get("top_canonical_concept_id") or "").strip()
        parsed = parse_matches(row.get("top_canonical_matches") or "")
        if not concept_id or not parsed:
            continue
        top_concept, top_strength = parsed[0]
        second_strength = parsed[1][1] if len(parsed) > 1 else 0.0
        if top_concept != concept_id:
            continue
        if top_strength < min_strength:
            continue
        if second_strength > 0.0:
            continue
        candidates.append(
            {
                "sap_module": row.get("sap_module", ""),
                "sap_table": row.get("sap_table", ""),
                "sap_field": row.get("sap_field", ""),
                "sap_description": row.get("sap_description", ""),
                "top_canonical_concept_id": concept_id,
                "top_canonical_strength": f"{top_strength:.2f}",
                "top_canonical_matches": row.get("top_canonical_matches", ""),
                "candidate_reason": "single_top_canonical_candidate",
            }
        )
    return candidates


def build_auto_p1_candidates(rows: list[dict[str, str]], min_strength: float) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in rows:
        knowledge_id = (row.get("top_knowledge_concept_id") or "").strip()
        parsed = parse_matches(row.get("top_knowledge_matches") or "")
        if not knowledge_id or not parsed:
            continue
        top_knowledge, top_strength = parsed[0]
        second_strength = parsed[1][1] if len(parsed) > 1 else 0.0
        if top_knowledge != knowledge_id:
            continue
        if top_strength < min_strength:
            continue
        if second_strength > 0.0:
            continue
        candidates.append(
            {
                "sap_module": row.get("sap_module", ""),
                "sap_table": row.get("sap_table", ""),
                "sap_field": row.get("sap_field", ""),
                "sap_description": row.get("sap_description", ""),
                "top_knowledge_concept_id": knowledge_id,
                "top_knowledge_strength": f"{top_strength:.2f}",
                "top_knowledge_matches": row.get("top_knowledge_matches", ""),
                "candidate_reason": "single_top_knowledge_candidate",
            }
        )
    return candidates


def parse_matches(value: str) -> list[tuple[str, float]]:
    matches: list[tuple[str, float]] = []
    for chunk in value.split("|"):
        piece = chunk.strip()
        if not piece or ":" not in piece:
            continue
        concept_id, strength = piece.rsplit(":", 1)
        try:
            matches.append((concept_id.strip(), float(strength.strip())))
        except ValueError:
            continue
    return matches


def sanitize_module(module: str) -> str:
    sanitized = []
    for char in (module or "UNKNOWN"):
        if char.isalnum():
            sanitized.append(char)
        else:
            sanitized.append("_")
    return "".join(sanitized) or "UNKNOWN"


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
