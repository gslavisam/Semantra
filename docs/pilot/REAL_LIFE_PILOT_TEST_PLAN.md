# Real-Life Pilot Test Plan

## Purpose

This document defines a practical pilot-validation sprint for the current Semantra product state.

It is aligned to the product shape as of 2026-05-29:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

The goal is not to add new scope during the sprint. The goal is to validate whether the implemented product behaves correctly on realistic, sanitized project inputs, whether the current governance and reuse model is usable in real analyst work, and whether the current product already demonstrates value worth presenting to the organization.

## What the Pilot Should Prove

At the end of the sprint, the team should be able to answer:

1. Can Semantra ingest realistic row-data, schema-spec, SQL snapshot, and canonical-only inputs?
2. Does the review loop remain trustworthy when data is ambiguous or incomplete?
3. Do governance gates behave correctly on saved artifacts?
4. Is the Catalog useful as a reuse surface, not just as a metadata list?
5. Does the Canonical Console support a practical stewardship loop on real findings?
6. Which flows are strong enough today to become the primary proof-of-concept and live-demo story?

## Recommended Mode

Run this as a short stabilization sprint, not as an open-ended exploration.

Recommended duration:

- 3 to 5 working days

Recommended rules:

- no net-new feature work unless a pilot finding exposes a true blocker
- allow bug fixes, diagnostics, hardening, and documentation corrections
- save artifacts whenever a scenario reaches a stable review state
- classify issues immediately as `blocker`, `important`, or `nice-to-have`
- capture value evidence as explicitly as defects: reuse saved time, avoided remapping, clearer governance handoff, stronger benchmark explanation, or easier stakeholder explanation

## Environment Prerequisites

Before starting, verify:

1. the workspace virtual environment is available
2. FastAPI and Streamlit both start locally
3. admin token is available if protected flows are enabled
4. optional LLM runtime is configured only if ambiguity validation or transformation generation is being tested
5. pilot inputs are stored in a stable local folder with a clear naming convention

Recommended startup command:

```powershell
cd d:\py_radno\Semantra
.\start_semantra.ps1
```

Default local URLs:

- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:8501`

## Pilot Data Pack

Use realistic but safe project-shaped data.

Preferred input types:

1. masked or anonymized business extracts
2. real schema-spec files from active delivery work
3. SQL DDL snapshots from real environments
4. at least one source with ambiguous or cryptic field names
5. at least one case where no target exists yet and canonical-first work is the right path

Minimum pilot pack:

1. one standard source-to-target case with row data on both sides
2. one schema-spec case where at least one side is field-per-row metadata
3. one SQL snapshot case with multiple tables requiring explicit table selection
4. one canonical-only case with source fields mapped only to canonical concepts
5. one integration family with at least two saved mapping-set versions for audit, diff, and reuse testing

## Scenario Matrix And Fixture Anchors

The track list below is sufficient for the main proof-of-value pilot loop, but by itself it is not a full capability-coverage matrix.

Before this addendum, the plan did not explicitly name the repo-local upload files or seeded artifacts for each scenario. Use the matrix below to keep the pilot repeatable and to remove ambiguity about which fixtures to upload.

### Core proof-of-value scenarios

1. `A1 Standard row-data baseline`
	- Track coverage: `A`, `B`, `C`, `F`
	- Upload files:
	  - source: `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv`
	  - target: `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`
	- Mode: `Standard`
	- Notes: use this as the default workspace state for review, decisions, preview, code generation, mapping-set governance, and benchmark-save checks.

2. `A2 Schema-spec baseline`
	- Track coverage: `A`
	- Upload files:
	  - source: `ui_fixtures/showcase_supplier_master/showcase_supplier_source_spec.csv`
	  - target: `ui_fixtures/showcase_supplier_master/showcase_supplier_target_spec.csv`
	- Mode: `Standard` with `Schema spec` on both sides
	- Notes: use this to prove field-per-row metadata handling instead of business-row ingest.

3. `A3 SQL snapshot baseline`
	- Track coverage: `A`
	- Upload files:
	  - source: `ui_fixtures/showcase_material_master/showcase_material_source_multi.sql`
	  - target: `ui_fixtures/showcase_material_master/showcase_material_target_multi.sql`
	- Table selection:
	  - source table: `mara_core`
	  - target table: `product_dim`
	- Mode: `Standard`
	- Notes: this is the repeatable multi-table table-selection check for the pilot.

4. `A4 Canonical-only baseline`
	- Track coverage: `A`, `E`
	- Upload files:
	  - source: `ui_fixtures/showcase_supplier_master/showcase_supplier_source_spec.csv`
	  - target: none
	- Mode: `Canonical`
	- Notes: use this for source-to-canonical review, canonical-gap surfacing, and stewardship follow-up without a real target dataset.

5. `A5 LLM ambiguity comparison`
	- Track coverage: `A`
	- Upload files:
	  - source: `ui_fixtures/showcase_supplier_master/showcase_supplier_source.csv`
	  - target: `ui_fixtures/showcase_supplier_master/showcase_supplier_target.json`
	- Mode: `Standard`
	- Notes: run once with `Use LLM validation = off` and once with `Use LLM validation = on`, then compare ambiguity handling, explanation quality, and bounded fallback behavior.

### Core governed-workflow scenarios

6. `B1 Review, preview, and governance gate`
	- Track coverage: `B`
	- Upload files: none; continue from `A1`
	- Notes: verify trust-layer explanations, source-to-concept and concept-to-target review, advisory preview before full approval, and accepted-only code-generation gating.

7. `B2 Decisions, export/import, and refinement`
	- Track coverage: `B`
	- Upload files: none; continue from `A1`
	- Notes: perform at least one manual override, export and import decisions as JSON or Excel, then validate refinement accept/discard behavior after an output artifact exists.

8. `B3 Transformation authoring and test sets`
	- Track coverage: `B`
	- Upload files: none; continue from `A1`
	- Notes: author or edit a transformation, save a transformation test set, load it, and run it after decisions are accepted.

9. `C1 Mapping-set governance`
	- Track coverage: `C`
	- Upload files: none; continue from `A1`
	- Notes: save version `v1`, make one controlled change, save `v2`, move status through `draft`, `review`, and `approved`, inspect audit and diff, then reuse the approved version.

10. `C2 Draft-session continuity`
	- Track coverage: `C`
	- Upload files: either continue from `A1` and save a fresh draft session, or use seeded `customer-draft-session` after running `backend/scripts/bootstrap_operational_smoke.ps1`
	- Notes: verify resume landing, cleared stale guidance outputs, and restored stable review contract.

11. `D1 Catalog approved reuse`
	- Track coverage: `D`
	- Upload files: none; use seeded `approved-customer-reuse-smoke`, or create it from `C1`
	- Notes: confirm detail load, `Latest approved version`, active `Reuse in Workspace`, and successful apply back into the workspace.

12. `D2 Catalog diff handoff`
	- Track coverage: `D`
	- Upload files: none; use seeded `browser-diff-focus`
	- Notes: load the version diff and confirm `Open current diff review focus` lands in `Workspace > Review` with the intended diff scope.

13. `D3 Catalog governance handoff`
	- Track coverage: `D`, `E`
	- Upload files: none; use seeded `Stewardship Smoke Sync`
	- Notes: confirm `Open Stewardship` lands in `Governance > Stewardship` instead of a generic governance surface.

14. `E1 Canonical queue and concept detail`
	- Track coverage: `E`
	- Upload files: none if `A4` already exists; otherwise upload `ui_fixtures/showcase_supplier_master/showcase_supplier_source_spec.csv` in `Canonical` mode first
	- Notes: inspect registry search/filtering, concept detail, canonical-gap queue, and stewardship item detail.

15. `E2 Overlay promotion and glossary sync`
	- Track coverage: `E`
	- Upload files:
	  - overlay CSV: `ui_fixtures/knowledge_demo_overlay.csv`
	- Notes: validate overlay upload, review candidate entries, and promote to the glossary when the state is ready.

16. `F1 Benchmark save and run`
	- Track coverage: `F`
	- Upload files: none; continue from accepted `A1`
	- Notes: save the current mapping as a benchmark, then run it or compare scoring profiles.

17. `F2 Benchmark explanation and correction impact`
	- Track coverage: `F`
	- Upload files: none; use seeded `operational-smoke-benchmark`
	- Notes: run `Compare scoring profiles`, generate explanation, then run correction impact.

18. `F3 Reusable learning loop`
	- Track coverage: `F`
	- Upload files: none; continue from accepted `A1`
	- Notes: save a reviewed correction, generate a reusable-rule candidate, promote it, then rerun the relevant benchmark or mapping check.

### Additional capability-coverage scenarios

19. `G1 Companion metadata enrichment`
	- Coverage goal: broader ingestion coverage beyond the main pilot story
	- Upload files:
	  - source dataset: `ui_fixtures/smoke_source.csv`
	  - source companion metadata: `ui_fixtures/smoke_source_companion.csv`
	  - target dataset: `ui_fixtures/smoke_target.csv`
	- Notes: the repo currently includes a repeatable source-companion fixture but does not include a dedicated target-companion fixture; if target-companion validation is in scope, add a delivery-local target companion CSV and record its path in the test log.

20. `G2 Async mapping job lifecycle`
	- Coverage goal: mapping runtime hardening
	- Upload files:
	  - source: `ui_fixtures/showcase_material_master/showcase_material_source.csv`
	  - target: `ui_fixtures/showcase_material_master/showcase_material_target.json`
	- Notes: start an async job, poll progress, cancel once, then rerun to completion.

21. `G3 Output artifact matrix`
	- Coverage goal: broader output coverage
	- Upload files: none; continue from accepted `A1`
	- Notes: validate Pandas, PySpark, and dbt starter outputs plus their warning surfaces.

22. `G4 Mapping Analysis audio`
	- Coverage goal: broader review-copilot coverage
	- Upload files: none; continue from `A1`
	- Notes: generate `Mapping Analysis Overview` first, then validate optional narration/audio generation if the runtime is configured.

23. `G5 Explicit LLM on/off comparison`
	- Coverage goal: bounded AI behavior
	- Upload files: reuse `A5`
	- Notes: compare deterministic-only and LLM-assisted runs for confidence presentation, explanation quality, and fallback clarity.

24. `G6 Overlay lifecycle state machine`
	- Coverage goal: broader governance coverage
	- Upload files:
	  - overlay CSV: `ui_fixtures/knowledge_demo_overlay.csv`
	- Notes: validate `validated -> active -> archive` constraints plus rollback, reload, and reseed if the environment is configured for those flows.

## Test Tracks

### Track A. Workspace ingestion and mapping

Validate:

- row-data upload
- schema-spec upload
- SQL snapshot upload with table selection
- standard mapping generation
- canonical-only mapping generation
- ambiguity-band LLM help when enabled

Expected outcomes:

- uploads are interpreted correctly
- schema profiles are usable downstream
- obvious matches remain deterministic-first
- ambiguous cases remain reviewable instead of looking falsely precise
- canonical-only mode works without a real target dataset

### Track B. Review, decisions, preview, and code generation

Validate:

- trust-layer explanations
- source-to-concept and concept-to-target views
- manual target adjustment
- transformation authoring
- advisory preview
- Pandas code generation

Expected outcomes:

- explanations remain coherent after manual edits
- preview can be used before final approval
- code generation respects governance gating and requires accepted active decisions
- transformation warnings remain understandable when execution is partial or risky

### Track C. Mapping-set governance and reuse

Validate:

- save mapping-set version
- save another version after a controlled change
- update status through `draft`, `review`, and `approved`
- apply an approved version back into Workspace
- inspect audit and diff views

Expected outcomes:

- version lineage is understandable
- owner, assignee, and review note persist correctly
- apply/reuse respects approval gating
- audit and diff reflect real change history

### Track D. Catalog and discovery

Validate:

- integration browse and search
- concept-centric lookup
- integration detail drilldown
- similar integrations
- `Reuse in Workspace`
- version diff handoff into `Workspace Review`
- governance handoff into `Canonical` and `Stewardship`

Expected outcomes:

- the catalog acts as a practical discovery surface
- approved versions can be reused back into the active review loop
- concept-centric lookup exposes real reuse evidence
- similarity signals are plausible, not random
- review handoff lands on the intended `Workspace` section and preserves diff-source scope without forcing a narrow source filter
- governance handoff lands on the intended `Canonical` or `Stewardship` surface and does not inherit stale governance filters

### Track E. Canonical Console and stewardship

Validate:

- canonical concept registry search and filtering
- concept detail drilldown
- canonical-gap queue review
- stewardship item detail
- overlay-promotion review and promote-to-glossary flow when appropriate

Expected outcomes:

- concept detail is understandable on real artifacts
- queue and stewardship states are coherent
- promotion is explicit and governed
- canonical governance behaves like a real operator workflow, not a hidden debug surface

### Track F. Benchmarks and reusable learning

Validate:

- save current mapping as benchmark
- load and run a saved benchmark dataset
- correction-impact run
- reviewed correction save flow
- reusable-rule candidate and promotion flow if the scenario supports it

Expected outcomes:

- benchmark save/run obey governance gates
- run history is inspectable
- correction-based learning only persists after closed review outcomes
- reusable learning behaves like a governed feedback loop, not as uncontrolled implicit memory

## Severity Rules

Use these severity levels:

1. `blocker`: the scenario cannot be completed or produces materially wrong behavior
2. `important`: the scenario completes but trust, correctness, or reuse is meaningfully compromised
3. `nice-to-have`: useful improvement, but not a gate for the current pilot

## Logging Template

Use one record per executed scenario.

```markdown
### Scenario ID
- Date:
- Tester:
- Dataset(s):
- Upload files or seeded artifacts:
- Selected tables if applicable:
- Input type: row-data | schema-spec | sql-snapshot | canonical-only
- LLM enabled: yes | no
- Area: Workspace | Canonical Console | Catalog | Benchmarks | Admin / Debug
- Outcome: pass | pass-with-issues | fail
- Severity if failed: blocker | important | nice-to-have
- Observed behavior:
- Expected behavior:
- Screenshot or artifact reference:
- Saved mapping set IDs or integration names:
- Evidence of value to the organization:
- Recommendation:
```

## Daily Cadence

Recommended daily loop:

1. select 2 to 4 scenarios for the day
2. execute them fully through the UI and, when useful, confirm the backend behavior directly
3. save artifacts when the scenario reaches a stable state
4. triage findings before starting the next batch
5. keep screenshots only for meaningful states or failures

## Exit Criteria

Treat the sprint as successful when all of the following are true:

1. at least one real scenario from each track A through F has been executed
2. both Standard and Canonical flows complete on realistic inputs
3. mapping-set save/version/apply/audit/diff work on real saved artifacts
4. Catalog search/detail/reuse works on real saved artifacts
5. Canonical Console stewardship actions are understandable and operable on real findings
6. remaining open issues are mostly `important` or `nice-to-have`, not `blocker`
7. at least one stable end-to-end story is strong enough to be reused in presentation and live-demo form without improvisation
8. if the sprint goal includes broader capability validation rather than only the main proof-of-value loop, at least three additional scenarios from `G1` through `G6` have been executed, including one operational state-lifecycle scenario (`G2` or `G6`) and one bounded-AI comparison (`A5` or `G5`)

## Recommended Next Step After the Pilot

Once the sprint completes:

1. fix blockers first
2. update the demo script, runbook, and presentation materials to use the strongest validated story
3. run one focused hardening pass based only on pilot findings
4. then decide whether the next priority is deeper concept/reuse discovery, operational hardening, or another bounded feature slice
