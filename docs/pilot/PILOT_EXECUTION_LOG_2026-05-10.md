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

## Scenario 4

Name: catalog handoff regression subset

Artifacts:

- seeded `browser-diff-focus` integration family (`v2` vs `v1`, both draft)
- seeded `Stewardship Smoke Sync` mapping set (`#770`)

Path:

- `Catalog` / `Load all integrations`
- `Browser Diff Focus Sync` detail -> `Open selected version` -> `Load version diff`
- `Open current diff review focus`
- manually set stale `Canonical concept search = legacy` in `Governance`
- return to `Catalog` diff readout -> `Open current diff Canonical review`
- switch integration detail to `Stewardship Smoke Sync` -> `Open selected version` -> `Open Stewardship`

Observed result:

- `Catalog` loaded `4` integrations with `2` approved entries on the live local stack
- `browser-diff-focus` diff handoff moved the UI into `Workspace > Review` and surfaced the expected status message:
	- `Catalog handoff: browser-diff-focus v2 -> Workspace Review with filters status=needs_review, confidence=All, canonical_concept=customer.id, source_scope=3 diff fields.`
- after intentionally setting stale canonical search `legacy`, `Open current diff Canonical review` moved the UI into `Governance > Canonical`
- the canonical handoff also cleared the stale search box and applied the expected scope filters:
	- `Source system = SAP`
	- `Business domain = Customer`
	- filtered canonical count dropped to `2`, matching the scoped landing instead of the stale pre-handoff search state
- `Stewardship Smoke Sync` integration detail showed `Unmatched sources: LAND1, REGIO` and the main drilldown CTA rendered as `Open Stewardship`
- `Open Stewardship` moved the UI into `Governance > Stewardship` instead of the generic canonical landing
- the live Stewardship landing remained operational even though the current canonical gap queue was empty on this runtime

Operational conclusion:

- the newer `Catalog` handoff CTA surfaces are now browser-confirmed end-to-end, not only helper-tested
- canonical handoff reset behavior is doing real recovery work against stale Governance state before the new focus is applied
- `Stewardship` routing from unmatched-source catalog drilldown is correctly distinguished from canonical review routing in the live UI
- the visible `Filter by source = All` assertion should still be treated as conditional on an already loaded Workspace review set; this run confirmed the handoff intent and scope message, but not that extra loaded-workspace-only presentation detail

Severity:

- low immediate pilot risk for the observed catalog handoff paths on the current local stack
- remaining follow-up is regression coverage depth, not an active blocker in the tested handoff behavior

## Scenario 5

Name: draft-session review restore with dirty review state

Artifacts:

- existing saved `Review` draft session (`customer-draft-session`)
- live local `Workspace` review state with `source.csv` / `target.csv`

Path:

- `Workspace > Review`
- set `Filter by source = phone`
- generate `Review Queue Plan`
- switch to `Workspace > Decisions -> Mapping Set Versions`
- `Load draft sessions`
- `Resume draft session`

Observed result:

- the live UI allowed the review slice to be intentionally dirtied with:
	- `Filter by source = phone`
	- generated `Review Queue Plan · LLM`
	- `Selected Mapping · 1 active`
- resuming the saved `Review` draft session returned the UI to `Workspace > Review` without a Streamlit navigation error
- after resume, the review context came back clean instead of carrying stale local review state:
	- `Filter by source = All`
	- `Review Queue Plan` returned to its unopened / generate state
	- `Selected Mapping · 2 active`
	- `Mapping Trust Layer` and `Scoring runtime` both rendered normally from the restored minimal contract

Operational conclusion:

- the current draft-session restore path is now browser-confirmed not only for navigation, already checked earlier, but also for review-state hygiene under intentionally dirty local filter/guidance state
- bounded guidance and filter state are not leaking across restore in a way that would silently narrow the restored review set
- this continuity path is now strong enough to belong in the standing pilot regression subset, not only as an ad-hoc smoke

Severity:

- low immediate pilot risk for the observed draft-session restore path on the current local stack
- useful hardening signal because the exercised failure mode would have been user-visible immediately after resume

## Scenario 6

Name: catalog diff review handoff over an already loaded review set

Artifacts:

