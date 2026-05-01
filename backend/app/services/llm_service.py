from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib import request
from urllib.error import URLError
from typing import Callable, Protocol

from app.core.config import settings
from app.models.mapping import LLMValidationResult, TransformationGenerationResponse


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


def build_provider_from_settings() -> LLMProvider | None:
    provider_name = settings.llm_provider.lower()
    if provider_name == "none":
        return None
    # Support LM Studio as OpenAI-compatible endpoint
    if provider_name in ("openai", "lmstudio"):
        # If LM Studio, use custom base_url and no API key
        base_url = settings.openai_base_url
        api_key = settings.openai_api_key
        if provider_name == "lmstudio":
            base_url = getattr(settings, "lmstudio_base_url", None) or "http://127.0.0.1:1234/v1/responses"
            api_key = ""
        return OpenAIResponsesProvider(api_key=api_key, model=settings.llm_model, base_url=base_url)
    if provider_name == "ollama":
        return OllamaProvider(model=settings.llm_model)
    return None


def call_validator(
    source_field: dict,
    candidate_targets: list[dict],
    provider: LLMProvider | None,
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

    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout)
            parsed = json.loads(raw_response)
            # Accept both old and new keys for backward compatibility
            confidence = float(parsed.get("confidence_score", parsed.get("confidence", 0.5)))
            reasoning = parsed.get("reasoning") or parsed.get("explanation") or []
            if isinstance(reasoning, str):
                reasoning = [reasoning]
            transformation_code = parsed.get("transformation_code")
            result = LLMValidationResult(
                selected_target=parsed["selected_target"],
                confidence=confidence,
                reasoning=list(reasoning),
                transformation_code=transformation_code,
                raw_response=raw_response,
            )
            if validate_result(result, candidate_targets):
                return result
        except (Exception, URLError):
            pass

        if attempt < retries - 1:
            time.sleep(0.05)

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

    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout)
            parsed = json.loads(raw_response)
            transformation_code = sanitize_generated_code(
                str(parsed.get("transformation_code") or parsed.get("code") or "").strip()
            )
            if not transformation_code:
                continue

            reasoning = parsed.get("reasoning") or parsed.get("explanation") or []
            if isinstance(reasoning, str):
                reasoning = [reasoning]
            warnings = parsed.get("warnings") or []
            if isinstance(warnings, str):
                warnings = [warnings]

            return TransformationGenerationResponse(
                transformation_code=transformation_code,
                reasoning=list(reasoning),
                warnings=list(warnings),
            )
        except (Exception, URLError):
            pass

        if attempt < retries - 1:
            time.sleep(0.05)

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