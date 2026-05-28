"""Benchmark UI for evaluation runs, profile comparison, and explanation surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st

from streamlit_ui.governance import mapping_benchmark_block_reason


AVAILABLE_SCORING_PROFILES = ["balanced", "schema_only", "data_rich", "canonical_first", "description_priority"]


def _section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


def benchmark_dataset_options() -> list[tuple[str, int]]:
    """Build selectbox labels for saved benchmark datasets loaded into session state."""

    datasets = st.session_state.get("benchmark_datasets", [])
    return [
        (
            f"#{item['dataset_id']} | {item['name']} | v{item['version']} | cases={item['case_count']}",
            item["dataset_id"],
        )
        for item in datasets
    ]


def _current_mapping_benchmark_block_reason(mapping_decisions: list[dict[str, Any]]) -> str:
    return mapping_benchmark_block_reason(mapping_decisions)


def _benchmark_explanation_enabled(
    benchmark_result: dict[str, Any] | None,
    correction_impact: dict[str, Any] | None,
    profile_comparison: dict[str, Any] | None,
) -> bool:
    return any(item is not None for item in (benchmark_result, correction_impact, profile_comparison))


def _benchmark_explanation_unlock_message(
    benchmark_result: dict[str, Any] | None,
    correction_impact: dict[str, Any] | None,
    profile_comparison: dict[str, Any] | None,
) -> str:
    if _benchmark_explanation_enabled(benchmark_result, correction_impact, profile_comparison):
        return "Loaded benchmark evidence is ready for benchmark explanation review."
    return "Run a benchmark, correction-impact check, or scoring-profile comparison first to unlock benchmark explanation."


def _benchmark_explanation_intro_caption() -> str:
    return (
        "Generate one bounded benchmark explanation for the currently loaded benchmark evidence before changing scoring assumptions. "
        "This is a read-only guidance surface and does not change scoring state."
    )


def _benchmark_explanation_payload(
    *,
    dataset_name: str,
    benchmark_result: dict[str, Any] | None,
    correction_impact: dict[str, Any] | None,
    profile_comparison: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "dataset_name": str(dataset_name or "").strip(),
        "benchmark_result": benchmark_result,
        "correction_impact": correction_impact,
        "profile_comparison": profile_comparison,
    }


def _benchmark_explanation_section_label(benchmark_explanation: dict[str, Any] | None) -> str:
    metadata = (benchmark_explanation or {}).get("generation_metadata") or {}
    detail = None
    if benchmark_explanation:
        detail = "LLM" if metadata.get("used_llm") else "Fallback"
    return _section_label("Benchmark Explanation", detail)


def _benchmark_explanation_action_label(benchmark_explanation: dict[str, Any] | None) -> str:
    return "Refresh benchmark explanation" if benchmark_explanation else "Generate benchmark explanation"


def _benchmark_explanation_empty_message(explanation_enabled: bool) -> str:
    if not explanation_enabled:
        return "No benchmark evidence is loaded yet."
    return "No benchmark explanation has been generated yet for the loaded benchmark evidence."


def _benchmark_explanation_success_message(dataset_name: str) -> str:
    return f"Generated benchmark explanation for {dataset_name}."


def _benchmark_explanation_error_message(error: object) -> str:
    return f"Benchmark explanation generation failed: {error}"


def _benchmark_explanation_metadata_caption(benchmark_explanation: dict[str, Any] | None) -> str:
    if not benchmark_explanation:
        return ""
    metadata = (benchmark_explanation or {}).get("generation_metadata") or {}
    detail = "LLM" if metadata.get("used_llm") else "Fallback"
    fallback_suffix = " with fallback contract" if metadata.get("fallback_used") else ""
    return f"{detail}{fallback_suffix}"


def _benchmark_explanation_output_heading(title: str) -> str:
    return str(title or "").strip()


def render_benchmark_tab(
    *,
    admin_token_required: Callable[[], bool],
    build_mapping_decisions: Callable[[], list[dict[str, Any]]],
    build_current_benchmark_case: Callable[[], dict | None],
    api_request: Callable[..., Any],
) -> None:
    """Render benchmark save, run, comparison, and explanation controls."""

    st.header("Benchmarks")
    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for benchmark dataset management and saved runs.")
        return
    if not token_required:
        st.info("Backend currently allows benchmark operations without an admin token.")

    st.subheader("Save Current Mapping As Benchmark")
    benchmark_case = build_current_benchmark_case()
    current_mapping_decisions = build_mapping_decisions()
    benchmark_block_reason = _current_mapping_benchmark_block_reason(current_mapping_decisions)
    benchmark_name = st.text_input(
        "Benchmark dataset name",
        value=st.session_state.get("benchmark_dataset_name", "mapping-review-benchmark"),
        key="benchmark_dataset_name",
    )
    if benchmark_case:
        st.json(benchmark_case)
    else:
        st.info("Upload data and keep at least one active mapping decision to create a benchmark dataset.")

    if st.button(
        "Save current mapping as benchmark",
        disabled=(benchmark_case is None) or (not benchmark_name.strip()) or bool(benchmark_block_reason),
        width="stretch",
        key="benchmark_save_current_mapping",
    ):
        try:
            saved = api_request(
                "POST",
                "/evaluation/datasets",
                json={"name": benchmark_name.strip(), "cases": [benchmark_case]},
            )
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Saved benchmark dataset #{saved['dataset_id']} ({saved['name']}, v{saved['version']}).",
            }
            st.rerun()
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Saving benchmark dataset failed: {error}",
            }
            st.rerun()
    if benchmark_block_reason:
        st.caption(benchmark_block_reason)

    st.subheader("Saved Benchmark Datasets")
    if "benchmark_datasets" not in st.session_state:
        try:
            st.session_state["benchmark_datasets"] = api_request("GET", "/evaluation/datasets")
        except httpx.HTTPError:
            st.session_state["benchmark_datasets"] = []
    list_columns = st.columns(2)
    if list_columns[0].button("Load saved benchmark datasets", width="stretch", key="benchmark_load_datasets"):
        try:
            st.session_state["benchmark_datasets"] = api_request("GET", "/evaluation/datasets")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded saved benchmark datasets."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading benchmark datasets failed: {error}"}
        st.rerun()
    if list_columns[1].button("Load benchmark runs", width="stretch", key="benchmark_load_runs"):
        try:
            st.session_state["benchmark_runs"] = api_request("GET", "/evaluation/runs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded benchmark run history."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading benchmark runs failed: {error}"}
        st.rerun()

    dataset_options = benchmark_dataset_options()
    if dataset_options:
        selected_label = st.selectbox(
            "Saved dataset",
            [label for label, _ in dataset_options],
            key="selected_benchmark_dataset_label",
        )
        selected_dataset_id = next(dataset_id for label, dataset_id in dataset_options if label == selected_label)
        selected_dataset = next(
            (item for item in st.session_state.get("benchmark_datasets", []) if item.get("dataset_id") == selected_dataset_id),
            None,
        )
        selected_dataset_name = str((selected_dataset or {}).get("name") or f"dataset #{selected_dataset_id}")
        with_llm = st.checkbox("Run selected benchmark with configured LLM", key="benchmark_with_llm")
        current_runtime_profile = str(st.session_state.get("runtime_config_snapshot", {}).get("scoring_profile", "balanced"))
        st.caption(f"Current runtime scoring profile: {current_runtime_profile}")
        available_profiles = list(
            st.session_state.get("runtime_config_snapshot", {}).get("available_scoring_profiles")
            or AVAILABLE_SCORING_PROFILES
        )
        default_profiles = [
            profile
            for profile in st.session_state.get("benchmark_profile_compare_selection", available_profiles)
            if profile in available_profiles
        ]
        if not default_profiles:
            default_profiles = list(available_profiles)
        selected_profiles = st.multiselect(
            "Profiles to compare",
            available_profiles,
            default=default_profiles,
            key="benchmark_profile_compare_selection",
            help="Compare saved benchmark accuracy across multiple scoring profiles and get a default-profile recommendation.",
        )
        benchmark_action_columns = st.columns(3)
        if benchmark_action_columns[0].button("Run selected benchmark", width="stretch", key="benchmark_run_selected"):
            try:
                result = api_request(
                    "POST",
                    f"/evaluation/datasets/{selected_dataset_id}/run?with_configured_llm={'true' if with_llm else 'false'}",
                )
                st.session_state["last_benchmark_result"] = result
                st.session_state.pop("last_benchmark_explanation", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Ran benchmark dataset #{selected_dataset_id}.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Running benchmark failed: {error}"}
            st.rerun()
        if benchmark_action_columns[1].button("Measure correction impact", width="stretch", key="benchmark_correction_impact"):
            try:
                impact = api_request(
                    "POST",
                    f"/evaluation/datasets/{selected_dataset_id}/correction-impact?with_configured_llm={'true' if with_llm else 'false'}",
                )
                st.session_state["last_correction_impact"] = impact
                st.session_state.pop("last_benchmark_explanation", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Measured correction impact for benchmark dataset #{selected_dataset_id}.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Measuring correction impact failed: {error}"}
            st.rerun()
        if benchmark_action_columns[2].button(
            "Compare scoring profiles",
            width="stretch",
            key="benchmark_compare_profiles",
            disabled=not selected_profiles,
        ):
            try:
                comparison = api_request(
                    "POST",
                    f"/evaluation/datasets/{selected_dataset_id}/compare-profiles",
                    params={
                        "with_configured_llm": str(with_llm).lower(),
                        "profiles": ",".join(selected_profiles),
                    },
                )
                st.session_state["last_profile_comparison"] = comparison
                st.session_state.pop("last_benchmark_explanation", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Compared scoring profiles for benchmark dataset #{selected_dataset_id}.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Comparing scoring profiles failed: {error}"}
            st.rerun()

        loaded_benchmark_result = st.session_state.get("last_benchmark_result")
        loaded_correction_impact = st.session_state.get("last_correction_impact")
        loaded_profile_comparison = st.session_state.get("last_profile_comparison")
    else:
        st.info(
            "No saved benchmark datasets are available yet. Save the current mapping as a benchmark or load an existing dataset to unlock scoring profile comparison."
        )

    datasets = st.session_state.get("benchmark_datasets")
    if datasets:
        st.dataframe(datasets, width="stretch", hide_index=True)

    benchmark_result = st.session_state.get("last_benchmark_result")
    if benchmark_result:
        st.subheader("Last Benchmark Result")
        st.json(benchmark_result)

    profile_comparison = st.session_state.get("last_profile_comparison")
    if profile_comparison:
        st.subheader("Scoring Profile Comparison")
        recommended_profile = profile_comparison.get("recommended_profile")
        recommendation_reason = str(profile_comparison.get("recommendation_reason", "")).strip()
        comparison_profiles = profile_comparison.get("profiles", [])
        if recommended_profile:
            st.success(f"Recommended default profile: {recommended_profile}")
        else:
            st.info("No clear default profile winner across the selected profiles.")
        if recommendation_reason:
            st.caption(recommendation_reason)
        st.dataframe(
            [
                {
                    "profile": item["profile"],
                    "accuracy": item["accuracy"],
                    "top1_accuracy": item["top1_accuracy"],
                    "correct_matches": item["correct_matches"],
                    "total_fields": item["total_fields"],
                }
                for item in comparison_profiles
            ],
            width="stretch",
            hide_index=True,
        )
        bucket_rows: list[dict[str, Any]] = []
        for item in comparison_profiles:
            bucket_metrics = item.get("confidence_by_bucket", {})
            bucket_rows.append(
                {
                    "profile": item["profile"],
                    "high_confidence": bucket_metrics.get("high_confidence", 0.0),
                    "medium_confidence": bucket_metrics.get("medium_confidence", 0.0),
                    "low_confidence": bucket_metrics.get("low_confidence", 0.0),
                }
            )
        if bucket_rows:
            st.caption("Confidence bucket accuracy by profile")
            st.dataframe(bucket_rows, width="stretch", hide_index=True)

    correction_impact = st.session_state.get("last_correction_impact")
    if correction_impact:
        st.subheader("Correction Impact")
        st.dataframe(
            [
                {
                    "baseline_accuracy": correction_impact["baseline"]["accuracy"],
                    "correction_aware_accuracy": correction_impact["correction_aware"]["accuracy"],
                    "accuracy_delta": correction_impact["accuracy_delta"],
                    "baseline_top1_accuracy": correction_impact["baseline"]["top1_accuracy"],
                    "correction_aware_top1_accuracy": correction_impact["correction_aware"]["top1_accuracy"],
                    "top1_accuracy_delta": correction_impact["top1_accuracy_delta"],
                    "correct_matches_delta": correction_impact["correct_matches_delta"],
                }
            ],
            width="stretch",
            hide_index=True,
        )

    benchmark_explanation = st.session_state.get("last_benchmark_explanation")
    loaded_benchmark_result = st.session_state.get("last_benchmark_result")
    loaded_correction_impact = st.session_state.get("last_correction_impact")
    loaded_profile_comparison = st.session_state.get("last_profile_comparison")
    explanation_enabled = _benchmark_explanation_enabled(
        loaded_benchmark_result,
        loaded_correction_impact,
        loaded_profile_comparison,
    )
    with st.expander(
        _benchmark_explanation_section_label(benchmark_explanation),
        expanded=bool(benchmark_explanation),
    ):
        st.caption(_benchmark_explanation_intro_caption())
        st.caption(
            _benchmark_explanation_unlock_message(
                loaded_benchmark_result,
                loaded_correction_impact,
                loaded_profile_comparison,
            )
        )
        if st.button(
            _benchmark_explanation_action_label(benchmark_explanation),
            width="stretch",
            key="benchmark_explain_loaded_results",
            disabled=not explanation_enabled,
        ):
            try:
                st.session_state["last_benchmark_explanation"] = api_request(
                    "POST",
                    "/evaluation/explain",
                    json=_benchmark_explanation_payload(
                        dataset_name=selected_dataset_name if dataset_options else "",
                        benchmark_result=loaded_benchmark_result,
                        correction_impact=loaded_correction_impact,
                        profile_comparison=loaded_profile_comparison,
                    ),
                    timeout=90.0,
                )
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": _benchmark_explanation_success_message(
                        selected_dataset_name if dataset_options else "the loaded benchmark"
                    ),
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": _benchmark_explanation_error_message(error),
                }
            st.rerun()

        if benchmark_explanation:
            st.caption(_benchmark_explanation_metadata_caption(benchmark_explanation))
            if benchmark_explanation.get("summary"):
                st.write(str(benchmark_explanation.get("summary")))
            findings_col, risks_col, actions_col = st.columns(3)
            with findings_col:
                st.caption(_benchmark_explanation_output_heading("Key findings"))
                for line in benchmark_explanation.get("key_findings") or []:
                    st.write(f"- {line}")
            with risks_col:
                st.caption(_benchmark_explanation_output_heading("Risks"))
                for line in benchmark_explanation.get("risks") or []:
                    st.write(f"- {line}")
            with actions_col:
                st.caption(_benchmark_explanation_output_heading("Next actions"))
                for line in benchmark_explanation.get("next_actions") or []:
                    st.write(f"- {line}")
        else:
            st.info(_benchmark_explanation_empty_message(explanation_enabled))

    benchmark_runs = st.session_state.get("benchmark_runs")
    if benchmark_runs:
        st.subheader("Benchmark Run History")
        st.dataframe(benchmark_runs, width="stretch", hide_index=True)