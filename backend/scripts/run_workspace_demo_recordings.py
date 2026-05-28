"""Record workspace-focused Semantra demo scenarios as videos and screenshots."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from run_operational_browser_e2e import print_json_block, run_bootstrap


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "ui_fixtures"


@dataclass(frozen=True)
class ScenarioDefinition:
    order: int
    key: str
    title: str
    objective: str


SCENARIOS: list[ScenarioDefinition] = [
    ScenarioDefinition(
        order=1,
        key="standard_two_file_mapping",
        title="Standard Two-File Mapping",
        objective="Upload a source and target pair, profile them, generate mapping, and land in Workspace review.",
    ),
    ScenarioDefinition(
        order=2,
        key="canonical_source_mapping",
        title="Canonical Source Mapping",
        objective="Run a canonical-only source mapping and show canonical review plus canonical-mode code generation.",
    ),
    ScenarioDefinition(
        order=3,
        key="llm_decision_flow",
        title="LLM Decision Flow",
        objective="Generate bounded LLM decision proposals from review and show the downstream Decisions workflow.",
    ),
    ScenarioDefinition(
        order=4,
        key="workspace_output_generation",
        title="Workspace Output Generation",
        objective="Show Pandas and dbt generation plus LLM refinement from an accepted Workspace mapping state.",
    ),
]

SCENARIO_BY_KEY = {scenario.key: scenario for scenario in SCENARIOS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record workspace-focused Semantra demo scenarios as individual videos and screenshots "
            "for presentation use."
        )
    )
    parser.add_argument(
        "--streamlit-url",
        default="http://127.0.0.1:8501",
        help="Semantra Streamlit URL. Defaults to http://127.0.0.1:8501.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Semantra API base URL. Defaults to http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--admin-token",
        default="",
        help="Admin token used for protected endpoints.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used for subprocess steps. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip operational smoke bootstrap before recording scenarios.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch Chromium in headed mode while recording.",
    )
    parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=0,
        help="Optional Playwright slow motion delay in milliseconds for debugging.",
    )
    parser.add_argument(
        "--record-video",
        action="store_true",
        help="Record each scenario as a video file.",
    )
    parser.add_argument(
        "--capture-screenshots",
        action="store_true",
        help="Capture one or more screenshots per scenario.",
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(scenario.key for scenario in SCENARIOS),
        help=(
            "Comma-separated scenario keys to run. "
            f"Available: {', '.join(scenario.key for scenario in SCENARIOS)}."
        ),
    )
    parser.add_argument(
        "--artifacts-dir",
        default="",
        help="Directory where scenario recordings should be saved.",
    )
    return parser.parse_args()


def normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_scenarios(raw_value: str) -> list[ScenarioDefinition]:
    requested_keys = [item.strip() for item in str(raw_value or "").split(",") if item.strip()]
    if not requested_keys:
        raise ValueError("At least one workspace demo scenario must be selected.")

    unknown = [key for key in requested_keys if key not in SCENARIO_BY_KEY]
    if unknown:
        raise ValueError(
            "Unknown workspace demo scenario(s): "
            + ", ".join(unknown)
            + ". Available: "
            + ", ".join(scenario.key for scenario in SCENARIOS)
        )

    ordered: list[ScenarioDefinition] = []
    seen: set[str] = set()
    for key in requested_keys:
        if key not in seen:
            seen.add(key)
            ordered.append(SCENARIO_BY_KEY[key])
    return ordered


def resolve_artifacts_dir(args: argparse.Namespace) -> Path:
    if args.artifacts_dir:
        artifacts_dir = Path(args.artifacts_dir)
    else:
        timestamp = datetime.now().strftime("workspace_recordings_%Y%m%d_%H%M%S")
        artifacts_dir = REPO_ROOT / "docs" / "pilot" / "demo_assets" / timestamp
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


class WorkspaceRecordingRunner:
    def __init__(self, page: Any, args: argparse.Namespace, scenario: ScenarioDefinition, scenario_dir: Path) -> None:
        self.page = page
        self.args = args
        self.scenario = scenario
        self.scenario_dir = scenario_dir
        self.screenshots_dir = scenario_dir / "screenshots"

    def run(self) -> dict[str, Any]:
        self.page.set_default_timeout(20_000)
        self.page.goto(self.args.streamlit_url, wait_until="domcontentloaded")
        self.wait_for_text("Semantra - Data Mapping Review and Benchmarking", timeout_ms=45_000)
        self.configure_connection()
        if self.scenario.key == "standard_two_file_mapping":
            return self.run_standard_two_file_mapping()
        if self.scenario.key == "canonical_source_mapping":
            return self.run_canonical_source_mapping()
        if self.scenario.key == "llm_decision_flow":
            return self.run_llm_decision_flow()
        if self.scenario.key == "workspace_output_generation":
            return self.run_workspace_output_generation()
        raise RuntimeError(f"Unsupported workspace demo scenario: {self.scenario.key}")

    def body_text(self) -> str:
        return normalized_text(self.page.locator("body").inner_text())

    def wait_for_text(self, text: str, *, timeout_ms: int = 15_000) -> str:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            body = self.body_text()
            if text in body:
                return body
            self.page.wait_for_timeout(250)
        raise RuntimeError(f"Timed out waiting for text: {text}")

    def wait_for_any_text(self, texts: list[str], *, timeout_ms: int = 15_000) -> str:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            body = self.body_text()
            if any(text in body for text in texts):
                return body
            self.page.wait_for_timeout(250)
        raise RuntimeError("Timed out waiting for any expected text: " + ", ".join(texts))

    def click_nav_label(self, group_name: str, label: str) -> None:
        group = self.page.get_by_role("radiogroup", name=group_name)
        group.locator("label").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.IGNORECASE)).click()
        self.page.wait_for_timeout(400)

    def click_button(self, name: str, *, timeout_ms: int = 20_000) -> None:
        button = self.page.get_by_role("button", name=name)
        button.scroll_into_view_if_needed(timeout=timeout_ms)
        button.click(timeout=timeout_ms)

    def fill_textbox(self, name: str, value: str, *, press_enter: bool = False) -> None:
        textbox = self.page.get_by_role("textbox", name=name)
        textbox.fill(value)
        if press_enter:
            textbox.press("Enter")
            self.page.wait_for_timeout(800)

    def set_checkbox(self, name: str, checked: bool) -> None:
        checkbox = self.page.get_by_role("checkbox", name=re.compile(re.escape(name), re.IGNORECASE))
        is_checked = checkbox.is_checked()
        if is_checked != checked:
            toggle_label = self.page.get_by_text(name, exact=True)
            toggle_label.scroll_into_view_if_needed()
            toggle_label.click()
            self.page.wait_for_timeout(250)
            if checkbox.is_checked() != checked:
                toggle_label.click()
            self.page.wait_for_timeout(250)

    def set_file_input(self, index: int, file_path: Path) -> None:
        self.page.locator('input[type="file"]').nth(index).set_input_files(str(file_path))
        self.page.wait_for_timeout(500)

    def configure_connection(self) -> None:
        self.fill_textbox("API Base URL", self.args.base_url)
        if self.args.admin_token:
            self.fill_textbox("Admin Token", self.args.admin_token, press_enter=True)
            self.wait_for_text("Semantra - Data Mapping Review and Benchmarking", timeout_ms=30_000)

    def open_workspace_setup(self) -> None:
        self.click_nav_label("Navigation", "Workspace")
        self.click_nav_label("Workspace section", "Setup")
        self.wait_for_text("1. Upload")

    def upload_standard_pair(self, *, use_llm: bool = False) -> dict[str, str]:
        self.open_workspace_setup()
        source_file = FIXTURE_ROOT / "showcase_customer_mapping" / "showcase_customer_source.csv"
        target_file = FIXTURE_ROOT / "showcase_customer_mapping" / "showcase_customer_target.json"
        self.set_file_input(0, source_file)
        self.set_file_input(1, target_file)
        self.click_button("Upload and profile", timeout_ms=30_000)
        self.wait_for_any_text(["3. Review Mapping", "Generate mapping"], timeout_ms=60_000)
        self.set_checkbox("Use LLM validation", use_llm)
        self.click_button("Generate mapping", timeout_ms=30_000)
        self.wait_for_text("Mapping is ready", timeout_ms=180_000)
        return {"source": str(source_file), "target": str(target_file)}

    def upload_canonical_source(self, *, use_llm: bool = False) -> dict[str, str]:
        self.open_workspace_setup()
        self.click_nav_label("Mapping mode", "Canonical")
        source_file = FIXTURE_ROOT / "showcase_customer_mapping" / "showcase_customer_source.csv"
        self.set_file_input(0, source_file)
        self.click_button("Upload and profile", timeout_ms=30_000)
        self.wait_for_any_text(["Generate canonical mapping", "3. Review Mapping"], timeout_ms=60_000)
        self.set_checkbox("Use LLM validation", use_llm)
        self.click_button("Generate canonical mapping", timeout_ms=30_000)
        self.wait_for_text("Mapping is ready", timeout_ms=180_000)
        return {"source": str(source_file), "target": "canonical"}

    def open_expander(self, title: str) -> None:
        pattern = re.compile(re.escape(title), re.IGNORECASE)
        expander_candidates = self.page.get_by_role("button", name=pattern)
        expander = expander_candidates.first if expander_candidates.count() else self.page.get_by_text(pattern).first
        expander.scroll_into_view_if_needed()
        expander.click()
        self.page.wait_for_timeout(350)

    def capture_screenshot(self, file_name: str) -> str:
        if not self.args.capture_screenshots:
            return ""
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self.screenshots_dir / file_name
        self.page.screenshot(path=str(screenshot_path), full_page=False)
        return str(screenshot_path)

    def scenario_prefix(self) -> str:
        return f"{self.scenario.order:02d}_{self.scenario.key}"

    def run_standard_two_file_mapping(self) -> dict[str, Any]:
        fixture_info = self.upload_standard_pair(use_llm=False)
        self.click_nav_label("Workspace section", "Review")
        review_body = self.wait_for_any_text(["Review Queue Plan", "Selected Mapping"], timeout_ms=30_000)
        screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_01.png")
        return {
            "fixture": fixture_info,
            "mapping_ready": "Mapping is ready" in review_body or "Review Queue Plan" in review_body,
            "screenshots": [screenshot] if screenshot else [],
        }

    def run_canonical_source_mapping(self) -> dict[str, Any]:
        fixture_info = self.upload_canonical_source(use_llm=False)
        self.click_nav_label("Workspace section", "Review")
        review_body = self.wait_for_any_text(
            [
                "Canonical-only review treats canonical concept IDs as virtual targets built from the glossary.",
                "Filter by canonical concept",
            ],
            timeout_ms=30_000,
        )
        review_screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_01.png")
        self.click_nav_label("Workspace section", "Output")
        self.wait_for_text("Artifact Generation", timeout_ms=30_000)
        self.click_button("Generate Pandas code", timeout_ms=30_000)
        output_body = self.wait_for_any_text(["Generated Pandas Code", "Generated pandas code generation"], timeout_ms=90_000)
        output_screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_02.png")
        return {
            "fixture": fixture_info,
            "review_ready": "canonical" in review_body.lower(),
            "pandas_generated": "Generated Pandas Code" in output_body,
            "screenshots": [item for item in [review_screenshot, output_screenshot] if item],
        }

    def run_llm_decision_flow(self) -> dict[str, Any]:
        fixture_info = self.upload_standard_pair(use_llm=True)
        self.click_nav_label("Workspace section", "Review")
        self.wait_for_text("LLM Decision Proposals", timeout_ms=30_000)
        self.open_expander("LLM Decision Proposals")
        self.set_checkbox("Use live LLM fill for rows without cached proposition", True)
        self.click_button("Generate proposals for current review slice", timeout_ms=30_000)
        review_body = self.wait_for_any_text(["Prepared ", "Proposal source", "pending"], timeout_ms=120_000)
        self.click_nav_label("Workspace section", "Decisions")
        self.wait_for_text("LLM Decision Proposals", timeout_ms=30_000)
        self.open_expander("LLM Decision Proposals")
        applied_safe_proposals = False
        apply_safe_button = self.page.get_by_role("button", name="Apply safe proposals")
        if apply_safe_button.is_visible() and apply_safe_button.is_enabled():
            apply_safe_button.click()
            applied_safe_proposals = True
            self.wait_for_any_text(["Applied ", "Active Decisions"], timeout_ms=60_000)
        screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_01.png")
        return {
            "fixture": fixture_info,
            "proposals_generated": any(token in review_body for token in ["Prepared ", "Proposal source", "pending"]),
            "safe_proposals_applied": applied_safe_proposals,
            "screenshots": [screenshot] if screenshot else [],
        }

    def run_catalog_approved_reuse(self) -> None:
        self.click_nav_label("Navigation", "Catalog")
        self.wait_for_text("Catalog", timeout_ms=30_000)
        self.click_button("Reset catalog state")
        self.fill_textbox("Search", "approved-customer-reuse-smoke")
        self.click_button("Run catalog query")
        self.wait_for_text("Integration detail", timeout_ms=30_000)
        self.click_button("Load detail")
        self.wait_for_text("Latest approved version:", timeout_ms=30_000)
        self.click_button("Reuse in Workspace", timeout_ms=30_000)
        self.wait_for_text("Reused mapping set", timeout_ms=30_000)

    def click_output_format(self, label: str) -> None:
        self.page.get_by_role("radiogroup", name="Artifact format").locator("label").filter(
            has_text=re.compile(rf"^{re.escape(label)}$", re.IGNORECASE)
        ).click()
        self.page.wait_for_timeout(350)

    def run_workspace_output_generation(self) -> dict[str, Any]:
        self.page.goto(self.args.streamlit_url, wait_until="domcontentloaded")
        self.wait_for_text("Semantra - Data Mapping Review and Benchmarking", timeout_ms=45_000)
        self.configure_connection()
        self.run_catalog_approved_reuse()
        self.click_nav_label("Navigation", "Workspace")
        self.click_nav_label("Workspace section", "Output")
        self.wait_for_text("Artifact Generation", timeout_ms=30_000)
        self.click_output_format("Pandas starter")
        self.click_button("Generate Pandas code", timeout_ms=30_000)
        pandas_body = self.wait_for_text("Generated Pandas Code", timeout_ms=90_000)
        pandas_screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_01.png")
        self.click_output_format("dbt model starter")
        self.click_button("Generate dbt model", timeout_ms=30_000)
        dbt_body = self.wait_for_text("Generated dbt Model SQL", timeout_ms=90_000)
        self.fill_textbox("What should change?", "Preserve the current scaffold, but normalize phone and email handling and keep null-safe behavior.")
        self.fill_textbox("Business rules / edge cases", "Phone values may start with +381 or 06, emails should be lowercase, and empty strings should stay null.")
        self.click_button("Refine with LLM", timeout_ms=30_000)
        refine_body = self.wait_for_any_text(["Accept refined version", "Generated a refinement candidate"], timeout_ms=120_000)
        refine_screenshot = self.capture_screenshot(f"{self.scenario_prefix()}_02.png")
        return {
            "fixture": {"mapping_source": "approved-customer-reuse-smoke"},
            "pandas_generated": "Generated Pandas Code" in pandas_body,
            "dbt_generated": "Generated dbt Model SQL" in dbt_body,
            "refinement_generated": any(token in refine_body for token in ["Accept refined version", "Generated a refinement candidate"]),
            "screenshots": [item for item in [pandas_screenshot, refine_screenshot] if item],
        }


def sanitize_file_stem(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def finalize_video(page: Any, scenario_dir: Path, scenario: ScenarioDefinition) -> str:
    video = page.video
    if video is None:
        return ""

    recorded_path = Path(video.path())
    if not recorded_path.exists():
        return ""

    final_video_path = scenario_dir / f"{scenario.order:02d}_{sanitize_file_stem(scenario.key)}.webm"
    if final_video_path.exists():
        final_video_path.unlink()
    shutil.move(str(recorded_path), str(final_video_path))

    video_tmp_dir = scenario_dir / "video_tmp"
    if video_tmp_dir.exists():
        shutil.rmtree(video_tmp_dir, ignore_errors=True)
    return str(final_video_path)


def write_root_readme(artifacts_dir: Path, scenarios: list[ScenarioDefinition], summary: dict[str, Any]) -> Path:
    lines: list[str] = [
        "# Workspace Demo Recordings",
        "",
        "Ovaj folder sadrzi workspace-focused Semantra demo recording artefakte generisane automatizovanim browser tokom.",
        "",
        "## Scenario Index",
        "",
    ]

    for scenario in scenarios:
        scenario_summary = summary.get("scenarios", {}).get(scenario.key, {})
        scenario_dir = artifacts_dir / f"{scenario.order:02d}_{sanitize_file_stem(scenario.key)}"
        lines.extend(
            [
                f"## {scenario.order:02d}. {scenario.title}",
                "",
                scenario.objective,
                "",
                f"Folder: `{scenario_dir}`",
                "",
                f"Video: `{scenario_summary.get('video') or ''}`",
                "",
            ]
        )
        screenshots = scenario_summary.get("screenshots") or []
        if screenshots:
            lines.append("Screenshots:")
            lines.append("")
            lines.extend(f"- `{path}`" for path in screenshots)
            lines.append("")
        result = scenario_summary.get("result") or {}
        if result:
            lines.append("Summary:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(result, indent=2, ensure_ascii=True))
            lines.append("```")
            lines.append("")

    readme_path = artifacts_dir / "README.md"
    readme_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return readme_path


def run_recordings(args: argparse.Namespace) -> dict[str, Any]:
    scenarios = resolve_scenarios(args.scenarios)
    artifacts_dir = resolve_artifacts_dir(args)

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is not installed in the selected Python environment. Install dependencies first."
        ) from error

    summary: dict[str, Any] = {
        "artifacts_dir": str(artifacts_dir),
        "scenarios": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed, slow_mo=max(args.slow_mo_ms, 0))
        try:
            for scenario in scenarios:
                scenario_folder_name = f"{scenario.order:02d}_{sanitize_file_stem(scenario.key)}"
                scenario_dir = artifacts_dir / scenario_folder_name
                scenario_dir.mkdir(parents=True, exist_ok=True)

                context_kwargs: dict[str, Any] = {"viewport": {"width": 1440, "height": 1600}}
                if args.record_video:
                    video_tmp_dir = scenario_dir / "video_tmp"
                    video_tmp_dir.mkdir(parents=True, exist_ok=True)
                    context_kwargs["record_video_dir"] = str(video_tmp_dir)
                    context_kwargs["record_video_size"] = {"width": 1440, "height": 1600}

                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                runner = WorkspaceRecordingRunner(page, args, scenario, scenario_dir)
                try:
                    result = runner.run()
                finally:
                    context.close()

                video_path = finalize_video(page, scenario_dir, scenario) if args.record_video else ""
                summary["scenarios"][scenario.key] = {
                    "title": scenario.title,
                    "objective": scenario.objective,
                    "folder": str(scenario_dir),
                    "video": video_path,
                    "screenshots": result.get("screenshots") or [],
                    "result": result,
                }
        finally:
            browser.close()

    summary_path = artifacts_dir / "workspace_demo_recordings_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    summary["summary_file"] = str(summary_path)
    summary["readme_file"] = str(write_root_readme(artifacts_dir, scenarios, summary))
    return summary


def main() -> int:
    args = parse_args()
    summary: dict[str, Any] = {}
    try:
        if not args.skip_bootstrap:
            summary["bootstrap"] = run_bootstrap(args)
        summary["recordings"] = run_recordings(args)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print_json_block("Workspace demo recordings summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())