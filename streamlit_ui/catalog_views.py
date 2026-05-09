from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st


CATALOG_DETAIL_STATE_KEYS = (
    "catalog_integration_detail",
    "catalog_concept_detail",
    "catalog_selected_mapping_set_detail",
    "catalog_selected_mapping_set_audit",
    "catalog_selected_mapping_set_diff",
)


def _mapping_set_reuse_block_reason(status: str | None) -> str:
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "approved":
        return ""
    current_status = normalized_status or "draft"
    return f"Only approved mapping set versions can be reused in Workspace. Current status: {current_status}."


def _clear_catalog_mapping_set_context() -> None:
    for key in (
        "catalog_selected_mapping_set_detail",
        "catalog_selected_mapping_set_audit",
        "catalog_selected_mapping_set_diff",
    ):
        st.session_state.pop(key, None)


def _load_catalog_integration_detail(
    integration_name: str,
    *,
    api_request: Callable[..., Any],
) -> None:
    _clear_catalog_mapping_set_context()
    st.session_state["catalog_integration_detail"] = api_request(
        "GET",
        f"/catalog/integrations/{integration_name}",
    )
    st.session_state["last_action"] = {
        "level": "success",
        "message": f"Loaded catalog detail for '{integration_name}'.",
    }


def _load_catalog_mapping_set_detail(
    mapping_set_id: int,
    *,
    api_request: Callable[..., Any],
) -> None:
    st.session_state["catalog_selected_mapping_set_detail"] = api_request(
        "GET",
        f"/mapping/sets/{mapping_set_id}",
    )
    st.session_state["catalog_selected_mapping_set_audit"] = None
    st.session_state["catalog_selected_mapping_set_diff"] = None
    st.session_state["last_action"] = {
        "level": "success",
        "message": f"Loaded mapping set #{mapping_set_id} into catalog drilldown.",
    }


def _load_catalog_mapping_set_audit(
    mapping_set_id: int,
    *,
    api_request: Callable[..., Any],
) -> None:
    st.session_state["catalog_selected_mapping_set_audit"] = api_request(
        "GET",
        f"/mapping/sets/{mapping_set_id}/audit",
    )
    st.session_state["last_action"] = {
        "level": "success",
        "message": f"Loaded audit trail for mapping set #{mapping_set_id}.",
    }


def _load_catalog_mapping_set_diff(
    mapping_set_id: int,
    against_mapping_set_id: int,
    *,
    api_request: Callable[..., Any],
) -> None:
    st.session_state["catalog_selected_mapping_set_diff"] = api_request(
        "GET",
        f"/mapping/sets/{mapping_set_id}/diff?against_id={against_mapping_set_id}",
    )
    st.session_state["last_action"] = {
        "level": "success",
        "message": f"Loaded diff for mapping set #{mapping_set_id} against #{against_mapping_set_id}.",
    }


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "high_confidence"
    if score >= 0.6:
        return "medium_confidence"
    return "low_confidence"


