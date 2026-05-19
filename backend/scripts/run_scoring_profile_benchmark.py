"""CLI utility for comparing Semantra scoring profiles on benchmark cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.evaluation_service import compare_scoring_profiles
from app.services.llm_service import build_provider_from_settings
from app.services.mapping_service import DEFAULT_SCORING_PROFILE, SCORING_PROFILES


DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mapping_gold.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Semantra scoring profiles on a benchmark case set and recommend a default profile."
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_FIXTURE_PATH),
        help="Path to benchmark cases JSON. Defaults to backend/tests/fixtures/mapping_gold.json.",
    )
    parser.add_argument(
        "--profiles",
        default=",".join(SCORING_PROFILES.keys()),
        help="Comma-separated scoring profiles to compare.",
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Include the currently configured LLM provider during benchmark execution.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full comparison as JSON instead of the text summary.",
    )
    return parser.parse_args()


def pick_recommendation(comparison: dict[str, object]) -> tuple[str | None, str]:
    ranked_profiles = sorted(
        comparison.items(),
        key=lambda item: (
            item[1].accuracy,
            item[1].top1_accuracy,
            item[1].correct_matches,
            item[0] == DEFAULT_SCORING_PROFILE,
        ),
        reverse=True,
    )
    top_name, top_metrics = ranked_profiles[0]
    ties = [
        name
        for name, metrics in ranked_profiles
        if metrics.accuracy == top_metrics.accuracy
        and metrics.top1_accuracy == top_metrics.top1_accuracy
        and metrics.correct_matches == top_metrics.correct_matches
    ]
    if len(ties) == 1:
        return top_name, f"Unique best profile on this benchmark: {top_name}."
    if DEFAULT_SCORING_PROFILE in ties:
        return DEFAULT_SCORING_PROFILE, (
            "No decisive benchmark winner across compared profiles; keep balanced as the default because it ties "
            "for best metrics and preserves existing behavior."
        )
    return None, "No decisive benchmark winner across compared profiles; choose based on scenario rather than fixture-only metrics."


def main() -> int:
    args = parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    profile_names = [item.strip() for item in args.profiles.split(",") if item.strip()]
    llm_provider = build_provider_from_settings() if args.with_llm else None
    comparison = compare_scoring_profiles(cases, profile_names=profile_names, llm_provider=llm_provider)
    recommended_profile, recommendation_reason = pick_recommendation(comparison)

    if args.json:
        print(
            json.dumps(
                {
                    "cases_path": str(Path(args.cases).resolve()),
                    "comparison": {name: metrics.model_dump(mode="json") for name, metrics in comparison.items()},
                    "recommended_profile": recommended_profile,
                    "recommendation_reason": recommendation_reason,
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 0

    print(f"Benchmark cases: {Path(args.cases).resolve()}")
    print("Profile comparison:")
    print("profile          accuracy  top1    correct/fields")
    for profile_name, metrics in comparison.items():
        print(
            f"{profile_name:<16} {metrics.accuracy:>7.4f}   {metrics.top1_accuracy:>7.4f}   "
            f"{metrics.correct_matches}/{metrics.total_fields}"
        )
    print()
    print(f"Recommended default: {recommended_profile or 'no-clear-winner'}")
    print(recommendation_reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())