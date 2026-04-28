from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a saved Semantra benchmark dataset and optionally inspect recent evaluation runs."
    )
    parser.add_argument("--dataset-id", type=int, required=True, help="Saved benchmark dataset id.")
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
        "--with-llm",
        action="store_true",
        help="Run the saved benchmark with the configured LLM validator enabled.",
    )
    parser.add_argument(
        "--show-runs",
        type=int,
        default=5,
        help="How many recent evaluation runs to print after execution. Use 0 to skip.",
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


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.admin_token)
    params = {"with_configured_llm": str(args.with_llm).lower()}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/evaluation/datasets/{args.dataset_id}/run",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            metrics = response.json()
            print_json_block("Benchmark run result:", metrics)

            if args.show_runs > 0:
                runs_response = client.get(f"{base_url}/evaluation/runs", headers=headers)
                runs_response.raise_for_status()
                recent_runs = runs_response.json()[: args.show_runs]
                print_json_block("Recent evaluation runs:", recent_runs)
    except httpx.HTTPStatusError as error:
        print(f"HTTP error: {error.response.status_code} {error.response.text}", file=sys.stderr)
        return 1
    except httpx.HTTPError as error:
        print(f"Request error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())