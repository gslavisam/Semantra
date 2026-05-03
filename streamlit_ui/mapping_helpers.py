from __future__ import annotations

from collections.abc import Callable


def suggested_mapping_by_source(mapping_response: dict) -> dict[str, dict]:
    return {item["source"]: item for item in mapping_response.get("mappings", [])}


def resolve_suggested_transformation_code(entry: dict | None, fallback_code: str | None = None) -> str:
    current_entry = entry or {}
    current_target = str(current_entry.get("target") or "").strip()
    suggested_target = str(current_entry.get("suggested_target") or "").strip()
    if suggested_target and current_target and suggested_target != current_target:
        return ""
    return str(current_entry.get("suggested_transformation_code") or fallback_code or "").strip()


def effective_transformation_code(source: str, session_state: dict, fallback_code: str | None = None) -> str | None:
    manual_code = session_state.get(f"manual_transform_{source}", "").strip()
    if manual_code and session_state.get(f"manual_apply_{source}", False):
        return manual_code

    suggested_code = (fallback_code or "").strip()
    if suggested_code and session_state.get(f"transform_{source}", False):
        return suggested_code
    return None


def transformation_mode(source: str, session_state: dict, fallback_code: str | None = None) -> str:
    manual_code = session_state.get(f"manual_transform_{source}", "").strip()
    if manual_code and session_state.get(f"manual_apply_{source}", False):
        return "custom"

    suggested_code = (fallback_code or "").strip()
    if suggested_code and session_state.get(f"transform_{source}", False):
        return "suggested"
    return "direct"


def transformation_mode_label(mode: str) -> str:
    labels = {
        "custom": "Transformation: custom",
        "suggested": "Transformation: suggested",
        "direct": "Transformation: direct",
    }
    return labels.get(mode, "Transformation: direct")


def knowledge_explanation_lines(explanation: list[str] | None) -> list[str]:
    lines = explanation or []
    return [
        line for line in lines
        if line.startswith("Internal metadata dictionary") or line.startswith("Context prior:")
    ]


def canonical_explanation_lines(explanation: list[str] | None) -> list[str]:
    lines = explanation or []
    return [
        line for line in lines
        if line.startswith("Canonical glossary aligns both fields")
    ]


def canonical_concept_labels(canonical_details: dict | None) -> list[str]:
    details = canonical_details or {}
    shared = details.get("shared_concepts") or []
    source = details.get("source_concepts") or []
    target = details.get("target_concepts") or []
    selected = shared or source or target
    labels: list[str] = []
    for concept in selected:
        concept_id = str(concept.get("concept_id") or "").strip()
        display_name = str(concept.get("display_name") or concept_id).strip()
        if not concept_id and not display_name:
            continue
        labels.append(f"{display_name} ({concept_id})" if concept_id else display_name)
    return labels


def canonical_path_label(
    source: str,
    target: str | None,
    canonical_details: dict | None,
    *,
    canonical_concept_labels_func: Callable[[dict | None], list[str]] = canonical_concept_labels,
) -> str:
    concept_labels = canonical_concept_labels_func(canonical_details)
    if not concept_labels:
        return ""
    target_label = str(target or "unmapped").strip() or "unmapped"
    return f"{source} -> {', '.join(concept_labels)} -> {target_label}"


def source_concept_rows(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source_func: Callable[[dict], dict[str, dict]] = suggested_mapping_by_source,
) -> list[dict]:
    selected_by_source = suggested_mapping_by_source_func(mapping_response)
    rows: list[dict] = []

    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked.get("candidates", []) if candidate.get("target") == current_target),
            None,
        )
        canonical_details = selected_candidate.get("canonical_details", {}) if selected_candidate else selected_row.get("canonical_details", {})
        concepts = canonical_details.get("shared_concepts") or canonical_details.get("source_concepts") or []
        for concept in concepts:
            concept_id = str(concept.get("concept_id") or "").strip()
            concept_name = str(concept.get("display_name") or concept_id).strip() or concept_id
            if not concept_id:
                continue
            rows.append(
                {
                    "source": source,
                    "concept": concept_name,
                    "concept_id": concept_id,
                    "target": current_target or "unmapped",
                    "strength": float(concept.get("strength", 0.0) or 0.0),
                }
            )

    return sorted(rows, key=lambda row: (row["source"], row["concept"], row["target"]))


