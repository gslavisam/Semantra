"""Centralized dbt codegen profile and helpers shared across generation and refinement."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class DbtCodegenProfile:
    """Runtime-configurable conventions for starter dbt model generation."""

    materialization: str = "view"
    source_mode: str = "ref"
    source_name: str = "raw"
    source_table_name: str = "source_model"
    ref_name: str = "source_model"
    quote_identifiers: bool = True
    source_cte_name: str = "source_data"


def current_dbt_codegen_profile() -> DbtCodegenProfile:
    """Return the currently active dbt codegen profile from runtime settings."""

    source_mode = str(settings.dbt_source_mode or "ref").strip().lower() or "ref"
    if source_mode not in {"ref", "source"}:
        source_mode = "ref"

    return DbtCodegenProfile(
        materialization=str(settings.dbt_materialization or "view").strip().lower() or "view",
        source_mode=source_mode,
        source_name=str(settings.dbt_source_name or "raw").strip() or "raw",
        source_table_name=str(settings.dbt_source_table_name or "source_model").strip() or "source_model",
        ref_name=str(settings.dbt_ref_name or "source_model").strip() or "source_model",
        quote_identifiers=bool(settings.dbt_quote_identifiers),
        source_cte_name=str(settings.dbt_source_cte_name or "source_data").strip() or "source_data",
    )


def dbt_profile_snapshot() -> dict[str, object]:
    """Return the active dbt profile as a plain dict for prompts and runtime snapshots."""

    profile = current_dbt_codegen_profile()
    snapshot = asdict(profile)
    snapshot["source_reference"] = dbt_source_relation(profile)
    return snapshot


def dbt_identifier(identifier: str, profile: DbtCodegenProfile | None = None) -> str:
    """Render one dbt column identifier according to the active quoting convention."""

    active_profile = profile or current_dbt_codegen_profile()
    normalized = str(identifier or "").strip()
    if active_profile.quote_identifiers:
        return f"{{{{ adapter.quote({json.dumps(normalized, ensure_ascii=True)}) }}}}"
    return normalized


def dbt_source_relation(profile: DbtCodegenProfile | None = None) -> str:
    """Render the active dbt source relation according to the selected convention."""

    active_profile = profile or current_dbt_codegen_profile()
    if active_profile.source_mode == "source":
        return (
            f"{{{{ source({_jinja_string(active_profile.source_name)}, "
            f"{_jinja_string(active_profile.source_table_name)}) }}}}"
        )
    return f"{{{{ ref({_jinja_string(active_profile.ref_name)}) }}}}"


def _jinja_string(value: str) -> str:
    escaped = str(value or "").replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"