from __future__ import annotations

from typing import Any

from app.models.mapping import (
    TransformationTestAssertion,
    TransformationTestCase,
    TransformationTestCaseResult,
    TransformationTestSetDetail,
    TransformationTestSetRunResponse,
)
from app.services.preview_service import build_preview


def _normalize_value(value: Any) -> str:
    return "" if value is None else str(value)


def _find_asserted_preview(assertion: TransformationTestAssertion, transformation_previews: list[Any]) -> Any | None:
    return next((preview for preview in transformation_previews if preview.target == assertion.target), None)


def run_transformation_test_case(
    mapping_decisions: list[Any],
    case: TransformationTestCase,
) -> TransformationTestCaseResult:
    preview = build_preview(case.source_rows, mapping_decisions)
    failures: list[str] = []

    for assertion in case.assertions:
        transformation_preview = _find_asserted_preview(assertion, preview.transformation_previews)
        if transformation_preview is None:
            failures.append(f"Missing transformation preview for target '{assertion.target}'.")
            continue

        if assertion.expected_status is not None and transformation_preview.status != assertion.expected_status:
            failures.append(
                f"Expected status '{assertion.expected_status}' for {assertion.target}, got '{transformation_preview.status}'."
            )

        if (
            assertion.expected_classification is not None
            and transformation_preview.classification != assertion.expected_classification
        ):
            failures.append(
                "Expected classification "
                f"'{assertion.expected_classification}' for {assertion.target}, got '{transformation_preview.classification}'."
            )

        if assertion.expected_warning_codes is not None:
            actual_warning_codes = [warning.code for warning in transformation_preview.warnings]
            if actual_warning_codes != assertion.expected_warning_codes:
                failures.append(
                    f"Expected warning codes {assertion.expected_warning_codes} for {assertion.target}, got {actual_warning_codes}."
                )

        if assertion.expected_output_values is not None:
            actual_output_values = [
                _normalize_value(row.values.get(assertion.target, ""))
                for row in preview.preview
            ]
            if actual_output_values != assertion.expected_output_values:
                failures.append(
                    f"Expected output values {assertion.expected_output_values} for {assertion.target}, got {actual_output_values}."
                )

    return TransformationTestCaseResult(
        case_name=case.case_name,
        passed=not failures,
        failures=failures,
        preview=preview.preview,
        transformation_previews=preview.transformation_previews,
    )


def run_transformation_test_set(test_set: TransformationTestSetDetail) -> TransformationTestSetRunResponse:
    case_results = [run_transformation_test_case(test_set.mapping_decisions, case) for case in test_set.cases]
    passed_cases = sum(1 for result in case_results if result.passed)
    return TransformationTestSetRunResponse(
        test_set_id=test_set.test_set_id,
        name=test_set.name,
        passed=passed_cases == len(case_results),
        total_cases=len(case_results),
        passed_cases=passed_cases,
        case_results=case_results,
    )