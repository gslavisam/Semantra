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

## Recommended Next Step After the Pilot

Once the sprint completes:

1. fix blockers first
2. update the demo script, runbook, and presentation materials to use the strongest validated story
3. run one focused hardening pass based only on pilot findings
4. then decide whether the next priority is deeper concept/reuse discovery, operational hardening, or another bounded feature slice
