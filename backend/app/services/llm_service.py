from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib import request
from urllib.error import URLError
from typing import Callable, Protocol

from app.core.config import settings
from app.models.mapping import LLMValidationResult


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
        http_request = request.Request(
            self.base_url or settings.openai_base_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
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
    if provider_name == "openai" and settings.openai_api_key:
        return OpenAIResponsesProvider(api_key=settings.openai_api_key)
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

    for attempt in range(retries):
        try:
            raw_response = provider.generate(prompt, timeout)
            parsed = json.loads(raw_response)
            result = LLMValidationResult(
                selected_target=parsed["selected_target"],
                confidence=float(parsed["confidence"]),
                reasoning=list(parsed.get("reasoning", [])),
                raw_response=raw_response,
            )
            if validate_result(result, candidate_targets):
                return result
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