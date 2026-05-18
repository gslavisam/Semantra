from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib import parse, request
from urllib.error import URLError
from typing import Callable, Protocol

from app.core.config import settings
from app.models.mapping import ArtifactRefinementResponse, LLMValidationResult, TransformationGenerationResponse
from app.models.mapping import CanonicalGapCandidate, CanonicalGapSuggestion


logger = logging.getLogger(__name__)

MAX_PROMPT_DESCRIPTION_LENGTH = 280
MAX_PROMPT_SAMPLE_VALUES = 5
MAX_PROMPT_SAMPLE_VALUE_LENGTH = 80


class LLMProvider(Protocol):
    def generate(self, prompt: str, timeout_seconds: float) -> str:
        ...


@dataclass
class StaticLLMProvider:
    responder: Callable[[str], str] | str

    def generate(self, prompt: str, timeout_seconds: float) -> str:
        if callable(self.responder):
            return self.responder(prompt)
        return self.responder


@dataclass
class OpenAIResponsesProvider:
    api_key: str
    model: str | None = None
    base_url: str | None = None

    def generate(self, prompt: str, timeout_seconds: float) -> str:
        payload = json.dumps(
            {
                "model": self.model or settings.llm_model,
                "input": prompt,
                "temperature": 0,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = request.Request(
            self.base_url or settings.openai_base_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["output"][0]["content"][0]["text"]


@dataclass
class OllamaProvider:
    model: str
    base_url: str | None = None

    def generate(self, prompt: str, timeout_seconds: float) -> str:
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        http_request = request.Request(
            self.base_url or settings.ollama_base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["response"]


@dataclass
class LMStudioProvider:
    """LM Studio exposes an OpenAI-compatible /v1/chat/completions endpoint.
    Use this instead of OpenAIResponsesProvider which targets the newer /v1/responses API.
    """

    model: str | None
    base_url: str

    def _chat_url(self) -> str:
        parsed_url = parse.urlparse(self.base_url)
        path = parsed_url.path.rstrip("/")
        if path.endswith("/chat/completions"):
            chat_path = path
        elif path.endswith("/v1"):
            chat_path = f"{path}/chat/completions"
        else:
            chat_path = "/v1/chat/completions"
        return parse.urlunparse(parsed_url._replace(path=chat_path, params="", query="", fragment=""))

    def _models_url(self) -> str:
        parsed_url = parse.urlparse(self.base_url)
        models_path = parsed_url.path.rstrip("/")
        if models_path.endswith("/chat/completions"):
            models_path = models_path[: -len("/chat/completions")] + "/models"
        elif models_path.endswith("/v1"):
            models_path = f"{models_path}/models"
        else:
            models_path = "/v1/models"
        return parse.urlunparse(parsed_url._replace(path=models_path, params="", query="", fragment=""))

    def list_models(self, timeout_seconds: float) -> list[str]:
        with request.urlopen(self._models_url(), timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))

        candidates = body.get("data") or []
        model_ids: list[str] = []
        for candidate in candidates:
            model_id = str(candidate.get("id", "")).strip()
            if model_id:
                model_ids.append(model_id)

        if model_ids:
            return model_ids

        raise ValueError("LM Studio did not return any available model IDs")

    def _resolve_model(self, timeout_seconds: float) -> str:
        configured_model = (self.model or "").strip()
        if configured_model and configured_model.lower() != "auto":
            return configured_model

        return self.list_models(timeout_seconds)[0]

    def generate(self, prompt: str, timeout_seconds: float) -> str:
        model = self._resolve_model(timeout_seconds)
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        http_request = request.Request(
            self._chat_url(),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def summarize_llm_runtime() -> dict[str, object]:
    provider_name = settings.llm_provider.strip().lower() or "none"
    configured_model = settings.llm_model.strip() or "n/a"

    snapshot: dict[str, object] = {
        "llm_status": "disabled",
        "llm_reachable": False,
        "llm_status_detail": "LLM is disabled in backend configuration.",
        "llm_resolved_model": configured_model,
    }
    if provider_name == "none":
        return snapshot

    snapshot.update(
        {
            "llm_status": "configured",
            "llm_reachable": None,
            "llm_status_detail": "LLM is configured, but live reachability is not verified for this provider.",
        }
    )

    if provider_name != "lmstudio":
        return snapshot

    provider = LMStudioProvider(model=settings.llm_model, base_url=settings.lmstudio_base_url)
    probe_timeout = max(0.5, min(settings.llm_timeout_seconds, 2.0))
    try:
        available_models = provider.list_models(probe_timeout)
    except Exception as error:
        snapshot.update(
            {
                "llm_status": "unreachable",
                "llm_reachable": False,
                "llm_status_detail": f"{classify_llm_error(error)}: {error}",
            }
        )
        return snapshot

    if not configured_model or configured_model.lower() == "auto":
        snapshot.update(
            {
                "llm_status": "reachable",
                "llm_reachable": True,
                "llm_status_detail": "LM Studio is reachable and at least one model is available.",
                "llm_resolved_model": available_models[0],
            }
        )
        return snapshot

    if configured_model in available_models:
        snapshot.update(
            {
                "llm_status": "reachable",
                "llm_reachable": True,
                "llm_status_detail": "LM Studio is reachable and the configured model is available.",
                "llm_resolved_model": configured_model,
            }
        )
        return snapshot

    snapshot.update(
        {
            "llm_status": "misconfigured",
            "llm_reachable": True,
            "llm_status_detail": f"Configured model '{configured_model}' is not currently reported by LM Studio.",
            "llm_resolved_model": available_models[0],
        }
    )
    return snapshot


@dataclass
class GeminiProvider:
    """Google Gemini via its OpenAI-compatible /v1beta/openai/chat/completions endpoint.

    Requires a Gemini API key from https://aistudio.google.com/apikey.
    Set SEMANTRA_GEMINI_API_KEY and optionally SEMANTRA_GEMINI_BASE_URL in .env.
    """

    api_key: str
    model: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    def generate(self, prompt: str, timeout_seconds: float) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        http_request = request.Request(
            self.base_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def build_provider_from_settings() -> LLMProvider | None:
    provider_name = settings.llm_provider.lower()
    if provider_name == "none":
        return None
    if provider_name == "lmstudio":
        base_url = getattr(settings, "lmstudio_base_url", None) or "http://127.0.0.1:1234/v1/chat/completions"
        return LMStudioProvider(model=settings.llm_model, base_url=base_url)
    if provider_name == "openai":
        return OpenAIResponsesProvider(api_key=settings.openai_api_key, model=settings.llm_model, base_url=settings.openai_base_url)
    if provider_name == "ollama":
        return OllamaProvider(model=settings.llm_model)
    if provider_name == "gemini":
        base_url = getattr(settings, "gemini_base_url", None) or "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.llm_model, base_url=base_url)
    return None


def classify_llm_error(error: Exception) -> str:
    if isinstance(error, URLError):
        return "network_error"
    if isinstance(error, json.JSONDecodeError):
        return "invalid_json"
    if isinstance(error, KeyError):
        return "missing_key"
    if isinstance(error, ValueError):
        return "invalid_value"
    if isinstance(error, TimeoutError):
        return "timeout"
    return error.__class__.__name__.lower()


def normalize_llm_list_field(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def request_llm_json(
    provider: LLMProvider,
    prompt: str,
    timeout_seconds: float,
    retries: int,
    operation_name: str,
) -> tuple[str, dict] | None:
    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout_seconds)
            return raw_response, parse_llm_json_payload(raw_response)
        except Exception as error:
            logger.warning(
                "LLM %s attempt %s/%s failed (%s): %s",
                operation_name,
                attempt + 1,
                retries,
                classify_llm_error(error),
                error,
            )

        if attempt < retries - 1:
            time.sleep(0.05)

    return None


def request_bounded_llm_json(
    provider: LLMProvider,
    prompt: str,
    operation_name: str,
) -> tuple[str, dict] | None:
    timeout_seconds = max(1.0, min(settings.llm_timeout_seconds, 5.0))
    retries = 1
    return request_llm_json(
        provider,
        prompt,
        timeout_seconds,
        retries,
        operation_name,
    )


def parse_llm_json_payload(raw_response: str) -> dict:
    candidates = [raw_response, strip_markdown_code_fences(raw_response)]
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            extracted = extract_first_json_object(normalized)
            if extracted is None:
                continue
            return json.loads(extracted)
    raise json.JSONDecodeError("Could not parse JSON from LLM response", raw_response, 0)


def strip_markdown_code_fences(raw_response: str) -> str:
    stripped = raw_response.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_first_json_object(raw_response: str) -> str | None:
    start = raw_response.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaping = False
    for index in range(start, len(raw_response)):
        char = raw_response[index]
        if in_string:
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw_response[start : index + 1]

    return None


def truncate_prompt_text(value: object, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def sanitize_prompt_sample_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    sanitized: list[str] = []
    for value in values[:MAX_PROMPT_SAMPLE_VALUES]:
        text = truncate_prompt_text(value, MAX_PROMPT_SAMPLE_VALUE_LENGTH)
        if text:
            sanitized.append(text)
    return sanitized


def sanitize_prompt_patterns(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def sanitize_prompt_field_context(field: dict) -> dict:
    sanitized = {
        "name": str(field.get("name") or "").strip(),
        "description": truncate_prompt_text(field.get("description") or "", MAX_PROMPT_DESCRIPTION_LENGTH),
        "declared_type": truncate_prompt_text(field.get("declared_type") or "", MAX_PROMPT_DESCRIPTION_LENGTH),
        "sample_values": sanitize_prompt_sample_values(field.get("sample_values")),
        "detected_patterns": sanitize_prompt_patterns(field.get("detected_patterns") or field.get("pattern")),
    }
    if "unique_ratio" in field:
        sanitized["unique_ratio"] = field.get("unique_ratio")
    if "confidence" in field:
        sanitized["confidence"] = field.get("confidence")
    return {key: value for key, value in sanitized.items() if value not in ("", [], None)}


def call_validator(
    source_field: dict,
    candidate_targets: list[dict],
    provider: LLMProvider | None,
    low_confidence_fallback_to_no_match: bool = False,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
) -> LLMValidationResult | None:
    if provider is None or not candidate_targets:
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_validator_prompt(source_field, candidate_targets)
    prompt += (
        "\n\nFor each mapping decision, return a JSON object with: 'selected_target', 'confidence' (0-1 float), 'reasoning' (list of strings explaining the choice and why others were not selected), and 'transformation_code' (Python Pandas code to convert the source column to the target format, or null/empty if not needed)."
        "\nAnalyze the field names and, if available, the data patterns. If a transformation is needed (e.g. extracting name from email, formatting dates, splitting or combining fields, type conversion, normalization), generate the appropriate Pandas code. If not, set 'transformation_code' to null or empty."
        "\nYou should infer the transformation based on the semantic meaning and typical data formats, not just on explicit examples."
        "\nExample: If mapping from an email field like 'ime.prezime@firma.com' to a name field, generate Pandas code to extract and format the name. If mapping from a date string to a date field, generate code to parse the date."
        "\nIf no transformation is needed, set 'transformation_code' to null or empty."
    )

    response = request_llm_json(provider, prompt, timeout, retries, "validator")
    if response is None:
        return None

    raw_response, parsed = response
    try:
        # Accept both old and new keys for backward compatibility
        confidence = float(parsed.get("confidence_score", parsed.get("confidence", 0.5)))
        transformation_code = parsed.get("transformation_code")
        result = LLMValidationResult(
            selected_target=parsed["selected_target"],
            confidence=confidence,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            transformation_code=transformation_code,
            raw_response=raw_response,
        )
        if (
            low_confidence_fallback_to_no_match
            and result.selected_target != "no_match"
            and result.confidence < settings.llm_min_confidence
        ):
            result = LLMValidationResult(
                selected_target="no_match",
                confidence=0.0,
                reasoning=list(result.reasoning)
                + [
                    "LLM selected a low-confidence candidate below the acceptance threshold; treated as no_match in rescue mode."
                ],
                transformation_code=None,
                raw_response=raw_response,
            )
        if validate_result(result, candidate_targets):
            return result
    except Exception as error:
        logger.warning("LLM validator response rejected (%s): %s", classify_llm_error(error), error)

    return None


def call_transformation_generator(
    source_field: dict,
    target_field: dict,
    user_instruction: str,
    provider: LLMProvider | None,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
) -> TransformationGenerationResponse | None:
    if provider is None or not user_instruction.strip():
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_transformation_generator_prompt(source_field, target_field, user_instruction)

    response = request_llm_json(provider, prompt, timeout, retries, "transformation")
    if response is None:
        return None

    _raw_response, parsed = response
    try:
        transformation_code = sanitize_generated_code(
            str(parsed.get("transformation_code") or parsed.get("code") or "").strip()
        )
        if not transformation_code:
            return None

        return TransformationGenerationResponse(
            transformation_code=transformation_code,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            warnings=normalize_llm_list_field(parsed.get("warnings") or []),
        )
    except Exception as error:
        logger.warning("LLM transformation response rejected (%s): %s", classify_llm_error(error), error)

    return None


def call_artifact_refinement(
    *,
    mapping_decisions: list[dict],
    mode: str,
    current_code: str,
    instruction: str,
    edge_cases: str,
    reference_excerpt: str,
    provider: LLMProvider | None,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
) -> ArtifactRefinementResponse | None:
    if provider is None or not current_code.strip() or not instruction.strip():
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_artifact_refinement_prompt(
        mapping_decisions=mapping_decisions,
        mode=mode,
        current_code=current_code,
        instruction=instruction,
        edge_cases=edge_cases,
        reference_excerpt=reference_excerpt,
    )

    response = request_llm_json(provider, prompt, timeout, retries, "artifact_refinement")
    if response is None:
        return None

    _raw_response, parsed = response
    try:
        code = sanitize_generated_code(str(parsed.get("code") or parsed.get("artifact_code") or "").strip())
        if not code:
            return None

        return ArtifactRefinementResponse(
            language="python-pyspark" if mode == "pyspark" else "python-pandas",
            code=code,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            warnings=normalize_llm_list_field(parsed.get("warnings") or []),
        )
    except Exception as error:
        logger.warning("LLM artifact refinement response rejected (%s): %s", classify_llm_error(error), error)

    return None


def call_canonical_gap_assistant(
    candidate: CanonicalGapCandidate,
    nearest_concepts: list[dict],
    provider: LLMProvider | None,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
) -> CanonicalGapSuggestion | None:
    if provider is None:
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_canonical_gap_prompt(candidate, nearest_concepts)
    response = request_llm_json(provider, prompt, timeout, retries, "canonical_gap")
    if response is None:
        return None

    raw_response, parsed = response
    try:
        suggestion = CanonicalGapSuggestion(
            action=parsed.get("action", "no_action"),
            concept_id=parsed.get("concept_id"),
            display_name=parsed.get("display_name"),
            aliases=normalize_llm_list_field(parsed.get("aliases") or []),
            confidence=float(parsed.get("confidence", 0.0) or 0.0),
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or []),
            risk_notes=normalize_llm_list_field(parsed.get("risk_notes") or []),
            raw_response=raw_response,
        )
        if validate_canonical_gap_suggestion(suggestion, candidate, nearest_concepts):
            return suggestion
    except Exception as error:
        logger.warning("LLM canonical gap response rejected (%s): %s", classify_llm_error(error), error)
    return None


def validate_result(result: LLMValidationResult | None, candidate_targets: list[dict]) -> bool:
    if result is None:
        return False

    valid_targets = {candidate["name"] for candidate in candidate_targets}
    valid_targets.add("no_match")

    if result.selected_target not in valid_targets:
        return False
    if not 0.0 <= result.confidence <= 1.0:
        return False
    if result.selected_target != "no_match" and result.confidence < settings.llm_min_confidence:
        return False
    if not isinstance(result.reasoning, list):
        return False
    return True


def validate_canonical_gap_suggestion(
    suggestion: CanonicalGapSuggestion,
    candidate: CanonicalGapCandidate,
    nearest_concepts: list[dict],
) -> bool:
    if suggestion.action == "no_action":
        return True
    if not 0.0 <= suggestion.confidence <= 1.0:
        return False
    if suggestion.confidence < settings.llm_min_confidence:
        return False
    if not suggestion.concept_id or not suggestion.display_name:
        return False
    aliases = {alias.strip().lower() for alias in suggestion.aliases if alias.strip()}
    if candidate.source.lower() not in aliases and candidate.target.lower() not in aliases:
        return False
    if suggestion.action == "existing_concept_alias":
        valid_concepts = {str(item.get("concept_id") or "") for item in nearest_concepts}
        return suggestion.concept_id in valid_concepts
    if suggestion.action == "new_canonical_concept":
        return "." in suggestion.concept_id
    return False


def build_validator_prompt(source_field: dict, candidate_targets: list[dict]) -> str:
    payload = {
        "source_field": sanitize_prompt_field_context(source_field),
        "candidate_targets": [sanitize_prompt_field_context(target) for target in candidate_targets],
        "rules": {
            "closed_set_only": True,
            "allow_no_match": True,
            "json_only": True,
            "description_truncation": MAX_PROMPT_DESCRIPTION_LENGTH,
            "sample_values_limit": MAX_PROMPT_SAMPLE_VALUES,
        },
        "response_format": {
            "selected_target": "string",
            "confidence": "0.0-1.0",
            "reasoning": ["short bullet points"],
        },
    }
    return (
        "You are a strict data mapping validator.\n"
        "Select the best target field only from the provided candidate_targets.\n"
        "If no good match exists, return no_match.\n"
        "Return only valid JSON.\n\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def build_canonical_gap_prompt(candidate: CanonicalGapCandidate, nearest_concepts: list[dict]) -> str:
    payload = {
        "canonical_gap_candidate": candidate.model_dump(mode="json"),
        "nearest_existing_canonical_concepts": nearest_concepts,
        "rules": {
            "json_only": True,
            "allowed_actions": ["existing_concept_alias", "new_canonical_concept", "no_action"],
            "do_not_invent_source_or_target_fields": True,
            "prefer_existing_concepts_when_semantically_correct": True,
            "return_no_action_if_uncertain_or_generic": True,
        },
        "response_format": {
            "action": "existing_concept_alias | new_canonical_concept | no_action",
            "concept_id": "canonical concept id or null",
            "display_name": "human readable concept name or null",
            "aliases": ["source/target aliases to attach"],
            "confidence": "0.0-1.0",
            "reasoning": ["short bullet points"],
            "risk_notes": ["short bullet points"],
        },
    }
    return (
        "You are a strict canonical glossary assistant.\n"
        "A mapping row is already selected, but its canonical path is missing.\n"
        "Suggest a controlled canonical overlay change only when it is well-supported by the provided source/target names, signals, and explanations.\n"
        "Use an existing concept if it fits. Propose a new canonical concept only for clear enterprise data concepts.\n"
        "Return only valid JSON.\n\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def build_transformation_generator_prompt(source_field: dict, target_field: dict, user_instruction: str) -> str:
    payload = {
        "source_field": sanitize_prompt_field_context(source_field),
        "target_field": sanitize_prompt_field_context(target_field),
        "user_instruction": user_instruction,
        "rules": {
            "json_only": True,
            "language": "python-pandas",
            "allowed_objects": ["df_source", "df_target", "pd"],
            "allow_expression_only": True,
            "description_truncation": MAX_PROMPT_DESCRIPTION_LENGTH,
            "sample_values_limit": MAX_PROMPT_SAMPLE_VALUES,
        },
        "response_format": {
            "transformation_code": "string",
            "reasoning": ["short bullet points"],
            "warnings": ["short bullet points"],
        },
    }
    return (
        "You generate pandas-oriented Python transformations for tabular data mapping.\n"
        "Return only valid JSON. Do not include markdown or code fences.\n"
        "Use only df_source, df_target, pd, and standard Python built-ins.\n"
        "The transformation_code may be either a full assignment like df_target[\"target\"] = ... or just the right-hand expression.\n\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def build_artifact_refinement_prompt(
    *,
    mapping_decisions: list[dict],
    mode: str,
    current_code: str,
    instruction: str,
    edge_cases: str,
    reference_excerpt: str,
) -> str:
    runtime_language = "python-pyspark" if mode == "pyspark" else "python-pandas"
    allowed_objects = ["df_source", "df_target", "F"] if mode == "pyspark" else ["df_source", "df_target", "pd"]
    payload = {
        "artifact_mode": mode,
        "current_code": current_code.strip(),
        "mapping_decisions": [
            {
                "source": str(item.get("source") or "").strip(),
                "target": str(item.get("target") or "").strip(),
                "status": str(item.get("status") or "accepted").strip(),
                "has_transformation": bool(str(item.get("transformation_code") or "").strip()),
            }
            for item in mapping_decisions
        ],
        "instruction": instruction.strip(),
        "edge_cases": edge_cases.strip(),
        "reference_excerpt": reference_excerpt.strip()[:2000],
        "rules": {
            "json_only": True,
            "language": runtime_language,
            "preserve_existing_scaffold_when_possible": True,
            "return_full_rewritten_code": True,
            "allowed_objects": allowed_objects,
        },
        "response_format": {
            "code": "string",
            "reasoning": ["short bullet points"],
            "warnings": ["short bullet points"],
        },
    }
    return (
        f"You refine {runtime_language} starter code for a data-mapping workflow.\n"
        "Return only valid JSON. Do not include markdown or code fences.\n"
        "Follow the requested runtime strictly and return the complete rewritten artifact in the code field.\n\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def sanitize_generated_code(code: str) -> str:
    if not code:
        return ""
    stripped = code.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()