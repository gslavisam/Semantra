"""Tag remaining SAP unmapped rows with a derived knowledge_available layer.

This script does not alter classification buckets or overlays. It creates a
supplemental tagging layer for the remaining `unmapped` SAP rows after current
canonical promotion runs.

Outputs under knowledge_sources/generated/runtime/sap/:
    - sap_remaining_knowledge_available_tags.csv
    - sap_remaining_knowledge_available_summary.csv

Usage:
    python support/sap/tag_sap_remaining_knowledge_available.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
TAGS_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_remaining_knowledge_available_tags.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_remaining_knowledge_available_summary.csv"


def main() -> None:
    rows = list(read_csv(CLASSIFICATION_PATH))
    unmapped_rows = [row for row in rows if (row.get("classification_bucket") or "").strip() == "unmapped"]

    tagged_rows: list[dict[str, str]] = []
    module_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    tag_level_counts: Counter[str] = Counter()

    for row in unmapped_rows:
        tag_level, reason = derive_knowledge_available_tag(row)
        module = (row.get("sap_module") or "UNKNOWN").strip() or "UNKNOWN"
        domain = (row.get("sap_domain") or "").strip()
        data_element = (row.get("sap_data_element") or "").strip()
        description = (row.get("sap_description") or "").strip()

        tagged_rows.append(
            {
                "sap_module": module,
                "sap_table": (row.get("sap_table") or "").strip(),
                "sap_field": (row.get("sap_field") or "").strip(),
                "sap_description": description,
                "sap_data_element": data_element,
                "sap_domain": domain,
                "classification_bucket": "unmapped",
                "knowledge_available": "true",
                "knowledge_tag_level": tag_level,
                "knowledge_tag_reason": reason,
                "knowledge_tag_note": build_note(module, domain, data_element, description),
            }
        )
        module_counts[module] += 1
        reason_counts[reason] += 1
        tag_level_counts[tag_level] += 1

    write_csv(
        TAGS_PATH,
        tagged_rows,
        [
            "sap_module",
            "sap_table",
            "sap_field",
            "sap_description",
            "sap_data_element",
            "sap_domain",
            "classification_bucket",
            "knowledge_available",
            "knowledge_tag_level",
            "knowledge_tag_reason",
            "knowledge_tag_note",
        ],
    )
    write_summary(unmapped_rows, module_counts, reason_counts, tag_level_counts)

    print(f"Remaining unmapped rows tagged: {len(tagged_rows)}")
    print(f"Wrote: {TAGS_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def derive_knowledge_available_tag(row: dict[str, str]) -> tuple[str, str]:
    description = (row.get("sap_description") or "").strip()
    domain = (row.get("sap_domain") or "").strip()
    data_element = (row.get("sap_data_element") or "").strip()
    table_description = (row.get("sap_table_description") or "").strip()

    if description and domain and data_element:
        return "high", "description_domain_data_element"
    if description and domain:
        return "medium", "description_domain"
    if description and table_description:
        return "medium", "description_table_context"
    if description:
        return "base", "description_only"
    return "base", "structural_metadata_only"


def build_note(module: str, domain: str, data_element: str, description: str) -> str:
    parts = ["source=sap_remaining_unmapped", f"module={module}"]
    if domain:
        parts.append(f"domain={domain}")
    if data_element:
        parts.append(f"data_element={data_element}")
    if description:
        parts.append(f"description={description[:80]}")
    return "; ".join(parts)


def write_summary(
    unmapped_rows: list[dict[str, str]],
    module_counts: Counter[str],
    reason_counts: Counter[str],
    tag_level_counts: Counter[str],
) -> None:
    total = len(unmapped_rows)
    summary_rows: list[dict[str, str]] = [
        {"scope": "overall", "label": "remaining_unmapped", "row_count": str(total), "ratio": "1.0000" if total else "0.0000"},
    ]
    for label, count in sorted(tag_level_counts.items()):
        summary_rows.append({"scope": "knowledge_tag_level", "label": label, "row_count": str(count), "ratio": f"{(count / total):.4f}" if total else "0.0000"})
    for label, count in sorted(reason_counts.items()):
        summary_rows.append({"scope": "knowledge_tag_reason", "label": label, "row_count": str(count), "ratio": f"{(count / total):.4f}" if total else "0.0000"})
    for label, count in module_counts.most_common(15):
        summary_rows.append({"scope": "sap_module", "label": label, "row_count": str(count), "ratio": f"{(count / total):.4f}" if total else "0.0000"})
    write_csv(SUMMARY_PATH, summary_rows, ["scope", "label", "row_count", "ratio"])


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