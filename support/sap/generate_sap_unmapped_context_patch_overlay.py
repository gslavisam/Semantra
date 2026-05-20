"""Generate auto-enrichment candidates for unmapped SAP fields.

This script is non-destructive. It reads the latest SAP classification output and
builds high-confidence candidate mappings for currently unmapped fields using a
context-rich profile (module, table, field, description, data element, domain).

Outputs under knowledge_sources/generated/runtime/sap/:
- sap_unmapped_auto_enrichment_candidates.csv
- sap_unmapped_auto_enrichment_overlay.csv
- sap_unmapped_auto_enrichment_summary.csv

The overlay output can be imported as a normal knowledge overlay and then
activated from the Canonical Console.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from app.models.schema import ColumnProfile
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.utils.normalization import semantic_token_set


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAP_RUNTIME_DIR = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap"
CLASSIFICATION_PATH = SAP_RUNTIME_DIR / "sap_full_inventory_classification.csv"
DEFAULT_OUTPUT_STEM = "sap_unmapped_auto_enrichment"

CANDIDATE_HEADERS = [
    "sap_module",
    "sap_table",
    "sap_field",
    "sap_description",
    "sap_data_element",
    "sap_domain",
    "sap_table_description",
    "classification_bucket",
    "top_canonical_concept_id",
    "top_canonical_strength",
    "second_canonical_concept_id",
    "second_canonical_strength",
    "strength_margin",
    "confidence_tier",
    "top_canonical_matches",
    "candidate_reason",
]

OVERLAY_HEADERS = ["entry_type", "canonical_term", "alias", "domain", "source_system", "note"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate auto-enrichment overlay candidates for unmapped SAP fields.")
    parser.add_argument(
        "--preset",
        choices=("safe", "aggressive", "custom"),
        default="safe",
        help="Preset threshold profile: safe, aggressive, or custom.",
    )
    parser.add_argument(
        "--min-strength",
        type=float,
        default=None,
        help="Minimum top canonical strength required for auto-candidate inclusion.",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=None,
        help="Minimum strength margin between top and second canonical candidate.",
    )
    parser.add_argument(
        "--include-buckets",
        default="",
        help="Comma-separated classification buckets to include (default: unmapped,knowledge_only).",
    )
    parser.add_argument(
        "--include-modules",
        default="",
        help="Optional comma-separated SAP modules to include (example: FI,MM).",
    )
    parser.add_argument(
        "--output-stem",
        default=DEFAULT_OUTPUT_STEM,
        help="Output filename stem under runtime/sap (without suffix).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit after bucket filter; 0 means full set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_knowledge_service.refresh()

    min_strength, min_margin, include_buckets = resolve_generation_profile(args)
    include_modules = {
        value.strip().upper()
        for value in args.include_modules.split(",")
        if value.strip()
    }

    candidates_path, overlay_path, summary_path = resolve_output_paths(args.output_stem)

    rows = [
        row
        for row in read_csv(CLASSIFICATION_PATH)
        if (row.get("classification_bucket") or "").strip() in include_buckets
    ]
    if include_modules:
        rows = [
            row
            for row in rows
            if (row.get("sap_module") or "").strip().upper() in include_modules
        ]
    if args.limit > 0:
        rows = rows[: args.limit]

    candidate_rows: list[dict[str, str]] = []
    overlay_rows: list[dict[str, str]] = []
    tier_counts: Counter[str] = Counter()

    for row in rows:
        profile = build_enriched_profile(row)
        matches = sorted(
            metadata_knowledge_service.match_canonical_concepts(profile, prefer_metadata_text=True),
            key=lambda match: (-match.strength, match.concept_id),
        )
        if not matches:
            continue

        top = matches[0]
        second = matches[1] if len(matches) > 1 else None
        second_strength = second.strength if second is not None else 0.0
        margin = top.strength - second_strength
        if top.strength < min_strength:
            continue
        if margin < min_margin:
            continue

        confidence_tier = confidence_tier_for(top.strength, margin)
        tier_counts[confidence_tier] += 1

        candidate_rows.append(
            {
                "sap_module": (row.get("sap_module") or "").strip(),
                "sap_table": (row.get("sap_table") or "").strip(),
                "sap_field": (row.get("sap_field") or "").strip(),
                "sap_description": (row.get("sap_description") or "").strip(),
                "sap_data_element": (row.get("sap_data_element") or "").strip(),
                "sap_domain": (row.get("sap_domain") or "").strip(),
                "sap_table_description": (row.get("sap_table_description") or "").strip(),
                "classification_bucket": (row.get("classification_bucket") or "").strip(),
                "top_canonical_concept_id": top.concept_id,
                "top_canonical_strength": f"{top.strength:.2f}",
                "second_canonical_concept_id": second.concept_id if second is not None else "",
                "second_canonical_strength": f"{second_strength:.2f}" if second is not None else "",
                "strength_margin": f"{margin:.2f}",
                "confidence_tier": confidence_tier,
                "top_canonical_matches": format_matches(matches),
                "candidate_reason": "context_enriched_unmapped_auto_candidate",
            }
        )

        overlay_rows.append(
            {
                "entry_type": "field_alias",
                "canonical_term": top.concept_id,
                "alias": f"{(row.get('sap_table') or '').strip()}.{(row.get('sap_field') or '').strip()}",
                "domain": (row.get("sap_module") or "").strip(),
                "source_system": "SAP",
                "note": build_context_patch_note(row, top_strength=top.strength, margin=margin, confidence_tier=confidence_tier),
            }
        )

    write_csv(candidates_path, candidate_rows, CANDIDATE_HEADERS)
    write_csv(overlay_path, overlay_rows, OVERLAY_HEADERS)
    write_summary(
        summary_path,
        {
            "preset": args.preset,
            "input_rows": str(len(rows)),
            "candidates": str(len(candidate_rows)),
            "overlay_rows": str(len(overlay_rows)),
            "min_strength": f"{min_strength:.2f}",
            "min_margin": f"{min_margin:.2f}",
            "include_buckets": ",".join(sorted(include_buckets)),
            "include_modules": ",".join(sorted(include_modules)) if include_modules else "ALL",
            "output_stem": args.output_stem,
            "tier_high": str(tier_counts.get("high", 0)),
            "tier_medium": str(tier_counts.get("medium", 0)),
        },
    )

    print(f"Input rows ({','.join(sorted(include_buckets))}): {len(rows)}")
    print(f"Auto candidates: {len(candidate_rows)}")
    print(f"Overlay rows: {len(overlay_rows)}")
    print(f"Wrote: {candidates_path}")
    print(f"Wrote: {overlay_path}")
    print(f"Wrote: {summary_path}")


def resolve_generation_profile(args: argparse.Namespace) -> tuple[float, float, set[str]]:
    preset_defaults: dict[str, tuple[float, float, str]] = {
        "safe": (0.75, 0.15, "unmapped,knowledge_only"),
        "aggressive": (0.60, 0.05, "unmapped,knowledge_only,weak_canonical_candidate"),
        "custom": (0.75, 0.15, "unmapped,knowledge_only"),
    }
    default_strength, default_margin, default_buckets = preset_defaults[args.preset]
    min_strength = float(args.min_strength) if args.min_strength is not None else default_strength
    min_margin = float(args.min_margin) if args.min_margin is not None else default_margin
    buckets_raw = args.include_buckets.strip() if args.include_buckets else default_buckets
    include_buckets = {value.strip() for value in buckets_raw.split(",") if value.strip()}
    return min_strength, min_margin, include_buckets


def resolve_output_paths(output_stem: str) -> tuple[Path, Path, Path]:
    stem = (output_stem or DEFAULT_OUTPUT_STEM).strip() or DEFAULT_OUTPUT_STEM
    candidates = SAP_RUNTIME_DIR / f"{stem}_candidates.csv"
    overlay = SAP_RUNTIME_DIR / f"{stem}_overlay.csv"
    summary = SAP_RUNTIME_DIR / f"{stem}_summary.csv"
    return candidates, overlay, summary


def build_enriched_profile(row: dict[str, str]) -> ColumnProfile:
    sap_table = (row.get("sap_table") or "").strip()
    sap_field = (row.get("sap_field") or "").strip()
    sap_module = (row.get("sap_module") or "").strip()
    sap_description = (row.get("sap_description") or "").strip()
    sap_table_description = (row.get("sap_table_description") or "").strip()
    sap_data_element = (row.get("sap_data_element") or "").strip()
    sap_domain = (row.get("sap_domain") or "").strip()

    normalized_name = " ".join(part for part in [sap_table, sap_field] if part)
    description_parts = [
        sap_description,
        f"module {sap_module}" if sap_module else "",
        f"table {sap_table}" if sap_table else "",
        sap_table_description,
        f"data element {sap_data_element}" if sap_data_element else "",
        f"domain {sap_domain}" if sap_domain else "",
    ]
    description = ". ".join(part for part in description_parts if part)
    declared_type = " ".join(part for part in [sap_data_element, sap_domain] if part)

    token_source = " ".join(part for part in [normalized_name, sap_description, sap_table_description, sap_module] if part)
    tokenized_name = sorted(token for token in semantic_token_set(token_source.replace("_", " ")) if token)

    return ColumnProfile(
        name=sap_field,
        normalized_name=normalized_name or sap_field,
        description=description,
        declared_type=declared_type,
        dtype="object",
        null_ratio=0.0,
        unique_ratio=1.0,
        avg_length=float(len(sap_field or normalized_name or "field")),
        non_null_count=1,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=["text"],
        tokenized_name=tokenized_name,
    )


def build_context_patch_note(row: dict[str, str], *, top_strength: float, margin: float, confidence_tier: str) -> str:
    sap_table = safe_note_value((row.get("sap_table") or "").strip())
    sap_field = safe_note_value((row.get("sap_field") or "").strip())
    sap_description = safe_note_value((row.get("sap_description") or "").strip())
    sap_table_description = safe_note_value((row.get("sap_table_description") or "").strip())
    sap_module = safe_note_value((row.get("sap_module") or "").strip())
    sap_data_element = safe_note_value((row.get("sap_data_element") or "").strip())
    sap_domain = safe_note_value((row.get("sap_domain") or "").strip())
    parts = [
        "context_patch=true",
        "system=SAP",
        f"object={sap_table}",
        f"field={sap_field}",
    ]
    if sap_table_description:
        parts.append(f"object_description={sap_table_description}")
    if sap_description:
        parts.append(f"field_description={sap_description}")
    parts.append(
        "note="
        + safe_note_value(
            "source=sap_unmapped_auto_enrichment"
            f"; confidence={confidence_tier}"
            f"; top_strength={top_strength:.2f}"
            f"; margin={margin:.2f}"
            f"; module={sap_module or 'UNKNOWN'}"
            f"; data_element={sap_data_element}"
            f"; domain={sap_domain}"
        )
    )
    return "; ".join(parts)


def confidence_tier_for(strength: float, margin: float) -> str:
    if strength >= 0.90 and margin >= 0.25:
        return "high"
    return "medium"


def format_matches(matches: list, limit: int = 3) -> str:
    return " | ".join(f"{match.concept_id}:{match.strength:.2f}" for match in matches[:limit])


def safe_note_value(value: str) -> str:
    return str(value or "").replace(";", ",").replace("\n", " ").strip()


def write_summary(path: Path, summary: dict[str, str]) -> None:
    rows = [{"metric": key, "value": value} for key, value in summary.items()]
    write_csv(path, rows, ["metric", "value"])


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