def _build_catalog_reuse_mapping_response(mapping_set_detail: dict[str, Any]) -> dict[str, Any]:
    name = str(mapping_set_detail.get("name") or "mapping-set").strip() or "mapping-set"
    version = int(mapping_set_detail.get("version") or 1)
    artifact_type = str(mapping_set_detail.get("artifact_type") or "standard").strip().lower()
    canonical_concepts = [
        str(concept).strip()
        for concept in mapping_set_detail.get("canonical_concepts", [])
        if str(concept).strip()
    ]
    canonical_concept_set = set(canonical_concepts)
    mapping_decisions = mapping_set_detail.get("mapping_decisions", [])
    source_count = len(mapping_decisions)
    matched_sources = 0
    mappings: list[dict[str, Any]] = []
    ranked_mappings: list[dict[str, Any]] = []

    for decision in mapping_decisions:
        source = str(decision.get("source") or "").strip()
        if not source:
            continue
        target = str(decision.get("target") or "").strip()
        status = str(decision.get("status") or "needs_review").strip() or "needs_review"
        transformation_code = str(decision.get("transformation_code") or "").strip()
        if target:
            matched_sources += 1
        confidence = 0.95 if target and status == "accepted" else 0.7 if target else 0.35
        candidate_payload: dict[str, Any] = {
            "target": target,
            "status": status,
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "method": "manual_review",
            "explanation": [f"Reused from saved mapping set '{name}' version {version}."],
            "signals": {"knowledge": 0.0, "pattern": 0.0, "semantic": 0.0, "canonical": 0.0},
            "canonical_details": {},
        }
        if transformation_code:
            candidate_payload["transformation_code"] = transformation_code
        if artifact_type == "canonical-only" and target and target in canonical_concept_set:
            candidate_payload["signals"]["canonical"] = 1.0
            candidate_payload["canonical_details"] = {
                "shared_concepts": [
                    {
                        "concept_id": target,
                        "display_name": target,
                        "strength": 1.0,
                    }
                ]
            }

        mappings.append(
            {
                **candidate_payload,
                "source": source,
            }
        )
        ranked_mappings.append(
            {
                "source": source,
                "selected": {**candidate_payload},
                "candidates": [{**candidate_payload}] if target else [],
            }
        )

    source_ratio = (matched_sources / source_count) if source_count else 0.0
    concept_count = len(canonical_concepts)
    concept_ratio = 1.0 if canonical_concepts else 0.0
    return {
        "mappings": mappings,
        "ranked_mappings": ranked_mappings,
        "canonical_coverage": {
            "source": {
                "coverage_ratio": source_ratio,
                "matched_columns": matched_sources,
                "total_columns": source_count,
                "unmatched_columns": [
                    str(source).strip()
                    for source in mapping_set_detail.get("unmatched_sources", [])
                    if str(source).strip()
                ],
            },
            "target": {
                "coverage_ratio": concept_ratio,
                "matched_columns": concept_count,
                "total_columns": concept_count,
            },
            "project": {
                "coverage_ratio": concept_ratio,
                "matched_columns": concept_count,
                "total_columns": concept_count,
                "concept_count": concept_count,
                "shared_concept_count": concept_count,
                "concepts": canonical_concepts,
            },
        },
    }


def _apply_mapping_set_detail_to_workspace(mapping_set_detail: dict[str, Any]) -> None:
    mapping_response = _build_catalog_reuse_mapping_response(mapping_set_detail)
    editor_state: dict[str, dict[str, Any]] = {}
    for decision in mapping_set_detail.get("mapping_decisions", []):
        source = str(decision.get("source") or "").strip()
        if not source:
            continue
        target = str(decision.get("target") or "").strip()
        status = str(decision.get("status") or "needs_review").strip() or "needs_review"
        transformation_code = str(decision.get("transformation_code") or "").strip()
        editor_state[source] = {
            "target": target,
            "status": status,
            "suggested_target": target,
            "suggested_transformation_code": transformation_code,
            "manual_transformation_code": transformation_code,
            "llm_transformation_instruction": "",
            "generated_transformation_reasoning": [],
            "generated_transformation_warnings": [],
            "apply_transformation": False,
            "manual_apply_transformation": bool(transformation_code),
            "manual": False,
        }
        st.session_state[f"transform_{source}"] = False
        st.session_state[f"manual_transform_{source}"] = transformation_code
        st.session_state[f"manual_apply_{source}"] = bool(transformation_code)

    st.session_state["mapping_response"] = mapping_response
    st.session_state["mapping_editor_state"] = editor_state
    st.session_state["preview_response"] = None
    st.session_state["codegen_response"] = None
    st.session_state["mapping_set_name"] = mapping_set_detail.get("name") or ""
    st.session_state["mapping_set_owner"] = mapping_set_detail.get("owner") or ""
    st.session_state["mapping_set_assignee"] = mapping_set_detail.get("assignee") or ""
    st.session_state["mapping_set_review_note"] = mapping_set_detail.get("review_note") or ""


