from __future__ import annotations

import json
from collections.abc import Callable
from io import BytesIO

from openpyxl import Workbook


def default_editor_entry(ranked: dict, selected_mapping: dict | None = None) -> dict[str, str | bool]:
    selected_mapping = selected_mapping or {}
    selected_target = None
    selected_status = "rejected"
    if ranked["selected"]:
        selected_target = ranked["selected"].get("target")
        selected_status = ranked["selected"].get("status", "needs_review")
    elif ranked["candidates"]:
        selected_target = ranked["candidates"][0]["target"]
        selected_status = "needs_review"
    return {
        "target": selected_target or "",
        "status": selected_status,
        "suggested_target": selected_target or "",
        "suggested_transformation_code": selected_mapping.get("transformation_code") or "",
        "manual_transformation_code": "",
        "llm_transformation_instruction": "",
        "generated_transformation_reasoning": [],
        "generated_transformation_warnings": [],
        "apply_transformation": False,
        "manual_apply_transformation": False,
        "manual": False,
    }


def initialize_mapping_editor_state(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source: Callable[[dict], dict[str, dict]],
    default_editor_entry_func: Callable[[dict, dict | None], dict[str, str | bool]] = default_editor_entry,
) -> None:
    editor_state: dict[str, dict[str, str]] = {}
    for ranked in mapping_response["ranked_mappings"]:
        selected_mapping = suggested_mapping_by_source(mapping_response).get(ranked["source"], {})
        editor_state[ranked["source"]] = default_editor_entry_func(ranked, selected_mapping)
    session_state["mapping_editor_state"] = editor_state


def schema_column_names(handle: dict) -> list[str]:
    return [column["name"] for column in handle["schema_profile"]["columns"]]


def ranked_sources(mapping_response: dict) -> set[str]:
    return {ranked["source"] for ranked in mapping_response["ranked_mappings"]}


def upsert_manual_mapping(source: str, target: str, status: str, session_state: dict) -> None:
    editor_state = session_state.setdefault("mapping_editor_state", {})
    current_entry = editor_state.get(source, {})
    editor_state[source] = {
        "target": target,
        "status": status,
        "suggested_target": current_entry.get("suggested_target", ""),
        "manual": True,
    }
    session_state["mapping_editor_state"] = editor_state


def remove_manual_mapping(
    source: str,
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source: Callable[[dict], dict[str, dict]],
    default_editor_entry_func: Callable[[dict, dict | None], dict[str, str | bool]] = default_editor_entry,
) -> None:
    editor_state = session_state.setdefault("mapping_editor_state", {})
    ranked_by_source = {ranked["source"]: ranked for ranked in mapping_response["ranked_mappings"]}
    if source in ranked_by_source:
        selected_mapping = suggested_mapping_by_source(mapping_response).get(source, {})
        editor_state[source] = default_editor_entry_func(ranked_by_source[source], selected_mapping)
    else:
        editor_state.pop(source, None)
    session_state["mapping_editor_state"] = editor_state


def manual_mapping_rows(
    mapping_response: dict,
    session_state: dict,
    *,
    ranked_sources_func: Callable[[dict], set[str]] = ranked_sources,
) -> list[dict]:
    editor_state = session_state.get("mapping_editor_state", {})
    auto_sources = ranked_sources_func(mapping_response)
    rows: list[dict] = []
    for source, entry in editor_state.items():
        if source in auto_sources and not entry.get("manual"):
            continue
        target = entry.get("target", "")
        status = entry.get("status", "needs_review")
        if not target or status == "rejected":
            continue
        rows.append(
            {
                "source": source,
                "target": target,
                "status": status,
                "suggested_target": entry.get("suggested_target") or None,
                "mode": "manual_override" if source in auto_sources else "manual_addition",
            }
        )
    return rows


