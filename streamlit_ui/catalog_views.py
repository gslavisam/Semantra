"""Catalog UI for approved integration discovery, detail, and reuse-fit review."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import streamlit as st

from streamlit_ui.governance import api_error_message, mapping_set_workspace_block_reason


CATALOG_DETAIL_STATE_KEYS = (
    "catalog_integration_detail",
    "catalog_concept_detail",
    "catalog_selected_mapping_set_detail",
    "catalog_selected_mapping_set_audit",
    "catalog_selected_mapping_set_diff",
    "catalog_reuse_fit_summary",
    "catalog_reuse_fit_error",
    "catalog_workspace_reuse_shortlist",
    "catalog_workspace_field_reuse_shortlist",
    "catalog_integration_pair_compare",
)

CATALOG_LAST_FIELD_IMPORT_STATE_KEY = "catalog_last_field_import"


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


def _catalog_concept_reuse_summary(concept_detail: dict[str, Any] | None) -> dict[str, int]:
    usage_records = (concept_detail or {}).get("integrations", [])
    integration_names = {
        _normalized_text(item.get("integration_name"))
        for item in usage_records
        if _normalized_text(item.get("integration_name"))
    }
    approved_integrations = {
        _normalized_text(item.get("integration_name"))
        for item in usage_records
        if _normalized_text(item.get("integration_name")) and _normalized_text(item.get("status")) == "approved"
    }
    source_systems = {
        _normalized_text(item.get("source_system"))
        for item in usage_records
        if _normalized_text(item.get("source_system"))
    }
    target_systems = {
        _normalized_text(item.get("target_system"))
        for item in usage_records
        if _normalized_text(item.get("target_system"))
    }
    return {
        "usage_count": int((concept_detail or {}).get("usage_count", len(usage_records)) or 0),
        "integration_count": len(integration_names),
        "approved_integration_count": len(approved_integrations),
        "source_system_count": len(source_systems),
        "target_system_count": len(target_systems),
    }


def _catalog_concept_reuse_rows(concept_detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in (concept_detail or {}).get("integrations", []):
        integration_name = _normalized_text(item.get("integration_name")) or "unknown"
        group = grouped.setdefault(
            integration_name,
            {
                "integration_name": integration_name,
                "source_system": _normalized_text(item.get("source_system")),
                "target_system": _normalized_text(item.get("target_system")),
                "business_domain": _normalized_text(item.get("business_domain")),
                "usage_versions": 0,
                "latest_version": 0,
                "latest_approved_version": 0,
                "approved_versions": 0,
                "artifact_types": set(),
                "owners": set(),
                "statuses": Counter(),
            },
        )
        group["usage_versions"] = int(group["usage_versions"]) + 1
        version = int(item.get("version") or 0)
        if version > int(group["latest_version"]):
            group["latest_version"] = version
        status = _normalized_text(item.get("status")) or "unknown"
        statuses = group["statuses"]
        if isinstance(statuses, Counter):
            statuses[status] += 1
        if status == "approved":
            group["approved_versions"] = int(group["approved_versions"]) + 1
            if version > int(group["latest_approved_version"]):
                group["latest_approved_version"] = version
        artifact_type = _normalized_text(item.get("artifact_type"))
        if artifact_type:
            artifact_types = group["artifact_types"]
            if isinstance(artifact_types, set):
                artifact_types.add(artifact_type)
        owner = _normalized_text(item.get("owner"))
        if owner:
            owners = group["owners"]
            if isinstance(owners, set):
                owners.add(owner)

    rows: list[dict[str, Any]] = []
    for group in grouped.values():
        statuses = group["statuses"]
        rows.append(
            {
                "integration_name": group["integration_name"],
                "source_system": group["source_system"],
                "target_system": group["target_system"],
                "business_domain": group["business_domain"],
                "usage_versions": group["usage_versions"],
                "latest_version": group["latest_version"],
                "latest_approved_version": group["latest_approved_version"] or None,
                "approved_versions": group["approved_versions"],
                "artifact_types": ", ".join(sorted(group["artifact_types"])),
                "owners": ", ".join(sorted(group["owners"])),
                "status_mix": ", ".join(
                    f"{status}={count}"
                    for status, count in sorted(statuses.items(), key=lambda pair: (pair[0] != "approved", pair[0]))
                ),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            -int(item.get("approved_versions") or 0),
            -int(item.get("usage_versions") or 0),
            _normalized_text(item.get("integration_name")).lower(),
        ),
    )


def _catalog_system_pair_matrix_rows(results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    target_systems = sorted({_normalized_text(item.get("target_system")) or "-" for item in results or []})
    grouped: dict[str, dict[str, Any]] = {}

    for item in results or []:
        source_system = _normalized_text(item.get("source_system")) or "-"
        target_system = _normalized_text(item.get("target_system")) or "-"
        integration_name = _normalized_text(item.get("integration_name")) or _normalized_text(item.get("name")) or "unknown"
        group = grouped.setdefault(
            source_system,
            {
                "source_system": source_system,
                "integration_names": set(),
                "approved_integration_names": set(),
                "system_pairs": set(),
                "concept_count": 0,
                "target_integrations": {target: set() for target in target_systems},
            },
        )
        group["integration_names"].add(integration_name)
        group["system_pairs"].add(f"{source_system}->{target_system}")
        if _normalized_text(item.get("status")) == "approved":
            group["approved_integration_names"].add(integration_name)
        group["concept_count"] = int(group["concept_count"]) + len(item.get("canonical_concepts", []))
        target_integrations = group["target_integrations"]
        target_integrations.setdefault(target_system, set()).add(integration_name)

    rows: list[dict[str, Any]] = []
    for payload in grouped.values():
        row: dict[str, Any] = {
            "source_system": payload["source_system"],
            "integration_count": len(payload["integration_names"]),
            "approved_integrations": len(payload["approved_integration_names"]),
            "system_pair_count": len(payload["system_pairs"]),
            "canonical_concept_hits": int(payload["concept_count"]),
        }
        for target_system in target_systems:
            row[target_system] = len(payload["target_integrations"].get(target_system, set()))
        rows.append(row)

    return sorted(
        rows,
        key=lambda item: (-int(item.get("integration_count") or 0), _normalized_text(item.get("source_system")).lower()),
    )


def _catalog_result_reuse_hints(
    results: list[dict[str, Any]] | None,
    *,
    min_shared_concepts: int = 2,
) -> dict[str, str]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in results or []:
        integration_name = _normalized_text(item.get("integration_name")) or _normalized_text(item.get("name"))
        if not integration_name:
            continue
        group = grouped.setdefault(
            integration_name,
            {
                "concepts": set(),
                "has_approved": False,
                "source_system": _normalized_text(item.get("source_system")),
                "target_system": _normalized_text(item.get("target_system")),
            },
        )
        group["concepts"].update(
            _normalized_text(concept)
            for concept in item.get("canonical_concepts", [])
            if _normalized_text(concept)
        )
        if _normalized_text(item.get("status")) == "approved":
            group["has_approved"] = True

    hints: dict[str, str] = {}
    for integration_name, payload in grouped.items():
        concepts = payload["concepts"]
        if not concepts:
            continue
        best_candidate: tuple[int, int, str, list[str]] | None = None
        for candidate_name, candidate in grouped.items():
            if candidate_name == integration_name or not candidate["has_approved"]:
                continue
            shared_concepts = sorted(concepts & candidate["concepts"])
            shared_count = len(shared_concepts)
            if shared_count < min_shared_concepts:
                continue
            same_system_pair = int(
                bool(payload["source_system"])
                and bool(payload["target_system"])
                and payload["source_system"] == candidate["source_system"]
                and payload["target_system"] == candidate["target_system"]
            )
            ranking = (same_system_pair, shared_count, candidate_name.lower(), shared_concepts[:3])
            if best_candidate is None or ranking > best_candidate:
                best_candidate = ranking
        if best_candidate is None:
            hints[integration_name] = ""
            continue
        same_system_pair, shared_count, candidate_name_lower, shared_examples = best_candidate
        candidate_name = next(
            name for name in grouped if name.lower() == candidate_name_lower
        )
        hint = f"Similar approved integration exists: {candidate_name} ({shared_count} shared concepts"
        if shared_examples:
            hint += f"; e.g. {', '.join(shared_examples)}"
        hint += ")"
        if same_system_pair:
            hint += " | same system pair"
        hints[integration_name] = hint
    return hints


def _mapping_set_reuse_block_reason(status: str | None) -> str:
    return mapping_set_workspace_block_reason(status, action_label="reused in Workspace")


def _catalog_reuse_fit_workspace_context() -> dict[str, Any]:
    upload_response = st.session_state.get("upload_response") or {}
    mapping_response = st.session_state.get("mapping_response") or {}
    canonical_coverage = mapping_response.get("canonical_coverage") or {}
    source_coverage = canonical_coverage.get("source") or {}
    project_coverage = canonical_coverage.get("project") or {}
    source_handle = upload_response.get("source") or {}
    target_handle = upload_response.get("target") or {}
    mapping_mode = (_normalized_text(upload_response.get("mapping_mode") or st.session_state.get("mapping_mode") or "standard").lower() or "standard")
    decision_rows = mapping_response.get("ranked_mappings") or mapping_response.get("mappings") or []
    status_counts = Counter(
        (_normalized_text(item.get("status")) or "unknown")
        for item in decision_rows
        if isinstance(item, dict)
    )
    return {
        "workspace_loaded": bool(upload_response or mapping_response),
        "mapping_mode": mapping_mode,
        "source_dataset_name": _normalized_text(source_handle.get("dataset_name")) or "Source dataset",
        "target_dataset_name": (
            _normalized_text(upload_response.get("target_system"))
            if mapping_mode == "canonical"
            else _normalized_text(target_handle.get("dataset_name"))
        )
        or "Target dataset",
        "source_system": _normalized_text(st.session_state.get("analysis_source_system")) or None,
        "target_system": (
            _normalized_text(st.session_state.get("analysis_target_system"))
            or (_normalized_text(upload_response.get("target_system")) if mapping_mode == "canonical" else "")
            or None
        ),
        "business_domain": _normalized_text(st.session_state.get("analysis_business_domain")) or None,
        "current_decision_count": len(decision_rows),
        "current_status_counts": dict(status_counts),
        "current_shared_concepts": [
            _normalized_text(concept)
            for concept in project_coverage.get("shared_concepts", [])
            if _normalized_text(concept)
        ],
        "current_unmatched_sources": [
            _normalized_text(source)
            for source in source_coverage.get("unmatched_columns", [])
            if _normalized_text(source)
        ],
        "current_concept_count": int(project_coverage.get("concept_count") or len(project_coverage.get("concepts", []) or [])),
    }


def _catalog_reuse_fit_payload(mapping_set_detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "mapping_set_detail": mapping_set_detail,
        "workspace_context": _catalog_reuse_fit_workspace_context(),
    }


def _catalog_workspace_field_selection_rows() -> list[dict[str, Any]]:
    upload_response = st.session_state.get("upload_response") or {}
    mapping_response = st.session_state.get("mapping_response") or {}
    editor_state = st.session_state.get("mapping_editor_state") or {}

    rows_by_source: dict[str, dict[str, Any]] = {}

    source_columns = (((upload_response.get("source") or {}).get("schema_profile") or {}).get("columns") or [])
    for column in source_columns:
        source_field = _normalized_text((column or {}).get("name"))
        if not source_field:
            continue
        rows_by_source[source_field] = {
            "source_field": source_field,
            "current_target": "",
            "current_status": "",
        }

    for mapping in mapping_response.get("mappings") or []:
        source_field = _normalized_text((mapping or {}).get("source"))
        if not source_field:
            continue
        row = rows_by_source.setdefault(
            source_field,
            {"source_field": source_field, "current_target": "", "current_status": ""},
        )
        row["current_target"] = _normalized_text((mapping or {}).get("target")) or row["current_target"]
        row["current_status"] = _normalized_text((mapping or {}).get("status")) or row["current_status"]

    for ranked in mapping_response.get("ranked_mappings") or []:
        source_field = _normalized_text((ranked or {}).get("source"))
        if not source_field:
            continue
        selected = (ranked or {}).get("selected") or {}
        row = rows_by_source.setdefault(
            source_field,
            {"source_field": source_field, "current_target": "", "current_status": ""},
        )
        row["current_target"] = _normalized_text(selected.get("target")) or row["current_target"]
        row["current_status"] = _normalized_text(selected.get("status")) or row["current_status"]

    for source_field, entry in editor_state.items():
        source_name = _normalized_text(source_field)
        if not source_name:
            continue
        row = rows_by_source.setdefault(
            source_name,
            {"source_field": source_name, "current_target": "", "current_status": ""},
        )
        row["current_target"] = _normalized_text((entry or {}).get("target")) or row["current_target"]
        row["current_status"] = _normalized_text((entry or {}).get("status")) or row["current_status"]

    return sorted(rows_by_source.values(), key=lambda item: _normalized_text(item.get("source_field")).lower())


def _catalog_field_reuse_shortlist_payload(selected_source_fields: list[str]) -> dict[str, Any]:
    selection_rows = _catalog_workspace_field_selection_rows()
    selection_by_source = {
        _normalized_text(item.get("source_field")): item
        for item in selection_rows
        if _normalized_text(item.get("source_field"))
    }
    return {
        "workspace_context": _catalog_reuse_fit_workspace_context(),
        "selected_fields": [
            {
                "source_field": source_field,
                "current_target": selection_by_source.get(source_field, {}).get("current_target") or None,
                "current_status": selection_by_source.get(source_field, {}).get("current_status") or None,
            }
            for source_field in selected_source_fields
            if source_field in selection_by_source
        ],
    }


def _preferred_catalog_review_handoff_concept(*concept_lists: list[str] | None) -> str:
    normalized_lists = [
        [_normalized_text(item) for item in (concept_list or []) if _normalized_text(item)]
        for concept_list in concept_lists
        if concept_list is not None
    ]
    for concept_list in normalized_lists:
        for concept in concept_list:
            if all(concept in other_list for other_list in normalized_lists[1:]):
                return concept
    for concept_list in normalized_lists:
        if concept_list:
            return concept_list[0]
    return ""


def _catalog_mapping_set_record_by_id(
    version_records: list[dict[str, Any]] | None,
    mapping_set_id: int | None,
) -> dict[str, Any] | None:
    target_id = int(mapping_set_id or 0)
    if target_id <= 0:
        return None
    for record in version_records or []:
        if int(record.get("mapping_set_id") or 0) == target_id:
            return record
    return None


def _catalog_mapping_set_diff_focus_sources(changes: list[dict[str, Any]] | None) -> list[str]:
    sources: list[str] = []
    for change in changes or []:
        source = _normalized_text(change.get("source"))
        if source and source not in sources:
            sources.append(source)
    return sources


def _catalog_reuse_fit_label(fit_assessment: str | None) -> str:
    normalized = _normalized_text(fit_assessment).lower()
    labels = {
        "strong_fit": "strong fit",
        "partial_fit": "partial fit",
        "low_fit": "low fit",
    }
    return labels.get(normalized, "")


def _catalog_reuse_fit_section_detail(reuse_fit_summary: dict[str, Any] | None) -> str:
    summary = reuse_fit_summary or {}
    fit_label = _catalog_reuse_fit_label(summary.get("fit_assessment"))
    if not summary:
        return ""
    metadata = summary.get("generation_metadata") or {}
    generation_label = "LLM" if metadata.get("used_llm") else "Fallback"
    if fit_label:
        return f"{fit_label} | {generation_label}"
    return generation_label


def _catalog_reuse_fit_action_label(reuse_fit_summary: dict[str, Any] | None) -> str:
    return "Refresh reuse-fit explanation" if reuse_fit_summary else "Generate reuse-fit explanation"


def _catalog_reuse_fit_intro_caption() -> str:
    return (
        "Generate one bounded reuse-fit explanation for the selected catalog version against the current workspace snapshot before applying reuse. "
        "This is a read-only guidance surface and does not apply or approve anything automatically."
    )


def _catalog_reuse_fit_unlock_message() -> str:
    return "Open the selected catalog version first to unlock reuse-fit review against the current workspace snapshot."


def _catalog_reuse_fit_empty_message() -> str:
    return "No workspace reuse-fit explanation has been generated yet for the selected version."


def _catalog_reuse_fit_success_message() -> str:
    return "Generated workspace reuse-fit explanation for the selected catalog mapping set."


def _catalog_reuse_fit_error_message(error: object) -> str:
    return f"Workspace reuse-fit explanation generation failed: {error}"


def _catalog_reuse_fit_metadata_caption(reuse_fit_summary: dict[str, Any] | None) -> str:
    if not reuse_fit_summary:
        return ""
    metadata = (reuse_fit_summary or {}).get("generation_metadata") or {}
    detail = "LLM" if metadata.get("used_llm") else "Fallback"
    fallback_suffix = " with fallback contract" if metadata.get("fallback_used") else ""
    return f"{detail}{fallback_suffix}"


def _catalog_reuse_fit_output_heading(title: str) -> str:
    return str(title or "").strip()


def _catalog_reuse_fit_ready_for_selected_version(
    selected_version: dict[str, Any] | None,
    selected_mapping_set_detail: dict[str, Any] | None,
) -> bool:
    if not selected_version or not selected_mapping_set_detail:
        return False
    return int(selected_version.get("mapping_set_id") or 0) == int(selected_mapping_set_detail.get("mapping_set_id") or 0)


def _catalog_version_compare_payload(
    selected_mapping_set_detail: dict[str, Any] | None,
    version_records: list[dict[str, Any]] | None,
    latest_approved_version: dict[str, Any] | None,
) -> dict[str, Any]:
    if not selected_mapping_set_detail:
        return {"recommended_target": None, "recommended_reason": "", "rows": []}

    selected_mapping_set_id = int(selected_mapping_set_detail.get("mapping_set_id") or 0)
    selected_version = int(selected_mapping_set_detail.get("version") or 0)
    selected_decision_count = int(selected_mapping_set_detail.get("decision_count") or 0)
    selected_name = _normalized_text(selected_mapping_set_detail.get("name"))
    selected_concepts = {
        _normalized_text(concept)
        for concept in selected_mapping_set_detail.get("canonical_concepts", [])
        if _normalized_text(concept)
    }
    latest_approved_mapping_set_id = int((latest_approved_version or {}).get("mapping_set_id") or 0)

    ranked_rows: list[dict[str, Any]] = []
    for item in version_records or []:
        candidate_mapping_set_id = int(item.get("mapping_set_id") or 0)
        if not candidate_mapping_set_id or candidate_mapping_set_id == selected_mapping_set_id:
            continue
        if selected_name and _normalized_text(item.get("name")) != selected_name:
            continue

        candidate_version = int(item.get("version") or 0)
        candidate_decision_count = int(item.get("decision_count") or 0)
        candidate_concepts = {
            _normalized_text(concept)
            for concept in item.get("canonical_concepts", [])
            if _normalized_text(concept)
        }
        shared_concepts = sorted(selected_concepts & candidate_concepts)

        compare_reasons: list[str] = []
        priority = 0
        if latest_approved_mapping_set_id and candidate_mapping_set_id == latest_approved_mapping_set_id:
            compare_reasons.append("latest approved baseline")
            priority = 4
        if candidate_version < selected_version:
            compare_reasons.append("previous version")
            priority = max(priority, 3)
        elif candidate_version > selected_version:
            compare_reasons.append("newer version")
            priority = max(priority, 2)
        else:
            compare_reasons.append("same version lineage")
            priority = max(priority, 1)

        ranked_rows.append(
            {
                "record": item,
                "priority": priority,
                "version_gap": abs(selected_version - candidate_version),
                "shared_concept_count": len(shared_concepts),
                "compare_reason": ", ".join(compare_reasons),
                "row": {
                    "mapping_set_id": candidate_mapping_set_id,
                    "version": candidate_version,
                    "status": _normalized_text(item.get("status")) or "-",
                    "decision_count": candidate_decision_count,
                    "decision_delta": f"{selected_decision_count - candidate_decision_count:+d}",
                    "shared_concepts": ", ".join(shared_concepts[:3]) or "-",
                    "compare_reason": ", ".join(compare_reasons),
                },
            }
        )

    ranked_rows.sort(
        key=lambda item: (
            -int(item["priority"]),
            int(item["version_gap"]),
            -int(item["shared_concept_count"]),
            -int(item["record"].get("version") or 0),
            int(item["record"].get("mapping_set_id") or 0),
        )
    )
    if not ranked_rows:
        return {"recommended_target": None, "recommended_reason": "", "rows": []}

    recommended_target = ranked_rows[0]["record"]
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(ranked_rows):
        row = dict(item["row"])
        row["suggested_action"] = "Recommended diff baseline" if index == 0 else "Optional peer compare"
        rows.append(row)
    return {
        "recommended_target": recommended_target,
        "recommended_reason": ranked_rows[0]["compare_reason"],
        "rows": rows,
    }


def _catalog_similar_compare_payload(
    selected_version: dict[str, Any] | None,
    similar_integrations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    selected_concepts = {
        _normalized_text(concept)
        for concept in (selected_version or {}).get("canonical_concepts", [])
        if _normalized_text(concept)
    }

    ranked_rows: list[dict[str, Any]] = []
    for item in similar_integrations or []:
        peer_version = item.get("latest_approved_version") or item.get("latest_version") or {}
        peer_mapping_set_id = int(peer_version.get("mapping_set_id") or 0)
        if not peer_mapping_set_id:
            continue

        shared_concepts = [
            _normalized_text(concept)
            for concept in item.get("shared_concepts", [])
            if _normalized_text(concept)
        ]
        if not shared_concepts and selected_concepts:
            candidate_concepts = {
                _normalized_text(concept)
                for concept in (peer_version or {}).get("canonical_concepts", [])
                if _normalized_text(concept)
            }
            shared_concepts = sorted(selected_concepts & candidate_concepts)

        compare_reasons: list[str] = []
        priority = 0
        if item.get("latest_approved_version"):
            compare_reasons.append("approved peer version available")
            priority += 4
        if item.get("same_source_system") and item.get("same_target_system"):
            compare_reasons.append("same system pair")
            priority += 3
        elif item.get("same_business_domain"):
            compare_reasons.append("same business domain")
            priority += 1
        if item.get("same_artifact_type"):
            compare_reasons.append("same artifact type")
            priority += 1

        similarity_score = float(item.get("similarity_score") or 0.0)
        shared_concept_count = max(int(item.get("shared_concept_count") or 0), len(shared_concepts))
        ranked_rows.append(
            {
                "integration_name": _normalized_text(item.get("integration_name")),
                "priority": priority,
                "similarity_score": similarity_score,
                "shared_concept_count": shared_concept_count,
                "compare_reason": ", ".join(compare_reasons) or "shared canonical coverage",
                "peer_version": peer_version,
                "row": {
                    "integration_name": _normalized_text(item.get("integration_name")) or "-",
                    "drilldown_version": int(peer_version.get("version") or 0),
                    "drilldown_status": _normalized_text(peer_version.get("status")) or "-",
                    "similarity_score": round(similarity_score, 2),
                    "shared_concept_count": shared_concept_count,
                    "shared_concepts": ", ".join(shared_concepts[:3]) or "-",
                    "compare_reason": ", ".join(compare_reasons) or "shared canonical coverage",
                },
            }
        )

    ranked_rows.sort(
        key=lambda item: (
            -int(item["priority"]),
            -float(item["similarity_score"]),
            -int(item["shared_concept_count"]),
            _normalized_text(item["integration_name"]).lower(),
        )
    )
    if not ranked_rows:
        return {"recommended_integration_name": "", "recommended_reason": "", "rows": []}

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(ranked_rows):
        row = dict(item["row"])
        row["suggested_action"] = "Open peer version" if index == 0 else "Open peer detail"
        rows.append(row)
    return {
        "recommended_integration_name": ranked_rows[0]["integration_name"],
        "recommended_reason": ranked_rows[0]["compare_reason"],
        "rows": rows,
    }


def _catalog_next_action_plan(
    mapping_set_detail: dict[str, Any] | None,
    workspace_context: dict[str, Any] | None,
) -> dict[str, str]:
    if not mapping_set_detail:
        return {
            "table_label": "Load detail",
            "primary_area": "Catalog",
            "primary_label": "",
            "primary_summary": "Load integration detail to decide the next action.",
            "secondary_area": "",
            "secondary_label": "",
            "secondary_summary": "",
        }

    workspace_loaded = bool((workspace_context or {}).get("workspace_loaded"))
    status = _normalized_text(mapping_set_detail.get("status")) or "unknown"
    artifact_type = _normalized_text(mapping_set_detail.get("artifact_type")) or "standard"
    unmatched_sources = [
        _normalized_text(source)
        for source in mapping_set_detail.get("unmatched_sources", [])
        if _normalized_text(source)
    ]

    if not workspace_loaded:
        plan = {
            "table_label": "Workspace setup handoff",
            "primary_area": "Workspace",
            "primary_label": "Open workspace setup handoff",
            "primary_summary": (
                "No workspace snapshot is loaded. Continue in Workspace, load the current datasets, and then compare or reuse this catalog version."
            ),
            "secondary_area": "",
            "secondary_label": "",
            "secondary_summary": "",
        }
        if status != "approved" or unmatched_sources or artifact_type == "canonical-only":
            plan.update(
                {
                    "secondary_area": "Governance",
                    "secondary_label": _catalog_governance_handoff_action_label(mapping_set_detail, scope_label=""),
                    "secondary_summary": (
                        "Inspect canonical coverage, stewardship, and approval context before treating this version as a stable reuse baseline."
                    ),
                }
            )
        return plan

    if status != "approved":
        return {
            "table_label": "Canonical governance handoff",
            "primary_area": "Governance",
            "primary_label": _catalog_governance_handoff_action_label(mapping_set_detail, scope_label=""),
            "primary_summary": (
                f"This version is {status}. Inspect governance owner, review note, and canonical coverage before reusing it in Workspace."
            ),
            "secondary_area": "Workspace",
            "secondary_label": "Open workspace review context",
            "secondary_summary": (
                "Keep the current workspace review set visible while you compare this catalog candidate against the active queue."
            ),
        }

    primary_summary = (
        "Continue in Workspace Review to compare the active review set with this approved catalog version before applying reuse."
    )
    if unmatched_sources:
        primary_summary += " After review, run canonical gaps if the same sources stay unmatched."

    secondary_area = ""
    secondary_label = ""
    secondary_summary = ""
    if unmatched_sources or artifact_type == "canonical-only":
        secondary_area = "Governance"
        secondary_label = _catalog_governance_handoff_action_label(mapping_set_detail, scope_label="")
        secondary_summary = (
            "Inspect canonical usage, gap queue, and overlay context for the concepts behind this reuse candidate."
        )

    return {
        "table_label": "Workspace review handoff",
        "primary_area": "Workspace",
        "primary_label": "Open workspace review handoff",
        "primary_summary": primary_summary,
        "secondary_area": secondary_area,
        "secondary_label": secondary_label,
        "secondary_summary": secondary_summary,
    }


def _catalog_governance_handoff_summary(next_action_plan: dict[str, Any] | None) -> str:
    plan = next_action_plan or {}
    if _normalized_text(plan.get("primary_area")).lower() == "governance":
        return str(plan.get("primary_summary") or "").strip()
    if _normalized_text(plan.get("secondary_area")).lower() == "governance":
        return str(plan.get("secondary_summary") or "").strip()
    return ""


def _catalog_governance_handoff_payload(mapping_set_detail: dict[str, Any] | None) -> dict[str, Any]:
    detail = mapping_set_detail or {}
    unmatched_sources: list[str] = []
    for value in detail.get("unmatched_sources", []):
        source = _normalized_text(value)
        if source and source not in unmatched_sources:
            unmatched_sources.append(source)

    canonical_concepts: list[str] = []
    for value in detail.get("canonical_concepts", []):
        concept = _normalized_text(value)
        if concept and concept not in canonical_concepts:
            canonical_concepts.append(concept)

    section = "Stewardship" if unmatched_sources else "Canonical"
    return {
        "section": section,
        "canonical_concept_id": canonical_concepts[0] if canonical_concepts else "",
        "canonical_source_system": _normalized_text(detail.get("source_system")),
        "canonical_business_domain": _normalized_text(detail.get("business_domain")),
        "focus_sources": unmatched_sources,
        "gap_source_filter": unmatched_sources[0] if len(unmatched_sources) == 1 else "",
    }


def _catalog_governance_handoff_reason(mapping_set_detail: dict[str, Any] | None) -> str:
    detail = mapping_set_detail or {}
    unmatched_sources = [
        _normalized_text(value)
        for value in detail.get("unmatched_sources", [])
        if _normalized_text(value)
    ]
    if len(unmatched_sources) == 1:
        return "1 unmatched source field"
    if unmatched_sources:
        return f"{len(unmatched_sources)} unmatched source fields"

    status = _normalized_text(detail.get("status")).lower()
    if status and status != "approved":
        return f"{status} version"

    artifact_type = _normalized_text(detail.get("artifact_type")).lower()
    if artifact_type == "canonical-only":
        return "canonical-only coverage"

    concept_count = len(
        [
            _normalized_text(value)
            for value in detail.get("canonical_concepts", [])
            if _normalized_text(value)
        ]
    )
    if concept_count:
        return "canonical coverage review"
    return "governance follow-up"


def _catalog_governance_handoff_action_label(
    mapping_set_detail: dict[str, Any] | None,
    *,
    scope_label: str,
) -> str:
    payload = _catalog_governance_handoff_payload(mapping_set_detail)
    section = _normalized_text(payload.get("section")) or "Governance"
    destination = "Stewardship" if section == "Stewardship" else "Canonical review"
    prefix = f"{scope_label} " if _normalized_text(scope_label) else ""
    return f"Open {prefix}{destination}"


def _catalog_governance_follow_up_caption(
    mapping_set_detail: dict[str, Any] | None,
    *,
    scope_label: str,
) -> str:
    payload = _catalog_governance_handoff_payload(mapping_set_detail)
    section = _normalized_text(payload.get("section")) or "Governance"
    reason = _catalog_governance_handoff_reason(mapping_set_detail)
    return f"{scope_label}: {section} for {reason}."


def _reset_catalog_governance_handoff_filters() -> None:
    st.session_state["debug_canonical_concept_query"] = ""
    st.session_state["debug_canonical_concept_focus"] = "all"
    st.session_state["debug_canonical_concept_source_system"] = ""
    st.session_state["debug_canonical_concept_business_domain"] = ""
    st.session_state.pop("debug_selected_canonical_concept_label", None)

    st.session_state["debug_canonical_gap_status_filter"] = ""
    st.session_state["debug_canonical_gap_owner_filter"] = ""
    st.session_state["debug_canonical_gap_assignee_filter"] = ""
    st.session_state["debug_canonical_gap_source_filter"] = ""
    st.session_state.pop("debug_selected_canonical_gap_label", None)


def _open_catalog_governance_handoff(mapping_set_detail: dict[str, Any], summary: str) -> None:
    version = int(mapping_set_detail.get("version") or 0)
    name = _normalized_text(mapping_set_detail.get("name")) or "mapping-set"
    handoff_payload = _catalog_governance_handoff_payload(mapping_set_detail)
    section = _normalized_text(handoff_payload.get("section")) or "Governance"

    _reset_catalog_governance_handoff_filters()

    st.session_state["pending_top_level_area"] = "Governance"
    st.session_state["pending_governance_section"] = section

    canonical_concept_id = _normalized_text(handoff_payload.get("canonical_concept_id"))
    if canonical_concept_id:
        st.session_state["pending_governance_canonical_concept_id"] = canonical_concept_id
    else:
        st.session_state.pop("pending_governance_canonical_concept_id", None)

    canonical_source_system = _normalized_text(handoff_payload.get("canonical_source_system"))
    if canonical_source_system:
        st.session_state["pending_governance_canonical_source_system"] = canonical_source_system
    else:
        st.session_state.pop("pending_governance_canonical_source_system", None)

    canonical_business_domain = _normalized_text(handoff_payload.get("canonical_business_domain"))
    if canonical_business_domain:
        st.session_state["pending_governance_canonical_business_domain"] = canonical_business_domain
    else:
        st.session_state.pop("pending_governance_canonical_business_domain", None)

    gap_source_filter = _normalized_text(handoff_payload.get("gap_source_filter"))
    if gap_source_filter:
        st.session_state["pending_governance_gap_source_filter"] = gap_source_filter
    else:
        st.session_state.pop("pending_governance_gap_source_filter", None)

    focus_sources = [
        _normalized_text(value)
        for value in handoff_payload.get("focus_sources", [])
        if _normalized_text(value)
    ]
    if focus_sources:
        st.session_state["governance_focus_sources"] = focus_sources
    else:
        st.session_state.pop("governance_focus_sources", None)

    st.session_state["last_action"] = {
        "level": "info",
        "message": f"Catalog handoff: {name} v{version} -> Governance ({section}). {summary}",
    }


def _open_catalog_handoff(area: str, mapping_set_detail: dict[str, Any], summary: str) -> None:
    if _normalized_text(area).lower() == "governance":
        _open_catalog_governance_handoff(mapping_set_detail, summary)
        return
    version = int(mapping_set_detail.get("version") or 0)
    name = _normalized_text(mapping_set_detail.get("name")) or "mapping-set"
    st.session_state["pending_top_level_area"] = area
    st.session_state["last_action"] = {
        "level": "info",
        "message": f"Catalog handoff: {name} v{version} -> {area}. {summary}",
    }


def _open_catalog_review_focus_handoff(
    *,
    mapping_set_detail: dict[str, Any],
    canonical_concept: str | None = None,
    confidence_label: str | None = None,
    source_fields: list[str] | None = None,
) -> None:
    """Open Workspace with Review filters prefilled from Catalog discovery context."""

    concept = _normalized_text(canonical_concept)
    confidence = _normalized_text(confidence_label) or "All"
    focus_sources: list[str] = []
    for value in source_fields or []:
        source = _normalized_text(value)
        if source and source not in focus_sources:
            focus_sources.append(source)
    name = _normalized_text(mapping_set_detail.get("name")) or "mapping-set"
    version = int(mapping_set_detail.get("version") or 0)

    st.session_state["pending_top_level_area"] = "Workspace"
    st.session_state["pending_workspace_section"] = "Review"
    st.session_state["filter_status"] = "needs_review"
    st.session_state["filter_confidence"] = confidence if confidence else "All"
    st.session_state["filter_source"] = focus_sources[0] if len(focus_sources) == 1 else "All"
    st.session_state["filter_canonical_concept"] = concept if concept else "All"
    if focus_sources:
        st.session_state["review_focus_sources"] = focus_sources
    else:
        st.session_state.pop("review_focus_sources", None)
    focus_summary = ""
    if len(focus_sources) == 1:
        focus_summary = f", source={focus_sources[0]}"
    elif focus_sources:
        focus_summary = f", source_scope={len(focus_sources)} diff fields"
    st.session_state["last_action"] = {
        "level": "info",
        "message": (
            f"Catalog handoff: {name} v{version} -> Workspace Review with filters "
            f"status=needs_review, confidence={st.session_state['filter_confidence']}, "
            f"canonical_concept={st.session_state['filter_canonical_concept']}{focus_summary}."
        ),
    }


def _catalog_detail_state_recovery(error: httpx.HTTPError) -> dict[str, str] | None:
    response = getattr(error, "response", None)
    if response is None or response.status_code != 404:
        return None
    try:
        detail = _normalized_text(response.json().get("detail"))
    except Exception:
        detail = ""
    if "Unknown catalog integration" not in detail:
        return None

    for key in ("catalog_results", "selected_catalog_integration_name", *CATALOG_DETAIL_STATE_KEYS):
        st.session_state.pop(key, None)
    return {
        "level": "warning",
        "message": (
            "Catalog results look stale relative to the backend. Reload catalog query results before opening integration detail again."
        ),
    }


def _clear_catalog_mapping_set_context() -> None:
    for key in (
        "catalog_selected_mapping_set_detail",
        "catalog_selected_mapping_set_audit",
        "catalog_selected_mapping_set_diff",
        "catalog_reuse_fit_summary",
        "catalog_reuse_fit_error",
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
    st.session_state["catalog_reuse_fit_summary"] = None
    st.session_state["catalog_reuse_fit_error"] = None
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


def _reset_workspace_generated_artifacts() -> None:
    for key in (
        "preview_response",
        "codegen_response",
        "codegen_refinement_response",
        "mapping_analysis_summary",
        "mapping_analysis_error",
        "mapping_analysis_spoken_script",
        "mapping_analysis_audio_bytes",
        "mapping_analysis_audio_mime_type",
        "mapping_analysis_audio_error",
        "review_plan_summary",
        "review_plan_error",
    ):
        st.session_state.pop(key, None)


def _catalog_field_reuse_compare_rows(matched_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a side-by-side current-versus-saved comparison for matched field reuse rows."""

    editor_state = st.session_state.get("mapping_editor_state") or {}
    rows: list[dict[str, str | bool]] = []
    for item in matched_rows:
        source = _normalized_text(item.get("source_field"))
        if not source:
            continue
        current_entry = editor_state.get(source) or {}
        current_target = _normalized_text(current_entry.get("target"))
        saved_target = _normalized_text(item.get("target"))
        current_status = _normalized_text(current_entry.get("status"))
        saved_status = _normalized_text(item.get("status"))
        current_transform = _normalized_text(current_entry.get("manual_transformation_code"))
        saved_transform_present = bool(item.get("transformation_present"))
        if current_target and saved_target:
            target_change = "same target" if current_target == saved_target else "override"
        elif saved_target:
            target_change = "safe fill"
        elif current_target:
            target_change = "clear current target"
        else:
            target_change = "still unmapped"
        if current_transform and saved_transform_present:
            transformation_change = "transform replace"
        elif saved_transform_present:
            transformation_change = "transform add"
        elif current_transform:
            transformation_change = "keep current transform"
        else:
            transformation_change = "no transform"
        has_conflict = target_change in {"override", "clear current target"} or transformation_change == "transform replace"
        if target_change == "safe fill" and transformation_change == "transform add":
            review_label = "safe fill + transform add"
        elif target_change == "safe fill":
            review_label = "safe fill"
        elif target_change == "override" and transformation_change == "transform replace":
            review_label = "override + transform replace"
        elif target_change == "override":
            review_label = "override"
        elif target_change == "clear current target":
            review_label = "clear current target"
        elif transformation_change == "transform replace":
            review_label = "transform replace"
        elif transformation_change == "transform add":
            review_label = "transform add"
        else:
            review_label = "aligned"
        rows.append(
            {
                "source_field": source,
                "current_target": current_target or "",
                "saved_target": saved_target or "",
                "reuse_label": review_label,
                "conflict": "yes" if has_conflict else "no",
                "target_change": target_change,
                "current_status": current_status or "",
                "saved_status": saved_status or "",
                "transformation_change": transformation_change,
            }
        )
    return rows


