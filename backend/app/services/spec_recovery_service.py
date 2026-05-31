"""Bounded LLM-assisted recovery for schema-spec uploads that miss deterministic layout detection."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.models.schema import SpecLayoutHint, SpecRecoveryResponse, SpecRecoverySuggestion
from app.services.llm_service import LLMProvider, normalize_llm_list_field, request_bounded_llm_json
from app.services.spec_upload_service import (
    DESCRIPTION_CANDIDATES,
    NAME_CANDIDATES,
    SAMPLE_VALUE_CANDIDATES,
    TYPE_CANDIDATES,
    build_spec_layout_hint,
    list_embedded_spec_candidates,
    normalize_header_candidate,
    parse_spec_payload,
    parse_spec_source_rows,
)
from app.utils.tabular import normalize_tabular_header


logger = logging.getLogger(__name__)


SPEC_RECOVERY_MAX_HEADERS = 32
SPEC_RECOVERY_MAX_SAMPLE_ROWS = 5
SPEC_RECOVERY_MAX_CELL_LENGTH = 120


def recover_spec_layout(
    payload: bytes,
    filename: str,
    provider: LLMProvider | None,
) -> SpecRecoveryResponse:
    """Return a bounded recovery proposal for schema-spec uploads and validate it via deterministic replay."""

    candidate_blocks = list_embedded_spec_candidates(payload, filename)
    rows, source_header_row_index = parse_spec_source_rows(payload, filename)
    if not candidate_blocks:
        candidate_blocks = [(rows, source_header_row_index)]
    candidate_headers_by_row = {
        header_row_index: list(candidate_rows[0].keys())
        for candidate_rows, header_row_index in candidate_blocks
        if candidate_rows
    }
    has_multiple_candidates = len(candidate_headers_by_row) > 1
    context_warnings: list[str] = []
    if source_header_row_index > 1:
        context_warnings.append(
            f"Recovery analyzed an embedded tabular block starting at row {source_header_row_index}."
        )
    if has_multiple_candidates:
        context_warnings.append(
            f"Bounded recovery considered {len(candidate_headers_by_row)} candidate tabular blocks before choosing one."
        )
    if not rows:
        logger.info("Spec recovery skipped for %s: no parsed rows available.", filename)
        return SpecRecoveryResponse(
            status="no_suggestion",
            failure_reason="Spec recovery requires at least one parsed row.",
            warnings=context_warnings + ["Upload recovery only works on parseable metadata files with at least one data row."],
        )

    deterministic_hint = build_spec_layout_hint(rows)
    if deterministic_hint is not None and not has_multiple_candidates:
        logger.info(
            "Spec recovery bypassed for %s: deterministic detection already succeeded with name_col=%s.",
            filename,
            deterministic_hint.name_col,
        )
        return SpecRecoveryResponse(
            status="recovered",
            suggestion=_hint_to_suggestion(deterministic_hint, header_row_index=source_header_row_index),
            hint=deterministic_hint,
            warnings=context_warnings + ["Deterministic spec detection already succeeded; bounded recovery was not required."],
        )

    headers = list(rows[0].keys())
    if len(headers) > SPEC_RECOVERY_MAX_HEADERS:
        logger.info(
            "Spec recovery skipped for %s: %s headers exceed bounded limit %s.",
            filename,
            len(headers),
            SPEC_RECOVERY_MAX_HEADERS,
        )
        return SpecRecoveryResponse(
            status="no_suggestion",
            failure_reason="Spec recovery is limited to compact metadata tables.",
            warnings=context_warnings + [
                f"Parsed header count {len(headers)} exceeds the bounded recovery limit of {SPEC_RECOVERY_MAX_HEADERS}."
            ],
        )

    alias_hint = _build_alias_recovery_hint(headers) if not has_multiple_candidates else None
    alias_candidate_recovery = _build_alias_candidate_recovery(candidate_blocks) if has_multiple_candidates else None
    if provider is None:
        if alias_candidate_recovery is not None:
            alias_hint, alias_header_row_index = alias_candidate_recovery
            logger.info(
                "Spec recovery used bounded multi-block alias fallback for %s because no LLM provider is configured.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=alias_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    f"Bounded recovery selected candidate block at row {alias_header_row_index} via close header aliases because no LLM provider was available.",
                ],
            )
        if alias_hint is not None:
            logger.info(
                "Spec recovery used bounded alias fallback for %s because no LLM provider is configured.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=source_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    "Bounded recovery matched close header aliases because no LLM provider was available.",
                ],
            )
        logger.info("Spec recovery unavailable for %s: bounded LLM provider is not configured.", filename)
        return SpecRecoveryResponse(
            status="unavailable",
            failure_reason="LLM upload recovery is disabled or unavailable in backend configuration.",
            warnings=context_warnings + [
                "Configure a bounded LLM provider before retrying schema-spec recovery."
                if not has_multiple_candidates
                else "Multiple candidate metadata tables were found; configure a bounded LLM provider or provide the header row manually."
            ],
        )

    prompt = build_spec_recovery_prompt(filename, candidate_blocks)
    response = request_bounded_llm_json(provider, prompt, "spec_recovery")
    if response is None:
        if alias_candidate_recovery is not None:
            alias_hint, alias_header_row_index = alias_candidate_recovery
            logger.warning(
                "Spec recovery used bounded multi-block alias fallback for %s after no usable LLM response.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=alias_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    f"LLM recovery returned no usable response; bounded recovery selected candidate block at row {alias_header_row_index} via close header aliases instead.",
                ],
            )
        if alias_hint is not None:
            logger.warning(
                "Spec recovery used bounded alias fallback for %s after no usable LLM response.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=source_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    "LLM recovery returned no usable response; bounded recovery matched close header aliases instead.",
                ],
            )
        logger.warning("Spec recovery produced no usable LLM response for %s.", filename)
        return SpecRecoveryResponse(
            status="no_suggestion",
            failure_reason="LLM did not return a usable schema-spec recovery suggestion.",
            warnings=context_warnings + ["No bounded recovery suggestion was produced for this metadata file."],
        )

    _raw_response, parsed = response
    suggestion = _normalize_spec_recovery_suggestion(
        parsed,
        candidate_headers_by_row,
        default_header_row_index=source_header_row_index,
    )
    if suggestion is None:
        if alias_candidate_recovery is not None:
            alias_hint, alias_header_row_index = alias_candidate_recovery
            logger.warning(
                "Spec recovery used bounded multi-block alias fallback for %s after invalid LLM suggestion.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=alias_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    f"LLM recovery returned an invalid suggestion; bounded recovery selected candidate block at row {alias_header_row_index} via close header aliases instead.",
                ],
            )
        if alias_hint is not None:
            logger.warning(
                "Spec recovery used bounded alias fallback for %s after invalid LLM suggestion.",
                filename,
            )
            return SpecRecoveryResponse(
                status="recovered",
                suggestion=_hint_to_suggestion(alias_hint, header_row_index=source_header_row_index),
                hint=alias_hint,
                warnings=context_warnings + [
                    "LLM recovery returned an invalid suggestion; bounded recovery matched close header aliases instead.",
                ],
            )
        logger.warning("Spec recovery returned an invalid bounded suggestion for %s.", filename)
        return SpecRecoveryResponse(
            status="invalid_suggestion",
            failure_reason="LLM returned a recovery suggestion outside the allowed parser contract.",
            warnings=context_warnings + ["Recovery suggestions must only reference headers present in the uploaded file."],
        )

    combined_warnings = context_warnings + list(suggestion.warnings)
    if suggestion.detected_mode != "spec":
        logger.info(
            "Spec recovery declined for %s: detected_mode=%s confidence=%.2f.",
            filename,
            suggestion.detected_mode,
            suggestion.confidence,
        )
        combined_warnings.append("Recovery suggestion did not identify a schema-spec metadata layout.")
        return SpecRecoveryResponse(
            status="no_suggestion",
            suggestion=suggestion,
            failure_reason="LLM did not identify a recoverable schema-spec layout.",
            warnings=combined_warnings,
        )

    try:
        parse_spec_payload(
            payload,
            filename,
            header_row_index=suggestion.header_row_index or source_header_row_index,
            name_col=suggestion.name_col,
            description_col=suggestion.description_col,
            type_col=suggestion.type_col,
            sample_values_col=suggestion.sample_values_col,
        )
    except ValueError as error:
        logger.warning(
            "Spec recovery replay failed for %s with name_col=%s: %s",
            filename,
            suggestion.name_col,
            error,
        )
        combined_warnings.append(f"Deterministic replay rejected the suggestion: {error}")
        return SpecRecoveryResponse(
            status="replay_failed",
            suggestion=suggestion,
            failure_reason=str(error),
            warnings=combined_warnings,
        )

    logger.info(
        "Spec recovery validated for %s with name_col=%s description_col=%s type_col=%s sample_values_col=%s confidence=%.2f.",
        filename,
        suggestion.name_col,
        suggestion.description_col or "-",
        suggestion.type_col or "-",
        suggestion.sample_values_col or "-",
        suggestion.confidence,
    )
    return SpecRecoveryResponse(
        status="recovered",
        suggestion=suggestion,
        hint=SpecLayoutHint(
            name_col=str(suggestion.name_col or "").strip(),
            description_col=_optional_text(suggestion.description_col),
            type_col=_optional_text(suggestion.type_col),
            sample_values_col=_optional_text(suggestion.sample_values_col),
            confidence=_clamp_confidence(suggestion.confidence),
        ),
        warnings=combined_warnings,
    )


def build_spec_recovery_prompt(
    filename: str,
    candidate_blocks: list[tuple[list[dict[str, object]], int]],
) -> str:
    """Build the bounded prompt used to recover schema-spec columns from a parseable metadata file."""

    serialized_candidates = []
    allowed_header_rows: list[int] = []
    for rows, header_row_index in candidate_blocks:
        if not rows:
            continue
        allowed_header_rows.append(header_row_index)
        serialized_candidates.append(
            {
                "header_row_index": header_row_index,
                "headers": list(rows[0].keys()),
                "sample_rows": _build_sample_rows(rows),
            }
        )
    payload = {
        "filename": filename,
        "candidate_blocks": serialized_candidates,
        "contract": {
            "allowed_detected_modes": ["spec", "row_data", "unknown"],
            "allowed_header_row_indexes": allowed_header_rows,
            "notes": [
                "Choose one candidate block by returning its header_row_index.",
                "Only use header names that belong to the chosen candidate block.",
                "Return detected_mode='spec' only when the file clearly describes fields/columns rather than ordinary business records.",
                "Use header_row_index from candidate_blocks as the original file row where the detected header starts.",
                "For this slice, keep sheet_name, record_path, and selected_table null unless directly evident from the payload.",
                "If you are not confident, return detected_mode='unknown' and leave all column fields null.",
            ],
        },
    }
    return (
        "You are recovering a schema-spec metadata upload for a deterministic parser. "
        "Stay strictly grounded in the provided headers and sample rows.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Return exactly these top-level fields: detected_mode, sheet_name, header_row_index, record_path, name_col, description_col, type_col, sample_values_col, selected_table, confidence, warnings.\n"
        "Never invent header names and never infer columns outside allowed_headers.\n\n"
        f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _normalize_spec_recovery_suggestion(
    parsed: dict[str, object],
    candidate_headers_by_row: dict[int, list[str]],
    *,
    default_header_row_index: int,
) -> SpecRecoverySuggestion | None:
    try:
        suggestion = SpecRecoverySuggestion.model_validate(parsed)
    except ValidationError:
        return None

    resolved_header_row_index = suggestion.header_row_index or default_header_row_index
    if resolved_header_row_index not in candidate_headers_by_row:
        return None

    suggestion = suggestion.model_copy(
        update={
            "warnings": normalize_llm_list_field(suggestion.warnings),
            "confidence": _clamp_confidence(suggestion.confidence),
            "header_row_index": resolved_header_row_index,
        }
    )

    if suggestion.detected_mode != "spec":
        return suggestion

    headers = candidate_headers_by_row[resolved_header_row_index]
    available_headers = {normalize_tabular_header(header): header for header in headers}
    resolved_name = _resolve_header(suggestion.name_col, available_headers)
    resolved_description = _resolve_header(suggestion.description_col, available_headers)
    resolved_type = _resolve_header(suggestion.type_col, available_headers)
    resolved_samples = _resolve_header(suggestion.sample_values_col, available_headers)

    if not resolved_name:
        return None
    if not any((resolved_description, resolved_type, resolved_samples)):
        return None

    return suggestion.model_copy(
        update={
            "name_col": resolved_name,
            "description_col": resolved_description,
            "type_col": resolved_type,
            "sample_values_col": resolved_samples,
            "sheet_name": _optional_text(suggestion.sheet_name),
            "record_path": _optional_text(suggestion.record_path),
            "selected_table": _optional_text(suggestion.selected_table),
        }
    )


def _build_sample_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    sample_rows: list[dict[str, object]] = []
    for row in rows[:SPEC_RECOVERY_MAX_SAMPLE_ROWS]:
        sample_rows.append(
            {
                key: _truncate_cell(value)
                for key, value in row.items()
            }
        )
    return sample_rows


def _build_alias_recovery_hint(headers: list[str]) -> SpecLayoutHint | None:
    resolved_name = _find_alias_header(headers, NAME_CANDIDATES)
    resolved_description = _find_alias_header(headers, DESCRIPTION_CANDIDATES)
    resolved_type = _find_alias_header(headers, TYPE_CANDIDATES)
    resolved_samples = _find_alias_header(headers, SAMPLE_VALUE_CANDIDATES)
    if not resolved_name:
        return None
    if not any((resolved_description, resolved_type, resolved_samples)):
        return None

    confidence = 0.85 if resolved_description and resolved_type else 0.72
    return SpecLayoutHint(
        name_col=resolved_name,
        description_col=resolved_description,
        type_col=resolved_type,
        sample_values_col=resolved_samples,
        confidence=confidence,
    )


def _build_alias_candidate_recovery(
    candidate_blocks: list[tuple[list[dict[str, object]], int]],
) -> tuple[SpecLayoutHint, int] | None:
    best_hint: SpecLayoutHint | None = None
    best_header_row_index: int | None = None
    best_score: tuple[int, int] | None = None
    ambiguous = False

    for rows, header_row_index in candidate_blocks:
        if not rows:
            continue
        headers = list(rows[0].keys())
        hint = _build_alias_recovery_hint(headers)
        if hint is None:
            continue
        score = _alias_candidate_score(hint)
        if best_score is None or score > best_score:
            best_hint = hint
            best_header_row_index = header_row_index
            best_score = score
            ambiguous = False
        elif score == best_score:
            ambiguous = True

    if best_hint is None or best_header_row_index is None or ambiguous:
        return None
    return best_hint, best_header_row_index


def _alias_candidate_score(hint: SpecLayoutHint) -> tuple[int, int]:
    optional_matches = sum(
        1
        for value in (hint.description_col, hint.type_col, hint.sample_values_col)
        if str(value or "").strip()
    )
    return optional_matches, int(round(_clamp_confidence(hint.confidence) * 100))


def _find_alias_header(headers: list[str], candidates: set[str]) -> str | None:
    best_header: str | None = None
    best_score = 0
    candidate_tokens = [_header_tokens(candidate) for candidate in candidates]

    for header in headers:
        header_tokens = _header_tokens(normalize_header_candidate(header))
        if not header_tokens:
            continue
        score = 0
        for tokens in candidate_tokens:
            if not tokens:
                continue
            if tokens.issubset(header_tokens):
                score = max(score, len(tokens) + 2)
            else:
                overlap = len(tokens & header_tokens)
                score = max(score, overlap)
        if score > best_score:
            best_score = score
            best_header = header

    return best_header if best_score >= 1 else None


def _header_tokens(value: str) -> set[str]:
    return {token for token in value.split() if token}


def _truncate_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if len(text) <= SPEC_RECOVERY_MAX_CELL_LENGTH:
        return text
    return text[: SPEC_RECOVERY_MAX_CELL_LENGTH - 3] + "..."


def _resolve_header(value: str | None, available_headers: dict[str, str]) -> str | None:
    normalized = normalize_tabular_header(value or "") if value else ""
    return available_headers.get(normalized) if normalized else None


def _hint_to_suggestion(hint: SpecLayoutHint, *, header_row_index: int = 1) -> SpecRecoverySuggestion:
    return SpecRecoverySuggestion(
        detected_mode="spec",
        header_row_index=header_row_index,
        name_col=hint.name_col,
        description_col=hint.description_col,
        type_col=hint.type_col,
        sample_values_col=hint.sample_values_col,
        confidence=_clamp_confidence(hint.confidence),
        warnings=[],
    )


def _optional_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clamp_confidence(value: float | int | None) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))