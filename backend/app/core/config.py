from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DOTENV_PATH = BASE_DIR / ".env"


@dataclass(slots=True)
class Settings:
    app_name: str = "Semantra API"
    app_version: str = "0.1.0"
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    max_upload_preview_rows: int = 10
    max_profile_samples: int = 5
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.65
    top_k_candidates: int = 3
    embedding_provider: str = "none"
    embedding_dimensions: int = 24
    llm_provider: str = "none"
    llm_model: str = "mock-validator"
    llm_timeout_seconds: float = 5.0
    llm_max_retries: int = 2
    llm_min_confidence: float = 0.5
    llm_gate_min_score: float = 0.4
    llm_gate_max_score: float = 0.75
    admin_api_token: str = ""
    sqlite_path: str = str(Path(__file__).resolve().parents[2] / "semantra.sqlite3")
    openai_base_url: str = "https://api.openai.com/v1/responses"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/api/generate"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1/responses"


def load_settings(dotenv_path: str | Path | None = None) -> Settings:
    settings = Settings()
    dotenv_values = parse_dotenv_file(Path(dotenv_path) if dotenv_path else DEFAULT_DOTENV_PATH)
    type_hints = get_type_hints(Settings)

    for field_name, field_info in settings.__dataclass_fields__.items():
        env_key = f"SEMANTRA_{field_name.upper()}"
        raw_value = os.environ.get(env_key, dotenv_values.get(env_key))
        if raw_value is None:
            continue
        setattr(settings, field_name, coerce_value(raw_value, type_hints.get(field_name, field_info.type)))

    return settings


def reload_settings(dotenv_path: str | Path | None = None) -> Settings:
    loaded = load_settings(dotenv_path)
    for field_name in settings.__dataclass_fields__:
        setattr(settings, field_name, getattr(loaded, field_name))
    return settings


def settings_snapshot() -> dict[str, Any]:
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "cors_origins": list(settings.cors_origins),
        "sqlite_path": settings.sqlite_path,
        "llm_gate_min_score": settings.llm_gate_min_score,
        "llm_gate_max_score": settings.llm_gate_max_score,
        "admin_api_token_configured": bool(settings.admin_api_token.strip()),
    }


def parse_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def coerce_value(raw_value: str, annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is list:
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    if annotation is int:
        return int(raw_value)
    if annotation is float:
        return float(raw_value)
    if annotation is bool:
        return raw_value.lower() in {"1", "true", "yes", "on"}
    if get_args(annotation):
        # Handle list[str] style annotations on Python 3.14.
        nested_origin = get_origin(annotation)
        if nested_origin is list:
            return [item.strip() for item in raw_value.split(",") if item.strip()]
    return raw_value


settings = load_settings()