def _restore_last_field_import() -> int:
    """Undo the most recent partial field import from Catalog back into Workspace."""

    snapshot = st.session_state.get(CATALOG_LAST_FIELD_IMPORT_STATE_KEY) or {}
    imported_sources = [source for source in snapshot.get("imported_sources") or [] if _normalized_text(source)]
    if not imported_sources:
        return 0

    editor_state = st.session_state.get("mapping_editor_state") or {}
    decision_audit = st.session_state.get("mapping_decision_audit") or {}
    previous_editor_state = snapshot.get("previous_editor_state") or {}
    previous_decision_audit = snapshot.get("previous_decision_audit") or {}
    previous_manual_transform = snapshot.get("previous_manual_transform") or {}
    previous_manual_apply = snapshot.get("previous_manual_apply") or {}
    previous_transform_apply = snapshot.get("previous_transform_apply") or {}

    restored_count = 0
    for raw_source in imported_sources:
        source = _normalized_text(raw_source)
        if not source:
            continue
        if source in previous_editor_state:
            previous_entry = previous_editor_state[source]
            if previous_entry is None:
                editor_state.pop(source, None)
            else:
                editor_state[source] = previous_entry
        if source in previous_decision_audit:
            previous_audit = previous_decision_audit[source]
            if previous_audit is None:
                decision_audit.pop(source, None)
            else:
                decision_audit[source] = previous_audit
        if source in previous_manual_transform:
            previous_value = previous_manual_transform[source]
            if previous_value is None:
                st.session_state.pop(f"manual_transform_{source}", None)
            else:
                st.session_state[f"manual_transform_{source}"] = previous_value
        if source in previous_manual_apply:
            previous_value = previous_manual_apply[source]
            if previous_value is None:
                st.session_state.pop(f"manual_apply_{source}", None)
            else:
                st.session_state[f"manual_apply_{source}"] = previous_value
        if source in previous_transform_apply:
            previous_value = previous_transform_apply[source]
            if previous_value is None:
                st.session_state.pop(f"transform_{source}", None)
            else:
                st.session_state[f"transform_{source}"] = previous_value
        restored_count += 1

    if not restored_count:
        return 0

    st.session_state["mapping_editor_state"] = editor_state
    st.session_state["mapping_decision_audit"] = decision_audit
    _reset_workspace_generated_artifacts()
    st.session_state.pop(CATALOG_LAST_FIELD_IMPORT_STATE_KEY, None)
    return restored_count


