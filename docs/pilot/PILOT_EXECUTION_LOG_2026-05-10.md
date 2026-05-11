# Pilot Execution Log - 2026-05-10

## Scenario 1

Name: showcase customer mapping

Artifacts:

- `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv`
- `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`

Path:

- Workspace
- Standard mode
- upload -> profile -> generate mapping

Observed result:

- upload and schema profiling succeeded
- source and target previews rendered correctly
- mapping job started and produced ranking/activity lines
- LLM-enabled path entered ambiguity validation but did not produce a clean, stable review-ready flow during the observed pilot run

Operational conclusion:

- keep `Use LLM validation` off by default for the stable pilot baseline
- treat LLM-assisted ambiguity review as an opt-in extension, not the primary showcase path

Severity:

- important for pilot reliability
- not a blocker for deterministic-first demo path

## Supporting validation

Focused pilot regression subset passed after the hardening change:

```powershell
python -m pytest tests/test_streamlit_workspace_views.py tests/test_streamlit_workspace_review_views.py tests/test_streamlit_catalog_views.py tests/test_streamlit_admin_views.py -q
```

Result:

- `53 passed`

## Open follow-up

- add at least one more manually observed real scenario log
- confirm the cleanest no-intervention pilot narrative from review through preview/export on the deterministic baseline

## Scenario 2

Name: showcase supplier master

Artifacts:

- `ui_fixtures/showcase_supplier_master/showcase_supplier_source.csv`
- `ui_fixtures/showcase_supplier_master/showcase_supplier_target.json`

Path:

- Workspace / Standard mode / deterministic baseline (`Use LLM validation = off`)
- upload -> profile -> generate mapping -> output governance check

Observed result:

- live UI on the older `8000/8501` listener reached `Mapping is ready` and `Output`, but preview behavior did not match repo/test expectations
- a fresh parallel runtime on `8001/8502` matched the intended semantics for the same fixture pair
- direct backend validation on `8001` produced:
	- `mapping_count = 14`
	- `preview_status = 200`
	- `preview_rows = 5`
	- `codegen_status = 409`
	- all 14 decisions remained `needs_review`, so codegen correctly stayed blocked

Operational conclusion:

- deterministic supplier master is a valid stable pilot/regression scenario on a clean current runtime
- preview should remain advisory-only for `needs_review` decisions, while codegen stays accepted-only
- when live behavior diverges from the narrow backend smoke test, treat it as local runtime drift first and verify against a fresh stack before changing code
- default-listener drift was traced to false-ready local startup; `start_semantra.ps1` now waits for backend and Streamlit ports before reporting success
- stale `backend unavailable` UI state after backend recovery was traced to cached negative reachability in the Streamlit helper; the helper now retries failed reachability for the same base URL and fresh `8501` loads show healthy runtime status again
- after the startup/readability fixes, the default `8000/8501` listener completed the supplier deterministic path cleanly: first-click upload/profile, mapping ready, preview success, and accepted-only codegen block remained intact

Severity:

- medium operational risk for local demo reliability
- not a product-logic blocker in current repo code

## Open follow-up

- no immediate pilot blocker remains in the current deterministic baseline; next follow-up can move back to backlog work outside the operational slice

## Scenario 3

Name: showcase customer mapping with LLM validation re-check

Artifacts:

- `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv`
- `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`

Path:

- Workspace / Standard mode / `Use LLM validation = on`
- upload -> profile -> generate mapping -> review-ready completion -> output governance check

Observed result:

- source and target upload/profile completed cleanly on the default `8000/8501` stack
- live UI showed the full LLM ambiguity-validation activity stream across all 8 source fields
- the mapping job completed without stalling and reached `Mapping results are ready for review` plus `Mapping is ready`
- output governance still behaved correctly on the LLM-assisted path:
	- preview remained available while all decisions were still `needs_review`
	- code generation stayed blocked until decisions were accepted
- accepted-path backend validation for the same fixture pair produced:
	- `preview_status = 200`
	- `preview_rows = 5`
	- `unresolved_targets = 0`
	- `codegen_status = 200`
- cancel edge-case validation on a longer LLM-backed mapping job produced:
	- initial cancel response `cancel_requested`
	- final polled status `canceled`
	- expected activity lines for cancellation request and cooperative stop at the next progress checkpoint

Operational conclusion:

- the previously suspicious LLM-enabled customer pilot path is materially healthier on the current hardened runtime than it was in the earlier observation
- `Use LLM validation = off` should still remain the default stable pilot baseline, but `Use LLM validation = on` is no longer showing the earlier review-readiness stall in this fixture-based re-check
- current governance semantics are coherent on both deterministic and LLM-assisted paths:
	- `needs_review` allows advisory preview
	- accepted decisions allow code generation
	- active jobs can now be canceled cooperatively without waiting for a timeout-only failure mode

Severity:

- low immediate pilot risk for the observed customer LLM scenario on the current local stack
- still not enough evidence to call the broader LLM runtime fully hardened across all fixtures or longer sessions

## Current testing readout

- the focused pilot/UAT cycle for the current hardening wave is in a good stopping state
- no immediate blocker was reproduced in the tested deterministic baseline, the re-checked LLM customer scenario, governance/output flow, or cancel edge-case behavior
- remaining unclosed risk is broader coverage, not a currently observed failure in the tested paths