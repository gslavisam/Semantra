"""Focused tests for runtime handling of non-output mapping resolution types."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.mapping import MappingDecision, TransformationSpec, TransformationSpecFieldRule
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


def test_build_preview_surfaces_transformation_spec_rule_context() -> None:
    rows = [{"cust_id": "1001", "first_name": "Ana", "last_name": "Smith"}]
    decisions = [
        MappingDecision(source="cust_id", target="customer_id", status="accepted"),
        MappingDecision(source="first_name", target="customer_name", status="accepted"),
    ]
    transformation_spec = TransformationSpec(
        target_grain="One row per customer",
        field_rules=[
            TransformationSpecFieldRule(
                target_field="customer_name",
                rule="Join first_name and last_name.",
                source_fields=["first_name", "last_name"],
            )
        ],
    )

    preview = build_preview(rows, decisions, transformation_spec=transformation_spec)
    customer_name_preview = next(item for item in preview.transformation_previews if item.target == "customer_name")

    assert customer_name_preview.spec_rule == "Join first_name and last_name."
    assert customer_name_preview.spec_source_fields == ["first_name", "last_name"]


def test_generate_pandas_code_includes_transformation_spec_comments() -> None:
    decisions = [MappingDecision(source="cust_id", target="customer_id", status="accepted")]
    transformation_spec = TransformationSpec(
        target_grain="One row per customer",
        global_rules="Deduplicate by customer_id.",
        defaults="Keep unknown values as null.",
        field_rules=[
            TransformationSpecFieldRule(
                target_field="customer_id",
                rule="Cast source code to string.",
                source_fields=["cust_id"],
            )
        ],
    )

    artifact = generate_pandas_code(decisions, transformation_spec=transformation_spec)

    assert "# Transformation Design" in artifact.code
    assert "One row per customer" in artifact.code
    assert "Deduplicate by customer_id." in artifact.code
    assert "Cast source code to string." in artifact.code


def test_generate_pyspark_code_includes_transformation_spec_comments() -> None:
    from app.services.codegen_service import generate_pyspark_code

    decisions = [MappingDecision(source="cust_id", target="customer_id", status="accepted")]
    transformation_spec = TransformationSpec(
        target_grain="One row per customer",
        global_rules="Deduplicate by customer_id.",
        field_rules=[
            TransformationSpecFieldRule(target_field="customer_id", rule="Cast source code to string.", source_fields=["cust_id"])
        ],
    )

    artifact = generate_pyspark_code(decisions, transformation_spec=transformation_spec)

    assert "# Transformation Design" in artifact.code
    assert "One row per customer" in artifact.code
    assert "Cast source code to string." in artifact.code
    assert "df_target = df_source.select(" in artifact.code


def test_generate_dbt_code_includes_transformation_spec_sql_comment() -> None:
    from app.services.codegen_service import generate_dbt_code

    decisions = [MappingDecision(source="cust_id", target="customer_id", status="accepted")]
    transformation_spec = TransformationSpec(
        target_grain="One row per customer",
        global_rules="Deduplicate by customer_id.",
        field_rules=[
            TransformationSpecFieldRule(target_field="customer_id", rule="Cast source code to string.", source_fields=["cust_id"])
        ],
    )

    artifact = generate_dbt_code(decisions, transformation_spec=transformation_spec)

    assert "/* " in artifact.code or "/*" in artifact.code
    assert "Transformation Design" in artifact.code
    assert "One row per customer" in artifact.code
    assert "Cast source code to string." in artifact.code
    assert "config(materialized=" in artifact.code