def concept_target_rows(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source_func: Callable[[dict], dict[str, dict]] = suggested_mapping_by_source,
) -> list[dict]:
    selected_by_source = suggested_mapping_by_source_func(mapping_response)
    grouped: dict[tuple[str, str], dict] = {}

    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked.get("candidates", []) if candidate.get("target") == current_target),
            None,
        )
        canonical_details = selected_candidate.get("canonical_details", {}) if selected_candidate else selected_row.get("canonical_details", {})
        concepts = canonical_details.get("shared_concepts") or canonical_details.get("target_concepts") or []
        for concept in concepts:
            concept_id = str(concept.get("concept_id") or "").strip()
            concept_name = str(concept.get("display_name") or concept_id).strip() or concept_id
            target = str(current_target or "unmapped").strip() or "unmapped"
            if not concept_id:
                continue
            key = (concept_id, target)
            group = grouped.setdefault(
                key,
                {
                    "concept": concept_name,
                    "concept_id": concept_id,
                    "target": target,
                    "source_columns": set(),
                    "mapping_count": 0,
                },
            )
            group["mapping_count"] += 1
            group["source_columns"].add(source)

    return [
        {
            "concept": group["concept"],
            "concept_id": group["concept_id"],
            "target": group["target"],
            "source_columns": " | ".join(sorted(group["source_columns"])),
            "mapping_count": group["mapping_count"],
        }
        for _, group in sorted(grouped.items(), key=lambda item: (item[1]["concept"], item[1]["target"]))
    ]


def canonical_concept_groups(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source_func: Callable[[dict], dict[str, dict]] = suggested_mapping_by_source,
    canonical_path_label_func: Callable[[str, str | None, dict | None], str] = canonical_path_label,
) -> list[dict]:
    selected_by_source = suggested_mapping_by_source_func(mapping_response)
    grouped: dict[str, dict] = {}

    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked.get("candidates", []) if candidate.get("target") == current_target),
            None,
        )
        canonical_details = selected_candidate.get("canonical_details", {}) if selected_candidate else selected_row.get("canonical_details", {})
        shared_concepts = canonical_details.get("shared_concepts") or []
        if not shared_concepts:
            continue

        for concept in shared_concepts:
            concept_id = str(concept.get("concept_id") or "").strip()
            if not concept_id:
                continue
            concept_name = str(concept.get("display_name") or concept_id).strip() or concept_id
            group = grouped.setdefault(
                concept_id,
                {
                    "concept": concept_name,
                    "concept_id": concept_id,
                    "mapping_count": 0,
                    "source_columns": set(),
                    "target_columns": set(),
                    "canonical_paths": set(),
                },
            )
            group["mapping_count"] += 1
            group["source_columns"].add(source)
            if current_target:
                group["target_columns"].add(current_target)
            canonical_path = canonical_path_label_func(source, current_target, {"shared_concepts": [concept]})
            if canonical_path:
                group["canonical_paths"].add(canonical_path)

    return [
        {
            "concept": group["concept"],
            "concept_id": group["concept_id"],
            "mapping_count": group["mapping_count"],
            "source_columns": " | ".join(sorted(group["source_columns"])),
            "target_columns": " | ".join(sorted(group["target_columns"])),
            "canonical_paths": " | ".join(sorted(group["canonical_paths"])),
        }
        for _, group in sorted(grouped.items(), key=lambda item: (item[1]["concept"], item[0]))
    ]


