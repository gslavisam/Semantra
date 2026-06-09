"""End-to-end test for the rich ``MappingCandidate`` payload.

The companion ``test_e2e_mapping.py`` exercises the SDK adapter, which
flattens the engine output to ``list[CandidateOption]``. This test goes
deeper: it calls the engine directly and asserts on the full
``MappingCandidate`` structure that drives the workspace review table in
the Semantra web app.

The test pins the following invariant: for a real showcase pair, the
engine must produce one ``MappingCandidate`` per source field, each one
carrying a non-empty explanation, a multi-signal ``ScoringSignals``
object, a ``canonical_details`` with at least one concept (when the
canonical glossary knows the field), and a status that is one of the
allowed decision statuses.

Skipped automatically when the Semantra FastAPI backend is not
importable in the current environment.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Iterable

import pytest

# Path setup identical to the demo.
_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "backend"), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from backend.app.services import mapping_service  # noqa: F401
    BACKEND_AVAILABLE = True
except Exception:  # noqa: BLE001
    BACKEND_AVAILABLE = False

from semantra_core.models.mapping import (  # noqa: E402
    CandidateOption,
    MappingCandidate,
    ScoringSignals,
)
from semantra_core.models.schema import (  # noqa: E402
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)


pytestmark = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="Semantra FastAPI backend not importable; skipping rich e2e test.",
)


# Minimal CSV loader (duplicated here to keep the test self-contained).
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
    if not patterns:
        patterns.append("text")
    return patterns


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
                dtype="str",
                null_ratio=(len(col_values) - len(non_null)) / len(col_values) if col_values else 0.0,
                unique_ratio=len(unique) / len(non_null) if non_null else 0.0,
                non_null_count=len(non_null),
                sample_values=non_null[:5],
                detected_patterns=patterns,
            )
        )
    return SchemaProfile(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        row_count=len(rows),
        columns=columns,
    )


def _load_supplier_pair() -> tuple[SchemaProfile, SchemaProfile]:
    """Load the supplier-master CSV pair as two SchemaProfiles."""
    folder = _REPO / "ui_fixtures" / "showcase_supplier_master"
    src_path = folder / "showcase_supplier_source.csv"
    tgt_path = folder / "showcase_supplier_target.csv"
    with open(src_path) as fh:
        reader = csv.reader(fh)
        src_header = next(reader)
        src_rows = [r for r in reader if r]
    with open(tgt_path) as fh:
        reader = csv.reader(fh)
        tgt_header = next(reader)
        tgt_rows = [r for r in reader if r]
    return (
        _build_profile_from_rows(src_path.stem, src_path.stem, src_header, src_rows),
        _build_profile_from_rows(tgt_path.stem, tgt_path.stem, tgt_header, tgt_rows),
    )


def test_rich_mapping_one_candidate_per_source_field() -> None:
    """The engine must produce one MappingCandidate per source column."""
    source, target = _load_supplier_pair()
    response = mapping_service.generate_mapping_candidates(
        source_schema=source, target_schema=target, write_decision_log=False
    )
    assert isinstance(response.mappings, list)
    # Supplier source has 14 columns.
    assert len(response.mappings) == len(source.columns) == 14
    for mc in response.mappings:
        assert isinstance(mc, MappingCandidate)


def test_rich_mapping_candidates_have_required_rich_fields() -> None:
    """Every MappingCandidate must carry a non-empty explanation and a real ScoringSignals."""
    source, target = _load_supplier_pair()
    response = mapping_service.generate_mapping_candidates(
        source_schema=source, target_schema=target, write_decision_log=False
    )
    for mc in response.mappings:
        # Each candidate must explain itself.
        assert isinstance(mc.explanation, list)
        assert mc.explanation, f"{mc.source}: empty explanation"
        # Multi-signal scoring object with all 10 dimensions.
        assert isinstance(mc.signals, ScoringSignals)
        for dim in (
            "name", "semantic", "knowledge", "canonical", "pattern",
            "statistical", "overlap", "embedding", "correction", "llm",
        ):
            assert hasattr(mc.signals, dim), f"{mc.source}: signals missing {dim!r}"
        # Status must be one of the valid decision statuses.
        assert mc.status in {"accepted", "needs_review", "rejected"}, (
            f"{mc.source}: bad status {mc.status!r}"
        )
        # Method must mention a real engine family.
        assert mc.method, f"{mc.source}: empty method"


def test_rich_mapping_canonical_details_present_for_known_concepts() -> None:
    """SAP-aliased source fields should resolve to a canonical concept on the source side."""
    source, target = _load_supplier_pair()
    response = mapping_service.generate_mapping_candidates(
        source_schema=source, target_schema=target, write_decision_log=False
    )
    by_source = {mc.source: mc for mc in response.mappings}

    # These are well-known canonical concepts in the Semantra glossary.
    expected = {
        "LIFNR": "supplier.id",       # Supplier ID
        "STCD1": "tax.id",            # Tax Registration ID
        "SPERR": "supplier.posting_block_flag",
        "TELF1": "contact.phone",     # Contact Phone
    }
    for src_field, concept_id in expected.items():
        mc = by_source.get(src_field)
        assert mc is not None, f"missing mapping for {src_field}"
        cd = mc.canonical_details
        assert cd is not None, f"{src_field}: no canonical_details"
        # The source should have at least one canonical concept match.
        ids = [c.concept_id for c in (cd.source_concepts or [])]
        assert ids, f"{src_field}: empty source_concepts"
        assert any(concept_id in i for i in ids), (
            f"{src_field}: expected concept containing {concept_id!r}, got {ids}"
        )


def test_rich_mapping_resolves_well_known_sap_targets() -> None:
    """The engine must map the well-known SAP fields to their target columns."""
    source, target = _load_supplier_pair()
    response = mapping_service.generate_mapping_candidates(
        source_schema=source, target_schema=target, write_decision_log=False
    )
    by_source = {mc.source: mc for mc in response.mappings}

    expected = {
        "LIFNR": "supplier_id",
        "NAME1": "supplier_name",
        "TELF1": "phone_number",
        "STCD1": "tax_id_number",
        "ZTERM": "payment_terms_id",
        "STRAS": "street_address",
        "PSTLZ": "postal_code",
        "LOEVM": "deletion_mark",
        "SPERR": "posting_block_flag",
    }
    failures = []
    for src_field, expected_target in expected.items():
        mc = by_source.get(src_field)
        if mc is None:
            failures.append(f"  - {src_field}: missing candidate")
            continue
        if mc.target != expected_target:
            failures.append(
                f"  - {src_field}: expected {expected_target!r}, got {mc.target!r} "
                f"(conf={mc.confidence:.2f})"
            )
    assert not failures, "rich-mapping mismatches:\n" + "\n".join(failures)


def test_rich_mapping_coverage_report_is_populated() -> None:
    """The response's canonical_coverage must be populated and consistent."""
    source, target = _load_supplier_pair()
    response = mapping_service.generate_mapping_candidates(
        source_schema=source, target_schema=target, write_decision_log=False
    )
    cov = response.canonical_coverage
    assert cov is not None
    # Source coverage must be within [0, 1].
    assert 0.0 <= cov.source.coverage_ratio <= 1.0
    assert 0.0 <= cov.target.coverage_ratio <= 1.0
    assert 0.0 <= cov.project.coverage_ratio <= 1.0
    # matched_columns cannot exceed total_columns.
    assert cov.source.matched_columns <= cov.source.total_columns
    assert cov.target.matched_columns <= cov.target.total_columns
    # The supplier case is well-known — at least half the source columns
    # should be matched to a canonical concept.
    assert cov.source.coverage_ratio >= 0.5, (
        f"supplier source coverage is suspiciously low: {cov.source.coverage_ratio:.0%}"
    )