- seeded `browser-diff-focus` integration family (`#778` v1, `#779` v2, both draft)
- existing saved `Review` draft session (`customer-draft-session`)

Path:

- `Workspace > Decisions -> Mapping Set Versions`
- `Resume draft session` for `customer-draft-session`
- `Catalog` / `Load all integrations`
- `browser-diff-focus` detail -> `Open selected version` -> `Load version diff`
- `Open current diff review focus`

Observed result:

- the local runtime initially had `0` catalog integrations, so the smoke first seeded a minimal `browser-diff-focus` family through the existing `/mapping/sets` API instead of adding a dedicated seed path
- after seeding, `Catalog` loaded `2` saved catalog integration versions and the drilldown exposed the expected version diff CTA path
- `Open current diff review focus` moved the UI into `Workspace > Review` while preserving the already restored review-backed workspace state
- the live UI showed the expected handoff status message:
	- `Catalog handoff: Browser Diff Focus Sync v2 → Workspace Review with filters status=needs_review, confidence=All, canonical_concept=customer.id, source_scope=6 diff fields.`
- the loaded-review presentation detail was now browser-confirmed, not only helper-tested:
	- `Filter by source = All`
	- review caption limited the scope through `Catalog diff focus is limiting Workspace Review to 6 changed source fields ...`
	- the restored review rows from `customer-draft-session` remained visible instead of being replaced by catalog data

Operational conclusion:

- the previously pending loaded-review assertion for `Catalog -> Workspace Review` diff handoff is now confirmed in the live UI
- this handoff uses a soft multi-source focus signal (`source_scope` plus review caption), not a hard source filter, which avoids silently narrowing an already loaded review set
- an empty local catalog runtime is an operational precondition issue, not a product blocker; the existing `/mapping/sets` API is sufficient to seed repeatable smoke fixtures

Severity:

- low immediate pilot risk for the observed loaded-review catalog handoff path on the current local stack
- useful operational hardening signal because it closes a browser-visible assertion that previously existed only in helper logic and tracker intent

## Scenario 7

Name: benchmark profile comparison and explanation over seeded saved dataset

Artifacts:

- seeded saved benchmark dataset `operational-smoke-benchmark` (`#156`, `v1`, `cases=3`)
- active local runtime on `8000/8501`

Path:

- `Benchmarks`
- `Load saved benchmark datasets`
- select `#156 | operational-smoke-benchmark | v1 | cases=3`
- `Compare scoring profiles`
- open `Benchmark Explanation`
- `Generate benchmark explanation`

Observed result:

- helper regression subset already passed for benchmark views together with Workspace and Catalog (`132 passed, 0 failed`), and the live runtime now also has a repeatable saved dataset fixture through the operational bootstrap
- `Benchmarks` loaded the saved dataset cleanly and exposed the expected compare actions without requiring a manual ad-hoc benchmark save step
- `Compare scoring profiles` returned a visible browser-level evidence surface:
	- `Scoring Profile Comparison`
	- `Recommended default profile: balanced`
	- recommendation reason: `No decisive benchmark winner across compared profiles; keep balanced as the default because it ties for best metrics and preserves existing behavior.`
- opening `Benchmark Explanation` after that evidence step showed the expected unlock state:
	- `Loaded benchmark evidence is ready for benchmark explanation review.`
- `Generate benchmark explanation` completed in the live UI and rendered a bounded fallback explanation with visible:
	- success status `Generated benchmark explanation for operational-smoke-benchmark.`
	- `Benchmark Explanation · Fallback`
	- `Key findings`, `Risks`, and `Next actions`

Operational conclusion:

- `Benchmarks` is no longer the least-proven of the three main pilot surfaces in this local runtime; the saved-dataset -> evidence -> explanation path is now browser-confirmed end to end
- the same operational bootstrap that already stabilized Catalog/Workspace smokes now removes the benchmark precondition gap as well, so the main pilot trio can be exercised repeatably on a fresh local runtime
- current benchmark explanation behavior is at least operationally safe even when the LLM path is not needed, because the fallback contract renders a complete bounded explanation surface

Severity:

- low immediate pilot risk for the observed benchmark compare/explanation path on the current local stack
- important closure signal because it expands operational hardening from mostly Workspace/Catalog confidence into a real Workspace/Catalog/Benchmarks trio