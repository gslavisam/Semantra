"""Run the repeatable Semantra operational hardening baseline for Workspace, Catalog, and Benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTEST_TARGETS = [
    "tests/test_streamlit_workspace_views.py",
    "tests/test_streamlit_workspace_review_views.py",
    "tests/test_streamlit_catalog_views.py",
    "tests/test_streamlit_benchmark_views.py",
    "tests/test_streamlit_admin_views.py",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the repeatable operational hardening baseline across Workspace, Catalog, and Benchmarks: "
            "bootstrap smoke fixtures, focused pytest subset, and live API smoke checks."
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
        "--python-executable",
        default=sys.executable,
        help="Python executable used for subprocess steps. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the focused pytest subset and run only bootstrap plus live API checks.",
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


def extract_json_block(output: str) -> dict[str, Any]:
    lines = [line for line in output.splitlines() if line.strip()]
    start_index = next((index for index, line in enumerate(lines) if line.lstrip().startswith("{")), None)
    if start_index is None:
        raise ValueError("Expected JSON payload in subprocess output.")
    return json.loads("\n".join(lines[start_index:]))


def run_command(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)


def run_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        args.python_executable,
        str(REPO_ROOT / "backend" / "scripts" / "bootstrap_operational_smoke.py"),
        "--base-url",
        args.base_url,
    ]
    if args.admin_token:
        command.extend(["--admin-token", args.admin_token])
    result = run_command(command, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(
            "Bootstrap failed: " + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        )
    payload = extract_json_block(result.stdout)
    payload["_command"] = " ".join(command)
    return payload


def run_focused_pytest(args: argparse.Namespace) -> dict[str, Any]:
    command = [args.python_executable, "-m", "pytest", *PYTEST_TARGETS, "-q"]
    result = run_command(command, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(
            "Focused pytest subset failed: " + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else "pytest completed"
    return {
        "summary": summary,
        "command": " ".join(command),
    }


def get_json(client: httpx.Client, url: str, headers: dict[str, str]) -> Any:
    response = client.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def post_json(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    response = client.post(url, headers=headers, params=params, json=payload)
    response.raise_for_status()
    return response.json()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run_live_api_smoke(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.admin_token)
    with httpx.Client(timeout=30.0) as client:
        runtime_config = get_json(client, f"{base_url}/observability/config", headers)
        draft_sessions = get_json(client, f"{base_url}/mapping/draft-sessions", headers)
        browser_diff_focus = get_json(client, f"{base_url}/catalog/integrations/browser-diff-focus", headers)
        approved_reuse = get_json(client, f"{base_url}/catalog/integrations/approved-customer-reuse-smoke", headers)
        stewardship = get_json(client, f"{base_url}/catalog/integrations/stewardship-smoke-sync", headers)
        benchmark_datasets = get_json(client, f"{base_url}/evaluation/datasets", headers)

        customer_draft = next(
            (item for item in draft_sessions if str(item.get("name") or "").strip() == "customer-draft-session"),
            None,
        )
        require(customer_draft is not None, "Expected customer-draft-session in /mapping/draft-sessions.")
        require(customer_draft.get("active_workspace_section") == "Review", "Expected Review draft-session fixture.")

        require(len(browser_diff_focus.get("versions", [])) >= 2, "Expected browser-diff-focus to have at least two versions.")

        latest_approved = approved_reuse.get("latest_approved_version") or {}
        require(latest_approved.get("status") == "approved", "Expected approved-customer-reuse-smoke latest approved version.")

        unmatched_sources = stewardship.get("unmatched_sources") or []
        require("LAND1" in unmatched_sources, "Expected stewardship-smoke-sync unmatched_sources to include LAND1.")

        benchmark_dataset = next(
            (item for item in benchmark_datasets if str(item.get("name") or "").strip() == "operational-smoke-benchmark"),
            None,
        )
        require(benchmark_dataset is not None, "Expected operational-smoke-benchmark dataset.")
        dataset_id = int(benchmark_dataset["dataset_id"])

        benchmark_run = post_json(
            client,
            f"{base_url}/evaluation/datasets/{dataset_id}/run",
            headers,
            params={"with_configured_llm": "false"},
        )
        profile_comparison = post_json(
            client,
            f"{base_url}/evaluation/datasets/{dataset_id}/compare-profiles",
            headers,
            params={"profiles": "balanced,canonical_first", "with_configured_llm": "false"},
        )
        evaluation_runs = get_json(client, f"{base_url}/evaluation/runs", headers)

        require(int(benchmark_run.get("total_cases") or 0) >= 1, "Expected benchmark run to include cases.")
        require(len(profile_comparison.get("profiles", [])) >= 2, "Expected at least two compared scoring profiles.")
        require(
            any(int(item.get("dataset_id") or 0) == dataset_id for item in evaluation_runs),
            "Expected evaluation run history to include the operational benchmark dataset.",
        )

    return {
        "workspace": {
            "runtime": {
                "app_version": runtime_config.get("app_version"),
                "backend_build": runtime_config.get("backend_build"),
                "scoring_profile": runtime_config.get("scoring_profile"),
                "llm_reachable": runtime_config.get("llm_reachable"),
            },
            "draft_session": {
                "draft_session_id": int(customer_draft["draft_session_id"]),
                "active_workspace_section": customer_draft.get("active_workspace_section"),
                "decision_count": int(customer_draft.get("decision_count") or 0),
            },
        },
        "catalog": {
            "browser_diff_focus_versions": len(browser_diff_focus.get("versions", [])),
            "approved_reuse_mapping_set_id": int(latest_approved["mapping_set_id"]),
            "approved_reuse_version": int(latest_approved["version"]),
            "stewardship_unmatched_sources": unmatched_sources,
        },
        "benchmarks": {
            "dataset_id": dataset_id,
            "dataset_version": int(benchmark_dataset.get("version") or 0),
            "case_count": int(benchmark_dataset.get("case_count") or 0),
            "benchmark_run_accuracy": benchmark_run.get("accuracy"),
            "compared_profiles": [item.get("profile") for item in profile_comparison.get("profiles", [])],
            "recommended_profile": profile_comparison.get("recommended_profile"),
            "evaluation_run_count": len(evaluation_runs),
        },
    }


def main() -> int:
    args = parse_args()
    summary: dict[str, Any] = {}
    try:
        summary["bootstrap"] = run_bootstrap(args)
        if not args.skip_pytest:
            summary["pytest"] = run_focused_pytest(args)
        summary["live_api_smoke"] = run_live_api_smoke(args)
    except (RuntimeError, ValueError, httpx.HTTPError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print_json_block("Operational hardening summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())