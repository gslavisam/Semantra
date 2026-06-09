"""End-to-end mapping demo using the new semantra-core + backend adapter.

What this does:
1. Loads two real CSV files from `ui_fixtures/showcase_customer_mapping/`.
2. Builds semantra-core Pydantic models (SchemaProfile, ColumnProfile) from them.
3. Runs the mapping twice and compares:
   a) InMemoryMappingEngine (stub — by design returns no candidates)
   b) BackendMappingEngine (real Semantra FastAPI mapping engine, via adapter)
4. Prints the actual mapping candidates produced by the real engine.

This proves that the new SDK can drive real, file-to-file mapping work, and
that the stub vs real implementation is a one-line swap.

Run from repo root with:
    cd /home/smili/Semantra
    PYTHONPATH=. /home/smili/Semantra/semantra-core/.venv/bin/python \\
        notebooks/04_real_file_mapping_demo.py

(The script also adds /home/smili/Semantra/backend to sys.path so the
backend's `app.*` internal imports resolve correctly.)
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

# Ensure both root paths are importable before importing semantra modules.
# This is needed because mapping_service uses `from app.core.config import ...`
# (relative to backend/) while the adapter uses `from backend.app.services ...`
# (relative to repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]   # /home/smili/Semantra
sys.path.insert(0, str(_REPO_ROOT / "backend"))   # for "from app..."
sys.path.insert(0, str(_REPO_ROOT))                # for "from backend.app..."

from semantra_core.models.schema import (  # noqa: E402
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.services import InMemoryMappingEngine  # noqa: E402
from semantra_core.services.protocols import MappingEngine  # noqa: E402
from semantra_backend_adapter import BackendMappingEngine  # noqa: E402

# ---------------------------------------------------------------------------
# 1. CSV ingestion
# ---------------------------------------------------------------------------

FIXTURE_DIR = _REPO_ROOT / "ui_fixtures" / "showcase_customer_mapping"
SOURCE_PATH = FIXTURE_DIR / "showcase_customer_source.csv"
TARGET_PATH = FIXTURE_DIR / "showcase_customer_target.csv"


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Phone is the loosest pattern: must have a '+' prefix OR an internal space,
# otherwise a date like '2023-01-15' (digits+dashes) would match.
PHONE_RE = re.compile(r"^(?:\+\d|\d.*[\s])[\d\s\-]{6,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def _detect_patterns(values: list[str]) -> list[str]:
    """Cheap, transparent pattern detector for a list of cell values.

    Pattern priority: strict (email, integer, float, date) first, loose
    (phone) last — otherwise a date like '2023-01-15' matches the loose
    phone regex '^+?\\d[\\d\\s\\-]{6,}$'.
    """
    non_empty = [v for v in values if v]
    if not non_empty:
        return ["empty"]
    patterns: list[str] = []
    if all(EMAIL_RE.match(v) for v in non_empty):
        patterns.append("email")
    if all(INT_RE.match(v) for v in non_empty):
        patterns.append("integer")
    elif all(FLOAT_RE.match(v) for v in non_empty):
        patterns.append("float")
    if all(DATE_RE.match(v) for v in non_empty):
        patterns.append("date")
    # Phone last because it is the loosest pattern.
    if all(PHONE_RE.match(v) for v in non_empty):
        patterns.append("phone")
    unique_ratio = len(set(non_empty)) / len(non_empty)
    if unique_ratio == 1.0 and len(non_empty) > 1:
        patterns.append("uuid")
    if unique_ratio < 0.5 and len(non_empty) > 1:
        patterns.append("categorical")
    if not patterns:
        patterns.append("text")
    return patterns


def _detect_dtype(values: list[str], patterns: list[str]) -> str:
    """Map detected patterns to a coarse dtype string."""
    if "integer" in patterns:
        return "int"
    if "float" in patterns:
        return "float"
    if "date" in patterns:
        return "date"
    return "str"


def load_csv(path: Path) -> SchemaProfile:
    """Read a CSV file from disk and return a semantra-core SchemaProfile."""
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = [row for row in reader if row]

    columns: list[ColumnProfile] = []
    for col_index, col_name in enumerate(header):
        col_values = [row[col_index] for row in rows]
        non_null_values = [v for v in col_values if v]
        null_count = len(col_values) - len(non_null_values)
        unique_values = set(non_null_values)
        patterns = _detect_patterns(col_values)
        dtype = _detect_dtype(col_values, patterns)

        columns.append(
            ColumnProfile(
                name=col_name,
                normalized_name=col_name.strip().lower().replace(" ", "_"),
                dtype=dtype,
                null_ratio=(null_count / len(col_values)) if col_values else 0.0,
                unique_ratio=(
                    len(unique_values) / len(non_null_values)
                    if non_null_values
                    else 0.0
                ),
                non_null_count=len(non_null_values),
                sample_values=non_null_values[:5],
                distinct_sample_values=list(unique_values)[:5],
                detected_patterns=patterns,
            )
        )

    return SchemaProfile(
        dataset_id=path.stem,
        dataset_name=path.stem,
        row_count=len(rows),
        columns=columns,
    )


# ---------------------------------------------------------------------------
# 2. Display helpers
# ---------------------------------------------------------------------------


def _print_schema(title: str, schema: SchemaProfile) -> None:
    print(f"\n--- {title} ({schema.row_count} rows) ---")
    print(f"{'column':<28} {'dtype':<6} {'nulls':>5} {'unique':>6}  patterns")
    print("-" * 70)
    for col in schema.columns:
        print(
            f"{col.name:<28} {col.dtype:<6} {col.null_ratio:>4.0%} "
            f"{col.unique_ratio:>5.0%}  {','.join(col.detected_patterns)}"
        )


def _print_candidates(candidates, limit: int = 12) -> None:
    if not candidates:
        print("  (no candidates)")
        return
    print(f"  Showing first {min(limit, len(candidates))} of {len(candidates)} candidates:")
    print(f"  {'source':<22} -> {'target':<22} conf   method")
    print("  " + "-" * 70)
    for c in candidates[:limit]:
        # CandidateOption is a flat list — but BackendMappingEngine sometimes
        # returns the outer MappingCandidate structure when present, so we
        # look for a `.source` attribute too.
        source = getattr(c, "source", "?")
        print(
            f"  {str(source):<22} -> {c.target:<22} "
            f"{c.confidence:>4.2f}  {c.method:<18} "
            f"({c.confidence_label})"
        )


# ---------------------------------------------------------------------------
# 3. Main
# ---------------------------------------------------------------------------


def run(engine: MappingEngine, source: DatasetHandle, target: SchemaProfile, label: str) -> list:
    print(f"\n=== {label} ===")
    print(f"Engine class: {type(engine).__name__}")
    print(f"Backed by: {'semantra-core reference stub' if label.startswith('A') else 'semantra FastAPI backend (via adapter)'}")
    candidates = engine.map_source_to_target(source, target)
    _print_candidates(candidates)
    return candidates


def main() -> int:
    print("=" * 70)
    print("Semantra: Real File-to-File Mapping Demo")
    print("=" * 70)
    print(f"Source: {SOURCE_PATH.relative_to(_REPO_ROOT)}")
    print(f"Target: {TARGET_PATH.relative_to(_REPO_ROOT)}")

    source_schema = load_csv(SOURCE_PATH)
    target_schema = load_csv(TARGET_PATH)
    _print_schema("SOURCE", source_schema)
    _print_schema("TARGET", target_schema)

    source_handle = DatasetHandle(
        dataset_id=source_schema.dataset_id,
        dataset_name=source_schema.dataset_name,
        schema_profile=source_schema,
        preview_rows=[],
    )

    # A) In-memory stub
    stub_engine = InMemoryMappingEngine()
    stub_candidates = run(stub_engine, source_handle, target_schema, "A) InMemoryMappingEngine (STUB)")

    # B) Real backend
    real_engine = BackendMappingEngine()
    real_candidates = run(real_engine, source_handle, target_schema, "B) BackendMappingEngine (REAL)")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Stub engine candidates:    {len(stub_candidates)}  (expected 0 by design)")
    print(f"Real engine candidates:    {len(real_candidates)}  (actual ranking from Semantra)")

    if real_candidates:
        # Show how each source field was actually resolved.
        print("\nPer-source-field resolution (real engine):")
        for source_col in source_schema.columns:
            matching = [
                c for c in real_candidates
                if getattr(c, "source", source_col.name) == source_col.name
            ]
            if matching:
                top = max(matching, key=lambda c: c.confidence)
                print(f"  {source_col.name:<28} -> {top.target:<22} conf={top.confidence:.2f} ({top.method})")
            else:
                print(f"  {source_col.name:<28} -> (no candidate)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
