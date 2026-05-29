# Pilot Execution Log - 2026-05-29

## Scenario 1

Name: primary proof-of-value demo flow re-check

Artifacts:

- seeded `approved-customer-reuse-smoke` mapping set (`approved`)
- seeded `customer-draft-session` draft session (`#55`)
- seeded `browser-diff-focus` mapping-set family (`v1`, `v2`)
- seeded `stewardship-smoke-sync` mapping set
- seeded `operational-smoke-benchmark` benchmark dataset (`#168`)

Path:

- bootstrap operational smoke state
- `Catalog` reuse
- `Workspace` draft-session resume
- `Catalog` diff handoff
- `Catalog` stewardship handoff
- `Benchmarks` scoring-profile comparison and explanation

Observed result:

- operational bootstrap succeeded and prepared all five fixture anchors for the main demo story
- `Catalog` reuse path was browser-confirmed through detail load, visible `Latest approved version`, visible `approved` status, and active `Reuse in Workspace` CTA
- after reuse, the live UI showed a loaded workspace state with `3` active decisions, confirming that the approved asset was not treated as read-only catalog history
- `Catalog` diff handoff was browser-confirmed end-to-end:
	- version detail opened
	- diff loaded successfully
	- `Open current diff review focus` was visible and routed correctly
- `Catalog` stewardship handoff was browser-confirmed end-to-end:
	- version drilldown opened successfully
	- `Open Stewardship` was visible and routed into the governance surface
- `Benchmarks` comparison and explanation were browser-confirmed end-to-end:
	- saved dataset load succeeded for `operational-smoke-benchmark`
	- `Scoring Profile Comparison` rendered successfully
	- `Recommended default profile: balanced` rendered successfully
	- `Benchmark Explanation` unlocked after the comparison result was loaded
	- explanation generated successfully under the explicit `Fallback` contract with visible `Key findings`, `Risks`, and `Next actions`
- the one unstable step in this run was draft-session resume presentation behavior:
	- `Load draft sessions` worked and the expected session entry was visible
	- however, this run did not consistently confirm the expected automatic switch back to `Workspace > Review`
	- continuity evidence remained present in the loaded workspace state, but the browser run did not surface a clean `Resumed draft session` confirmation or the expected immediate `Review Queue Plan` / `Filter by source` landing

Operational conclusion:

- the current primary demo story is strong enough to keep as the main stakeholder/PoC flow because reuse, governance handoff, and benchmark evidence all worked on the live stack
- the strongest value proof in the current run is organizational rather than algorithmic novelty:
	- approved reuse avoids starting from zero
	- catalog handoff keeps governance follow-up tied to the correct artifact context
	- benchmarks provide explainable quality evidence instead of only a raw score
- draft-session continuity should remain in the main story, but with a live-demo fallback until the automatic `Review` landing is hardened more conclusively in browser validation

Severity:

- `pass-with-issues`
- overall pilot/demo story is viable
- remaining issue is an `important` UX continuity concern, not a blocker for the broader proof-of-value flow

Evidence of value to the organization:

- reuse of an approved integration artifact was demonstrated directly from `Catalog`, reducing the need to remap from scratch
- governance follow-up was demonstrated as contextual handoff rather than manual navigation/search work
- benchmark comparison and explanation produced a defensible recommendation (`balanced`) with explicit rationale, which is useful in stakeholder review and delivery governance conversations

Recommended next step:

- keep this flow as the primary stakeholder demo
- add one narrow hardening slice for draft-session resume landing behavior before relying on that step as a fully polished continuity showcase