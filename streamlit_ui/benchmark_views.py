from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st


def benchmark_dataset_options() -> list[tuple[str, int]]:
    datasets = st.session_state.get("benchmark_datasets", [])
    return [
        (
            f"#{item['dataset_id']} | {item['name']} | v{item['version']} | cases={item['case_count']}",
            item["dataset_id"],
        )
        for item in datasets
    ]


def render_benchmark_tab(
    *,
    admin_token_required: Callable[[], bool],
    build_current_benchmark_case: Callable[[], dict | None],
    api_request: Callable[..., Any],
) -> None:
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
        disabled=(benchmark_case is None) or (not benchmark_name.strip()),
        use_container_width=True,
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

    st.subheader("Saved Benchmark Datasets")
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
        with_llm = st.checkbox("Run selected benchmark with configured LLM", key="benchmark_with_llm")
        benchmark_action_columns = st.columns(2)
        if benchmark_action_columns[0].button("Run selected benchmark", width="stretch", key="benchmark_run_selected"):
            try:
                result = api_request(
                    "POST",
                    f"/evaluation/datasets/{selected_dataset_id}/run?with_configured_llm={'true' if with_llm else 'false'}",
                )
                st.session_state["last_benchmark_result"] = result
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
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Measured correction impact for benchmark dataset #{selected_dataset_id}.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Measuring correction impact failed: {error}"}
            st.rerun()
    else:
        st.info("No saved benchmark datasets loaded yet.")

    datasets = st.session_state.get("benchmark_datasets")
    if datasets:
        st.dataframe(datasets, width="stretch", hide_index=True)

    benchmark_result = st.session_state.get("last_benchmark_result")
    if benchmark_result:
        st.subheader("Last Benchmark Result")
        st.json(benchmark_result)

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

    benchmark_runs = st.session_state.get("benchmark_runs")
    if benchmark_runs:
        st.subheader("Benchmark Run History")
        st.dataframe(benchmark_runs, width="stretch", hide_index=True)