def _reuse_catalog_mapping_set_in_workspace(
    mapping_set_id: int,
    *,
    api_request: Callable[..., Any],
) -> dict[str, Any]:
    mapping_set_detail = api_request(
        "POST",
        f"/mapping/sets/{mapping_set_id}/apply",
        json={
            "changed_by": None,
            "note": "Applied from catalog reuse flow.",
        },
    )
    _apply_mapping_set_detail_to_workspace(mapping_set_detail)
    st.session_state["last_action"] = {
        "level": "success",
        "message": (
            f"Reused mapping set '{mapping_set_detail['name']}' version {mapping_set_detail['version']} in Workspace. "
            "Open Workspace > Review or Decisions to continue."
        ),
    }
    return mapping_set_detail


def render_catalog_tab(
    *,
    admin_token_required: Callable[[], bool],
    api_request: Callable[..., Any],
) -> None:
    st.header("Catalog")
    st.caption("Browse saved integrations, search reusable mapping assets, and inspect canonical concept usage across versions.")

    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for catalog discovery endpoints.")
        return
    if not token_required:
        st.info("Backend currently allows catalog discovery without an admin token.")

    st.subheader("Search and Filters")
    search_columns = st.columns([3, 2, 2, 2])
    query_text = search_columns[0].text_input(
        "Search",
        value=st.session_state.get("catalog_query", ""),
        key="catalog_query",
        placeholder="Integration name, system pair, owner, domain, or canonical concept",
    )
    source_system = search_columns[1].text_input(
        "Source system",
        value=st.session_state.get("catalog_filter_source_system", ""),
        key="catalog_filter_source_system",
        placeholder="Example: SAP",
    )
    target_system = search_columns[2].text_input(
        "Target system",
        value=st.session_state.get("catalog_filter_target_system", ""),
        key="catalog_filter_target_system",
        placeholder="Example: Salesforce",
    )
    business_domain = search_columns[3].text_input(
        "Business domain",
        value=st.session_state.get("catalog_filter_business_domain", ""),
        key="catalog_filter_business_domain",
        placeholder="Example: Customer",
    )

    filter_columns = st.columns([2, 2, 2, 2])
    owner = filter_columns[0].text_input(
        "Owner",
        value=st.session_state.get("catalog_filter_owner", ""),
        key="catalog_filter_owner",
        placeholder="Example: governance-team",
    )
    status = filter_columns[1].selectbox(
        "Status",
        ["", "draft", "review", "approved", "archived"],
        key="catalog_filter_status",
        format_func=lambda value: value or "Any status",
    )
    artifact_type = filter_columns[2].selectbox(
        "Artifact type",
        ["", "standard", "canonical-only"],
        key="catalog_filter_artifact_type",
        format_func=lambda value: value or "Any artifact type",
    )
    mode = filter_columns[3].radio(
        "Mode",
        ["Search", "Browse"],
        horizontal=True,
        key="catalog_query_mode",
    )

    action_columns = st.columns(3)
    if action_columns[0].button("Run catalog query", width="stretch", key="catalog_run_query"):
        params = {
            key: value
            for key, value in {
                "q": query_text.strip(),
                "source_system": source_system.strip(),
                "target_system": target_system.strip(),
                "business_domain": business_domain.strip(),
                "owner": owner.strip(),
                "status": status,
                "artifact_type": artifact_type,
            }.items()
            if value
        }
        try:
            path = "/catalog/search" if mode == "Search" else "/catalog/integrations"
            st.session_state["catalog_results"] = api_request("GET", path, params=params)
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Loaded {len(st.session_state['catalog_results'])} catalog result(s).",
            }
            st.rerun()
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Catalog query failed: {error}",
            }
            st.rerun()
    if action_columns[1].button("Load all integrations", width="stretch", key="catalog_load_all"):
        try:
            st.session_state["catalog_results"] = api_request("GET", "/catalog/integrations")
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Loaded {len(st.session_state['catalog_results'])} saved catalog integration versions.",
            }
            st.rerun()
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Loading catalog integrations failed: {error}",
            }
            st.rerun()
    if action_columns[2].button("Reset catalog state", width="stretch", key="catalog_reset"):
        for key in ("catalog_results", "selected_catalog_integration_name", *CATALOG_DETAIL_STATE_KEYS):
            st.session_state.pop(key, None)
        st.session_state["last_action"] = {"level": "info", "message": "Cleared catalog results and detail state."}
        st.rerun()

    results = st.session_state.get("catalog_results", [])
    if results:
        st.subheader("Integration Results")
        st.dataframe(
            [
                {
                    "integration_name": item.get("integration_name"),
                    "version": item.get("version"),
                    "status": item.get("status"),
                    "artifact_type": item.get("artifact_type"),
                    "source_system": item.get("source_system"),
                    "target_system": item.get("target_system"),
                    "business_domain": item.get("business_domain"),
                    "owner": item.get("owner"),
                    "decision_count": item.get("decision_count"),
                    "canonical_concepts": ", ".join(item.get("canonical_concepts", [])),
                }
                for item in results
            ],
            width="stretch",
            hide_index=True,
        )

        unique_names: list[str] = []
        seen_names: set[str] = set()
        for item in results:
            integration_name = str(item.get("integration_name") or "").strip()
            if integration_name and integration_name not in seen_names:
                seen_names.add(integration_name)
                unique_names.append(integration_name)

        detail_columns = st.columns([3, 1])
        selected_name = detail_columns[0].selectbox(
            "Integration detail",
            unique_names,
            key="selected_catalog_integration_name",
        )
        if detail_columns[1].button("Load detail", width="stretch", key="catalog_load_detail"):
            try:
                _load_catalog_integration_detail(selected_name, api_request=api_request)
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading integration detail failed: {error}",
                }
                st.rerun()
    else:
        st.info("No catalog results loaded yet. Run a search or load saved integrations.")

    integration_detail = st.session_state.get("catalog_integration_detail")
    if integration_detail:
        st.subheader("Integration Detail")
        summary_columns = st.columns(4)
        summary_columns[0].metric("Latest version", integration_detail["latest_version"]["version"])
        summary_columns[1].metric("Versions", len(integration_detail.get("versions", [])))
        summary_columns[2].metric("Canonical concepts", len(integration_detail.get("canonical_concepts", [])))
        summary_columns[3].metric("Unmatched sources", len(integration_detail.get("unmatched_sources", [])))
        st.caption(
            "Systems: "
            f"{integration_detail.get('source_system') or '-'} -> {integration_detail.get('target_system') or '-'} | "
            f"Domain: {integration_detail.get('business_domain') or '-'} | "
            f"Interface: {integration_detail.get('interface_type') or '-'}"
        )
        if integration_detail.get("description"):
            st.write(integration_detail["description"])
        latest_approved = integration_detail.get("latest_approved_version")
        if latest_approved:
            st.caption(
                f"Latest approved version: v{latest_approved['version']} ({latest_approved.get('status')}, owner={latest_approved.get('owner') or '-'})"
            )
        st.write("**Canonical concepts:** " + (", ".join(integration_detail.get("canonical_concepts", [])) or "-"))
        st.write("**Unmatched sources:** " + (", ".join(integration_detail.get("unmatched_sources", [])) or "-"))
        st.dataframe(integration_detail.get("versions", []), width="stretch", hide_index=True)

        version_records = integration_detail.get("versions", [])
        version_labels = [
            f"#{item['mapping_set_id']} | {item['name']} | v{item['version']} | {item['status']}"
            for item in version_records
        ]
        selected_version_label = st.selectbox(
            "Catalog version drilldown",
            version_labels,
            key="catalog_selected_version_label",
        )
        selected_version = version_records[version_labels.index(selected_version_label)]
        reuse_block_reason = _mapping_set_reuse_block_reason(selected_version.get("status"))
        drilldown_actions = st.columns(4)
        if drilldown_actions[0].button("Open selected version", width="stretch", key="catalog_open_selected_version"):
            try:
                _load_catalog_mapping_set_detail(selected_version["mapping_set_id"], api_request=api_request)
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading mapping set detail failed: {error}",
                }
                st.rerun()
        if drilldown_actions[1].button("Load selected audit", width="stretch", key="catalog_open_selected_audit"):
            try:
                _load_catalog_mapping_set_audit(selected_version["mapping_set_id"], api_request=api_request)
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading mapping set audit failed: {error}",
                }
                st.rerun()
        if drilldown_actions[2].button(
            "Reuse in Workspace",
            width="stretch",
            key="catalog_reuse_selected_version",
            disabled=bool(reuse_block_reason),
        ):
            try:
                _reuse_catalog_mapping_set_in_workspace(selected_version["mapping_set_id"], api_request=api_request)
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Reusing mapping set in workspace failed: {error}",
                }
                st.rerun()
        if reuse_block_reason:
            st.caption(reuse_block_reason)
        if drilldown_actions[3].button(
            "Open approved version",
            width="stretch",
            key="catalog_open_approved_version",
            disabled=not bool(latest_approved),
        ):
            try:
                _load_catalog_mapping_set_detail(latest_approved["mapping_set_id"], api_request=api_request)
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading approved mapping set detail failed: {error}",
                }
                st.rerun()

        selected_mapping_set_detail = st.session_state.get("catalog_selected_mapping_set_detail")
        if selected_mapping_set_detail:
            st.subheader("Mapping Set Drilldown")
            st.caption(
                f"#{selected_mapping_set_detail['mapping_set_id']} | {selected_mapping_set_detail['name']} | "
                f"v{selected_mapping_set_detail['version']} | {selected_mapping_set_detail['status']}"
            )
            drilldown_summary = st.columns(4)
            drilldown_summary[0].metric("Decisions", selected_mapping_set_detail.get("decision_count", 0))
            drilldown_summary[1].metric("Status", selected_mapping_set_detail.get("status", "-"))
            drilldown_summary[2].metric("Owner", selected_mapping_set_detail.get("owner") or "-")
            drilldown_summary[3].metric("Assignee", selected_mapping_set_detail.get("assignee") or "-")
            if selected_mapping_set_detail.get("review_note"):
                st.caption(f"Review note: {selected_mapping_set_detail['review_note']}")
            st.dataframe(selected_mapping_set_detail.get("mapping_decisions", []), width="stretch", hide_index=True)

            comparison_candidates = [
                item
                for item in version_records
                if item.get("name") == selected_mapping_set_detail.get("name")
                and item.get("mapping_set_id") != selected_mapping_set_detail.get("mapping_set_id")
            ]
            if comparison_candidates:
                comparison_labels = [
                    f"#{item['mapping_set_id']} | {item['name']} | v{item['version']} | {item['status']}"
                    for item in comparison_candidates
                ]
                comparison_columns = st.columns([3, 1])
                selected_comparison_label = comparison_columns[0].selectbox(
                    "Compare selected version against",
                    comparison_labels,
                    key="catalog_selected_mapping_set_diff_label",
                )
                comparison_mapping_set = comparison_candidates[
                    comparison_labels.index(selected_comparison_label)
                ]
                if comparison_columns[1].button(
                    "Load version diff",
                    width="stretch",
                    key="catalog_load_selected_mapping_set_diff",
                ):
                    try:
                        _load_catalog_mapping_set_diff(
                            selected_mapping_set_detail["mapping_set_id"],
                            comparison_mapping_set["mapping_set_id"],
                            api_request=api_request,
                        )
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Loading mapping set diff failed: {error}",
                        }
                        st.rerun()

            selected_mapping_set_audit = st.session_state.get("catalog_selected_mapping_set_audit")
            if selected_mapping_set_audit:
                st.caption("Selected mapping set audit")
                st.dataframe(selected_mapping_set_audit, width="stretch", hide_index=True)

            selected_mapping_set_diff = st.session_state.get("catalog_selected_mapping_set_diff")
            if selected_mapping_set_diff:
                st.caption(
                    "Selected mapping set diff: "
                    f"v{selected_mapping_set_diff.get('current_version')} vs "
                    f"v{selected_mapping_set_diff.get('against_version')}"
                )
                diff_summary = st.columns(3)
                diff_summary[0].metric("Added", selected_mapping_set_diff.get("added_count", 0))
                diff_summary[1].metric("Removed", selected_mapping_set_diff.get("removed_count", 0))
                diff_summary[2].metric("Changed", selected_mapping_set_diff.get("changed_count", 0))
                st.dataframe(selected_mapping_set_diff.get("changes", []), width="stretch", hide_index=True)

        similar_integrations = integration_detail.get("similar_integrations", [])
        if similar_integrations:
            st.subheader("Similar Integrations")
            st.caption(
                "Similarity is ranked by shared canonical concepts first, then by same source system, target system, business domain, and artifact type."
            )
            st.dataframe(
                [
                    {
                        "integration_name": item.get("integration_name"),
                        "similarity_score": item.get("similarity_score"),
                        "shared_concept_count": item.get("shared_concept_count"),
                        "shared_concepts": ", ".join(item.get("shared_concepts", [])),
                        "same_source_system": item.get("same_source_system"),
                        "same_target_system": item.get("same_target_system"),
                        "same_business_domain": item.get("same_business_domain"),
                        "same_artifact_type": item.get("same_artifact_type"),
                        "latest_version": item.get("latest_version", {}).get("version"),
                        "latest_status": item.get("latest_version", {}).get("status"),
                    }
                    for item in similar_integrations
                ],
                width="stretch",
                hide_index=True,
            )
            similar_names = [item["integration_name"] for item in similar_integrations]
            similar_columns = st.columns([3, 1])
            selected_similar_name = similar_columns[0].selectbox(
                "Open similar integration detail",
                similar_names,
                key="catalog_selected_similar_integration_name",
            )
            if similar_columns[1].button("Open similar integration", width="stretch", key="catalog_open_similar_integration"):
                try:
                    _load_catalog_integration_detail(selected_similar_name, api_request=api_request)
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Loading similar integration failed: {error}",
                    }
                    st.rerun()

    st.subheader("Concept Lookup")
    concept_columns = st.columns([3, 1])
    concept_id = concept_columns[0].text_input(
        "Canonical concept",
        value=st.session_state.get("catalog_concept_query", ""),
        key="catalog_concept_query",
        placeholder="Example: customer.id",
    )
    if concept_columns[1].button("Lookup concept", width="stretch", key="catalog_lookup_concept", disabled=not concept_id.strip()):
        try:
            st.session_state["catalog_concept_detail"] = api_request(
                "GET",
                f"/catalog/concepts/{concept_id.strip()}",
            )
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Loaded catalog concept usage for '{concept_id.strip()}'.",
            }
            st.rerun()
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Concept lookup failed: {error}",
            }
            st.rerun()

    concept_detail = st.session_state.get("catalog_concept_detail")
    if concept_detail:
        st.caption(
            f"Concept {concept_detail['concept_id']} appears in {concept_detail['usage_count']} saved mapping version(s)."
        )
        st.dataframe(concept_detail.get("integrations", []), width="stretch", hide_index=True)