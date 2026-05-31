"""Main Streamlit entry point and thin adapter layer for the Semantra UI."""

from __future__ import annotations

import streamlit as st

from streamlit_ui.api import (
    DEFAULT_API_BASE_URL,
    admin_token_required,
    api_request,
    api_request_content,
    list_canonical_target_fields,
    recover_spec_hint_for_upload,
    request_llm_mapping_refinement,
    request_mapping_analysis_audio,
    request_mapping_analysis_narration,
    request_mapping_analysis_summary,
    request_review_plan_summary,
    request_llm_transformation_suggestion,
    request_transformation_templates,
    sql_tables_for_upload,
    upload_file_to_request_files,
    uploaded_file_bytes,
)
from streamlit_ui.shared_views import (
    render_dataset_summary,
    render_sidebar_help,
    render_sidebar_reference,
    render_last_action_status,
    render_llm_runtime_status,
    render_onboarding_hint,
    render_operation_strip,
    render_status_badge_legend,
    render_step_status,
    render_workspace_copilot_sidebar_brief,
    render_workspace_copilot_sidebar_context,
)


st.set_page_config(page_title="Semantra - Data Integration", page_icon="ST", layout="wide")
ROW_DATA_UPLOAD_TYPES = ["csv", "json", "xml", "xlsx"]
ALL_UPLOAD_TYPES = [*ROW_DATA_UPLOAD_TYPES, "sql"]
ALL_FILTER_OPTION = "All"


# These thin adapters keep imports local so AST-based tests can still load
# individual function definitions from this file without importing full UI modules.


# Mapping helper adapters

def suggested_mapping_by_source(mapping_response: dict) -> dict[str, dict]:
    from streamlit_ui.mapping_helpers import suggested_mapping_by_source as _impl

    return _impl(mapping_response)


def resolve_suggested_transformation_code(entry: dict | None, fallback_code: str | None = None) -> str:
    from streamlit_ui.mapping_helpers import resolve_suggested_transformation_code as _impl

    return _impl(entry, fallback_code)


def effective_transformation_code(source: str, fallback_code: str | None = None) -> str | None:
    from streamlit_ui.mapping_helpers import effective_transformation_code as _impl

    return _impl(source, st.session_state, fallback_code)


def transformation_mode(source: str, fallback_code: str | None = None) -> str:
    from streamlit_ui.mapping_helpers import transformation_mode as _impl

    return _impl(source, st.session_state, fallback_code)


def transformation_mode_label(mode: str) -> str:
    from streamlit_ui.mapping_helpers import transformation_mode_label as _impl

    return _impl(mode)


def knowledge_explanation_lines(explanation: list[str] | None) -> list[str]:
    from streamlit_ui.mapping_helpers import knowledge_explanation_lines as _impl

    return _impl(explanation)


def canonical_explanation_lines(explanation: list[str] | None) -> list[str]:
    from streamlit_ui.mapping_helpers import canonical_explanation_lines as _impl

    return _impl(explanation)


def canonical_concept_labels(canonical_details: dict | None) -> list[str]:
    from streamlit_ui.mapping_helpers import canonical_concept_labels as _impl

    return _impl(canonical_details)


def canonical_path_label(source: str, target: str | None, canonical_details: dict | None) -> str:
    from streamlit_ui.mapping_helpers import canonical_path_label as _impl

    return _impl(source, target, canonical_details, canonical_concept_labels_func=canonical_concept_labels)