def build_mapping_decisions(
    session_state: dict,
    *,
    resolve_suggested_transformation_code: Callable[[dict | None, str | None], str],
    effective_transformation_code: Callable[[str, str | None], str | None],
) -> list[dict]:
    decisions: list[dict] = []
    for source, entry in session_state.get("mapping_editor_state", {}).items():
        target = entry.get("target", "")
        status = entry.get("status", "needs_review")
        if not target or status == "rejected":
            continue
        transformation_code = effective_transformation_code(source, resolve_suggested_transformation_code(entry))
        decision = {"source": source, "target": target, "status": status}
        if transformation_code:
            decision["transformation_code"] = transformation_code
        decisions.append(decision)
    return decisions


def export_mapping_payload(session_state: dict, *, build_mapping_decisions_func: Callable[[], list[dict]]) -> str:
    payload = {
        "source_dataset_id": session_state.get("upload_response", {}).get("source", {}).get("dataset_id"),
        "target_dataset_id": session_state.get("upload_response", {}).get("target", {}).get("dataset_id"),
        "mapping_decisions": build_mapping_decisions_func(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=True)


def export_mapping_excel_bytes(session_state: dict, *, build_mapping_decisions_func: Callable[[], list[dict]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "mapping_decisions"
    worksheet.append(["source", "target", "status", "transformation_code"])

    for decision in build_mapping_decisions_func():
        worksheet.append(
            [
                decision.get("source", ""),
                decision.get("target", ""),
                decision.get("status", ""),
                decision.get("transformation_code", "") or "",
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_mapping_set_payload(
    name: str,
    session_state: dict,
    *,
    build_mapping_decisions_func: Callable[[], list[dict]],
    created_by: str | None = None,
    note: str | None = None,
    owner: str | None = None,
    assignee: str | None = None,
    review_note: str | None = None,
) -> dict:
    upload_response = session_state.get("upload_response", {})
    mapping_response = session_state.get("mapping_response", {})
    canonical_coverage = mapping_response.get("canonical_coverage", {}) if isinstance(mapping_response, dict) else {}
    source_coverage = canonical_coverage.get("source", {}) if isinstance(canonical_coverage, dict) else {}
    project_coverage = canonical_coverage.get("project", {}) if isinstance(canonical_coverage, dict) else {}
    mapping_mode = str(upload_response.get("mapping_mode", "standard") or "standard").strip().lower()
    target_system = upload_response.get("target_system") if mapping_mode == "canonical" else None
    return {
        "name": name,
        "source_dataset_id": upload_response.get("source", {}).get("dataset_id"),
        "target_dataset_id": upload_response.get("target", {}).get("dataset_id"),
        "mapping_decisions": build_mapping_decisions_func(),
        "integration_name": name,
        "target_system": target_system,
        "artifact_type": "canonical-only" if mapping_mode == "canonical" else "standard",
        "canonical_concepts": project_coverage.get("concepts", []) or [],
        "unmatched_sources": source_coverage.get("unmatched_columns", []) or [],
        "created_by": (created_by or "").strip() or None,
        "note": (note or "").strip() or None,
        "owner": (owner or "").strip() or None,
        "assignee": (assignee or "").strip() or None,
        "review_note": (review_note or "").strip() or None,
    }


def build_current_benchmark_case(
    session_state: dict,
    *,
    build_mapping_decisions_func: Callable[[], list[dict]],
    schema_columns_for_case: Callable[[dict], list[dict]],
) -> dict | None:
    upload_response = session_state.get("upload_response")
    mapping_decisions = build_mapping_decisions_func()
    if not upload_response or not mapping_decisions or not upload_response.get("target"):
        return None
    return {
        "source_columns": schema_columns_for_case(upload_response["source"]),
        "target_columns": schema_columns_for_case(upload_response["target"]),
        "ground_truth": {decision["source"]: decision["target"] for decision in mapping_decisions},
        "row_count": upload_response["source"]["schema_profile"]["row_count"],
    }


def apply_imported_mapping_payload(
    raw_payload: bytes,
    session_state: dict,
    *,
    schema_column_names_func: Callable[[dict], list[str]] = schema_column_names,
) -> None:
    payload = json.loads(raw_payload.decode("utf-8"))
    imported_decisions = payload.get("mapping_decisions", [])
    editor_state = session_state.get("mapping_editor_state", {})
    upload_response = session_state.get("upload_response")
    valid_sources = set(schema_column_names_func(upload_response["source"])) if upload_response else set()
    for decision in imported_decisions:
        source = decision["source"]
        if valid_sources and source not in valid_sources:
            continue
        current_entry = editor_state.get(source, {})
        editor_state[source] = {
            "target": decision["target"],
            "status": decision.get("status", "accepted"),
            "suggested_target": current_entry.get("suggested_target", ""),
            "suggested_transformation_code": current_entry.get("suggested_transformation_code", ""),
            "manual_transformation_code": decision.get("transformation_code", ""),
            "llm_transformation_instruction": current_entry.get("llm_transformation_instruction", ""),
            "generated_transformation_reasoning": current_entry.get("generated_transformation_reasoning", []),
            "generated_transformation_warnings": current_entry.get("generated_transformation_warnings", []),
            "apply_transformation": False,
            "manual_apply_transformation": bool(decision.get("transformation_code")),
            "manual": source not in editor_state or current_entry.get("manual", False),
        }
        session_state[f"manual_transform_{source}"] = decision.get("transformation_code", "")
        session_state[f"manual_apply_{source}"] = bool(decision.get("transformation_code"))
    session_state["mapping_editor_state"] = editor_state


def build_pending_corrections(session_state: dict) -> list[dict]:
    pending: list[dict] = []
    for source, entry in session_state.get("mapping_editor_state", {}).items():
        target = entry.get("target", "")
        suggested_target = entry.get("suggested_target", "")
        status = entry.get("status", "needs_review")
        if status == "rejected":
            rejected_target = suggested_target or target
            if not rejected_target:
                continue
            pending.append(
                {
                    "source": source,
                    "suggested_target": rejected_target,
                    "corrected_target": None,
                    "status": "rejected",
                }
            )
            continue
        if not target:
            continue
        if target == suggested_target:
            continue
        if status != "accepted":
            continue
        correction_status = "accepted"
        pending.append(
            {
                "source": source,
                "suggested_target": suggested_target or None,
                "corrected_target": target,
                "status": correction_status,
            }
        )
    return pending


def correction_governance_block_reason(session_state: dict) -> str:
    blocked_statuses: set[str] = set()
    for entry in session_state.get("mapping_editor_state", {}).values():
        target = entry.get("target", "")
        suggested_target = entry.get("suggested_target", "")
        status = str(entry.get("status", "needs_review") or "needs_review").strip().lower() or "needs_review"
        has_reviewed_change = status == "rejected" or (bool(target) and target != suggested_target)
        if has_reviewed_change and status not in {"accepted", "rejected"}:
            blocked_statuses.add(status)
    if not blocked_statuses:
        return ""
    return (
        "Saving reviewed corrections is blocked until pending corrections come from closed review outcomes "
        f"(accepted or rejected). Review statuses: {', '.join(sorted(blocked_statuses))}."
    )


def persist_corrections(
    note: str,
    session_state: dict,
    *,
    build_pending_corrections_func: Callable[[], list[dict]],
    api_request: Callable[..., dict],
) -> list[dict]:
    saved_entries: list[dict] = []
    pending = build_pending_corrections_func()
    for correction in pending:
        payload = {
            "source": correction["source"],
            "suggested_target": correction["suggested_target"],
            "corrected_target": correction["corrected_target"],
            "status": correction["status"],
            "note": note or f"Saved from Streamlit review with status={correction['status']}",
        }
        saved_entries.append(api_request("POST", "/observability/corrections", json=payload))
    for saved in saved_entries:
        session_state["mapping_editor_state"][saved["source"]]["suggested_target"] = saved.get("corrected_target") or ""
    session_state["saved_corrections"] = saved_entries
    return saved_entries