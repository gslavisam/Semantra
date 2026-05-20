"""Promote safe SAP canonical matches into the canonical glossary and context enrichment.

This script consumes the generated SAP inventory classification export and executes a
conservative batch promotion for high-confidence description-derived SAP aliases.

Outputs under knowledge_sources/generated/runtime/sap/:
    - sap_promoted_canonical_aliases.csv
    - sap_promotion_review_queue.csv
    - sap_promotion_summary.csv

Usage:
    python support/sap/promote_sap_canonical_matches.py
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.services.metadata_knowledge_service import CANONICAL_GLOSSARY_HEADERS, metadata_knowledge_service
from app.utils.knowledge_text import filter_canonical_aliases, normalize_canonical_alias_text, split_csv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
PROMOTED_REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_promoted_canonical_aliases.csv"
REVIEW_QUEUE_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_promotion_review_queue.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_promotion_summary.csv"

AMBIGUOUS_DESCRIPTIONS = {
    "city",
    "company id",
    "customer number",
    "document type",
    "full name",
    "item number",
    "material number",
    "payment reference",
    "plant",
    "source system",
    "state",
    "title",
}
BLOCKED_FIELD_TOKENS = ("/", "_ANA")
BLOCKED_FIELD_PREFIXES = ("HASH",)


@dataclass(frozen=True)
class PromotionCandidate:
    row: dict[str, str]
    top_canonical_strength: float
    second_canonical_strength: float


def main() -> None:
    classification_rows = list(read_csv(CLASSIFICATION_PATH))
    candidates: list[PromotionCandidate] = []
    review_rows: list[dict[str, str]] = []

    for row in classification_rows:
        if row["classification_bucket"] == "description_alias_match":
            candidate, skip_reason = evaluate_description_candidate(row)
            if candidate is not None:
                candidates.append(candidate)
            else:
                review_rows.append(build_review_row(row, skip_reason or "description_match_not_safe_for_auto_promotion"))
        elif row["classification_bucket"] in {"strong_canonical_candidate", "weak_canonical_candidate", "knowledge_only", "unmapped"}:
            review_rows.append(build_review_row(row, row["classification_bucket"]))

    promoted_rows = apply_promotions(candidates)
    write_csv(PROMOTED_REPORT_PATH, promoted_rows, list(promoted_rows[0].keys()) if promoted_rows else promoted_report_headers())
    write_csv(REVIEW_QUEUE_PATH, review_rows, list(review_rows[0].keys()) if review_rows else review_queue_headers())
    write_summary(promoted_rows, review_rows, len(classification_rows))

    metadata_knowledge_service.refresh()

    print(f"Processed classification rows: {len(classification_rows)}")
    print(f"Promoted SAP aliases: {sum(1 for row in promoted_rows if row['alias_added'] == 'true')}")
    print(f"Added SAP canonical contexts: {sum(1 for row in promoted_rows if row['context_added'] == 'true')}")
    print(f"Review queue rows: {len(review_rows)}")
    print(f"Wrote: {PROMOTED_REPORT_PATH}")
    print(f"Wrote: {REVIEW_QUEUE_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def evaluate_description_candidate(row: dict[str, str]) -> tuple[PromotionCandidate | None, str | None]:
    matches = parse_matches(row.get("top_canonical_matches", ""))
    if not matches:
        return None, "missing_top_canonical_match"
    top_concept_id, top_strength = matches[0]
    second_strength = matches[1][1] if len(matches) > 1 else 0.0
    description_concept_id = row.get("description_canonical_concept_id", "").strip()
    field_name = row.get("sap_field", "").strip()
    description = row.get("sap_description", "").strip().lower()

    if not description_concept_id:
        return None, "missing_description_canonical_concept"
    if description_concept_id != top_concept_id:
        return None, "description_top_concept_conflict"
    if top_strength < 0.9:
        return None, "top_canonical_strength_below_threshold"
    if second_strength > 0.0:
        return None, "competing_top_canonical_candidate_present"
    if any(token in field_name for token in BLOCKED_FIELD_TOKENS):
        return None, "blocked_field_pattern"
    if any(field_name.startswith(prefix) for prefix in BLOCKED_FIELD_PREFIXES):
        return None, "blocked_field_prefix"
    if description in AMBIGUOUS_DESCRIPTIONS:
        return None, "ambiguous_description"
    return PromotionCandidate(row=row, top_canonical_strength=top_strength, second_canonical_strength=second_strength), None


def apply_promotions(candidates: list[PromotionCandidate]) -> list[dict[str, str]]:
    glossary_path = metadata_knowledge_service.canonical_glossary_path
    context_path = metadata_knowledge_service.canonical_glossary_path.parent / "canonical_field_context_enrichment.csv"

    glossary_rows = load_glossary_rows(glossary_path)
    glossary_by_concept = {row["concept_id"]: row for row in glossary_rows}
    context_rows = list(read_csv(context_path))
    existing_context_keys = {
        (row["concept_id"], row["system"], row["object_name"], row["field_name"])
        for row in context_rows
    }
    promoted_rows: list[dict[str, str]] = []

    for candidate in candidates:
        row = candidate.row
        concept_id = row["description_canonical_concept_id"].strip()
        alias = normalize_canonical_alias_text(row["sap_field"])
        if not concept_id or not alias:
            promoted_rows.append(build_promoted_row(row, concept_id, alias, False, False, "skipped_missing_concept_or_alias"))
            continue
        glossary_row = glossary_by_concept.get(concept_id)
        if glossary_row is None:
            promoted_rows.append(build_promoted_row(row, concept_id, alias, False, False, "skipped_missing_glossary_concept"))
            continue

        existing_aliases = {
            normalized
            for normalized in (
                normalize_canonical_alias_text(value)
                for value in split_csv_values(glossary_row.get("aliases") or "")
            )
            if normalized
        }
        alias_added = alias not in existing_aliases
        if alias_added:
            existing_aliases.add(alias)
            glossary_row["aliases"] = ", ".join(sorted(filter_canonical_aliases(existing_aliases)))

        concept = metadata_knowledge_service._canonical_concepts_by_id.get(concept_id)
        context_key = (concept_id, "SAP", row["sap_table"].strip(), row["sap_field"].strip())
        context_added = context_key not in existing_context_keys
        if context_added:
            context_rows.append(
                {
                    "concept_id": concept_id,
                    "system": "SAP",
                    "object_name": row["sap_table"].strip(),
                    "field_name": row["sap_field"].strip(),
                    "category": concept.entity if concept is not None else concept_id.split(".", 1)[0],
                    "object_description": row.get("sap_table_description", "").strip(),
                    "field_description": row.get("sap_description", "").strip(),
                    "note": (
                        "source=sap_full_inventory_classification; confidence=high; "
                        f"reason=description_alias_match; module={row.get('sap_module', '').strip() or 'UNKNOWN'}"
                    ),
                }
            )
            existing_context_keys.add(context_key)

        status = "promoted" if alias_added or context_added else "already_present"
        promoted_rows.append(build_promoted_row(row, concept_id, alias, alias_added, context_added, status))

    write_glossary_rows(glossary_path, glossary_rows)
    write_csv(context_path, context_rows, ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"])
    return promoted_rows


def build_promoted_row(
    row: dict[str, str],
    concept_id: str,
    alias: str,
    alias_added: bool,
    context_added: bool,
    status: str,
) -> dict[str, str]:
    return {
        "sap_module": row.get("sap_module", ""),
        "sap_table": row.get("sap_table", ""),
        "sap_field": row.get("sap_field", ""),
        "sap_description": row.get("sap_description", ""),
        "canonical_concept_id": concept_id,
        "normalized_alias": alias,
        "top_canonical_matches": row.get("top_canonical_matches", ""),
        "alias_added": str(alias_added).lower(),
        "context_added": str(context_added).lower(),
        "promotion_status": status,
    }


def build_review_row(row: dict[str, str], review_reason: str) -> dict[str, str]:
    return {
        "sap_module": row.get("sap_module", ""),
        "sap_table": row.get("sap_table", ""),
        "sap_field": row.get("sap_field", ""),
        "sap_description": row.get("sap_description", ""),
        "classification_bucket": row.get("classification_bucket", ""),
        "description_canonical_concept_id": row.get("description_canonical_concept_id", ""),
        "top_canonical_concept_id": row.get("top_canonical_concept_id", ""),
        "top_canonical_matches": row.get("top_canonical_matches", ""),
        "top_knowledge_matches": row.get("top_knowledge_matches", ""),
        "review_reason": review_reason,
    }


def write_summary(promoted_rows: list[dict[str, str]], review_rows: list[dict[str, str]], total_rows: int) -> None:
    status_counts = Counter(row["promotion_status"] for row in promoted_rows)
    review_reason_counts = Counter(row["review_reason"] for row in review_rows)
    rows: list[dict[str, str]] = []
    for status, count in sorted(status_counts.items()):
        rows.append({
            "scope": "promotion_status",
            "label": status,
            "row_count": str(count),
            "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000",
        })
    for reason, count in sorted(review_reason_counts.items()):
        rows.append({
            "scope": "review_reason",
            "label": reason,
            "row_count": str(count),
            "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000",
        })
    write_csv(SUMMARY_PATH, rows, ["scope", "label", "row_count", "ratio"])


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


def parse_matches(value: str) -> list[tuple[str, float]]:
    matches: list[tuple[str, float]] = []
    for chunk in value.split("|"):
        normalized = chunk.strip()
        if not normalized or ":" not in normalized:
            continue
        concept_id, strength = normalized.rsplit(":", 1)
        try:
            matches.append((concept_id.strip(), float(strength.strip())))
        except ValueError:
            continue
    return matches


def promoted_report_headers() -> list[str]:
    return [
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "canonical_concept_id",
        "normalized_alias",
        "top_canonical_matches",
        "alias_added",
        "context_added",
        "promotion_status",
    ]


def review_queue_headers() -> list[str]:
    return [
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "classification_bucket",
        "description_canonical_concept_id",
        "top_canonical_concept_id",
        "top_canonical_matches",
        "top_knowledge_matches",
        "review_reason",
    ]


if __name__ == "__main__":
    main()