def source_concept_rows(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_helpers import source_concept_rows as _impl

    return _impl(mapping_response, st.session_state, suggested_mapping_by_source_func=suggested_mapping_by_source)


def concept_target_rows(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_helpers import concept_target_rows as _impl

    return _impl(mapping_response, st.session_state, suggested_mapping_by_source_func=suggested_mapping_by_source)


def canonical_concept_groups(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_helpers import canonical_concept_groups as _impl

    return _impl(
        mapping_response,
        st.session_state,
        suggested_mapping_by_source_func=suggested_mapping_by_source,
        canonical_path_label_func=canonical_path_label,
    )


def detect_spec_hint_for_upload(uploaded_file, cache_key: str) -> dict | None:
    from streamlit_ui.api import detect_spec_hint_for_upload as _impl

    return _impl(uploaded_file, cache_key)


def upload_dataset_handle(
    uploaded_file,
    *,
    mode: str,
    selected_table: str | None = None,
    header_row_index: int | None = None,
    name_col: str | None = None,
    description_col: str | None = None,
    type_col: str | None = None,
    sample_values_col: str | None = None,
) -> dict:
    from streamlit_ui.api import upload_dataset_handle as _impl

    return _impl(
        uploaded_file,
        mode=mode,
        selected_table=selected_table,
        header_row_index=header_row_index,
        name_col=name_col,
        description_col=description_col,
        type_col=type_col,
        sample_values_col=sample_values_col,
    )


def enrich_dataset_metadata(
    dataset_id: str,
    uploaded_file,
    *,
    header_row_index: int | None = None,
    name_col: str | None = None,
    description_col: str | None = None,
    type_col: str | None = None,
    sample_values_col: str | None = None,
) -> dict:
    from streamlit_ui.api import enrich_dataset_metadata as _impl

    return _impl(
        dataset_id,
        uploaded_file,
        header_row_index=header_row_index,
        name_col=name_col,
        description_col=description_col,
        type_col=type_col,
        sample_values_col=sample_values_col,
    )


# Local diagnostic helper

def knowledge_debug_rows(mapping_response: dict) -> list[dict]:
    rows: list[dict] = []
    selected_by_source = suggested_mapping_by_source(mapping_response)
    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        target = selected_row.get("target")
        if not target:
            continue
        selected_candidate = next((candidate for candidate in ranked.get("candidates", []) if candidate.get("target") == target), None)
        selected_payload = selected_candidate or ranked.get("selected") or selected_row
        signals = selected_payload.get("signals", {}) if isinstance(selected_payload, dict) else {}
        canonical_details = selected_payload.get("canonical_details", {}) if isinstance(selected_payload, dict) else {}
        knowledge_lines = knowledge_explanation_lines(selected_payload.get("explanation", []) if isinstance(selected_payload, dict) else [])
        canonical_lines = canonical_explanation_lines(selected_payload.get("explanation", []) if isinstance(selected_payload, dict) else [])
        if not knowledge_lines and not canonical_lines and float(signals.get("knowledge", 0.0) or 0.0) <= 0 and float(signals.get("canonical", 0.0) or 0.0) <= 0:
            continue
        rows.append(
            {
                "source": source,
                "target": target,
                "knowledge_signal": float(signals.get("knowledge", 0.0) or 0.0),
                "canonical_signal": float(signals.get("canonical", 0.0) or 0.0),
                "confidence": float(selected_payload.get("confidence", 0.0) or 0.0) if isinstance(selected_payload, dict) else 0.0,
                "validator": validator_badge(selected_payload.get("method", "manual_review")) if isinstance(selected_payload, dict) else "Manual",
                "knowledge_explanations": knowledge_lines,
                "canonical_explanations": canonical_lines,
                "canonical_concepts": canonical_concept_labels(canonical_details),
            }
        )
    return rows


def trust_layer_rows(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_helpers import trust_layer_rows as _impl

    return _impl(
        mapping_response,
        st.session_state,
        suggested_mapping_by_source_func=suggested_mapping_by_source,
        resolve_suggested_transformation_code_func=resolve_suggested_transformation_code,
        effective_transformation_code_func=lambda source, _session_state, fallback_code=None: effective_transformation_code(source, fallback_code),
        transformation_mode_func=lambda source, _session_state, fallback_code=None: transformation_mode(source, fallback_code),
    )


# Workspace review view adapters

def render_mapping_analysis_panel(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import render_mapping_analysis_panel as _impl

    return _impl(
        mapping_response,
        request_mapping_analysis_audio=request_mapping_analysis_audio,
        request_mapping_analysis_narration=request_mapping_analysis_narration,
        request_mapping_analysis_summary=request_mapping_analysis_summary,
    )

def display_trust_layer(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import display_trust_layer as _impl

    return _impl(
        mapping_response,
        trust_layer_rows=trust_layer_rows,
        has_knowledge_match=has_knowledge_match,
        has_canonical_match=has_canonical_match,
        canonical_concept_labels=canonical_concept_labels,
        transformation_mode_label=transformation_mode_label,
        llm_runtime_enabled=llm_runtime_enabled,
        request_llm_mapping_refinement=request_llm_mapping_refinement,
        request_llm_transformation_suggestion=request_llm_transformation_suggestion,
        request_transformation_templates=request_transformation_templates,
        materialize_transformation_template=materialize_transformation_template,
        api_request=api_request,
    )


def has_knowledge_match(signals: dict | None, explanation: list[str] | str | None = None) -> bool:
    from streamlit_ui.mapping_helpers import has_knowledge_match as _impl

    return _impl(signals, explanation)


def has_canonical_match(signals: dict | None, explanation: list[str] | str | None = None) -> bool:
    from streamlit_ui.mapping_helpers import has_canonical_match as _impl

    return _impl(signals, explanation)


# Local app helpers

def reset_flow_state() -> None:
    for key in (
        "upload_response",
        "mapping_response",
        "mapping_analysis_summary",
        "mapping_analysis_error",
        "mapping_analysis_spoken_script",
        "mapping_analysis_audio_bytes",
        "mapping_analysis_audio_mime_type",
        "mapping_analysis_audio_error",
        "review_plan_summary",
        "review_plan_error",
        "canonical_gap_candidates",
        "canonical_gap_suggestions",
        "canonical_gap_triage_summary",
        "canonical_gap_triage_error",
        "catalog_reuse_fit_summary",
        "catalog_reuse_fit_error",
        "preview_response",
        "codegen_response",
        "codegen_refinement_response",
        "workspace_copilot_chat_history",
        "workspace_copilot_chat_last_response",
        "saved_corrections",
        "mapping_editor_state",
        "transformation_templates",
        "source_signature",
        "source_spec_signature",
        "source_spec_hint",
        "source_spec_header_row_index",
        "source_tables",
        "target_signature",
        "target_spec_signature",
        "target_spec_hint",
        "target_spec_header_row_index",
        "target_tables",
        "source_table",
        "target_table",
        "mapping_mode",
        "canonical_target_system",
        "active_draft_session",
        "source_upload_mode",
        "target_upload_mode",
        "source_companion_spec_header_row_index",
        "target_companion_spec_header_row_index",
    ):
        st.session_state.pop(key, None)


def handle_api_base_url_change() -> None:
    normalized_base_url = str(st.session_state.get("api_base_url") or "").strip().rstrip("/") or DEFAULT_API_BASE_URL
    previous_base_url = str(st.session_state.get("active_api_base_url") or DEFAULT_API_BASE_URL).strip().rstrip("/") or DEFAULT_API_BASE_URL
    st.session_state["api_base_url"] = normalized_base_url
    if normalized_base_url == previous_base_url:
        return

    reset_flow_state()
    for key in list(st.session_state.keys()):
        if key.startswith(("benchmark_", "catalog_", "debug_")):
            st.session_state.pop(key, None)

    for key in (
        "runtime_config_snapshot",
        "runtime_config_snapshot_refreshed_at",
        "admin_requirement",
        "admin_requirement_signature",
        "backend_reachable",
        "backend_reachable_base_url",
        "pending_top_level_area",
        "pending_workspace_section",
        "pending_governance_section",
        "active_governance_section",
        "review_focus_sources",
        "governance_focus_sources",
        "pending_governance_canonical_concept_id",
        "pending_governance_canonical_source_system",
        "pending_governance_canonical_business_domain",
        "pending_governance_gap_source_filter",
    ):
        st.session_state.pop(key, None)

    st.session_state["active_api_base_url"] = normalized_base_url
    st.session_state["pending_top_level_area"] = "Workspace"
    st.session_state["pending_workspace_section"] = "Setup"
    st.session_state["active_top_level_area"] = "Workspace"
    st.session_state["active_workspace_section"] = "Setup"
    st.session_state["last_action"] = {
        "level": "info",
        "message": (
            f"API base URL switched to {normalized_base_url}. "
            "Cleared transient backend state so the UI can reload against the new runtime."
        ),
    }


def llm_runtime_enabled() -> bool:
    config = st.session_state.get("runtime_config_snapshot")
    if not config:
        return False
    if str(config.get("llm_provider", "none")).strip().lower() == "none":
        return False
    return str(config.get("llm_status", "configured")).strip().lower() not in {"unreachable", "misconfigured"}


def materialize_transformation_template(template: dict | None, source: str, target: str) -> str:
    if not template:
        return ""
    code_template = str(template.get("code_template") or "")
    if not code_template:
        return ""
    return code_template.replace("{source}", source).replace("{target}", target)


def schema_columns_for_case(handle: dict) -> list[dict]:
    return [
        {
            "name": column["name"],
            "normalized_name": column["normalized_name"],
            "dtype": column["dtype"],
            "null_ratio": column["null_ratio"],
            "unique_ratio": column["unique_ratio"],
            "avg_length": column["avg_length"],
            "non_null_count": column["non_null_count"],
            "sample_values": column["sample_values"],
            "distinct_sample_values": column["distinct_sample_values"],
            "detected_patterns": column["detected_patterns"],
            "tokenized_name": column["tokenized_name"],
        }
        for column in handle["schema_profile"]["columns"]
    ]


def validator_badge(method: str) -> str:
    labels = {
        "llm_validated": "LLM validator",
        "multi_signal_heuristic": "Heuristic",
        "manual_review": "Manual",
    }
    return labels.get(method, method.replace("_", " ").title())


# Workspace review/state adapters

def render_mapping_review(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import render_mapping_review as _impl

    return _impl(
        mapping_response,
        current_mapping_rows=current_mapping_rows,
        source_concept_rows=source_concept_rows,
        concept_target_rows=concept_target_rows,
        all_filter_option=ALL_FILTER_OPTION,
        validator_badge=validator_badge,
        canonical_path_label=canonical_path_label,
        request_review_plan_summary=request_review_plan_summary,
        llm_runtime_enabled=llm_runtime_enabled,
        request_llm_mapping_refinement=request_llm_mapping_refinement,
    )


def render_canonical_concept_summary(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import render_canonical_concept_summary as _impl

    return _impl(
        mapping_response,
        canonical_concept_groups=canonical_concept_groups,
    )


def current_mapping_rows(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_helpers import current_mapping_rows as _impl

    return _impl(
        mapping_response,
        st.session_state,
        suggested_mapping_by_source_func=suggested_mapping_by_source,
        validator_badge=validator_badge,
        canonical_path_label_func=canonical_path_label,
    )


def initialize_mapping_editor_state(mapping_response: dict) -> None:
    from streamlit_ui.mapping_state import initialize_mapping_editor_state as _impl

    return _impl(
        mapping_response,
        st.session_state,
        suggested_mapping_by_source=suggested_mapping_by_source,
        default_editor_entry_func=default_editor_entry,
    )


def selected_target_options(ranked: dict) -> list[str]:
    from streamlit_ui.mapping_helpers import selected_target_options as _impl

    return _impl(ranked)


def schema_column_names(handle: dict) -> list[str]:
    from streamlit_ui.mapping_state import schema_column_names as _impl

    return _impl(handle)


def ranked_sources(mapping_response: dict) -> set[str]:
    from streamlit_ui.mapping_state import ranked_sources as _impl

    return _impl(mapping_response)


def render_mapping_editor(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import render_mapping_editor as _impl

    return _impl(mapping_response, selected_target_options=selected_target_options)


def render_canonical_gap_assistant(mapping_response: dict) -> None:
    from streamlit_ui.workspace_review_views import render_canonical_gap_assistant as _impl

    return _impl(mapping_response, api_request=api_request)


def upsert_manual_mapping(source: str, target: str, status: str) -> None:
    from streamlit_ui.mapping_state import upsert_manual_mapping as _impl

    return _impl(source, target, status, st.session_state)


def default_editor_entry(ranked: dict, selected_mapping: dict | None = None) -> dict[str, str | bool]:
    from streamlit_ui.mapping_state import default_editor_entry as _impl

    return _impl(ranked, selected_mapping)


def remove_manual_mapping(source: str, mapping_response: dict) -> None:
    from streamlit_ui.mapping_state import remove_manual_mapping as _impl

    return _impl(
        source,
        mapping_response,
        st.session_state,
        suggested_mapping_by_source=suggested_mapping_by_source,
        default_editor_entry_func=default_editor_entry,
    )


def manual_mapping_rows(mapping_response: dict) -> list[dict]:
    from streamlit_ui.mapping_state import manual_mapping_rows as _impl

    return _impl(mapping_response, st.session_state, ranked_sources_func=ranked_sources)


def render_manual_mapping_panel(mapping_response: dict) -> None:
    from streamlit_ui.workspace_decision_views import render_manual_mapping_panel as _impl

    return _impl(
        mapping_response,
        schema_column_names=schema_column_names,
        build_mapping_decisions=build_mapping_decisions,
        upsert_manual_mapping=upsert_manual_mapping,
        manual_mapping_rows=manual_mapping_rows,
        remove_manual_mapping=remove_manual_mapping,
        list_canonical_target_fields=list_canonical_target_fields,
    )


def build_mapping_decisions() -> list[dict]:
    from streamlit_ui.mapping_state import build_mapping_decisions as _impl

    return _impl(
        st.session_state,
        resolve_suggested_transformation_code=resolve_suggested_transformation_code,
        effective_transformation_code=effective_transformation_code,
    )


def export_mapping_payload() -> str:
    from streamlit_ui.mapping_state import export_mapping_payload as _impl

    return _impl(st.session_state, build_mapping_decisions_func=build_mapping_decisions)


def export_mapping_excel_bytes() -> bytes:
    from streamlit_ui.mapping_state import export_mapping_excel_bytes as _impl

    return _impl(st.session_state, build_mapping_decisions_func=build_mapping_decisions)


def build_mapping_set_payload(
    name: str,
    created_by: str | None = None,
    note: str | None = None,
    owner: str | None = None,
    assignee: str | None = None,
    review_note: str | None = None,
) -> dict:
    from streamlit_ui.mapping_state import build_mapping_set_payload as _impl

    return _impl(
        name,
        st.session_state,
        build_mapping_decisions_func=build_mapping_decisions,
        created_by=created_by,
        note=note,
        owner=owner,
        assignee=assignee,
        review_note=review_note,
    )


def build_current_benchmark_case() -> dict | None:
    from streamlit_ui.mapping_state import build_current_benchmark_case as _impl

    return _impl(
        st.session_state,
        build_mapping_decisions_func=build_mapping_decisions,
        schema_columns_for_case=schema_columns_for_case,
    )


def apply_imported_mapping_payload(raw_payload: bytes) -> None:
    from streamlit_ui.mapping_state import apply_imported_mapping_payload as _impl

    return _impl(raw_payload, st.session_state, schema_column_names_func=schema_column_names)


def build_pending_corrections() -> list[dict]:
    from streamlit_ui.mapping_state import build_pending_corrections as _impl

    return _impl(st.session_state)


def correction_governance_block_reason() -> str:
    from streamlit_ui.mapping_state import correction_governance_block_reason as _impl

    return _impl(st.session_state)


def persist_corrections(note: str) -> list[dict]:
    from streamlit_ui.mapping_state import persist_corrections as _impl

    return _impl(
        note,
        st.session_state,
        build_pending_corrections_func=build_pending_corrections,
        api_request=api_request,
    )


# Workspace decisions adapters

def render_mapping_decision_summary() -> None:
    from streamlit_ui.workspace_decision_views import render_mapping_decision_summary as _impl

    return _impl(build_mapping_decisions=build_mapping_decisions)


def render_active_draft_review_state_panel() -> None:
    from streamlit_ui.workspace_decision_views import render_active_draft_review_state_panel as _impl

    return _impl(api_request=api_request)


def render_active_draft_decision_state_panel() -> None:
    from streamlit_ui.workspace_decision_views import render_active_draft_decision_state_panel as _impl

    return _impl(api_request=api_request)


def render_mapping_io_panel() -> None:
    from streamlit_ui.workspace_decision_views import render_mapping_io_panel as _impl

    return _impl(
        build_mapping_decisions=build_mapping_decisions,
        export_mapping_payload=export_mapping_payload,
        export_mapping_excel_bytes=export_mapping_excel_bytes,
        apply_imported_mapping_payload=apply_imported_mapping_payload,
        api_request=api_request,
        build_mapping_set_payload=build_mapping_set_payload,
    )


def render_mapping_set_versions_panel() -> None:
    from streamlit_ui.workspace_decision_views import render_mapping_set_versions_panel as _impl

    return _impl(
        build_mapping_decisions=build_mapping_decisions,
        apply_imported_mapping_payload=apply_imported_mapping_payload,
        api_request=api_request,
        build_mapping_set_payload=build_mapping_set_payload,
    )


def render_correction_panel() -> None:
    from streamlit_ui.workspace_decision_views import render_correction_panel as _impl

    return _impl(
        build_pending_corrections=build_pending_corrections,
        correction_block_reason=correction_governance_block_reason,
        admin_token_required=admin_token_required,
        api_request=api_request,
        persist_corrections=persist_corrections,
    )


# Top-level tab adapters

def render_admin_debug_tab() -> None:
    from streamlit_ui.admin_views import render_admin_debug_tab as _impl

    return _impl(
        admin_token_required=admin_token_required,
        api_request=api_request,
        api_request_content=api_request_content,
        upload_file_to_request_files=upload_file_to_request_files,
        current_mapping_rows=current_mapping_rows,
        knowledge_debug_rows=knowledge_debug_rows,
    )


def render_canonical_console_tab() -> None:
    from streamlit_ui.admin_views import render_canonical_console_panel as _impl

    if admin_token_required() and not str(st.session_state.get("admin_token", "")).strip():
        st.header("Governance")
        st.warning("Admin token is required for governance endpoints.")
        return

    return _impl(
        api_request=api_request,
        api_request_content=api_request_content,
        upload_file_to_request_files=upload_file_to_request_files,
    )


def render_benchmark_tab() -> None:
    from streamlit_ui.benchmark_views import render_benchmark_tab as _impl

    return _impl(
        admin_token_required=admin_token_required,
        build_mapping_decisions=build_mapping_decisions,
        build_current_benchmark_case=build_current_benchmark_case,
        api_request=api_request,
    )


def render_catalog_tab() -> None:
    from streamlit_ui.catalog_views import render_catalog_tab as _impl

    return _impl(
        admin_token_required=admin_token_required,
        api_request=api_request,
    )


def render_workspace_tab() -> None:
    from streamlit_ui.workspace_views import render_workspace_tab as _impl

    return _impl(
        all_upload_types=ALL_UPLOAD_TYPES,
        detect_spec_hint_for_upload=detect_spec_hint_for_upload,
        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
        sql_tables_for_upload=sql_tables_for_upload,
        api_request=api_request,
        upload_dataset_handle=upload_dataset_handle,
        enrich_dataset_metadata=enrich_dataset_metadata,
        uploaded_file_bytes=uploaded_file_bytes,
        render_dataset_summary=render_dataset_summary,
        initialize_mapping_editor_state=initialize_mapping_editor_state,
        render_mapping_analysis_panel=render_mapping_analysis_panel,
        display_trust_layer=display_trust_layer,
        render_mapping_review=render_mapping_review,
        render_mapping_editor=render_mapping_editor,
        render_canonical_gap_assistant=render_canonical_gap_assistant,
        render_canonical_concept_summary=render_canonical_concept_summary,
        render_active_draft_review_state_panel=render_active_draft_review_state_panel,
        render_active_draft_decision_state_panel=render_active_draft_decision_state_panel,
        render_manual_mapping_panel=render_manual_mapping_panel,
        render_mapping_decision_summary=render_mapping_decision_summary,
        render_mapping_io_panel=render_mapping_io_panel,
        render_mapping_set_versions_panel=render_mapping_set_versions_panel,
        render_correction_panel=render_correction_panel,
        build_mapping_decisions=build_mapping_decisions,
        request_mapping_analysis_summary=request_mapping_analysis_summary,
    )


# Application root

TOP_LEVEL_AREAS = ["Workspace", "Catalog", "Benchmarks", "System", "Governance"]

def main() -> None:
    st.title("Semantra - Guided Data Mapping")
    st.caption("Upload and profile data -> Review mappings -> Define transformations -> Generate governed outputs")
    render_step_status()
    render_last_action_status()

    pending_top_level_area = st.session_state.pop("pending_top_level_area", None)
    if pending_top_level_area in TOP_LEVEL_AREAS:
        st.session_state["active_top_level_area"] = pending_top_level_area

    with st.sidebar:
        sidebar_view = st.radio(
            "Sidebar view",
            ("System", "WS Copilot", "WS Brief", "Help", "Reference"),
            key="sidebar_view_mode",
            horizontal=True,
            label_visibility="collapsed",
        )
        st.divider()
        if sidebar_view == "System":
            st.header("Connection")
            st.text_input("API Base URL", value=DEFAULT_API_BASE_URL, key="api_base_url", on_change=handle_api_base_url_change)
            st.text_input("Admin Token", value="", key="admin_token", type="password")
            st.markdown(
                "This UI talks to the Semantra FastAPI backend. LLM and TTS provider endpoints are configured behind that backend and shown below in Runtime."
            )
            render_llm_runtime_status()
            st.divider()
            render_operation_strip(compact=True)
            render_status_badge_legend(title="Unified Status Legend", compact=True)
            if st.button("Reset flow"):
                reset_flow_state()
                st.session_state["last_action"] = {"level": "info", "message": "Flow state was reset."}
                st.rerun()
        elif sidebar_view == "WS Copilot":
            render_workspace_copilot_sidebar_context()
        elif sidebar_view == "WS Brief":
            render_workspace_copilot_sidebar_brief()
        elif sidebar_view == "Help":
            render_sidebar_help()
        else:
            render_sidebar_reference()

    selected_top_level_area = st.radio(
        "Navigation",
        TOP_LEVEL_AREAS,
        key="active_top_level_area",
        horizontal=True,
        label_visibility="collapsed",
    )
    render_onboarding_hint(selected_top_level_area)

    if selected_top_level_area == "Workspace":
        render_workspace_tab()
    elif selected_top_level_area == "Governance":
        render_canonical_console_tab()
    elif selected_top_level_area == "Catalog":
        render_catalog_tab()
    elif selected_top_level_area == "System":
        render_admin_debug_tab()
    elif selected_top_level_area == "Benchmarks":
        render_benchmark_tab()
# comment

if __name__ == "__main__":
    main()