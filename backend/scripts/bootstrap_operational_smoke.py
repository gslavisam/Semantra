"""Seed repeatable Semantra smoke prerequisites through the public API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FIXTURE = REPO_ROOT / "ui_fixtures" / "source.csv"
TARGET_FIXTURE = REPO_ROOT / "ui_fixtures" / "target.csv"
BENCHMARK_FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "mapping_gold.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed repeatable pilot smoke prerequisites such as catalog diff fixtures, "
            "stewardship drilldown fixtures, and a review-ready draft session."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SEMANTRA_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Semantra API base URL. Defaults to SEMANTRA_API_BASE_URL or http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--admin-token",
        default=os.environ.get("SEMANTRA_ADMIN_API_TOKEN", ""),
        help="Admin token used for protected endpoints. Defaults to SEMANTRA_ADMIN_API_TOKEN.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the bootstrap plan without calling the API.",
    )
    return parser.parse_args()


def build_headers(admin_token: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    return headers


def print_json_block(title: str, payload: object) -> None:
    print(title)
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def get_json(client: httpx.Client, url: str, headers: dict[str, str]) -> Any:
    response = client.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def post_json(client: httpx.Client, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
    response = client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def browser_diff_payload(version: int) -> dict[str, Any]:
    if version == 1:
        mapping_decisions = [
            {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            {"source": "phone", "target": "customer.phone", "status": "accepted"},
            {"source": "email", "target": "customer.email", "status": "accepted"},
        ]
    else:
        mapping_decisions = [
            {"source": "customer_number", "target": "customer.id", "status": "accepted"},
            {"source": "mobile_phone", "target": "customer.phone", "status": "accepted"},
            {"source": "email_address", "target": "customer.email", "status": "accepted"},
        ]
    return {
        "name": "Browser Diff Focus Sync",
        "integration_name": "browser-diff-focus",
        "source_system": "SAP",
        "target_system": "Salesforce",
        "business_domain": "Customer",
        "interface_type": "batch",
        "artifact_type": "standard",
        "canonical_concepts": ["customer.id", "customer.phone", "customer.email"],
        "unmatched_sources": [],
        "mapping_decisions": mapping_decisions,
        "created_by": "operational-smoke-bootstrap",
        "note": f"Bootstrap seed for browser diff focus v{version}",
    }


def stewardship_payload() -> dict[str, Any]:
    return {
        "name": "Stewardship Smoke Sync",
        "integration_name": "stewardship-smoke-sync",
        "source_system": "SAP",
        "target_system": "Salesforce",
        "business_domain": "Customer",
        "interface_type": "batch",
        "artifact_type": "standard",
        "canonical_concepts": ["customer.id"],
        "unmatched_sources": ["LAND1", "REGIO"],
        "mapping_decisions": [
            {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
        ],
        "created_by": "operational-smoke-bootstrap",
        "note": "Bootstrap seed for stewardship smoke drilldown",
    }


def approved_reuse_dbt_payload() -> dict[str, Any]:
    return {
        "name": "Approved Customer Reuse Smoke",
        "integration_name": "approved-customer-reuse-smoke",
        "source_system": "SAP",
        "target_system": "Salesforce",
        "business_domain": "Customer",
        "interface_type": "batch",
        "description": "Approved fixture for repeatable catalog reuse and dbt output smoke.",
        "artifact_type": "standard",
        "canonical_concepts": ["customer.id", "customer.phone", "customer.email"],
        "unmatched_sources": [],
        "mapping_decisions": [
            {"source": "cust_id", "target": "customer_id", "status": "accepted"},
            {"source": "phone", "target": "phone_number", "status": "accepted"},
            {"source": "client_mail", "target": "customer_email", "status": "accepted"},
        ],
        "created_by": "operational-smoke-bootstrap",
        "owner": "governance-team",
        "assignee": "catalog-smoke",
        "review_note": "Approved for repeatable workspace reuse and dbt smoke.",
        "note": "Bootstrap seed for approved catalog reuse and dbt smoke",
    }


def approval_status_payload() -> dict[str, Any]:
    return {
        "status": "approved",
        "changed_by": "operational-smoke-bootstrap",
        "note": "Promoted bootstrap fixture for repeatable workspace reuse and dbt smoke.",
        "owner": "governance-team",
        "assignee": "catalog-smoke",
        "review_note": "Approved for repeatable workspace reuse and dbt smoke.",
    }


def load_benchmark_cases() -> list[dict[str, Any]]:
    return list(json.loads(BENCHMARK_FIXTURE.read_text(encoding="utf-8")))


def draft_session_payload(upload_payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "name": "customer-draft-session",
        "mapping_mode": "standard",
        "active_workspace_section": "Review",
        "source_handle": upload_payload["source"],
        "target_handle": upload_payload["target"],
        "mapping_runtime": {
            "generated_at": timestamp,
            "app_version": "dev",
            "scoring_profile": "balanced",
            "description_priority": False,
            "code_fingerprint": "operational-smoke-bootstrap",
        },
        "mapping_editor_state": {
            "cust_id": {
                "target": "customer_id",
                "status": "accepted",
                "suggested_target": "customer_id",
                "manual_transformation_code": "",
                "suggested_transformation_code": "",
                "llm_transformation_instruction": "",
                "manual_apply_transformation": False,
                "manual": False,
            },
            "phone": {
                "target": "phone_number",
                "status": "needs_review",
                "suggested_target": "phone_number",
                "manual_transformation_code": "value.strip()",
                "suggested_transformation_code": "",
                "llm_transformation_instruction": "trim spaces",
                "manual_apply_transformation": True,
                "manual": True,
            },
            "client_mail": {
                "target": "customer_email",
                "status": "accepted",
                "suggested_target": "customer_email",
                "manual_transformation_code": "value.lower()",
                "suggested_transformation_code": "",
                "llm_transformation_instruction": "normalize email casing",
                "manual_apply_transformation": True,
                "manual": True,
            },
        },
        "mapping_decision_audit": {
            "cust_id": {
                "origin": "manual_mapping",
                "applied_at": timestamp,
                "details": {"reason": "validated during smoke bootstrap"},
            }
        },
    }


def ensure_browser_diff_focus(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    detail_url = f"{base_url}/catalog/integrations/browser-diff-focus"
    existing_versions: list[dict[str, Any]] = []
    detail_response = client.get(detail_url, headers=headers)
    if detail_response.status_code == 200:
        detail = detail_response.json()
        existing_versions = list(detail.get("versions", []))
    elif detail_response.status_code != 404:
        detail_response.raise_for_status()

    present_versions = {int(item.get("version") or 0) for item in existing_versions}
    created: list[dict[str, Any]] = []
    for version in (1, 2):
        if any(existing >= version for existing in present_versions):
            continue
        created.append(post_json(client, f"{base_url}/mapping/sets", browser_diff_payload(version), headers))
        present_versions.add(version)

    refreshed_versions = existing_versions
    if created or not existing_versions:
        refreshed = get_json(client, detail_url, headers)
        refreshed_versions = list(refreshed.get("versions", []))
    refreshed_versions.sort(key=lambda item: int(item.get("version") or 0), reverse=True)
    return {
        "integration_name": "browser-diff-focus",
        "created_mapping_set_ids": [int(item["mapping_set_id"]) for item in created],
        "versions": [
            {"mapping_set_id": int(item["mapping_set_id"]), "version": int(item["version"]), "status": item.get("status")}
            for item in refreshed_versions
        ],
    }


def ensure_stewardship_smoke(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    mapping_sets = get_json(client, f"{base_url}/mapping/sets", headers)
    existing = [
        item
        for item in mapping_sets
        if str(item.get("integration_name") or "").strip().lower() == "stewardship-smoke-sync"
    ]
    if existing:
        existing.sort(key=lambda item: int(item.get("version") or 0), reverse=True)
        record = existing[0]
        return {
            "integration_name": "stewardship-smoke-sync",
            "created": False,
            "mapping_set_id": int(record["mapping_set_id"]),
            "version": int(record["version"]),
        }

    created = post_json(client, f"{base_url}/mapping/sets", stewardship_payload(), headers)
    return {
        "integration_name": "stewardship-smoke-sync",
        "created": True,
        "mapping_set_id": int(created["mapping_set_id"]),
        "version": int(created["version"]),
    }


def ensure_approved_reuse_dbt_smoke(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    detail_url = f"{base_url}/catalog/integrations/approved-customer-reuse-smoke"
    detail_response = client.get(detail_url, headers=headers)
    created = False
    promoted = False

    if detail_response.status_code == 200:
        detail = detail_response.json()
        latest_version = detail["latest_version"]
        latest_approved_version = detail.get("latest_approved_version")
        if latest_approved_version and int(latest_approved_version.get("mapping_set_id") or 0) == int(
            latest_version.get("mapping_set_id") or 0
        ):
            return {
                "integration_name": "approved-customer-reuse-smoke",
                "created": False,
                "promoted": False,
                "mapping_set_id": int(latest_version["mapping_set_id"]),
                "version": int(latest_version["version"]),
                "status": latest_version.get("status"),
            }
        mapping_set_id = int(latest_version["mapping_set_id"])
    elif detail_response.status_code == 404:
        created_record = post_json(client, f"{base_url}/mapping/sets", approved_reuse_dbt_payload(), headers)
        created = True
        mapping_set_id = int(created_record["mapping_set_id"])
    else:
        detail_response.raise_for_status()

    approved_record = post_json(
        client,
        f"{base_url}/mapping/sets/{mapping_set_id}/status",
        approval_status_payload(),
        headers,
    )
    promoted = True
    return {
        "integration_name": "approved-customer-reuse-smoke",
        "created": created,
        "promoted": promoted,
        "mapping_set_id": int(approved_record["mapping_set_id"]),
        "version": int(approved_record["version"]),
        "status": approved_record.get("status"),
    }


def ensure_customer_draft_session(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    draft_sessions = get_json(client, f"{base_url}/mapping/draft-sessions", headers)
    existing = [item for item in draft_sessions if str(item.get("name") or "").strip() == "customer-draft-session"]
    if existing:
        existing.sort(key=lambda item: int(item.get("draft_session_id") or 0), reverse=True)
        record = existing[0]
        return {
            "created": False,
            "draft_session_id": int(record["draft_session_id"]),
            "decision_count": int(record.get("decision_count") or 0),
            "active_workspace_section": record.get("active_workspace_section"),
        }

    with SOURCE_FIXTURE.open("rb") as source_file, TARGET_FIXTURE.open("rb") as target_file:
        upload_response = client.post(
            f"{base_url}/upload",
            headers={key: value for key, value in headers.items() if key != "Accept"},
            data={"mapping_mode": "standard"},
            files={
                "source_file": (SOURCE_FIXTURE.name, source_file.read(), "text/csv"),
                "target_file": (TARGET_FIXTURE.name, target_file.read(), "text/csv"),
            },
        )
    upload_response.raise_for_status()
    upload_payload = upload_response.json()
    created = post_json(client, f"{base_url}/mapping/draft-sessions", draft_session_payload(upload_payload), headers)
    return {
        "created": True,
        "draft_session_id": int(created["draft_session_id"]),
        "decision_count": int(created.get("decision_count") or 0),
        "active_workspace_section": created.get("active_workspace_section"),
    }


def ensure_benchmark_dataset(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    datasets = get_json(client, f"{base_url}/evaluation/datasets", headers)
    existing = [item for item in datasets if str(item.get("name") or "").strip() == "operational-smoke-benchmark"]
    if existing:
        existing.sort(key=lambda item: int(item.get("dataset_id") or 0), reverse=True)
        record = existing[0]
        return {
            "created": False,
            "dataset_id": int(record["dataset_id"]),
            "version": int(record.get("version") or 0),
            "case_count": int(record.get("case_count") or 0),
        }

    created = post_json(
        client,
        f"{base_url}/evaluation/datasets",
        {
            "name": "operational-smoke-benchmark",
            "cases": load_benchmark_cases(),
        },
        headers,
    )
    return {
        "created": True,
        "dataset_id": int(created["dataset_id"]),
        "version": int(created.get("version") or 0),
        "case_count": int(created.get("case_count") or 0),
    }


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.admin_token)
    plan = {
        "browser_diff_focus_versions": [1, 2],
        "stewardship_smoke_sync": True,
        "approved_customer_reuse_smoke": True,
        "customer_draft_session": str(SOURCE_FIXTURE.name),
        "operational_smoke_benchmark": str(BENCHMARK_FIXTURE.name),
    }

    if args.dry_run:
        print_json_block("Bootstrap plan:", plan)
        return 0

    if not SOURCE_FIXTURE.exists() or not TARGET_FIXTURE.exists() or not BENCHMARK_FIXTURE.exists():
        print(
            f"Required fixtures are missing: {SOURCE_FIXTURE}, {TARGET_FIXTURE}, and {BENCHMARK_FIXTURE} must exist.",
            file=sys.stderr,
        )
        return 1

    try:
        with httpx.Client(timeout=30.0) as client:
            summary = {
                "browser_diff_focus": ensure_browser_diff_focus(client, base_url, headers),
                "stewardship_smoke_sync": ensure_stewardship_smoke(client, base_url, headers),
                "approved_customer_reuse_smoke": ensure_approved_reuse_dbt_smoke(client, base_url, headers),
                "customer_draft_session": ensure_customer_draft_session(client, base_url, headers),
                "operational_smoke_benchmark": ensure_benchmark_dataset(client, base_url, headers),
            }
    except httpx.HTTPStatusError as error:
        print(f"HTTP error: {error.response.status_code} {error.response.text}", file=sys.stderr)
        return 1
    except httpx.HTTPError as error:
        print(f"Request error: {error}", file=sys.stderr)
        return 1

    print_json_block("Operational smoke bootstrap summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())