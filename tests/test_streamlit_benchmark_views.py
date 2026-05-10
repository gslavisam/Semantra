from streamlit_ui.benchmark_views import _current_mapping_benchmark_block_reason


def test_current_mapping_benchmark_block_reason_requires_all_accepted_decisions() -> None:
    assert _current_mapping_benchmark_block_reason([{"source": "cust_id", "status": "accepted"}]) == ""
    assert _current_mapping_benchmark_block_reason([{"source": "phone", "status": "needs_review"}]) == (
        "Saving current mapping as benchmark is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )