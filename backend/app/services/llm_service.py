from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib import request
from urllib.error import URLError
from typing import Callable, Protocol

from app.core.config import settings
from app.models.mapping import LLMValidationResult, TransformationGenerationResponse


logger = logging.getLogger(__name__)


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

    model: str
    base_url: str

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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


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


def build_validator_prompt(source_field: dict, candidate_targets: list[dict]) -> str:
    payload = {
        "source_field": source_field,
        "candidate_targets": candidate_targets,
        "rules": {
            "closed_set_only": True,
            "allow_no_match": True,
            "json_only": True,
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


def build_transformation_generator_prompt(source_field: dict, target_field: dict, user_instruction: str) -> str:
    payload = {
        "source_field": source_field,
        "target_field": target_field,
        "user_instruction": user_instruction,
        "rules": {
            "json_only": True,
            "language": "python-pandas",
            "allowed_objects": ["df_source", "df_target", "pd"],
            "allow_expression_only": True,
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