from __future__ import annotations

from collections import Counter
from collections.abc import Callable
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
)


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


def _catalog_reuse_fit_label(fit_assessment: str | None) -> str:
    normalized = _normalized_text(fit_assessment).lower()
    labels = {
        "strong_fit": "strong fit",
        "partial_fit": "partial fit",
        "low_fit": "low fit",
    }
    return labels.get(normalized, "")


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
                    "secondary_area": "Canonical Console",
                    "secondary_label": "Open canonical governance handoff",
                    "secondary_summary": (
                        "Inspect canonical coverage, stewardship, and approval context before treating this version as a stable reuse baseline."
                    ),
                }
            )
        return plan

    if status != "approved":
        return {
            "table_label": "Canonical governance handoff",
            "primary_area": "Canonical Console",
            "primary_label": "Open canonical governance handoff",
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
        secondary_area = "Canonical Console"
        secondary_label = "Open canonical governance handoff"
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


def _open_catalog_handoff(area: str, mapping_set_detail: dict[str, Any], summary: str) -> None:
    version = int(mapping_set_detail.get("version") or 0)
    name = _normalized_text(mapping_set_detail.get("name")) or "mapping-set"
    st.session_state["pending_top_level_area"] = area
    st.session_state["last_action"] = {
        "level": "info",
        "message": f"Catalog handoff: {name} v{version} -> {area}. {summary}",
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
                    _catalog_reuse_fit_label((reuse_fit_summary or {}).get("fit_assessment")) if reuse_fit_summary else None,
                ),
                expanded=bool(reuse_fit_summary or reuse_fit_error),
            ):
                st.caption(
                    "Bounded reuse assessment for the selected catalog version against the current workspace snapshot. "
                    "This does not apply or approve anything automatically."
                )
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
                    st.info("Open the selected catalog version first to inspect workspace fit.")
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
                        "Refresh reuse fit" if reuse_fit_summary else "Generate reuse fit",
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
                                "message": "Generated workspace reuse-fit explanation for the selected catalog mapping set.",
                            }
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["catalog_reuse_fit_summary"] = None
                            st.session_state["catalog_reuse_fit_error"] = f"Generating reuse-fit explanation failed: {error}"
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": st.session_state["catalog_reuse_fit_error"],
                            }
                            st.rerun()

                    if reuse_fit_error:
                        st.warning(reuse_fit_error)
                    if reuse_fit_summary:
                        fit_columns = st.columns(3)
                        fit_columns[0].metric("Fit", _catalog_reuse_fit_label(reuse_fit_summary.get("fit_assessment")))
                        fit_columns[1].metric(
                            "Generated with",
                            "LLM" if (reuse_fit_summary.get("generation_metadata") or {}).get("used_llm") else "Fallback",
                        )
                        fit_columns[2].metric("Catalog decisions", selected_mapping_set_detail.get("decision_count", 0))
                        st.write(reuse_fit_summary.get("summary") or "")
                        st.write("**Key matches**")
                        for item in reuse_fit_summary.get("key_matches", []):
                            st.write(f"- {item}")
                        st.write("**Risks**")
                        for item in reuse_fit_summary.get("risks", []):
                            st.write(f"- {item}")
                        st.write("**Next actions**")
                        for item in reuse_fit_summary.get("next_actions", []):
                            st.write(f"- {item}")
                    else:
                        st.info("No workspace reuse-fit explanation has been generated yet for the selected version.")

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
                similar_columns = st.columns([3, 1, 1])
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