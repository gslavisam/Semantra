"""Focused tests for runtime handling of non-output mapping resolution types."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.mapping import MappingDecision
from app.services.codegen_service import generate_pandas_code
from app.services.preview_service import build_preview
from app.services.transformation_spec_service import transformation_spec_target_fields


def test_transformation_spec_target_fields_skips_out_of_scope_decisions() -> None:
    decisions = [
        MappingDecision(source="cust_id", target="customer_id", status="accepted"),
        MappingDecision(
            source="legacy_flag",
            target="employee.termination_date",
            status="accepted",
            resolution_type="out_of_scope",
        ),
        MappingDecision(
            source="managed_id",
            target="employee_id",
            status="accepted",
            resolution_type="target_managed",
        ),
    ]

    assert transformation_spec_target_fields(decisions) == ["customer_id"]


def test_build_preview_skips_out_of_scope_decisions() -> None:
    rows = [{"cust_id": "1001", "legacy_flag": "X"}]
    decisions = [
        MappingDecision(source="cust_id", target="customer_id", status="accepted"),
        MappingDecision(
            source="legacy_flag",
            target="employee.termination_date",
            status="accepted",
            resolution_type="out_of_scope",
            resolution_payload={"reason": "Technical staging field only."},
        ),
        MappingDecision(
            source="managed_id",
            target="employee_id",
            status="accepted",
            resolution_type="target_managed",
            resolution_payload={"reason": "Assigned by destination system."},
        ),
    ]

    preview = build_preview(rows, decisions)

    assert preview.preview[0].values == {"customer_id": "1001"}
    assert preview.unresolved_targets == []


def test_generate_pandas_code_skips_out_of_scope_decisions() -> None:
    decisions = [
        MappingDecision(source="cust_id", target="customer_id", status="accepted"),
        MappingDecision(
            source="legacy_flag",
            target="employee.termination_date",
            status="accepted",
            resolution_type="out_of_scope",
        ),
        MappingDecision(
            source="managed_id",
            target="employee_id",
            status="accepted",
            resolution_type="target_managed",
        ),
    ]

    artifact = generate_pandas_code(decisions)

    assert 'df_target["customer_id"] = df_source["cust_id"]' in artifact.code
    assert 'employee.termination_date' not in artifact.code
    assert 'employee_id' not in artifact.code
    assert any(warning.message.startswith("Skipped inactive mapping") for warning in artifact.warnings)