# LLM Refine and Decision Proposals Test Coverage (2026-06-02)

## Scope
This document checks whether automated tests confirm full functionality for:

1. LLM Mapping Refine - Batch LLM refine
2. Preview LLM refine inside Details and Transformation
3. Accept refined mapping and Discard refined mapping inside Details and Transformation
4. LLM Decision Proposals

## Test Execution Snapshot

Executed on 2026-06-02:

```powershell
Set-Location D:/py_radno/Semantra
D:/py_radno/.venv/Scripts/python.exe -m pytest tests/test_streamlit_workspace_review_views.py tests/test_streamlit_workspace_decision_views.py tests/test_streamlit_api.py -q
```

Result:
- 52 passed

Refine-endpoint specific backend test:

```powershell
Set-Location D:/py_radno/Semantra/backend
D:/py_radno/.venv/Scripts/python.exe -m pytest tests/test_canonical_mapping_api.py::test_mapping_refine_endpoint_uses_transient_manual_hints_and_closed_candidate_set -q
```

Result:
- 1 passed

Note:
- Running the full `backend/tests/test_canonical_mapping_api.py` suite currently has one unrelated failure in canonical concept expectations (`shared_concepts` empty on one test). This does not block the refine-endpoint test above.

## Coverage Matrix

### 1) Batch LLM refine

Current status: PARTIAL

What is covered:
- Indirect LLM refine behavior for proposal materialization with live fill:
  - `test_llm_decision_proposals_for_filtered_rows_can_use_live_fill`
  - File: `tests/test_streamlit_workspace_review_views.py`

What is not covered:
- No direct UI test for pressing `Batch refine low-confidence rows`
- No direct assertion for batch counters/messages (`refined_count`, `no_match_count`, `failed_sources`)
- No direct test for `Apply refined mappings immediately` checkbox behavior inside batch panel

Conclusion:
- Core helper logic is partially verified, but full batch-panel behavior is not fully confirmed by dedicated test cases.

### 2) Preview LLM refine in Details and Transformation

Current status: PARTIAL

What is covered:
- Streamlit API payload contract for refine request:
  - `test_request_llm_mapping_refinement_posts_expected_payload`
  - `test_request_llm_mapping_refinement_defaults_canonical_candidate_pool_size_to_10`
  - File: `tests/test_streamlit_api.py`
- Backend `/mapping/refine` endpoint handling transient manual hints and closed candidate set:
  - `test_mapping_refine_endpoint_uses_transient_manual_hints_and_closed_candidate_set`
  - File: `backend/tests/test_canonical_mapping_api.py`

What is not covered:
- No direct UI test for clicking per-row `Preview LLM refine` button in Details panel
- No direct UI test asserting refine preview rendering text per row

Conclusion:
- Request/response contracts are tested, but end-to-end UI interaction for the Details preview button is not fully covered.

### 3) Accept refined mapping / Discard refined mapping (Details panel)

Current status: MISSING DIRECT TESTS

What is covered:
- No dedicated tests found for direct accept/discard refined mapping actions in Review Details UI.

What is not covered:
- No direct tests for `Accept refined mapping` button action
- No direct tests for `Discard refine preview` button action
- No direct tests for `_apply_llm_mapping_refinement` and `_clear_llm_mapping_refinement` helper behavior

Conclusion:
- This area currently has a clear test gap and does not yet have explicit automated confirmation.

### 4) LLM Decision Proposals

Current status: STRONG HELPER COVERAGE, PARTIAL UI COVERAGE

What is covered:
- Proposal building and safety gating in Review helpers:
  - `test_build_llm_decision_proposal_creates_safe_accept_current_proposal`
  - `test_build_llm_decision_proposal_marks_unsupported_switch_as_not_safe`
  - `test_llm_decision_proposals_for_filtered_rows_can_use_live_fill`
  - File: `tests/test_streamlit_workspace_review_views.py`
- Proposal apply behavior in Decisions helpers:
  - `test_apply_llm_decision_proposal_switches_target_and_accepts`
  - `test_apply_llm_decision_proposal_rejects_stale_state`
  - File: `tests/test_streamlit_workspace_decision_views.py`

What is not covered:
- No direct UI-level test of pressing `Apply safe proposals`
- No direct UI-level test for `Apply selected proposal` and `Dismiss selected proposal` button wiring

Conclusion:
- Decision-proposal core logic is well covered at helper level, but UI panel button flows are not fully validated by dedicated interaction tests.

## Answer to the original question

Do test cases currently confirm full functionality for all 4 requested areas?

- No, not fully.
- Coverage is good for API/helper logic (especially around proposal generation/apply and refine payload contracts), but there are missing direct UI interaction tests for:
  - Batch refine button behavior
  - Per-row preview button behavior in Details panel
  - Accept/Discard refined mapping button behavior in Details panel
  - Decisions panel apply/dismiss button wiring

## Recommended next tests (high priority)

1. Add Review UI test: batch refine button click with mixed row outcomes (success/no_match/error-continue)
2. Add Review UI test: per-row preview click shows row-local refinement state and message
3. Add Review UI test: accept refined mapping updates target/status/audit fields
4. Add Review UI test: discard refined mapping removes preview state and keeps row stable
5. Add Decisions UI test: apply safe proposals removes only applied rows from pending list
6. Add Decisions UI test: apply selected and dismiss selected proposal mutate proposal cache correctly