def _merge_mapping_set_fields_into_workspace(
    mapping_set_detail: dict[str, Any],
    *,
    selected_sources: list[str],
) -> int:
    """Merge only selected mapping decisions from a saved mapping set into the active workspace state."""

    normalized_sources = [source for source in {_normalized_text(item) for item in selected_sources} if source]
    if not normalized_sources:
        return 0

    upload_response = st.session_state.get("upload_response") or {}
    valid_source_names = {
        _normalized_text((column or {}).get("name"))
        for column in (((upload_response.get("source") or {}).get("schema_profile") or {}).get("columns") or [])
        if _normalized_text((column or {}).get("name"))
    }
    if valid_source_names:
        normalized_sources = [source for source in normalized_sources if source in valid_source_names]
    if not normalized_sources:
        return 0

    selected_source_set = set(normalized_sources)
    editor_state = st.session_state.get("mapping_editor_state") or {}
    decision_audit = st.session_state.get("mapping_decision_audit") or {}
    previous_editor_state: dict[str, dict[str, Any] | None] = {}
    previous_decision_audit: dict[str, dict[str, Any] | None] = {}
    previous_manual_transform: dict[str, str | None] = {}
    previous_manual_apply: dict[str, bool | None] = {}
    previous_transform_apply: dict[str, bool | None] = {}
    applied_count = 0

    for decision in mapping_set_detail.get("mapping_decisions", []):
        source = _normalized_text((decision or {}).get("source"))
        if source not in selected_source_set:
            continue
        target = _normalized_text((decision or {}).get("target"))
        status = _normalized_text((decision or {}).get("status")) or "needs_review"
        transformation_code = _normalized_text((decision or {}).get("transformation_code"))
        current_entry = editor_state.get(source, {})
        previous_editor_state[source] = dict(current_entry) if source in editor_state else None
        previous_decision_audit[source] = dict(decision_audit[source]) if source in decision_audit else None
        previous_manual_transform[source] = st.session_state.get(f"manual_transform_{source}")
        previous_manual_apply[source] = st.session_state.get(f"manual_apply_{source}")
        previous_transform_apply[source] = st.session_state.get(f"transform_{source}")
        editor_state[source] = {
            "target": target,
            "status": status,
            "suggested_target": current_entry.get("suggested_target", ""),
            "suggested_transformation_code": current_entry.get("suggested_transformation_code", ""),
            "manual_transformation_code": transformation_code,
            "llm_transformation_instruction": current_entry.get("llm_transformation_instruction", ""),
            "generated_transformation_reasoning": current_entry.get("generated_transformation_reasoning", []),
            "generated_transformation_warnings": current_entry.get("generated_transformation_warnings", []),
            "apply_transformation": False,
            "manual_apply_transformation": bool(transformation_code),
            "manual": source not in editor_state or bool(current_entry.get("manual", False)),
        }
        st.session_state[f"transform_{source}"] = False
        st.session_state[f"manual_transform_{source}"] = transformation_code
        st.session_state[f"manual_apply_{source}"] = bool(transformation_code)
        decision_audit[source] = {
            "origin": "catalog_field_reuse",
            "applied_at": datetime.now(UTC).isoformat(),
            "details": {
                "mapping_set_id": int(mapping_set_detail.get("mapping_set_id") or 0),
                "mapping_set_name": _normalized_text(mapping_set_detail.get("name")) or None,
                "mapping_set_version": int(mapping_set_detail.get("version") or 0),
                "mode": "selected_field_import",
            },
        }
        applied_count += 1

    if not applied_count:
        return 0

    st.session_state["mapping_editor_state"] = editor_state
    st.session_state["mapping_decision_audit"] = decision_audit
    st.session_state[CATALOG_LAST_FIELD_IMPORT_STATE_KEY] = {
        "mapping_set_id": int(mapping_set_detail.get("mapping_set_id") or 0),
        "mapping_set_name": _normalized_text(mapping_set_detail.get("name")) or None,
        "mapping_set_version": int(mapping_set_detail.get("version") or 0),
        "imported_sources": list(previous_editor_state.keys()),
        "previous_editor_state": previous_editor_state,
        "previous_decision_audit": previous_decision_audit,
        "previous_manual_transform": previous_manual_transform,
        "previous_manual_apply": previous_manual_apply,
        "previous_transform_apply": previous_transform_apply,
    }
    _reset_workspace_generated_artifacts()
    return applied_count


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
    """Render catalog discovery, detail, comparison, and workspace reuse surfaces."""

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
        discovery_rows = _catalog_system_pair_matrix_rows(results)
        reuse_hints = _catalog_result_reuse_hints(results)
        workspace_context = _catalog_reuse_fit_workspace_context()
        if discovery_rows:
            unique_integrations = {
                _normalized_text(item.get("integration_name"))
                for item in results
                if _normalized_text(item.get("integration_name"))
            }
            approved_integrations = {
                _normalized_text(item.get("integration_name"))
                for item in results
                if _normalized_text(item.get("integration_name")) and _normalized_text(item.get("status")) == "approved"
            }
            system_pairs = {
                f"{_normalized_text(item.get('source_system')) or '-'}->{_normalized_text(item.get('target_system')) or '-'}"
                for item in results
            }
            distinct_concepts = {
                _normalized_text(concept)
                for item in results
                for concept in item.get("canonical_concepts", [])
                if _normalized_text(concept)
            }
            with st.expander(
                _section_label("Discovery Overview", f"{len(system_pairs)} system pairs"),
                expanded=True,
            ):
                discovery_columns = st.columns(4)
                discovery_columns[0].metric("Integrations", len(unique_integrations))
                discovery_columns[1].metric("Approved integrations", len(approved_integrations))
                discovery_columns[2].metric("System pairs", len(system_pairs))
                discovery_columns[3].metric("Distinct concepts", len(distinct_concepts))
                st.caption(
                    "High-level discovery matrix over the current catalog result set. Cells show how many distinct integrations exist for each source-system to target-system path."
                )
                st.dataframe(discovery_rows, width="stretch", hide_index=True)

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
                    "reuse_hint": reuse_hints.get(_normalized_text(item.get("integration_name")), ""),
                    "next_action": _catalog_next_action_plan(item, workspace_context).get("table_label", ""),
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

        with st.expander("Workspace Reuse Shortlist", expanded=False):
            st.caption(
                "Rank approved catalog candidates against the current workspace context using deterministic concept/system/domain/quality signals."
            )
            st.caption(
                "This panel is action-based: click Generate workspace shortlist. Candidates are drawn from approved catalog integrations, not only from the visible table row."
            )
            shortlist_top_n = st.slider(
                "Top candidates",
                min_value=3,
                max_value=15,
                value=int(st.session_state.get("catalog_reuse_shortlist_top_n", 5) or 5),
                key="catalog_reuse_shortlist_top_n",
            )
            if st.button("Generate workspace shortlist", width="stretch", key="catalog_generate_reuse_shortlist"):
                try:
                    shortlist_payload = api_request(
                        "POST",
                        "/catalog/reuse-shortlist",
                        json={
                            "workspace_context": _catalog_reuse_fit_workspace_context(),
                            "top_n": shortlist_top_n,
                        },
                    )
                    st.session_state["catalog_workspace_reuse_shortlist"] = shortlist_payload
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Generated workspace reuse shortlist with {len(shortlist_payload.get('candidates', []))} candidate(s).",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Generating workspace shortlist failed: {error}",
                    }
                    st.rerun()

            has_shortlist_run = "catalog_workspace_reuse_shortlist" in st.session_state
            shortlist = st.session_state.get("catalog_workspace_reuse_shortlist") or {}
            shortlist_rows = shortlist.get("candidates") or []
            if shortlist_rows:
                st.caption(
                    f"Considered integrations: {shortlist.get('considered_integrations', 0)} | workspace_loaded={shortlist.get('workspace_loaded', False)}"
                )
                st.dataframe(
                    [
                        {
                            "integration_name": item.get("integration_name"),
                            "mapping_set_id": item.get("mapping_set_id"),
                            "version": item.get("version"),
                            "score": round(float(item.get("score", 0.0) or 0.0), 3),
                            "concept_overlap": round(float(item.get("concept_overlap_score", 0.0) or 0.0), 3),
                            "system_match": round(float(item.get("system_match_score", 0.0) or 0.0), 3),
                            "domain_match": round(float(item.get("domain_match_score", 0.0) or 0.0), 3),
                            "quality": round(float(item.get("accepted_quality_score", 0.0) or 0.0), 3),
                            "shared_concepts": ", ".join(item.get("shared_concepts") or []),
                        }
                        for item in shortlist_rows
                    ],
                    width="stretch",
                    hide_index=True,
                )
                shortlist_names = [item.get("integration_name") for item in shortlist_rows if _normalized_text(item.get("integration_name"))]
                shortlist_selected_name = st.selectbox(
                    "Open shortlist integration",
                    shortlist_names,
                    key="catalog_shortlist_selected_integration",
                )
                shortlist_selected = next(
                    (
                        item
                        for item in shortlist_rows
                        if _normalized_text(item.get("integration_name")) == _normalized_text(shortlist_selected_name)
                    ),
                    shortlist_rows[0],
                )
                for reason in shortlist_selected.get("reasons") or []:
                    st.caption(f"- {reason}")
                shortlist_actions = st.columns(3)
                if shortlist_actions[0].button("Open shortlisted integration", width="stretch", key="catalog_open_shortlist_integration"):
                    try:
                        _load_catalog_integration_detail(shortlist_selected_name, api_request=api_request)
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Loading shortlisted integration failed: {error}",
                        }
                        st.rerun()
                if shortlist_actions[1].button("Open shortlisted version", width="stretch", key="catalog_open_shortlist_version"):
                    try:
                        _load_catalog_mapping_set_detail(int(shortlist_selected.get("mapping_set_id") or 0), api_request=api_request)
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Loading shortlisted version failed: {error}",
                        }
                        st.rerun()
                if shortlist_actions[2].button("Open review focus", width="stretch", key="catalog_open_shortlist_review_focus"):
                    _open_catalog_review_focus_handoff(
                        mapping_set_detail={
                            "name": shortlist_selected.get("integration_name"),
                            "version": shortlist_selected.get("version"),
                        },
                        canonical_concept=(shortlist_selected.get("shared_concepts") or [""])[0],
                    )

        with st.expander("Field Reuse Search", expanded=False):
            st.caption(
                "Search approved catalog integrations using only selected source fields from the current workspace. "
                "This is field-scoped discovery before any reuse action."
            )
            st.caption(
                "The shortlist uses exact source-field overlap first, then current target agreement, system/domain alignment, and approved-artifact quality proxies."
            )
            field_rows = _catalog_workspace_field_selection_rows()
            if not field_rows:
                st.info("Load a source dataset in Workspace first so Catalog can search by selected workspace fields.")
            else:
                selected_source_fields = st.multiselect(
                    "Selected workspace source fields",
                    options=[item.get("source_field") for item in field_rows if _normalized_text(item.get("source_field"))],
                    key="catalog_field_reuse_selected_sources",
                    help="Choose only the source fields you want to search across approved saved integrations.",
                )
                field_top_n = st.slider(
                    "Top field-match candidates",
                    min_value=3,
                    max_value=15,
                    value=int(st.session_state.get("catalog_field_reuse_shortlist_top_n", 5) or 5),
                    key="catalog_field_reuse_shortlist_top_n",
                )
                if st.button(
                    "Generate field reuse shortlist",
                    width="stretch",
                    key="catalog_generate_field_reuse_shortlist",
                    disabled=not selected_source_fields,
                ):
                    try:
                        shortlist_payload = _catalog_field_reuse_shortlist_payload(selected_source_fields)
                        shortlist_payload["top_n"] = field_top_n
                        field_shortlist = api_request(
                            "POST",
                            "/catalog/field-reuse-shortlist",
                            json=shortlist_payload,
                        )
                        st.session_state["catalog_workspace_field_reuse_shortlist"] = field_shortlist
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Generated field reuse shortlist with {len(field_shortlist.get('candidates', []))} candidate(s).",
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Generating field reuse shortlist failed: {error}",
                        }
                        st.rerun()

                has_field_shortlist_run = "catalog_workspace_field_reuse_shortlist" in st.session_state
                field_shortlist = st.session_state.get("catalog_workspace_field_reuse_shortlist") or {}
                field_shortlist_rows = field_shortlist.get("candidates") or []
                if field_shortlist_rows:
                    st.caption(
                        f"Selected fields: {field_shortlist.get('selected_field_count', 0)} | "
                        f"considered integrations: {field_shortlist.get('considered_integrations', 0)} | "
                        f"workspace_loaded={field_shortlist.get('workspace_loaded', False)}"
                    )
                    st.dataframe(
                        [
                            {
                                "integration_name": item.get("integration_name"),
                                "mapping_set_id": item.get("mapping_set_id"),
                                "version": item.get("version"),
                                "score": round(float(item.get("score", 0.0) or 0.0), 3),
                                "matched_fields": int(item.get("matched_field_count") or 0),
                                "source_overlap": round(float(item.get("source_field_overlap_score", 0.0) or 0.0), 3),
                                "target_match": round(float(item.get("current_target_match_score", 0.0) or 0.0), 3),
                                "system_match": round(float(item.get("system_match_score", 0.0) or 0.0), 3),
                                "domain_match": round(float(item.get("domain_match_score", 0.0) or 0.0), 3),
                            }
                            for item in field_shortlist_rows
                        ],
                        width="stretch",
                        hide_index=True,
                    )
                    field_shortlist_names = [
                        item.get("integration_name")
                        for item in field_shortlist_rows
                        if _normalized_text(item.get("integration_name"))
                    ]
                    selected_field_candidate_name = st.selectbox(
                        "Open field-match candidate",
                        field_shortlist_names,
                        key="catalog_field_reuse_selected_integration",
                    )
                    selected_field_candidate = next(
                        (
                            item
                            for item in field_shortlist_rows
                            if _normalized_text(item.get("integration_name")) == _normalized_text(selected_field_candidate_name)
                        ),
                        field_shortlist_rows[0],
                    )
                    for reason in selected_field_candidate.get("reasons") or []:
                        st.caption(f"- {reason}")
                    matched_rows = selected_field_candidate.get("matched_fields") or []
                    if matched_rows:
                        st.dataframe(
                            [
                                {
                                    "source_field": item.get("source_field"),
                                    "saved_target": item.get("target") or "",
                                    "status": item.get("status") or "",
                                    "current_target_match": "yes" if item.get("current_target_match") else "no",
                                    "transformation": "yes" if item.get("transformation_present") else "no",
                                }
                                for item in matched_rows
                            ],
                            width="stretch",
                            hide_index=True,
                        )
                        compare_rows = _catalog_field_reuse_compare_rows(matched_rows)
                        if compare_rows:
                            conflicts_only = st.checkbox(
                                "Show only conflict fields",
                                value=False,
                                key=f"catalog_field_reuse_conflicts_only_{int(selected_field_candidate.get('mapping_set_id') or 0)}",
                                help="Filter the comparison to fields where import would override the current target or replace an existing transform.",
                            )
                            display_compare_rows = [row for row in compare_rows if row.get("conflict") == "yes"] if conflicts_only else compare_rows
                            st.caption("Current Workspace vs saved mapping set for the selected matched fields.")
                            if display_compare_rows:
                                st.dataframe(display_compare_rows, width="stretch", hide_index=True)
                            else:
                                st.caption("No conflict fields in the current comparison.")
                    selected_match_sources = st.multiselect(
                        "Matched fields to import",
                        options=[_normalized_text(item.get("source_field")) for item in matched_rows if _normalized_text(item.get("source_field"))],
                        default=[_normalized_text(item.get("source_field")) for item in matched_rows if _normalized_text(item.get("source_field"))],
                        key=f"catalog_field_reuse_matched_sources_{int(selected_field_candidate.get('mapping_set_id') or 0)}",
                        help="Choose which overlapping source fields should be merged into the active Workspace decisions.",
                    )
                    last_field_import = st.session_state.get(CATALOG_LAST_FIELD_IMPORT_STATE_KEY) or {}
                    last_import_sources = [source for source in last_field_import.get("imported_sources") or [] if _normalized_text(source)]
                    if last_import_sources:
                        last_import_name = _normalized_text(last_field_import.get("mapping_set_name")) or "saved mapping set"
                        last_import_version = int(last_field_import.get("mapping_set_version") or 0)
                        st.caption(
                            f"Last partial import: {last_import_name} v{last_import_version} | fields: {', '.join(last_import_sources)}"
                        )
                    field_actions = st.columns(4)
                    if field_actions[0].button(
                        "Open field-match integration",
                        width="stretch",
                        key="catalog_open_field_reuse_integration",
                    ):
                        try:
                            _load_catalog_integration_detail(selected_field_candidate_name, api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": f"Loading field-match integration failed: {error}",
                            }
                            st.rerun()
                    if field_actions[1].button(
                        "Open field-match version",
                        width="stretch",
                        key="catalog_open_field_reuse_version",
                    ):
                        try:
                            _load_catalog_mapping_set_detail(int(selected_field_candidate.get("mapping_set_id") or 0), api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": f"Loading field-match version failed: {error}",
                            }
                            st.rerun()
                    if field_actions[2].button(
                        "Import selected fields into Workspace",
                        width="stretch",
                        key="catalog_import_field_reuse_selection",
                        disabled=not selected_match_sources,
                    ):
                        try:
                            mapping_set_detail = api_request(
                                "GET",
                                f"/mapping/sets/{int(selected_field_candidate.get('mapping_set_id') or 0)}",
                            )
                            applied_count = _merge_mapping_set_fields_into_workspace(
                                mapping_set_detail,
                                selected_sources=selected_match_sources,
                            )
                            if applied_count:
                                st.session_state["last_action"] = {
                                    "level": "success",
                                    "message": (
                                        f"Imported {applied_count} field decision(s) from '{selected_field_candidate_name}' into the active Workspace. "
                                        "Open Workspace > Decisions or Review to continue."
                                    ),
                                }
                                st.session_state["pending_top_level_area"] = "Workspace"
                            else:
                                st.session_state["last_action"] = {
                                    "level": "warning",
                                    "message": "No selected field decisions were imported into the current Workspace.",
                                }
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": f"Importing selected field decisions failed: {error}",
                            }
                            st.rerun()
                    if field_actions[3].button(
                        "Undo last field import",
                        width="stretch",
                        key="catalog_undo_last_field_reuse_import",
                        disabled=not last_import_sources,
                    ):
                        restored_count = _restore_last_field_import()
                        if restored_count:
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": f"Reverted the last partial field import for {restored_count} field(s).",
                            }
                            st.session_state["pending_top_level_area"] = "Workspace"
                        else:
                            st.session_state["last_action"] = {
                                "level": "warning",
                                "message": "There is no partial field import snapshot to restore.",
                            }
                        st.rerun()
                else:
                    if has_field_shortlist_run:
                        st.info(
                            "No field-match candidates were returned. Most commonly this means there are no approved integrations with overlap for the selected fields."
                        )
                        st.caption(
                            f"Considered integrations: {field_shortlist.get('considered_integrations', 0)} | workspace_loaded={field_shortlist.get('workspace_loaded', False)}"
                        )
                    else:
                        st.info("No field reuse shortlist generated yet. Click Generate field reuse shortlist.")

        if len(unique_names) >= 2:
            with st.expander("Integration Pair Compare", expanded=False):
                st.caption("Compare two integrations side-by-side before deciding reuse or diff drilldown.")
                compare_columns = st.columns(2)
                compare_base_name = compare_columns[0].selectbox(
                    "Base integration",
                    unique_names,
                    key="catalog_compare_base_name",
                )
                compare_peer_options = [name for name in unique_names if _normalized_text(name) != _normalized_text(compare_base_name)]
                compare_peer_name = compare_columns[1].selectbox(
                    "Peer integration",
                    compare_peer_options,
                    key="catalog_compare_peer_name",
                )
                if st.button("Compare integrations", width="stretch", key="catalog_compare_integrations"):
                    try:
                        compare_payload = api_request(
                            "POST",
                            "/catalog/compare-integrations",
                            json={
                                "base_integration_name": compare_base_name,
                                "peer_integration_name": compare_peer_name,
                            },
                        )
                        st.session_state["catalog_integration_pair_compare"] = compare_payload
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": "Loaded integration compare summary.",
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Comparing integrations failed: {error}",
                        }
                        st.rerun()

                compare_payload = st.session_state.get("catalog_integration_pair_compare") or {}
                if compare_payload:
                    st.write(compare_payload.get("compare_summary") or "")
                    summary_metrics = st.columns(4)
                    summary_metrics[0].metric("Shared concepts", len(compare_payload.get("shared_concepts") or []))
                    summary_metrics[1].metric("Base-only concepts", len(compare_payload.get("base_only_concepts") or []))
                    summary_metrics[2].metric("Peer-only concepts", len(compare_payload.get("peer_only_concepts") or []))
                    summary_metrics[3].metric(
                        "System/domain parity",
                        "yes"
                        if (
                            compare_payload.get("same_source_system")
                            and compare_payload.get("same_target_system")
                            and compare_payload.get("same_business_domain")
                        )
                        else "partial",
                    )
                    st.dataframe(
                        [
                            {
                                "bucket": "shared_concepts",
                                "concepts": ", ".join(compare_payload.get("shared_concepts") or []),
                            },
                            {
                                "bucket": "base_only_concepts",
                                "concepts": ", ".join(compare_payload.get("base_only_concepts") or []),
                            },
                            {
                                "bucket": "peer_only_concepts",
                                "concepts": ", ".join(compare_payload.get("peer_only_concepts") or []),
                            },
                        ],
                        width="stretch",
                        hide_index=True,
                    )
                    for action in compare_payload.get("suggested_next_actions") or []:
                        st.caption(f"- {action}")
                    compare_action_columns = st.columns(4)
                    if compare_action_columns[0].button("Open base detail", width="stretch", key="catalog_open_compare_base_detail"):
                        try:
                            _load_catalog_integration_detail(compare_base_name, api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = _catalog_detail_state_recovery(error) or {
                                "level": "error",
                                "message": f"Loading base integration detail failed: {error}",
                            }
                            st.rerun()
                    if compare_action_columns[1].button("Open peer detail", width="stretch", key="catalog_open_compare_peer_detail"):
                        try:
                            _load_catalog_integration_detail(compare_peer_name, api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = _catalog_detail_state_recovery(error) or {
                                "level": "error",
                                "message": f"Loading peer integration detail failed: {error}",
                            }
                            st.rerun()
                    if compare_action_columns[2].button("Open base review focus", width="stretch", key="catalog_open_compare_base_focus"):
                        _open_catalog_review_focus_handoff(
                            mapping_set_detail=compare_payload.get("base_integration", {}).get("latest_version", {})
                            or {"name": compare_base_name, "version": 0},
                            canonical_concept=(compare_payload.get("shared_concepts") or [""])[0],
                        )
                        st.rerun()
                    if compare_action_columns[3].button("Open peer review focus", width="stretch", key="catalog_open_compare_peer_focus"):
                        _open_catalog_review_focus_handoff(
                            mapping_set_detail=compare_payload.get("peer_integration", {}).get("latest_version", {})
                            or {"name": compare_peer_name, "version": 0},
                            canonical_concept=(compare_payload.get("shared_concepts") or [""])[0],
                        )
                        st.rerun()

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
                st.session_state["last_action"] = _catalog_detail_state_recovery(error) or {
                    "level": "error",
                    "message": f"Loading integration detail failed: {error}",
                }
                st.rerun()
    else:
        st.info("No catalog results loaded yet. Run a search or load saved integrations.")

    integration_detail = st.session_state.get("catalog_integration_detail")
    if integration_detail:
        with st.expander(
            _section_label("Integration Detail", f"{len(integration_detail.get('versions', []))} versions"),
            expanded=True,
        ):
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
                        "message": api_error_message(error, default_prefix="Reusing mapping set in workspace failed"),
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
            reuse_fit_summary = st.session_state.get("catalog_reuse_fit_summary")
            reuse_fit_error = st.session_state.get("catalog_reuse_fit_error")
            reuse_fit_context = _catalog_reuse_fit_workspace_context()
            reuse_fit_ready = _catalog_reuse_fit_ready_for_selected_version(
                selected_version,
                selected_mapping_set_detail,
            )
            with st.expander(
                _section_label(
                    "Workspace Reuse Fit",
                    _catalog_reuse_fit_section_detail(reuse_fit_summary) or None,
                ),
                expanded=bool(reuse_fit_summary or reuse_fit_error),
            ):
                st.caption(_catalog_reuse_fit_intro_caption())
                st.caption(
                    "Workspace context: "
                    f"{reuse_fit_context.get('source_dataset_name') or 'Source dataset'} -> "
                    f"{reuse_fit_context.get('target_dataset_name') or 'Target dataset'} | "
                    f"mode={reuse_fit_context.get('mapping_mode') or 'standard'} | "
                    f"active decisions={reuse_fit_context.get('current_decision_count', 0)} | "
                    f"shared concepts={len(reuse_fit_context.get('current_shared_concepts', []))} | "
                    f"unmatched sources={len(reuse_fit_context.get('current_unmatched_sources', []))}"
                )
                if not reuse_fit_ready:
                    st.info(_catalog_reuse_fit_unlock_message())
                    if st.button(
                        "Open selected version for fit review",
                        width="stretch",
                        key="catalog_open_selected_version_for_fit",
                    ):
                        try:
                            _load_catalog_mapping_set_detail(selected_version["mapping_set_id"], api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": f"Loading mapping set detail failed: {error}",
                            }
                            st.rerun()
                else:
                    if st.button(
                        _catalog_reuse_fit_action_label(reuse_fit_summary),
                        width="stretch",
                        key="catalog_explain_workspace_fit",
                    ):
                        try:
                            st.session_state["catalog_reuse_fit_summary"] = api_request(
                                "POST",
                                "/catalog/reuse-fit",
                                json=_catalog_reuse_fit_payload(selected_mapping_set_detail),
                                timeout=90.0,
                            )
                            st.session_state["catalog_reuse_fit_error"] = None
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": _catalog_reuse_fit_success_message(),
                            }
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["catalog_reuse_fit_summary"] = None
                            st.session_state["catalog_reuse_fit_error"] = _catalog_reuse_fit_error_message(error)
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": st.session_state["catalog_reuse_fit_error"],
                            }
                            st.rerun()

                    if reuse_fit_error:
                        st.warning(reuse_fit_error)
                    if reuse_fit_summary:
                        fit_columns = st.columns(2)
                        fit_columns[0].metric("Fit", _catalog_reuse_fit_label(reuse_fit_summary.get("fit_assessment")))
                        fit_columns[1].metric("Catalog decisions", selected_mapping_set_detail.get("decision_count", 0))
                        st.caption(_catalog_reuse_fit_metadata_caption(reuse_fit_summary))
                        st.write(reuse_fit_summary.get("summary") or "")
                        st.caption(_catalog_reuse_fit_output_heading("Key matches"))
                        for item in reuse_fit_summary.get("key_matches", []):
                            st.write(f"- {item}")
                        st.caption(_catalog_reuse_fit_output_heading("Risks"))
                        for item in reuse_fit_summary.get("risks", []):
                            st.write(f"- {item}")
                        st.caption(_catalog_reuse_fit_output_heading("Next actions"))
                        for item in reuse_fit_summary.get("next_actions", []):
                            st.write(f"- {item}")
                    else:
                        st.info(_catalog_reuse_fit_empty_message())

            if selected_mapping_set_detail:
                selected_workspace_context = _catalog_reuse_fit_workspace_context()
                selected_next_action_plan = _catalog_next_action_plan(
                    selected_mapping_set_detail,
                    selected_workspace_context,
                )
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

                handoff_columns = st.columns(2)
                st.caption(selected_next_action_plan.get("primary_summary") or "")
                if handoff_columns[0].button(
                    selected_next_action_plan.get("primary_label") or "Continue",
                    width="stretch",
                    key="catalog_open_primary_handoff",
                    disabled=not bool(selected_next_action_plan.get("primary_area")) or selected_next_action_plan.get("primary_area") == "Catalog",
                ):
                    _open_catalog_handoff(
                        selected_next_action_plan["primary_area"],
                        selected_mapping_set_detail,
                        selected_next_action_plan.get("primary_summary") or "Continue from Catalog.",
                    )
                    st.rerun()
                if selected_next_action_plan.get("secondary_area"):
                    if handoff_columns[1].button(
                        selected_next_action_plan.get("secondary_label") or "Open secondary handoff",
                        width="stretch",
                        key="catalog_open_secondary_handoff",
                    ):
                        _open_catalog_handoff(
                            selected_next_action_plan["secondary_area"],
                            selected_mapping_set_detail,
                            selected_next_action_plan.get("secondary_summary") or "Continue from Catalog.",
                        )
                        st.rerun()
                else:
                    handoff_columns[1].caption("No secondary governance handoff is needed for this version right now.")

                st.dataframe(selected_mapping_set_detail.get("mapping_decisions", []), width="stretch", hide_index=True)

                version_compare_payload = _catalog_version_compare_payload(
                    selected_mapping_set_detail,
                    version_records,
                    latest_approved,
                )
                if version_compare_payload.get("rows"):
                    recommended_compare_target = version_compare_payload.get("recommended_target") or {}
                    st.caption(
                        "Version compare path: start from the recommended baseline, then load a diff only when you need row-level changes."
                    )
                    st.dataframe(version_compare_payload["rows"], width="stretch", hide_index=True)
                    st.caption(
                        f"Recommended diff baseline: v{recommended_compare_target.get('version')} "
                        f"({recommended_compare_target.get('status') or '-'}) | "
                        f"{version_compare_payload.get('recommended_reason') or 'peer compare'}"
                    )

                comparison_candidates = [
                    item
                    for item in version_records
                    if item.get("name") == selected_mapping_set_detail.get("name")
                    and item.get("mapping_set_id") != selected_mapping_set_detail.get("mapping_set_id")
                ]
                if comparison_candidates:
                    recommended_compare_mapping_set_id = int(
                        ((version_compare_payload.get("recommended_target") or {}).get("mapping_set_id") or 0)
                    )
                    comparison_labels = [
                        f"#{item['mapping_set_id']} | {item['name']} | v{item['version']} | {item['status']}"
                        for item in comparison_candidates
                    ]
                    comparison_columns = st.columns([3, 1])
                    selected_comparison_label = comparison_columns[0].selectbox(
                        "Compare selected version against",
                        comparison_labels,
                        index=next(
                            (
                                index
                                for index, item in enumerate(comparison_candidates)
                                if int(item.get("mapping_set_id") or 0) == recommended_compare_mapping_set_id
                            ),
                            0,
                        ),
                        key="catalog_selected_mapping_set_diff_label",
                    )
                    comparison_mapping_set = comparison_candidates[
                        comparison_labels.index(selected_comparison_label)
                    ]
                    selected_review_focus_concept = _preferred_catalog_review_handoff_concept(
                        selected_mapping_set_detail.get("canonical_concepts", []),
                        comparison_mapping_set.get("canonical_concepts", []),
                    )
                    comparison_action_columns = st.columns(2)
                    if comparison_action_columns[0].button(
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
                    if comparison_action_columns[1].button(
                        "Open compare review focus",
                        width="stretch",
                        key="catalog_open_selected_mapping_set_review_focus",
                    ):
                        _open_catalog_review_focus_handoff(
                            mapping_set_detail=comparison_mapping_set,
                            canonical_concept=selected_review_focus_concept,
                        )
                        st.rerun()

                selected_mapping_set_audit = st.session_state.get("catalog_selected_mapping_set_audit")
                if selected_mapping_set_audit:
                    st.caption("Selected mapping set audit")
                    st.dataframe(selected_mapping_set_audit, width="stretch", hide_index=True)

                selected_mapping_set_diff = st.session_state.get("catalog_selected_mapping_set_diff")
                if selected_mapping_set_diff:
                    baseline_mapping_set = _catalog_mapping_set_record_by_id(
                        version_records,
                        selected_mapping_set_diff.get("against_mapping_set_id"),
                    )
                    diff_focus_sources = _catalog_mapping_set_diff_focus_sources(
                        selected_mapping_set_diff.get("changes", [])
                    )
                    diff_review_focus_concept = _preferred_catalog_review_handoff_concept(
                        selected_mapping_set_detail.get("canonical_concepts", []),
                        (baseline_mapping_set or {}).get("canonical_concepts", []),
                    )
                    current_governance_summary = _catalog_governance_handoff_summary(
                        _catalog_next_action_plan(selected_mapping_set_detail, selected_workspace_context)
                    )
                    baseline_governance_summary = _catalog_governance_handoff_summary(
                        _catalog_next_action_plan(baseline_mapping_set, selected_workspace_context)
                    )
                    st.caption(
                        "Selected mapping set diff: "
                        f"v{selected_mapping_set_diff.get('current_version')} vs "
                        f"v{selected_mapping_set_diff.get('against_version')}"
                    )
                    diff_summary = st.columns(3)
                    diff_summary[0].metric("Added", selected_mapping_set_diff.get("added_count", 0))
                    diff_summary[1].metric("Removed", selected_mapping_set_diff.get("removed_count", 0))
                    diff_summary[2].metric("Changed", selected_mapping_set_diff.get("changed_count", 0))
                    diff_actions: list[dict[str, Any]] = [
                        {
                            "label": "Open current diff review focus",
                            "key": "catalog_open_current_diff_review_focus",
                            "callback": lambda: _open_catalog_review_focus_handoff(
                                mapping_set_detail=selected_mapping_set_detail,
                                canonical_concept=diff_review_focus_concept,
                                source_fields=diff_focus_sources,
                            ),
                        },
                        {
                            "label": "Open baseline diff review focus",
                            "key": "catalog_open_baseline_diff_review_focus",
                            "callback": lambda: _open_catalog_review_focus_handoff(
                                mapping_set_detail=baseline_mapping_set
                                or {
                                    "name": selected_mapping_set_diff.get("against_name") or selected_mapping_set_detail.get("name"),
                                    "version": selected_mapping_set_diff.get("against_version") or 0,
                                },
                                canonical_concept=diff_review_focus_concept,
                                source_fields=diff_focus_sources,
                            ),
                        },
                    ]
                    if current_governance_summary:
                        diff_actions.append(
                            {
                                "label": _catalog_governance_handoff_action_label(
                                    selected_mapping_set_detail,
                                    scope_label="current diff",
                                ),
                                "key": "catalog_open_current_diff_governance_handoff",
                                "callback": lambda: _open_catalog_handoff(
                                    "Governance",
                                    selected_mapping_set_detail,
                                    current_governance_summary,
                                ),
                            }
                        )
                    if baseline_governance_summary and baseline_mapping_set:
                        diff_actions.append(
                            {
                                "label": _catalog_governance_handoff_action_label(
                                    baseline_mapping_set,
                                    scope_label="baseline diff",
                                ),
                                "key": "catalog_open_baseline_diff_governance_handoff",
                                "callback": lambda: _open_catalog_handoff(
                                    "Governance",
                                    baseline_mapping_set,
                                    baseline_governance_summary,
                                ),
                            }
                        )
                    diff_action_columns = st.columns(len(diff_actions))
                    for diff_action_column, diff_action in zip(diff_action_columns, diff_actions):
                        if diff_action_column.button(
                            diff_action["label"],
                            width="stretch",
                            key=diff_action["key"],
                        ):
                            diff_action["callback"]()
                            st.rerun()
                    governance_follow_up_notes: list[str] = []
                    if current_governance_summary:
                        governance_follow_up_notes.append(
                            _catalog_governance_follow_up_caption(
                                selected_mapping_set_detail,
                                scope_label="Current diff",
                            )
                        )
                    if baseline_governance_summary and baseline_mapping_set:
                        governance_follow_up_notes.append(
                            _catalog_governance_follow_up_caption(
                                baseline_mapping_set,
                                scope_label="Baseline diff",
                            )
                        )
                    if governance_follow_up_notes:
                        st.caption("Governance follow-up: " + " | ".join(governance_follow_up_notes))
                    st.dataframe(selected_mapping_set_diff.get("changes", []), width="stretch", hide_index=True)

            similar_integrations = integration_detail.get("similar_integrations", [])
            if similar_integrations:
                similar_compare_payload = _catalog_similar_compare_payload(selected_version, similar_integrations)
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
                if similar_compare_payload.get("rows"):
                    st.caption(
                        "Peer drilldown path: prefer approved peer versions with the closest system and canonical overlap before opening the broader integration detail."
                    )
                    st.dataframe(similar_compare_payload["rows"], width="stretch", hide_index=True)
                similar_names = [item["integration_name"] for item in similar_integrations]
                recommended_similar_name = _normalized_text(similar_compare_payload.get("recommended_integration_name"))
                similar_columns = st.columns([3, 1, 1, 1])
                selected_similar_name = similar_columns[0].selectbox(
                    "Open similar integration detail",
                    similar_names,
                    index=next(
                        (
                            index
                            for index, name in enumerate(similar_names)
                            if _normalized_text(name) == recommended_similar_name
                        ),
                        0,
                    ),
                    key="catalog_selected_similar_integration_name",
                )
                selected_similar_integration = next(
                    (
                        item
                        for item in similar_integrations
                        if _normalized_text(item.get("integration_name")) == _normalized_text(selected_similar_name)
                    ),
                    similar_integrations[0],
                )
                selected_peer_version = selected_similar_integration.get("latest_approved_version") or selected_similar_integration.get("latest_version") or {}
                st.caption(
                    f"Selected peer drilldown: v{selected_peer_version.get('version') or '-'} "
                    f"({selected_peer_version.get('status') or '-'}) | "
                    f"{similar_compare_payload.get('recommended_reason') if _normalized_text(selected_similar_name) == recommended_similar_name else 'Open peer detail to inspect version lineage.'}"
                )
                selected_peer_review_focus_concept = _preferred_catalog_review_handoff_concept(
                    selected_version.get("canonical_concepts", []),
                    selected_similar_integration.get("shared_concepts", []),
                )
                if similar_columns[1].button("Open similar integration", width="stretch", key="catalog_open_similar_integration"):
                    try:
                        _load_catalog_integration_detail(selected_similar_name, api_request=api_request)
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = _catalog_detail_state_recovery(error) or {
                            "level": "error",
                            "message": f"Loading similar integration failed: {error}",
                        }
                        st.rerun()
                if similar_columns[2].button(
                    "Open peer version",
                    width="stretch",
                    key="catalog_open_similar_integration_version",
                    disabled=not bool(selected_peer_version.get("mapping_set_id")),
                ):
                    try:
                        _load_catalog_mapping_set_detail(int(selected_peer_version["mapping_set_id"]), api_request=api_request)
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Loading similar integration version failed: {error}",
                        }
                        st.rerun()
                if similar_columns[3].button(
                    "Open peer review focus",
                    width="stretch",
                    key="catalog_open_similar_integration_review_focus",
                    disabled=not bool(selected_peer_version),
                ):
                    _open_catalog_review_focus_handoff(
                        mapping_set_detail=selected_peer_version or {"name": selected_similar_name, "version": 0},
                        canonical_concept=selected_peer_review_focus_concept,
                    )
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
        reuse_summary = _catalog_concept_reuse_summary(concept_detail)
        reuse_rows = _catalog_concept_reuse_rows(concept_detail)
        with st.expander(
            _section_label("Concept Usage Summary", f"{reuse_summary['usage_count']} versions"),
            expanded=True,
        ):
            st.caption(
                f"Concept {concept_detail['concept_id']} appears in {reuse_summary['usage_count']} saved mapping version(s)."
            )
            summary_columns = st.columns(5)
            summary_columns[0].metric("Usage versions", reuse_summary["usage_count"])
            summary_columns[1].metric("Integrations", reuse_summary["integration_count"])
            summary_columns[2].metric("Approved integrations", reuse_summary["approved_integration_count"])
            summary_columns[3].metric("Source systems", reuse_summary["source_system_count"])
            summary_columns[4].metric("Target systems", reuse_summary["target_system_count"])

            if reuse_rows:
                st.write("**Concept-centric reuse view**")
                st.caption(
                    "Grouped view of how this canonical concept is reused across integrations, with latest and approved version signals."
                )
                st.dataframe(reuse_rows, width="stretch", hide_index=True)
                integration_options = [row["integration_name"] for row in reuse_rows if _normalized_text(row.get("integration_name"))]
                if integration_options:
                    concept_action_columns = st.columns([3, 1])
                    selected_concept_integration = concept_action_columns[0].selectbox(
                        "Open integration from concept reuse view",
                        integration_options,
                        key="catalog_selected_concept_integration_name",
                    )
                    if concept_action_columns[1].button(
                        "Open integration",
                        width="stretch",
                        key="catalog_open_concept_integration",
                    ):
                        try:
                            _load_catalog_integration_detail(selected_concept_integration, api_request=api_request)
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": f"Loading integration from concept reuse view failed: {error}",
                            }
                            st.rerun()

            st.write("**Version-level usage records**")
            st.dataframe(concept_detail.get("integrations", []), width="stretch", hide_index=True)