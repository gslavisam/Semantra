"""Create new canonical concepts for the most common SAP unmapped descriptions.

This script promotes high-frequency SAP `unmapped` description families into new
canonical concepts by writing directly to:
- metadata_dict/canonical_glossary_erp.csv
- metadata_dict/canonical_field_context_enrichment.csv

Outputs under knowledge_sources/generated/runtime/sap/:
    - sap_top_unmapped_description_concepts.csv
    - sap_top_unmapped_description_concepts_summary.csv

Usage:
    python support/sap/promote_sap_top_unmapped_descriptions.py --limit 50
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.services.metadata_knowledge_service import CANONICAL_GLOSSARY_HEADERS, metadata_knowledge_service
from app.utils.knowledge_text import normalize_canonical_alias_text, split_csv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
PROMOTED_REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_top_unmapped_description_concepts.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_top_unmapped_description_concepts_summary.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote top SAP unmapped descriptions into new canonical concepts.")
    parser.add_argument("--limit", type=int, default=50, help="How many top unmapped descriptions to promote.")
    parser.add_argument(
        "--target-total",
        type=int,
        default=0,
        help="Target cumulative count of auto-generated SAP concepts. If set, only the additional concepts needed to reach this total are created.",
    )
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency required for a description family.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    classification_rows = list(read_csv(CLASSIFICATION_PATH))
    glossary_path = metadata_knowledge_service.canonical_glossary_path
    context_path = glossary_path.parent / "canonical_field_context_enrichment.csv"

    glossary_rows = load_glossary_rows(glossary_path)
    glossary_by_concept = {row["concept_id"]: row for row in glossary_rows}
    context_rows = list(read_csv(context_path))
    existing_context_keys = {(row["concept_id"], row["system"], row["object_name"], row["field_name"]) for row in context_rows}
    existing_alias_lookup = build_existing_alias_lookup(glossary_rows)
    existing_generated_count = count_generated_sap_terms(glossary_rows)

    grouped_rows = group_unmapped_rows(classification_rows, min_frequency=args.min_frequency)
    promotion_limit = resolve_promotion_limit(args.limit, args.target_total, existing_generated_count)

    promoted_rows: list[dict[str, str]] = []
    created_concept_ids: set[str] = set()

    for rank, (normalized_description, rows) in enumerate(grouped_rows[:promotion_limit], start=1):
        description = rows[0].get("sap_description", "").strip()
        if not description:
            continue

        if normalized_description in existing_alias_lookup:
            continue

        concept_id = next_available_concept_id(description, glossary_by_concept, created_concept_ids)
        created_concept_ids.add(concept_id)

        dominant_domain = most_common_non_empty(row.get("sap_domain", "") for row in rows)
        dominant_module = most_common_non_empty(row.get("sap_module", "") for row in rows)
        dominant_data_element = most_common_non_empty(row.get("sap_data_element", "") for row in rows)
        display_name = build_display_name(description)
        data_type = infer_data_type(description, dominant_domain)
        concept_description = build_concept_description(description, rows, dominant_module, dominant_domain, dominant_data_element)

        concept_row = {
            "concept_id": concept_id,
            "entity": concept_id.split(".", 1)[0],
            "attribute": concept_id.split(".", 1)[1],
            "display_name": display_name,
            "description": concept_description,
            "data_type": data_type,
            "aliases": description,
        }
        glossary_rows.append(concept_row)
        glossary_by_concept[concept_id] = concept_row
        existing_alias_lookup[normalized_description] = concept_id

        for row in rows:
            context_key = (concept_id, "SAP", row.get("sap_table", "").strip(), row.get("sap_field", "").strip())
            context_added = context_key not in existing_context_keys
            if context_added:
                context_rows.append(
                    {
                        "concept_id": concept_id,
                        "system": "SAP",
                        "object_name": row.get("sap_table", "").strip(),
                        "field_name": row.get("sap_field", "").strip(),
                        "category": concept_id.split(".", 1)[0],
                        "object_description": row.get("sap_table_description", "").strip(),
                        "field_description": row.get("sap_description", "").strip(),
                        "note": (
                            "source=sap_full_inventory_classification; confidence=medium; "
                            f"reason=top_unmapped_description; rank={rank}; frequency={len(rows)}; "
                            f"module={row.get('sap_module', '').strip() or 'UNKNOWN'}"
                        ),
                    }
                )
                existing_context_keys.add(context_key)

            promoted_rows.append(
                {
                    "action_type": "new_canonical_concept",
                    "rule_name": "top_unmapped_description",
                    "selection_rank": str(rank),
                    "description_frequency": str(len(rows)),
                    "sap_module": row.get("sap_module", ""),
                    "sap_table": row.get("sap_table", ""),
                    "sap_field": row.get("sap_field", ""),
                    "sap_description": row.get("sap_description", ""),
                    "source_bucket": row.get("classification_bucket", ""),
                    "canonical_concept_id": concept_id,
                    "alias_added": "true",
                    "concept_created": "true",
                    "context_added": str(context_added).lower(),
                }
            )

    write_glossary_rows(glossary_path, glossary_rows)
    write_csv(
        context_path,
        context_rows,
        ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"],
    )
    metadata_knowledge_service.refresh()

    write_csv(PROMOTED_REPORT_PATH, promoted_rows, promoted_headers())
    write_summary(grouped_rows, promoted_rows)

    concept_count = len({row["canonical_concept_id"] for row in promoted_rows})
    print(f"Processed classification rows: {len(classification_rows)}")
    print(f"Candidate description families: {len(grouped_rows)}")
    print(f"Existing generated SAP concepts: {existing_generated_count}")
    print(f"Requested promotion limit: {promotion_limit}")
    print(f"Created concepts: {concept_count}")
    print(f"Promoted rows: {len(promoted_rows)}")
    print(f"Wrote: {PROMOTED_REPORT_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def group_unmapped_rows(rows: list[dict[str, str]], *, min_frequency: int) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("classification_bucket", "").strip() != "unmapped":
            continue
        description = row.get("sap_description", "").strip()
        normalized = normalize_canonical_alias_text(description)
        if not normalized:
            continue
        grouped[normalized].append(row)

    ranked = [
        (normalized, group)
        for normalized, group in grouped.items()
        if len(group) >= min_frequency
    ]
    ranked.sort(key=lambda item: (-len(item[1]), item[1][0].get("sap_description", "").strip().lower()))
    return ranked


def build_existing_alias_lookup(glossary_rows: list[dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in glossary_rows:
        concept_id = row.get("concept_id", "").strip()
        if not concept_id:
            continue
        candidates = [
            concept_id,
            row.get("display_name", ""),
            row.get("description", ""),
            *split_csv_values(row.get("aliases") or ""),
        ]
        for candidate in candidates:
            normalized = normalize_canonical_alias_text(candidate)
            if normalized and normalized not in lookup:
                lookup[normalized] = concept_id
    return lookup


def count_generated_sap_terms(glossary_rows: list[dict[str, str]]) -> int:
    return sum(1 for row in glossary_rows if row.get("concept_id", "").startswith("sap_term."))


def resolve_promotion_limit(limit: int, target_total: int, existing_generated_count: int) -> int:
    if target_total > 0:
        return max(0, target_total - existing_generated_count)
    return max(0, limit)


def next_available_concept_id(
    description: str,
    glossary_by_concept: dict[str, dict[str, str]],
    created_concept_ids: set[str],
) -> str:
    slug = slugify(description)
    base = f"sap_term.{slug or 'generated'}"
    candidate = base
    suffix = 2
    while candidate in glossary_by_concept or candidate in created_concept_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    if not lowered:
        return "generated"
    return lowered[:60].rstrip("_")


def build_display_name(description: str) -> str:
    text = re.sub(r"\s+", " ", description.strip())
    if not text:
        return "SAP Generated Concept"
    return text[:120]


def build_concept_description(
    description: str,
    rows: list[dict[str, str]],
    dominant_module: str,
    dominant_domain: str,
    dominant_data_element: str,
) -> str:
    module_part = f" Module focus: {dominant_module}." if dominant_module else ""
    domain_part = f" Domain: {dominant_domain}." if dominant_domain else ""
    data_element_part = f" Data element: {dominant_data_element}." if dominant_data_element else ""
    return (
        f"Auto-generated canonical concept for the SAP description '{description}' "
        f"based on {len(rows)} unmapped field occurrences.{module_part}{domain_part}{data_element_part}"
    ).strip()


def infer_data_type(description: str, sap_domain: str) -> str:
    description_normalized = description.lower()
    domain_normalized = sap_domain.lower()
    if "date" in description_normalized or domain_normalized in {"datum", "dats"}:
        return "date"
    if any(token in description_normalized for token in ("amount", "price", "cost", "weight", "quantity", "balance", "rate", "percent")):
        return "decimal"
    if any(token in description_normalized for token in ("flag", "indicator", "inactive", "active", "blocked", "complete")):
        return "boolean"
    return "string"


def most_common_non_empty(values) -> str:
    counts = Counter(value.strip() for value in values if str(value).strip())
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def load_glossary_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{header: str(row.get(header) or "").strip() for header in CANONICAL_GLOSSARY_HEADERS} for row in reader]


def write_glossary_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_GLOSSARY_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def promoted_headers() -> list[str]:
    return [
        "action_type",
        "rule_name",
        "selection_rank",
        "description_frequency",
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "source_bucket",
        "canonical_concept_id",
        "alias_added",
        "concept_created",
        "context_added",
    ]


def write_summary(grouped_rows: list[tuple[str, list[dict[str, str]]]], promoted_rows: list[dict[str, str]]) -> None:
    concept_count = len({row["canonical_concept_id"] for row in promoted_rows})
    promoted_field_count = len(promoted_rows)
    top_frequency = max((len(group) for _, group in grouped_rows), default=0)
    rows = [
        {"scope": "run_status", "label": "concepts_created", "row_count": str(concept_count), "ratio": "1.0000" if concept_count else "0.0000"},
        {"scope": "run_status", "label": "promoted_fields", "row_count": str(promoted_field_count), "ratio": "1.0000" if promoted_field_count else "0.0000"},
        {"scope": "run_status", "label": "largest_description_family", "row_count": str(top_frequency), "ratio": "1.0000" if top_frequency else "0.0000"},
    ]
    write_csv(SUMMARY_PATH, rows, ["scope", "label", "row_count", "ratio"])


if __name__ == "__main__":
    main()