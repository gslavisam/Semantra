from streamlit_ui.benchmark_views import (
    _benchmark_explanation_enabled,
    _benchmark_explanation_payload,
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
        "Run a benchmark, correction-impact check, or scoring-profile comparison to unlock this explanation."
    )
    assert _benchmark_explanation_unlock_message({"accuracy": 1.0}, None, None) == (
        "Generate or refresh the explanation for the currently loaded benchmark evidence."
    )


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