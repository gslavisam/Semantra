"""Bounded LLM provider integration and prompt-handling helpers for Semantra."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from urllib import parse, request
from urllib.error import HTTPError, URLError
from typing import Any, Callable, Protocol

from app.core.config import settings
from app.models.mapping import (
    ArtifactRefinementResponse,
    LLMValidationResult,
    TransformationGenerationResponse,
    TransformationSpec,
    TransformationSpecProposalResponse,
)
from app.models.mapping import CanonicalGapCandidate, CanonicalGapSuggestion
from app.services.dbt_codegen_profile import dbt_profile_snapshot
from app.services.prompt_templates import (
    ARTIFACT_REFINEMENT_PROMPT_TEMPLATE,
    CANONICAL_GAP_PROMPT_TEMPLATE,
    PromptTemplate,
    TRANSFORMATION_GENERATOR_PROMPT_TEMPLATE,
    TRANSFORMATION_SPEC_PROMPT_TEMPLATE,
    VALIDATOR_PROMPT_TEMPLATE,
)
from app.services.transformation_spec_service import normalize_transformation_spec, summarize_transformation_spec


logger = logging.getLogger(__name__)

MAX_PROMPT_DESCRIPTION_LENGTH = 280
MAX_PROMPT_SAMPLE_VALUES = 5
MAX_PROMPT_SAMPLE_VALUE_LENGTH = 80


def resolve_bounded_llm_timeout() -> float:
    """Return the configured short timeout used for bounded LLM operations."""

    return max(1.0, min(settings.llm_timeout_seconds, settings.llm_bounded_timeout_seconds))


def resolve_probe_timeout(total_timeout_seconds: float, *, probe_timeout_seconds: float) -> float:
    """Return a short reachability timeout without silently ignoring the configured ceiling."""

    return max(0.5, min(total_timeout_seconds, probe_timeout_seconds))


@dataclass(frozen=True, slots=True)
class LLMPromptEnvelope:
    """Structured prompt split into system instructions, task instructions, and payload."""

    system_instructions: tuple[str, ...]
    task_instructions: tuple[str, ...]
    payload: Any
    payload_label: str | None = None

    def render(self) -> str:
        sections: list[str] = []
        system_text = "\n".join(line.strip() for line in self.system_instructions if str(line).strip())
        task_text = "\n".join(line.strip() for line in self.task_instructions if str(line).strip())
        serialized_payload = self.payload if isinstance(self.payload, str) else json.dumps(self.payload, ensure_ascii=True)
        if system_text:
            sections.append(f"SYSTEM:\n{system_text}")
        if task_text:
            sections.append(f"TASK:\n{task_text}")
        if self.payload_label is None:
            sections.append(serialized_payload)
        else:
            sections.append(f"{self.payload_label}:\n{serialized_payload}")
        return "\n\n".join(sections)


def _build_prompt_envelope(template: PromptTemplate, payload: Any, **context: str) -> LLMPromptEnvelope:
    return LLMPromptEnvelope(
        system_instructions=tuple(
            line.format(**context).strip()
            for line in template.system_instructions
            if str(line).strip()
        ),
        task_instructions=tuple(
            line.format(**context).strip()
            for line in template.task_instructions
            if str(line).strip()
        ),
        payload=payload,
        payload_label=template.payload_label,
    )


def _prompt_text(prompt: str | LLMPromptEnvelope) -> str:
    return prompt if isinstance(prompt, str) else prompt.render()


def _prompt_system_text(prompt: str | LLMPromptEnvelope) -> str:
    if isinstance(prompt, str):
        return ""
    return "\n".join(line for line in prompt.system_instructions if str(line).strip())


def _prompt_user_text(prompt: str | LLMPromptEnvelope) -> str:
    if isinstance(prompt, str):
        return prompt
    sections: list[str] = []
    task_text = "\n".join(line for line in prompt.task_instructions if str(line).strip())
    serialized_payload = prompt.payload if isinstance(prompt.payload, str) else json.dumps(prompt.payload, ensure_ascii=True)
    if task_text:
        sections.append(f"TASK:\n{task_text}")
    if prompt.payload_label is None:
        sections.append(serialized_payload)
    else:
        sections.append(f"{prompt.payload_label}:\n{serialized_payload}")
    return "\n\n".join(sections)


class LLMProvider(Protocol):
    """Protocol implemented by bounded LLM providers used throughout Semantra."""

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        ...


@dataclass
class StaticLLMProvider:
    """Deterministic test provider that returns a fixed response or callback-generated text."""

    responder: Callable[[str], str] | str

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        rendered_prompt = _prompt_text(prompt)
        if callable(self.responder):
            return self.responder(rendered_prompt)
        return self.responder


@dataclass
class OpenAIResponsesProvider:
    """Provider wrapper for OpenAI's responses-style API."""

    api_key: str
    model: str | None = None
    base_url: str | None = None

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        if isinstance(prompt, LLMPromptEnvelope):
            input_payload: str | list[dict[str, object]] = []
            system_text = _prompt_system_text(prompt)
            if system_text:
                input_payload.append({"role": "system", "content": [{"type": "input_text", "text": system_text}]})
            input_payload.append({"role": "user", "content": [{"type": "input_text", "text": _prompt_user_text(prompt)}]})
        else:
            input_payload = prompt
        payload_dict: dict[str, object] = {
            "model": self.model or settings.llm_model,
            "input": input_payload,
            "temperature": 0,
        }
        if json_mode:
            payload_dict["text"] = {"format": {"type": "json_object"}}
        payload = json.dumps(payload_dict).encode("utf-8")
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
    """Provider wrapper for local Ollama text generation endpoints."""

    model: str
    base_url: str | None = None

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        body: dict[str, object] = {"model": self.model, "prompt": _prompt_user_text(prompt), "stream": False}
        system_text = _prompt_system_text(prompt)
        if system_text:
            body["system"] = system_text
        if json_mode:
            body["format"] = "json"
        payload = json.dumps(body).encode("utf-8")
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
    _cached_model: str | None = field(default=None, repr=False, compare=False)

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
        if self._cached_model:
            return self._cached_model
        resolved = self.list_models(timeout_seconds)[0]
        self._cached_model = resolved
        return resolved

    def _make_chat_request(self, payload_dict: dict, timeout_seconds: float) -> str:
        payload = json.dumps(payload_dict).encode("utf-8")
        http_request = request.Request(
            self._chat_url(),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        model = self._resolve_model(timeout_seconds)
        messages = []
        system_text = _prompt_system_text(prompt)
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": _prompt_user_text(prompt)})
        payload_dict: dict[str, object] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
        }
        if json_mode:
            payload_dict["response_format"] = {"type": "json_object"}
        try:
            return self._make_chat_request(payload_dict, timeout_seconds)
        except HTTPError as exc:
            # If json_mode caused a compatibility error (400/422), retry without it
            if json_mode and exc.code in (400, 422):
                logger.debug(
                    "LM Studio rejected json_object response_format (HTTP %s); retrying without json_mode",
                    exc.code,
                )
                payload_dict.pop("response_format", None)
                return self._make_chat_request(payload_dict, timeout_seconds)
            raise


def summarize_llm_runtime() -> dict[str, object]:
    """Summarize configured LLM runtime reachability and model status for admin surfaces."""

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
    probe_timeout = resolve_probe_timeout(
        settings.llm_timeout_seconds,
        probe_timeout_seconds=settings.llm_probe_timeout_seconds,
    )
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


def summarize_tts_runtime() -> dict[str, object]:
    """Summarize configured TTS runtime reachability and model status for admin surfaces."""

    provider_name = settings.tts_provider.strip().lower() or "none"
    configured_model = settings.lmstudio_orpheus_model.strip() or "n/a"

    snapshot: dict[str, object] = {
        "tts_status": "disabled",
        "tts_reachable": False,
        "tts_status_detail": "TTS is disabled in backend configuration.",
    }
    if provider_name == "none":
        return snapshot

    snapshot.update(
        {
            "tts_status": "configured",
            "tts_reachable": None,
            "tts_status_detail": "TTS is configured, but live reachability is not verified for this provider.",
        }
    )

    if not provider_name.startswith("lmstudio"):
        return snapshot

    probe_base_url = str(settings.lmstudio_tts_base_url or "").strip() or str(settings.lmstudio_base_url or "").strip()
    provider = LMStudioProvider(model=settings.lmstudio_orpheus_model, base_url=probe_base_url)
    probe_timeout = max(0.5, min(settings.tts_timeout_seconds, 2.0))
    try:
        available_models = provider.list_models(probe_timeout)
    except Exception as error:
        snapshot.update(
            {
                "tts_status": "unreachable",
                "tts_reachable": False,
                "tts_status_detail": f"{classify_llm_error(error)}: {error}",
            }
        )
        return snapshot

    if not configured_model or configured_model.lower() == "auto":
        snapshot.update(
            {
                "tts_status": "reachable",
                "tts_reachable": True,
                "tts_status_detail": "LM Studio is reachable and at least one model is available for TTS.",
            }
        )
        return snapshot

    if configured_model in available_models:
        snapshot.update(
            {
                "tts_status": "reachable",
                "tts_reachable": True,
                "tts_status_detail": "LM Studio is reachable and the configured TTS model is available.",
            }
        )
        return snapshot

    snapshot.update(
        {
            "tts_status": "misconfigured",
            "tts_reachable": True,
            "tts_status_detail": f"Configured TTS model '{configured_model}' is not currently reported by LM Studio.",
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

    def generate(self, prompt: str | LLMPromptEnvelope, timeout_seconds: float, *, json_mode: bool = False) -> str:
        messages = []
        system_text = _prompt_system_text(prompt)
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": _prompt_user_text(prompt)})
        payload_dict: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if json_mode:
            payload_dict["response_format"] = {"type": "json_object"}
        payload = json.dumps(payload_dict).encode("utf-8")
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
    """Build the currently configured bounded LLM provider instance, or return None when disabled."""

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
    """Normalize common provider and parsing failures into stable error labels."""

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


def _build_llm_json_error_response(raw_response: str, error: Exception) -> tuple[str, dict]:
    return (
        raw_response,
        {
            "raw_response": raw_response,
            "error": classify_llm_error(error),
            "error_message": str(error),
        },
    )


def _salvage_transformation_code(raw_response: str) -> str | None:
    """Try regex-based extraction of transformation_code when JSON parsing produced empty/broken output.

    Handles two common failure modes of small models:
    - Properly escaped JSON string that somehow broke standard parsing
    - Code with unescaped double quotes (e.g. df_source["col"]) inside the JSON value
    """
    if not raw_response:
        return None

    # Strategy 1: standard escaped JSON string value
    match = re.search(r'"transformation_code"\s*:\s*"((?:[^"\\]|\\.)+)"', raw_response)
    if match:
        code = match.group(1)
        code = code.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        code = sanitize_generated_code(code.strip())
        if code:
            logger.debug("salvaged transformation_code via strategy-1 (escaped string)")
            return code

    # Strategy 2: code contains unescaped double quotes; grab up to next top-level key or closing brace
    match = re.search(
        r'"transformation_code"\s*:\s*"(.+?)"\s*(?:,\s*"(?:reasoning|warnings|error|code)"|(?:\s*\}))',
        raw_response,
        re.DOTALL,
    )
    if match:
        code = sanitize_generated_code(match.group(1).strip())
        if code:
            logger.debug("salvaged transformation_code via strategy-2 (greedy up to next key)")
            return code

    return None


def _build_transformation_generation_fallback(raw_response: str, error: str | None = None) -> TransformationGenerationResponse:
    warning = (
        f"LLM fallback: {error}."
        if error
        else "LLM fallback: invalid or incomplete transformation output."
    )
    snippet = raw_response.strip()
    if len(snippet) > 800:
        snippet = f"{snippet[:800]}..."
    warnings = [warning]
    if snippet:
        warnings.append(f"raw_response: {snippet}")
    return TransformationGenerationResponse(
        transformation_code="",
        reasoning=[
            "LLM did not produce a valid transformation payload, so a fallback response is returned."
        ],
        warnings=warnings,
    )


def normalize_llm_list_field(value: object) -> list[str]:
    """Normalize a string-or-list LLM field into a list of strings."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def request_llm_json(
    provider: LLMProvider,
    prompt: str | LLMPromptEnvelope,
    timeout_seconds: float,
    retries: int,
    operation_name: str,
) -> tuple[str, dict] | None:
    """Request JSON from a provider with retry logging and parsed-payload validation."""

    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout_seconds, json_mode=True)
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
            if isinstance(error, json.JSONDecodeError) and attempt == retries - 1:
                return _build_llm_json_error_response(raw_response, error)
        if attempt < retries - 1:
            time.sleep(0.05)

    return None


def request_bounded_llm_json(
    provider: LLMProvider,
    prompt: str | LLMPromptEnvelope,
    operation_name: str,
) -> tuple[str, dict] | None:
    """Request JSON using Semantra's short bounded timeout and retry contract."""

    timeout_seconds = resolve_bounded_llm_timeout()
    retries = 1
    return request_llm_json(
        provider,
        prompt,
        timeout_seconds,
        retries,
        operation_name,
    )


def parse_artifact_refinement_payload(raw_response: str) -> dict:
    """Salvage near-JSON artifact refinement responses that embed code strings unsafely."""

    current_code_match = re.search(
        r'"current_code"\s*:\s*"(?P<code>.*?)"\s*,\s*"mapping_decisions"\s*:',
        raw_response,
        re.DOTALL,
    )
    top_level_code_match = re.search(
        r'"code"\s*:\s*"(?P<code>.*?)"\s*,\s*"reasoning"\s*:',
        raw_response,
        re.DOTALL,
    )
    reasoning_match = re.search(r'"reasoning"\s*:\s*(\[[\s\S]*?\])', raw_response, re.DOTALL)
    warnings_match = re.search(r'"warnings"\s*:\s*(\[[\s\S]*?\])', raw_response, re.DOTALL)

    if not current_code_match and not top_level_code_match:
        raise json.JSONDecodeError("Could not salvage artifact refinement payload", raw_response, 0)

    def _decode_code_fragment(fragment: str) -> str:
        return (
            fragment.replace('\\r', '\r')
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace('\\\\', '\\')
        )

    response_format: dict[str, object] = {}
    if reasoning_match:
        response_format["reasoning"] = json.loads(reasoning_match.group(1))
    if warnings_match:
        response_format["warnings"] = json.loads(warnings_match.group(1))

    return {
        "current_code": _decode_code_fragment((current_code_match or top_level_code_match).group("code")),
        "response_format": response_format,
    }


def parse_llm_json_payload(raw_response: str) -> dict:
    """Parse JSON from raw model output, tolerating markdown fences, leading prose, and repeated payload echoes."""

    candidates = [raw_response, strip_markdown_code_fences(raw_response)]
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            objects = extract_json_objects(normalized)
            for obj in objects:
                try:
                    return json.loads(obj)
                except json.JSONDecodeError:
                    continue
    raise json.JSONDecodeError("Could not parse JSON from LLM response", raw_response, 0)


def strip_markdown_code_fences(raw_response: str) -> str:
    """Remove surrounding markdown code fences from raw LLM output when present."""

    stripped = raw_response.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_objects(raw_response: str) -> list[str]:
    """Extract all balanced JSON objects embedded in model output text."""

    objects: list[str] = []
    start = raw_response.find("{")
    if start < 0:
        return objects

    depth = 0
    in_string = False
    escaping = False
    object_start = None
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
            if depth == 0:
                object_start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and object_start is not None:
                objects.append(raw_response[object_start : index + 1])
                object_start = None

    return objects


def extract_first_json_object(raw_response: str) -> str | None:
    """Extract the first balanced JSON object embedded in model output text."""

    objects = extract_json_objects(raw_response)
    return objects[0] if objects else None


def extract_last_json_object(raw_response: str) -> str | None:
    """Extract the last balanced JSON object embedded in model output text."""

    objects = extract_json_objects(raw_response)
    return objects[-1] if objects else None


def truncate_prompt_text(value: object, max_length: int) -> str:
    """Truncate prompt text fields to a bounded length while preserving readability."""

    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def sanitize_prompt_sample_values(values: object) -> list[str]:
    """Normalize and bound sample values before placing them into an LLM prompt."""

    if not isinstance(values, list):
        return []
    sanitized: list[str] = []
    for value in values[:MAX_PROMPT_SAMPLE_VALUES]:
        text = truncate_prompt_text(value, MAX_PROMPT_SAMPLE_VALUE_LENGTH)
        if text:
            sanitized.append(text)
    return sanitized


def sanitize_prompt_patterns(value: object) -> list[str]:
    """Normalize detected pattern fields into a compact prompt-safe list."""

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def sanitize_prompt_field_context(field: dict) -> dict:
    """Trim one field context dictionary down to the prompt-safe keys used by LLM flows."""

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
    """Run the closed-set mapping validator for one source field and candidate target set."""

    if provider is None or not candidate_targets:
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_validator_prompt_envelope(source_field, candidate_targets)

    response = request_llm_json(provider, prompt, timeout, retries, "validator")
    if response is None:
        return None

    raw_response, parsed = response
    if parsed.get("error"):
        logger.warning(
            "LLM validator response rejected (%s): %s",
            parsed.get("error"),
            parsed.get("error_message"),
        )
        logger.debug("LLM validator raw response: %s", raw_response)
        return None

    try:
        # Accept both old and new keys for backward compatibility
        confidence = float(parsed.get("confidence_score", parsed.get("confidence", 0.5)))
        result = LLMValidationResult(
            selected_target=parsed["selected_target"],
            confidence=confidence,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            transformation_code=None,
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
    """Request bounded transformation code generation for one source-target pair."""

    if provider is None or not user_instruction.strip():
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_transformation_generator_prompt_envelope(source_field, target_field, user_instruction)

    response = request_llm_json(provider, prompt, timeout, retries, "transformation")
    if response is None:
        return _build_transformation_generation_fallback("", "no_response")

    _raw_response, parsed = response
    if parsed.get("error"):
        logger.warning(
            "LLM transformation response rejected (%s): %s",
            parsed.get("error"),
            parsed.get("error_message"),
        )
        logger.debug("LLM transformation raw response: %s", _raw_response)
        # Try to salvage transformation_code from the broken raw response
        salvaged = _salvage_transformation_code(_raw_response)
        if salvaged:
            logger.info("Salvaged transformation_code from broken LLM response (%s)", parsed.get("error"))
            return TransformationGenerationResponse(
                transformation_code=salvaged,
                reasoning=["Salvaged from partially-structured LLM response."],
                warnings=[f"LLM response had parse issues ({parsed.get('error')}); code was salvaged via regex extraction."],
            )
        return _build_transformation_generation_fallback(_raw_response, parsed.get("error"))

    try:
        transformation_code = sanitize_generated_code(
            str(parsed.get("transformation_code") or parsed.get("code") or "").strip()
        )
        if not transformation_code:
            # JSON parsed OK but code field is empty — try to salvage anyway
            salvaged = _salvage_transformation_code(_raw_response)
            if salvaged:
                logger.info("Salvaged transformation_code from empty field in valid JSON response")
                return TransformationGenerationResponse(
                    transformation_code=salvaged,
                    reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
                    warnings=normalize_llm_list_field(parsed.get("warnings") or ["Code field was empty; salvaged via regex extraction."]),
                )
            return _build_transformation_generation_fallback(_raw_response, "empty_transformation_code")

        return TransformationGenerationResponse(
            transformation_code=transformation_code,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            warnings=normalize_llm_list_field(parsed.get("warnings") or []),
        )
    except Exception as error:
        logger.warning("LLM transformation response rejected (%s): %s", classify_llm_error(error), error)
        return _build_transformation_generation_fallback(_raw_response, classify_llm_error(error))


def call_transformation_spec_generator(
    *,
    mapping_decisions: list[dict],
    instruction: str,
    current_spec: dict | None,
    provider: LLMProvider | None,
    max_retries: int | None = None,
    timeout_seconds: float | None = None,
) -> TransformationSpecProposalResponse | None:
    """Request a bounded natural-language to structured transformation spec proposal."""

    if provider is None or not instruction.strip():
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_transformation_spec_prompt_envelope(
        mapping_decisions=mapping_decisions,
        instruction=instruction,
        current_spec=current_spec,
    )

    response = request_llm_json(provider, prompt, timeout, retries, "transformation_spec")
    if response is None:
        return None

    _raw_response, parsed = response
    if parsed.get("error"):
        logger.warning(
            "LLM transformation spec response rejected (%s): %s",
            parsed.get("error"),
            parsed.get("error_message"),
        )
        logger.debug("LLM transformation spec raw response: %s", _raw_response)
        return None

    try:
        raw_spec = parsed.get("transformation_spec") or parsed.get("spec") or parsed
        proposed_spec = TransformationSpec.model_validate(raw_spec)
        normalized_spec = normalize_transformation_spec(proposed_spec, mapping_decisions)
        summary = summarize_transformation_spec(normalized_spec, mapping_decisions)
        return TransformationSpecProposalResponse(
            transformation_spec=normalized_spec,
            summary=summary,
            reasoning=normalize_llm_list_field(parsed.get("reasoning") or parsed.get("explanation") or []),
            warnings=normalize_llm_list_field(parsed.get("warnings") or []),
        )
    except Exception as error:
        logger.warning("LLM transformation spec response rejected (%s): %s", classify_llm_error(error), error)

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
    """Request bounded refinement of a generated output artifact without applying it automatically."""

    if provider is None or not current_code.strip() or not instruction.strip():
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_artifact_refinement_prompt_envelope(
        mapping_decisions=mapping_decisions,
        mode=mode,
        current_code=current_code,
        instruction=instruction,
        edge_cases=edge_cases,
        reference_excerpt=reference_excerpt,
    )

    response = None
    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout)
            try:
                parsed = parse_llm_json_payload(raw_response)
            except json.JSONDecodeError:
                parsed = parse_artifact_refinement_payload(raw_response)
            response = (raw_response, parsed)
            break
        except Exception as error:
            logger.warning(
                "LLM %s attempt %s/%s failed (%s): %s",
                "artifact_refinement",
                attempt + 1,
                retries,
                classify_llm_error(error),
                error,
            )
        if attempt < retries - 1:
            time.sleep(0.05)
    if response is None:
        return None

    _raw_response, parsed = response
    try:
        response_format = parsed.get("response_format") if isinstance(parsed.get("response_format"), dict) else {}
        echoed_current_code = str(parsed.get("current_code") or "").strip()
        fallback_code = echoed_current_code if echoed_current_code and echoed_current_code != current_code.strip() else ""
        code = sanitize_generated_code(
            str(
                parsed.get("code")
                or parsed.get("artifact_code")
                or response_format.get("code")
                or fallback_code
                or ""
            ).strip()
        )
        if not code:
            return None

        return ArtifactRefinementResponse(
            language=(
                "python-pyspark"
                if mode == "pyspark"
                else "sql-dbt"
                if mode == "dbt"
                else "python-pandas"
            ),
            code=code,
            reasoning=normalize_llm_list_field(
                parsed.get("reasoning") or parsed.get("explanation") or response_format.get("reasoning") or []
            ),
            warnings=normalize_llm_list_field(parsed.get("warnings") or response_format.get("warnings") or []),
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
    """Request a bounded canonical-gap suggestion for one candidate and its nearest known concepts."""

    if provider is None:
        return None

    retries = max_retries if max_retries is not None else settings.llm_max_retries
    timeout = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    prompt = build_canonical_gap_prompt_envelope(candidate, nearest_concepts)
    response = request_llm_json(provider, prompt, timeout, retries, "canonical_gap")
    if response is None:
        return None

    raw_response, parsed = response
    if parsed.get("error"):
        logger.warning(
            "LLM canonical gap response rejected (%s): %s",
            parsed.get("error"),
            parsed.get("error_message"),
        )
        logger.debug("LLM canonical gap raw response: %s", raw_response)
        return None

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
    """Validate that an LLM mapping result selects a permitted target with coherent fields."""

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
    """Validate that a canonical-gap suggestion satisfies Semantra's bounded contract."""

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
    """Build the closed-set mapping validation prompt for one source field."""

    return build_validator_prompt_envelope(source_field, candidate_targets).render()


def build_validator_prompt_envelope(source_field: dict, candidate_targets: list[dict]) -> LLMPromptEnvelope:
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
    return _build_prompt_envelope(VALIDATOR_PROMPT_TEMPLATE, payload)


def build_canonical_gap_prompt(candidate: CanonicalGapCandidate, nearest_concepts: list[dict]) -> str:
    """Build the bounded prompt used to suggest a canonical-gap action."""

    return build_canonical_gap_prompt_envelope(candidate, nearest_concepts).render()


def build_canonical_gap_prompt_envelope(
    candidate: CanonicalGapCandidate,
    nearest_concepts: list[dict],
) -> LLMPromptEnvelope:
    payload = {
        "canonical_gap_candidate": candidate.model_dump(mode="json"),
        "nearest_existing_canonical_concepts": nearest_concepts,
        "rules": {
            "json_only": True,
            "allowed_actions": ["existing_concept_alias", "new_canonical_concept", "no_action"],
            "do_not_invent_source_or_target_fields": True,
            "prefer_existing_concepts_when_semantically_correct": True,
            "return_no_action_only_if_uncertain_or_generic": True,
            "reject_no_action_unless_there_is_no_clear_concept_match": True,
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
    return _build_prompt_envelope(CANONICAL_GAP_PROMPT_TEMPLATE, payload)


def build_transformation_generator_prompt(source_field: dict, target_field: dict, user_instruction: str) -> str:
    """Build the bounded prompt used to generate transformation code for one field pair."""

    return build_transformation_generator_prompt_envelope(source_field, target_field, user_instruction).render()


def build_transformation_generator_prompt_envelope(
    source_field: dict,
    target_field: dict,
    user_instruction: str,
) -> LLMPromptEnvelope:
    payload = {
        "source_field": sanitize_prompt_field_context(source_field),
        "target_field": sanitize_prompt_field_context(target_field),
        "user_instruction": user_instruction,
        "response_format": {
            "transformation_code": "string (pandas expression or empty string for direct mapping)",
            "reasoning": ["short bullet points"],
            "warnings": ["short bullet points"],
        },
    }
    return _build_prompt_envelope(TRANSFORMATION_GENERATOR_PROMPT_TEMPLATE, payload)


def build_transformation_spec_prompt(
    *,
    mapping_decisions: list[dict],
    instruction: str,
    current_spec: dict | None,
) -> str:
    """Build the bounded prompt used to propose a structured transformation design spec."""

    return build_transformation_spec_prompt_envelope(
        mapping_decisions=mapping_decisions,
        instruction=instruction,
        current_spec=current_spec,
    ).render()


def build_transformation_spec_prompt_envelope(
    *,
    mapping_decisions: list[dict],
    instruction: str,
    current_spec: dict | None,
) -> LLMPromptEnvelope:
    target_fields: list[str] = []
    seen_targets: set[str] = set()
    for item in mapping_decisions:
        target = str(item.get("target") or "").strip()
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)
        target_fields.append(target)

    payload = {
        "mapping_decisions": [
            {
                "source": str(item.get("source") or "").strip(),
                "target": str(item.get("target") or "").strip(),
                "status": str(item.get("status") or "accepted").strip(),
                "has_transformation_code": bool(str(item.get("transformation_code") or "").strip()),
            }
            for item in mapping_decisions
            if str(item.get("target") or "").strip()
        ],
        "allowed_target_fields": target_fields,
        "instruction": instruction.strip(),
        "current_spec": current_spec or {},
        "rules": {
            "json_only": True,
            "closed_target_set": True,
            "do_not_generate_code": True,
            "do_not_invent_new_target_fields": True,
            "return_reviewable_business_rules_only": True,
        },
        "response_format": {
            "transformation_spec": {
                "target_grain": "string",
                "global_rules": "string",
                "defaults": "string",
                "examples": "string",
                "field_rules": [{"target_field": "one of allowed_target_fields", "rule": "string"}],
            },
            "reasoning": ["short bullet points"],
            "warnings": ["short bullet points"],
        },
    }
    return _build_prompt_envelope(TRANSFORMATION_SPEC_PROMPT_TEMPLATE, payload)


def build_artifact_refinement_prompt(
    *,
    mapping_decisions: list[dict],
    mode: str,
    current_code: str,
    instruction: str,
    edge_cases: str,
    reference_excerpt: str,
) -> str:
    """Build the bounded prompt used to refine an already generated code artifact."""

    return build_artifact_refinement_prompt_envelope(
        mapping_decisions=mapping_decisions,
        mode=mode,
        current_code=current_code,
        instruction=instruction,
        edge_cases=edge_cases,
        reference_excerpt=reference_excerpt,
    ).render()


def build_artifact_refinement_prompt_envelope(
    *,
    mapping_decisions: list[dict],
    mode: str,
    current_code: str,
    instruction: str,
    edge_cases: str,
    reference_excerpt: str,
) -> LLMPromptEnvelope:
    runtime_language = "python-pyspark" if mode == "pyspark" else "sql-dbt" if mode == "dbt" else "python-pandas"
    dbt_profile = dbt_profile_snapshot() if mode == "dbt" else None
    allowed_objects = (
        ["df_source", "df_target", "F"]
        if mode == "pyspark"
        else [str(dbt_profile["source_cte_name"]), "ref", "source", "config", "adapter.quote"]
        if mode == "dbt"
        else ["df_source", "df_target", "pd"]
    )
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
            "dbt_profile": dbt_profile,
        },
        "response_format": {
            "code": "string",
            "reasoning": ["short bullet points"],
            "warnings": ["short bullet points"],
        },
    }
    return _build_prompt_envelope(ARTIFACT_REFINEMENT_PROMPT_TEMPLATE, payload, runtime_language=runtime_language)


def sanitize_generated_code(code: str) -> str:
    """Normalize generated code by stripping fences and extraneous wrapper text."""

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