def trust_layer_rows(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source_func: Callable[[dict], dict[str, dict]] = suggested_mapping_by_source,
    resolve_suggested_transformation_code_func: Callable[[dict | None, str | None], str] = resolve_suggested_transformation_code,
    effective_transformation_code_func: Callable[[str, dict, str | None], str | None] = effective_transformation_code,
    transformation_mode_func: Callable[[str, dict, str | None], str] = transformation_mode,
) -> list[dict]:
    selected_by_source = suggested_mapping_by_source_func(mapping_response)
    rows: list[dict] = []
    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked["candidates"] if candidate["target"] == current_target),
            None,
        )
        fallback_code = resolve_suggested_transformation_code_func(current_state, selected_row.get("transformation_code"))
        rows.append(
            {
                "source": source,
                "target": current_target,
                "confidence": selected_candidate["confidence"] if selected_candidate else selected_row.get("confidence", 0.0),
                "explanation": selected_candidate["explanation"] if selected_candidate else selected_row.get("explanation", []),
                "signals": selected_candidate["signals"] if selected_candidate else selected_row.get("signals", {}),
                "canonical_details": selected_candidate.get("canonical_details", {}) if selected_candidate else selected_row.get("canonical_details", {}),
                "suggested_transformation_code": fallback_code,
                "active_transformation_code": effective_transformation_code_func(source, session_state, fallback_code),
                "transformation_mode": transformation_mode_func(source, session_state, fallback_code),
            }
        )
    return rows


def current_mapping_rows(
    mapping_response: dict,
    session_state: dict,
    *,
    suggested_mapping_by_source_func: Callable[[dict], dict[str, dict]] = suggested_mapping_by_source,
    validator_badge: Callable[[str], str],
    canonical_path_label_func: Callable[[str, str | None, dict | None], str] = canonical_path_label,
) -> list[dict]:
    selected_by_source = suggested_mapping_by_source_func(mapping_response)
    rows: list[dict] = []
    for ranked in mapping_response["ranked_mappings"]:
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked["candidates"] if candidate["target"] == current_target),
            None,
        )
        canonical_details = selected_candidate.get("canonical_details", {}) if selected_candidate else selected_row.get("canonical_details", {})
        rows.append(
            {
                "source": source,
                "target": current_target,
                "confidence": selected_candidate["confidence"] if selected_candidate else selected_row.get("confidence", 0.0),
                "confidence_label": (
                    selected_candidate["confidence_label"] if selected_candidate else selected_row.get("confidence_label", "low_confidence")
                ),
                "status": current_state.get("status", selected_row.get("status", "needs_review")),
                "validator": validator_badge(
                    selected_candidate["method"] if selected_candidate else selected_row.get("method", "manual_review")
                ),
                "canonical_path": canonical_path_label_func(source, current_target, canonical_details),
            }
        )
    return rows


def selected_target_options(ranked: dict) -> list[str]:
    options = [candidate["target"] for candidate in ranked["candidates"]]
    selected = ranked["selected"]["target"] if ranked["selected"] and ranked["selected"].get("target") else None
    if selected and selected not in options:
        options.insert(0, selected)
    return options


def has_knowledge_match(signals: dict | None, explanation: list[str] | str | None = None) -> bool:
    if isinstance(signals, dict):
        try:
            if float(signals.get("knowledge", 0.0) or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            pass

    if isinstance(explanation, str):
        explanation_text = explanation.lower()
        return (
            "knowledge" in explanation_text
            or "metadata" in explanation_text
            or "context prior" in explanation_text
        )

    if isinstance(explanation, list):
        for item in explanation:
            if not isinstance(item, str):
                continue
            item_text = item.lower()
            if "knowledge" in item_text or "metadata" in item_text or "context prior" in item_text:
                return True

    return False


def has_canonical_match(signals: dict | None, explanation: list[str] | str | None = None) -> bool:
    if isinstance(signals, dict):
        try:
            if float(signals.get("canonical", 0.0) or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            pass

    if isinstance(explanation, str):
        return "canonical glossary" in explanation.lower()

    if isinstance(explanation, list):
        for item in explanation:
            if not isinstance(item, str):
                continue
            if "canonical glossary" in item.lower():
                return True

    return False