"""Run the repeatable Semantra browser E2E smoke for Workspace, Catalog, and Benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the operational browser E2E smoke across Workspace, Catalog, Governance, and Benchmarks "
            "after bootstrapping the repeatable smoke fixtures."
        )
    )
    parser.add_argument(
        "--streamlit-url",
        default=os.environ.get("SEMANTRA_STREAMLIT_URL", "http://127.0.0.1:8501"),
        help="Semantra Streamlit URL. Defaults to SEMANTRA_STREAMLIT_URL or http://127.0.0.1:8501.",
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
        "--skip-bootstrap",
        action="store_true",
        help="Skip the smoke bootstrap and assume the required fixtures already exist.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch the browser in headed mode instead of headless mode.",
    )
    parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=0,
        help="Optional Playwright slow motion delay in milliseconds for debugging.",
    )
    parser.add_argument(
        "--capture-demo-assets",
        action="store_true",
        help="Capture numbered screenshot assets for the manual live demo flow.",
    )
    parser.add_argument(
        "--record-demo-video",
        action="store_true",
        help="Record the full browser demo flow as a Playwright video.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="",
        help=(
            "Directory where demo screenshots, video, and summary should be saved. "
            "If omitted, a timestamped folder under docs/pilot/demo_assets is used when capture or record is enabled."
        ),
    )
    return parser.parse_args()


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


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class BrowserSmokeRunner:
    def __init__(self, page: Any, args: argparse.Namespace, artifacts_dir: Path | None = None) -> None:
        self.page = page
        self.args = args
        self.artifacts_dir = artifacts_dir
        self.screenshots_dir = (artifacts_dir / "screenshots") if artifacts_dir else None

    def run(self) -> dict[str, Any]:
        self.page.set_default_timeout(15_000)
        self.page.goto(self.args.streamlit_url, wait_until="domcontentloaded")
        self.wait_for_text("Semantra - Guided Data Mapping", timeout_ms=45_000)
        self.configure_connection()
        approved_reuse = self.run_catalog_approved_reuse_flow()
        workspace = self.run_workspace_draft_resume()
        catalog = {
            "approved_reuse": approved_reuse,
            "diff_review_handoff": self.run_catalog_diff_review_flow(),
            "stewardship_handoff": self.run_catalog_stewardship_flow(),
        }
        benchmarks = self.run_benchmark_flow()
        return {
            "workspace": workspace,
            "catalog": catalog,
            "benchmarks": benchmarks,
        }

    def capture_event(self, event_number: int, event_name: str) -> list[str]:
        if not self.screenshots_dir:
            return []

        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-z0-9]+", "_", event_name.strip().lower()).strip("_") or f"event_{event_number:02d}"

        current_scroll = int(self.page.evaluate("() => Math.round(window.scrollY || 0)"))
        viewport_height = int((self.page.viewport_size or {"height": 1600}).get("height") or 1600)
        document_height = int(
            self.page.evaluate(
                "() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight, document.documentElement.offsetHeight)"
            )
        )

        target_positions = [current_scroll]
        lower_position = min(current_scroll + int(viewport_height * 0.82), max(document_height - viewport_height, 0))
        if lower_position > current_scroll + 200:
            target_positions.append(lower_position)

        screenshot_paths: list[str] = []
        for part_number, scroll_position in enumerate(dict.fromkeys(target_positions), start=1):
            self.page.evaluate("(y) => window.scrollTo(0, y)", scroll_position)
            self.page.wait_for_timeout(350)
            screenshot_path = self.screenshots_dir / f"{event_number:02d}_{safe_name}_{part_number:02d}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=False)
            screenshot_paths.append(str(screenshot_path))

        self.page.evaluate("(y) => window.scrollTo(0, y)", current_scroll)
        self.page.wait_for_timeout(150)
        return screenshot_paths

    def body_text(self) -> str:
        return _normalized_text(self.page.locator("body").inner_text())

    def wait_for_text(self, text: str, *, timeout_ms: int = 15_000) -> str:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            body = self.body_text()
            if text in body:
                return body
            self.page.wait_for_timeout(250)
        raise RuntimeError(f"Timed out waiting for text: {text}")

    def wait_for_all_texts(self, texts: list[str], *, timeout_ms: int = 15_000) -> str:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            body = self.body_text()
            if all(text in body for text in texts):
                return body
            self.page.wait_for_timeout(250)
        raise RuntimeError("Timed out waiting for expected page texts: " + ", ".join(texts))

    def wait_for_workspace_section(self, label: str, *, timeout_ms: int = 15_000) -> None:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        radio = self.page.get_by_role("radio", name=label)
        while time.monotonic() < deadline:
            try:
                if radio.is_checked():
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(250)
        raise RuntimeError(f"Timed out waiting for Workspace section '{label}' to become active.")

    def click_nav_label(self, group_name: str, label: str) -> None:
        group = self.page.get_by_role("radiogroup", name=group_name)
        group.locator("label").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.IGNORECASE)).click()
        self.page.wait_for_timeout(500)

    def click_button(self, name: str, *, timeout_ms: int = 15_000) -> None:
        button = self.page.get_by_role("button", name=name)
        button.scroll_into_view_if_needed(timeout=timeout_ms)
        button.click(timeout=timeout_ms)

    def fill_textbox(self, name: str, value: str, *, press_enter: bool = False) -> None:
        textbox = self.page.get_by_role("textbox", name=name)
        textbox.fill(value)
        if press_enter:
            textbox.press("Enter")
            self.page.wait_for_timeout(800)

    def select_combobox_option(self, label: str, option_text: str) -> str:
        combobox = self.page.get_by_role("combobox", name=re.compile(re.escape(label), re.IGNORECASE))
        current_text = _normalized_text(combobox.text_content())
        if _normalized_text(option_text) in current_text:
            return current_text
        combobox.click()
        option = self.page.get_by_role("option", name=re.compile(re.escape(option_text), re.IGNORECASE))
        option.click()
        self.page.wait_for_timeout(500)
        return _normalized_text(combobox.text_content())

    def configure_connection(self) -> None:
        self.fill_textbox("API Base URL", self.args.base_url)
        if self.args.admin_token:
            self.fill_textbox("Admin Token", self.args.admin_token, press_enter=True)
            self.wait_for_text("Semantra - Guided Data Mapping", timeout_ms=30_000)

    def run_workspace_draft_resume(self) -> dict[str, Any]:
        self.click_nav_label("Navigation", "Workspace")
        self.click_nav_label("Workspace section", "Decisions")
        self.page.get_by_text("Mapping Set Versions", exact=True).click()
        self.page.get_by_role("button", name="Load draft sessions").wait_for(state="visible", timeout=15_000)
        self.click_button("Load draft sessions")
        self.wait_for_text("Saved draft sessions", timeout_ms=30_000)
        selected_label = self.select_combobox_option("Select draft session", "customer-draft-session") or "customer-draft-session"
        self.click_button("Resume draft session")
        self.wait_for_workspace_section("Review", timeout_ms=30_000)
        restored_body = self.body_text()
        self.click_nav_label("Workspace section", "Output")
        output_body = self.wait_for_all_texts(
            [
                "Artifact Generation",
                "Transformation Design · Ready for next output step",
            ],
            timeout_ms=30_000,
        )
        self.page.get_by_text(re.compile(r"^Transformation Design .*Ready for next output step$", re.IGNORECASE)).click()
        target_grain = self.page.get_by_role("textbox", name="Target grain").input_value().strip()
        defaults = self.page.get_by_role("textbox", name="Defaults / fallback behavior").input_value().strip()
        return {
            "draft_session_label": selected_label,
            "review_focus_restored": "Review Queue Plan" in restored_body,
            "source_filter_visible": "Filter by source" in restored_body,
            "output_transformation_ready": "Transformation Design · Ready for next output step" in output_body,
            "target_grain_restored": target_grain,
            "defaults_restored": defaults,
            "screenshots": self.capture_event(2, "workspace_resume"),
        }

    def search_and_open_catalog_detail(self, integration_name: str) -> str:
        self.click_nav_label("Navigation", "Catalog")
        self.wait_for_text("Catalog")
        self.click_button("Reset catalog state")
        self.wait_for_text("Search and Filters", timeout_ms=30_000)
        self.fill_textbox("Search", integration_name)
        self.click_button("Run catalog query")
        self.wait_for_text("Integration detail", timeout_ms=30_000)
        selected_label = self.select_combobox_option("Integration detail", integration_name)
        self.click_button("Load detail")
        self.wait_for_text("Integration Detail", timeout_ms=30_000)
        return selected_label or integration_name

    def run_catalog_diff_review_flow(self) -> dict[str, Any]:
        selected_label = self.search_and_open_catalog_detail("browser-diff-focus")
        self.click_button("Open selected version")
        self.wait_for_text("Mapping Set Drilldown", timeout_ms=30_000)
        self.click_button("Load version diff")
        diff_body = self.wait_for_text("Selected mapping set diff: v2 vs v1", timeout_ms=30_000)
        self.click_button("Open current diff review focus")
        handoff_body = self.wait_for_all_texts(
            [
                "Catalog handoff:",
                "source_scope=",
                "Filter by source",
                "Review Queue Plan",
            ],
            timeout_ms=30_000,
        )
        return {
            "integration_label": selected_label,
            "diff_loaded": "Selected mapping set diff: v2 vs v1" in diff_body,
            "workspace_review_handoff": "source_scope=" in handoff_body,
            "screenshots": self.capture_event(3, "catalog_diff_handoff"),
        }

    def run_catalog_stewardship_flow(self) -> dict[str, Any]:
        selected_label = self.search_and_open_catalog_detail("stewardship-smoke-sync")
        self.click_button("Open selected version")
        self.wait_for_text("Mapping Set Drilldown", timeout_ms=30_000)
        self.click_button("Open Stewardship")
        governance_body = self.wait_for_all_texts(
            [
                "Governance",
                "Governance section",
                "Stewardship",
                "Catalog handoff:",
            ],
            timeout_ms=30_000,
        )
        return {
            "integration_label": selected_label,
            "governance_handoff": "Stewardship" in governance_body,
            "screenshots": self.capture_event(4, "catalog_stewardship_handoff"),
        }

    def run_catalog_approved_reuse_flow(self) -> dict[str, Any]:
        selected_label = self.search_and_open_catalog_detail("approved-customer-reuse-smoke")
        detail_body = self.wait_for_text("Latest approved version:", timeout_ms=30_000)
        self.click_button("Reuse in Workspace")
        reuse_body = self.wait_for_all_texts(
            [
                "Reused mapping set",
                "Workspace",
            ],
            timeout_ms=30_000,
        )
        return {
            "integration_label": selected_label,
            "latest_approved_visible": "Latest approved version:" in detail_body,
            "reuse_applied": "Reused mapping set" in reuse_body,
            "screenshots": self.capture_event(1, "catalog_reuse"),
        }

    def run_benchmark_flow(self) -> dict[str, Any]:
        self.click_nav_label("Navigation", "Benchmarks")
        self.wait_for_text("Saved Benchmark Datasets")
        self.click_button("Load saved benchmark datasets")
        self.wait_for_text("Loaded saved benchmark datasets.", timeout_ms=30_000)
        selected_dataset = (
            self.select_combobox_option("Saved dataset", "operational-smoke-benchmark")
            or "operational-smoke-benchmark"
        )
        self.click_button("Compare scoring profiles", timeout_ms=30_000)
        comparison_body = self.wait_for_all_texts(
            [
                "Scoring Profile Comparison",
                "Recommended default profile:",
            ],
            timeout_ms=45_000,
        )
        self.page.get_by_text("Benchmark Explanation", exact=True).click()
        explanation_button = self.page.get_by_role("button", name="Generate benchmark explanation")
        explanation_button.wait_for(state="visible", timeout=15_000)
        deadline = time.monotonic() + 30.0
        while explanation_button.is_disabled() and time.monotonic() < deadline:
            self.page.wait_for_timeout(250)
        if explanation_button.is_disabled():
            raise RuntimeError("Benchmark explanation stayed disabled after scoring-profile comparison.")
        explanation_button.click()
        explanation_body = self.wait_for_all_texts(
            [
                "Generated benchmark explanation for operational-smoke-benchmark.",
                "Key findings",
                "Risks",
                "Next actions",
            ],
            timeout_ms=90_000,
        )
        metadata_signal = "Fallback" if "Fallback" in explanation_body else "LLM" if "LLM" in explanation_body else ""
        return {
            "dataset_label": selected_dataset,
            "profile_comparison_visible": "Scoring Profile Comparison" in comparison_body,
            "recommended_profile_visible": "Recommended default profile:" in comparison_body,
            "benchmark_explanation_generated": "Generated benchmark explanation for operational-smoke-benchmark." in explanation_body,
            "explanation_metadata": metadata_signal,
            "screenshots": self.capture_event(5, "benchmarks_explanation"),
        }


def resolve_artifacts_dir(args: argparse.Namespace) -> Path | None:
    if not (args.capture_demo_assets or args.record_demo_video or args.artifacts_dir):
        return None

    if args.artifacts_dir:
        artifacts_dir = Path(args.artifacts_dir)
    else:
        timestamp = datetime.now().strftime("live_demo_%Y%m%d_%H%M%S")
        artifacts_dir = REPO_ROOT / "docs" / "pilot" / "demo_assets" / timestamp

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def run_browser_smoke(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is not installed in the selected Python environment. "
            "Install dependencies first, then run `python -m playwright install chromium`."
        ) from error

    try:
        with sync_playwright() as playwright:
            artifacts_dir = resolve_artifacts_dir(args)
            browser = playwright.chromium.launch(headless=not args.headed, slow_mo=max(args.slow_mo_ms, 0))
            context_kwargs: dict[str, Any] = {"viewport": {"width": 1440, "height": 1600}}
            if args.record_demo_video and artifacts_dir:
                video_tmp_dir = artifacts_dir / "video_tmp"
                video_tmp_dir.mkdir(parents=True, exist_ok=True)
                context_kwargs["record_video_dir"] = str(video_tmp_dir)
                context_kwargs["record_video_size"] = {"width": 1440, "height": 1600}

            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            video = page.video
            try:
                summary = BrowserSmokeRunner(page, args, artifacts_dir=artifacts_dir if args.capture_demo_assets else None).run()
            finally:
                context.close()
                browser.close()

            if artifacts_dir:
                summary["artifacts_dir"] = str(artifacts_dir)

            if args.record_demo_video and artifacts_dir and video is not None:
                recorded_video_path = Path(video.path())
                final_video_path = artifacts_dir / "manual_live_demo_recording.webm"
                if recorded_video_path.exists():
                    final_video_path.parent.mkdir(parents=True, exist_ok=True)
                    if final_video_path.exists():
                        final_video_path.unlink()
                    shutil.move(str(recorded_video_path), str(final_video_path))
                    summary["demo_video"] = str(final_video_path)
                video_tmp_dir = artifacts_dir / "video_tmp"
                if video_tmp_dir.exists():
                    shutil.rmtree(video_tmp_dir, ignore_errors=True)

            if artifacts_dir:
                summary_path = artifacts_dir / "operational_browser_e2e_summary.json"
                summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
                summary["summary_file"] = str(summary_path)

            return summary
    except PlaywrightError as error:
        message = str(error)
        if "Executable doesn't exist" in message or "browserType.launch" in message:
            raise RuntimeError(
                "Playwright browser binaries are missing. Run `python -m playwright install chromium` first."
            ) from error
        raise RuntimeError(f"Browser smoke failed: {message}") from error


def main() -> int:
    args = parse_args()
    summary: dict[str, Any] = {}
    try:
        if not args.skip_bootstrap:
            summary["bootstrap"] = run_bootstrap(args)
        summary["browser_e2e"] = run_browser_smoke(args)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print_json_block("Operational browser E2E summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())