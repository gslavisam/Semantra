"""Tests Streamlit benchmark view helpers and related workflow state."""

from streamlit_ui.benchmark_views import (
    _benchmark_explanation_action_label,
    _benchmark_explanation_enabled,
    _benchmark_explanation_empty_message,
    _benchmark_explanation_error_message,
    _benchmark_explanation_intro_caption,
    _benchmark_explanation_metadata_caption,
    _benchmark_explanation_output_heading,
    _benchmark_explanation_payload,
    _benchmark_explanation_section_label,
    _benchmark_explanation_success_message,
    _benchmark_explanation_unlock_message,
    _current_mapping_benchmark_block_reason,
)


def test_benchmark_explanation_enabled_requires_any_loaded_result() -> None:
    assert _benchmark_explanation_enabled(None, None, None) is False
    assert _benchmark_explanation_enabled({"accuracy": 1.0}, None, None) is True
    assert _benchmark_explanation_enabled(None, {"accuracy_delta": 0.1}, None) is True
    assert _benchmark_explanation_enabled(None, None, {"recommended_profile": "balanced"}) is True


def test_benchmark_explanation_unlock_message_reflects_loaded_state() -> None:
    assert _benchmark_explanation_unlock_message(None, None, None) == (
        "Run a benchmark, correction-impact check, or scoring-profile comparison first to unlock benchmark explanation."
    )
    assert _benchmark_explanation_unlock_message({"accuracy": 1.0}, None, None) == (
        "Loaded benchmark evidence is ready for benchmark explanation review."
    )


def test_benchmark_explanation_intro_caption_states_read_only_role() -> None:
    assert _benchmark_explanation_intro_caption() == (
        "Generate one bounded benchmark explanation for the currently loaded benchmark evidence before changing scoring assumptions. "
        "This is a read-only guidance surface and does not change scoring state."
    )


def test_benchmark_explanation_section_label_reflects_generation_mode() -> None:
    assert _benchmark_explanation_section_label(None) == "Benchmark Explanation"
    assert _benchmark_explanation_section_label({"generation_metadata": {"used_llm": True}}) == (
        "Benchmark Explanation · LLM"
    )
    assert _benchmark_explanation_section_label({"generation_metadata": {"used_llm": False}}) == (
        "Benchmark Explanation · Fallback"
    )


def test_benchmark_explanation_action_and_empty_state_helpers_use_explanation_noun() -> None:
    assert _benchmark_explanation_action_label(None) == "Generate benchmark explanation"
    assert _benchmark_explanation_action_label({"summary": "x"}) == "Refresh benchmark explanation"
    assert _benchmark_explanation_empty_message(False) == "No benchmark evidence is loaded yet."
    assert _benchmark_explanation_empty_message(True) == (
        "No benchmark explanation has been generated yet for the loaded benchmark evidence."
    )


def test_benchmark_explanation_success_and_error_helpers_use_shared_copy_pattern() -> None:
    assert _benchmark_explanation_success_message("the loaded benchmark") == (
        "Generated benchmark explanation for the loaded benchmark."
    )
    assert _benchmark_explanation_error_message("boom") == "Benchmark explanation generation failed: boom"


def test_benchmark_explanation_metadata_caption_uses_llm_fallback_pattern() -> None:
    assert _benchmark_explanation_metadata_caption(None) == ""
    assert _benchmark_explanation_metadata_caption(
        {"generation_metadata": {"used_llm": True, "fallback_used": False}}
    ) == "LLM"
    assert _benchmark_explanation_metadata_caption(
        {"generation_metadata": {"used_llm": False, "fallback_used": True}}
    ) == "Fallback with fallback contract"


def test_benchmark_explanation_output_heading_preserves_section_title() -> None:
    assert _benchmark_explanation_output_heading("Key findings") == "Key findings"
    assert _benchmark_explanation_output_heading(" Next actions ") == "Next actions"


def test_benchmark_explanation_payload_preserves_loaded_result_shapes() -> None:
    payload = _benchmark_explanation_payload(
        dataset_name="email-case",
        benchmark_result={"accuracy": 1.0},
        correction_impact={"accuracy_delta": 0.5},
        profile_comparison={"recommended_profile": "balanced"},
    )

    assert payload == {
        "dataset_name": "email-case",
        "benchmark_result": {"accuracy": 1.0},
        "correction_impact": {"accuracy_delta": 0.5},
        "profile_comparison": {"recommended_profile": "balanced"},
    }


def test_current_mapping_benchmark_block_reason_requires_all_accepted_decisions() -> None:
    assert _current_mapping_benchmark_block_reason([{"source": "cust_id", "status": "accepted"}]) == ""
    assert _current_mapping_benchmark_block_reason([{"source": "phone", "status": "needs_review"}]) == (
        "Saving current mapping as benchmark is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )