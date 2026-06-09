"""End-to-end mapping demo with the FULL rich output.

The companion script ``04_real_file_mapping_demo.py`` calls the SDK's
``BackendMappingEngine`` adapter, which flattens the response to
``list[CandidateOption]`` — perfect for an agent that just needs "give me
the next-best target". But the underlying engine actually produces a
``list[MappingCandidate]`` with per-source-field decisions, confidence
breakdowns, multi-signal explanations, and canonical-concept paths.

This script calls the engine **directly** (bypassing the adapter) so the
caller can see — and assert on — the full payload. The output matches the
shape the original Semantra web app shows in the workspace review table.

Run from repo root with:
    cd /home/smili/Semantra
    /home/smili/Semantra/semantra-core/.venv/bin/python \\
        notebooks/04b_supplier_rich_mapping_demo.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Path setup (same trick as 04_…): backend/ uses "from app..." imports
# while the adapter uses "from backend.app...". Both need to be reachable.
_REPO_ROOT = Path(__file__).resolve().parents[2]   # /home/smili/Semantra
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_REPO_ROOT))

# Direct backend access (no adapter flattening).
from backend.app.services import mapping_service  # noqa: E402

# SDK models.
from semantra_core.models.mapping import (  # noqa: E402
    MappingCandidate,
    ScoringSignals,
)
from semantra_core.models.schema import (  # noqa: E402
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)

# ---------------------------------------------------------------------------
# 1. CSV ingestion (same shape as in 04_… for consistency)
# ---------------------------------------------------------------------------

FIXTURE_DIR = _REPO_ROOT / "ui_fixtures" / "showcase_supplier_master"
SOURCE_PATH = FIXTURE_DIR / "showcase_supplier_source.csv"
TARGET_PATH = FIXTURE_DIR / "showcase_supplier_target.csv"

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^(?:\+\d|\d.*[\s])[\d\s\-]{6,}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")


def _detect_patterns(values: Iterable[str]) -> list[str]:
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return ["empty"]
    patterns: list[str] = []
    if all(_EMAIL.match(v) for v in non_empty):
        patterns.append("email")
    if all(_INT.match(v) for v in non_empty):
        patterns.append("integer")
    elif all(_FLOAT.match(v) for v in non_empty):
        patterns.append("float")
    if all(_DATE.match(v) for v in non_empty):
        patterns.append("date")
    if all(_PHONE.match(v) for v in non_empty):
        patterns.append("phone")
    unique_ratio = len(set(non_empty)) / len(non_empty)
    if unique_ratio == 1.0 and len(non_empty) > 1:
        patterns.append("uuid")
    if unique_ratio < 0.5 and len(non_empty) > 1:
        patterns.append("categorical")
    if not patterns:
        patterns.append("text")
    return patterns


def _detect_dtype(values: Iterable[str], patterns: list[str]) -> str:
    if "integer" in patterns:
        return "int"
    if "float" in patterns:
        return "float"
    if "date" in patterns:
        return "date"
    return "str"


def _build_profile_from_rows(
    dataset_id: str,
    dataset_name: str,
    header: list[str],
    rows: list[list[str]],
) -> SchemaProfile:
    columns: list[ColumnProfile] = []
    for col_index, col_name in enumerate(header):
        col_values = [row[col_index] if col_index < len(row) else "" for row in rows]
        non_null = [v for v in col_values if v not in (None, "")]
        unique = set(non_null)
        patterns = _detect_patterns(col_values)
        columns.append(
            ColumnProfile(
                name=col_name,
                normalized_name=col_name.strip().lower().replace(" ", "_"),
                dtype=_detect_dtype(col_values, patterns),
                null_ratio=(len(col_values) - len(non_null)) / len(col_values) if col_values else 0.0,
                unique_ratio=len(unique) / len(non_null) if non_null else 0.0,
                non_null_count=len(non_null),
                sample_values=non_null[:5],
                distinct_sample_values=list(unique)[:5],
                detected_patterns=patterns,
            )
        )
    return SchemaProfile(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        row_count=len(rows),
        columns=columns,
    )


def load_csv(path: Path) -> SchemaProfile:
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = [row for row in reader if row]
    return _build_profile_from_rows(path.stem, path.stem, header, rows)


# ---------------------------------------------------------------------------
# 2. Rich output formatting
# ---------------------------------------------------------------------------


def _fmt_concept_list(concepts) -> str:
    """Format a list of CanonicalConceptMatchDetail as 'Display (id) / ...'."""
    items = []
    for c in concepts or []:
        display = getattr(c, "display_name", "")
        cid = getattr(c, "concept_id", "")
        if display and cid:
            items.append(f"{display} ({cid})")
        elif display:
            items.append(display)
        elif cid:
            items.append(cid)
    return " / ".join(items) if items else "-"


def _fmt_signal_breakdown(signals: ScoringSignals) -> str:
    """Compact signal breakdown: name=0.14, semantic=0.02, ..."""
    parts = []
    for name in (
        "name", "semantic", "knowledge", "canonical",
        "pattern", "statistical", "overlap", "embedding",
        "correction", "llm",
    ):
        v = getattr(signals, name, 0.0)
        if v:
            parts.append(f"{name}={v:.2f}")
    return ", ".join(parts) if parts else "all-zero"


def _fmt_canonical_path(cand: MappingCandidate) -> str:
    """Build 'SOURCE → concept (id) → TARGET' or 'No shared canonical path.'."""
    source_name = cand.source or "?"
    target_name = cand.target or "(no target)"
    details = cand.canonical_details
    shared = details.shared_concepts if details else []
    if shared:
        c = shared[0]
        return f"{source_name} → {c.display_name} ({c.concept_id}) → {target_name}"
    # Fall back to first source concept if no shared.
    src = (details.source_concepts if details else [])
    if src:
        c = src[0]
        return f"{source_name} → {c.display_name} ({c.concept_id}) → {target_name}"
    return "No shared canonical path."


def _fmt_confidence_pct(conf: float) -> str:
    """Format as integer percent when whole, else one decimal."""
    pct = conf * 100
    if abs(pct - round(pct)) < 0.05:
        return f"{round(pct)}%"
    return f"{pct:.1f}%"


def _fmt_validator(method: str) -> str:
    """Map engine method to a friendly validator label."""
    if not method:
        return "-"
    m = method.lower()
    if "llm" in m:
        return "LLM"
    if "heuristic" in m or "multi_signal" in m:
        return "Heuristic"
    return method


def _fmt_decision_type(cand: MappingCandidate) -> str:
    """Infer decision type from status + target."""
    if cand.status == "accepted" and cand.target:
        return "Direct mapping"
    if cand.status == "needs_review" and cand.target:
        return "Direct mapping (review)"
    if cand.status == "rejected" or not cand.target:
        return "-"
    return "Direct mapping"


def _fmt_status(cand: MappingCandidate) -> str:
    return cand.status or "-"


def _fmt_llm(cand: MappingCandidate) -> str:
    if cand.llm_consulted:
        rec = cand.llm_recommendation
        if rec is not None:
            return f"called ({rec.confidence:.2f})"
        return "called"
    return "-"


def _fmt_llm_consulted(cand: MappingCandidate) -> str:
    return "Yes" if cand.llm_consulted else "-"


def _fmt_review_conclusion(cand: MappingCandidate) -> str:
    """Multi-line explanation with each engine sentence separated by ' | '."""
    parts = cand.explanation or []
    if not parts:
        return "(no explanation)"
    return " | ".join(parts)


# Column widths (tuned for terminal output).
_WIDTHS = {
    "Source": 8,
    "Target": 22,
    "Confidence": 11,
    "LLM": 12,
    "Status": 13,
    "Validator": 10,
    "Source concepts": 40,
    "Target concepts": 40,
    "Canonical path": 70,
    "Decision type": 22,
    "Transformation rule": 20,
    "LLM consulted": 13,
}


def _row(values: list[str], key_for_width: list[str]) -> str:
    cells = []
    for v, key in zip(values, key_for_width):
        w = _WIDTHS.get(key, 20)
        # Truncate with ellipsis if too long, but try to keep one full line.
        s = v if len(v) <= w else v[: w - 1] + "…"
        cells.append(s.ljust(w))
    return "  ".join(cells)


def _header(key_for_width: list[str]) -> str:
    return _row(key_for_width, key_for_width)


def _divider(key_for_width: list[str]) -> str:
    parts = []
    for key in key_for_width:
        w = _WIDTHS.get(key, 20)
        parts.append("-" * w)
    return "  ".join(parts)


COLUMNS = [
    "Source",
    "Target",
    "Confidence",
    "LLM",
    "Status",
    "Validator",
    "Source concepts",
    "Target concepts",
    "Canonical path",
    "Decision type",
    "Transformation rule",
    "LLM consulted",
]


def _candidate_row(cand: MappingCandidate) -> str:
    details = cand.canonical_details
    return _row(
        [
            cand.source or "?",
            cand.target or "(no target)",
            _fmt_confidence_pct(cand.confidence),
            _fmt_llm(cand),
            _fmt_status(cand),
            _fmt_validator(cand.method),
            _fmt_concept_list(details.source_concepts if details else []),
            _fmt_concept_list(details.target_concepts if details else []),
            _fmt_canonical_path(cand),
            _fmt_decision_type(cand),
            cand.transformation_code or "-",
            _fmt_llm_consulted(cand),
        ],
        COLUMNS,
    )


# ---------------------------------------------------------------------------
# 3. Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 130)
    print("Semantra: Rich File-to-File Mapping Demo (supplier case)")
    print("=" * 130)
    print(f"Source: {SOURCE_PATH.relative_to(_REPO_ROOT)}")
    print(f"Target: {TARGET_PATH.relative_to(_REPO_ROOT)}")
    print()

    source_schema = load_csv(SOURCE_PATH)
    target_schema = load_csv(TARGET_PATH)
    source_handle = DatasetHandle(
        dataset_id=source_schema.dataset_id,
        dataset_name=source_schema.dataset_name,
        schema_profile=source_schema,
    )

    # Call the engine directly to get the FULL MappingCandidate payload.
    response = mapping_service.generate_mapping_candidates(
        source_schema=source_schema,
        target_schema=target_schema,
        write_decision_log=False,  # demo only — don't pollute the DB
    )
    mappings: list[MappingCandidate] = response.mappings

    # -- Per-source-field decision table ----------------------------------
    print("MAPPING DECISIONS")
    print("=" * 130)
    print(_header(COLUMNS))
    print(_divider(COLUMNS))
    for cand in mappings:
        print(_candidate_row(cand))
    print()

    # -- Per-field rich description ---------------------------------------
    print("PER-FIELD REVIEW DETAIL")
    print("=" * 130)
    for cand in mappings:
        print()
        print(f"{cand.source} → {cand.target or '(no target)'}")
        print(f"  Canonical path:   {_fmt_canonical_path(cand)}")
        print(f"  Signal breakdown: {_fmt_signal_breakdown(cand.signals)}")
        print(f"  Review conclusion: {_fmt_review_conclusion(cand)}")
    print()

    # -- Coverage report --------------------------------------------------
    coverage = response.canonical_coverage
    print("CANONICAL COVERAGE")
    print("=" * 130)
    print(f"  Source:  {coverage.source.matched_columns}/{coverage.source.total_columns} columns matched "
          f"({coverage.source.coverage_ratio:.0%})")
    print(f"  Target:  {coverage.target.matched_columns}/{coverage.target.total_columns} columns matched "
          f"({coverage.target.coverage_ratio:.0%})")
    print(f"  Project: {coverage.project.matched_columns}/{coverage.project.total_columns} columns matched "
          f"({coverage.project.coverage_ratio:.0%}), "
          f"shared concepts: {len(coverage.project.shared_concepts)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
