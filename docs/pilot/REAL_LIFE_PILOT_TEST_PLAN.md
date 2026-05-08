# Real-Life Pilot Test Plan

## Purpose

This document defines a short live-data validation sprint for Semantra after the current implementation wave.

The goal is not to add new scope during the sprint.

The goal is to validate whether the currently implemented product slices behave correctly on realistic project inputs, especially where source or target inputs arrive as schema-only artifacts rather than clean row datasets.

This plan is intentionally aligned to the code and scope implemented up to 2026-05-05:

- schema-spec upload support
- SQL schema snapshot support with table selection
- canonical-only mapping mode
- improved scoring and bounded LLM rescue behavior
- mapping-set save/version/apply/audit/diff flow
- enterprise catalog list/search/detail/concept lookup
- similar integration discovery
- `Reuse in Workspace` from Catalog

## Recommended Mode

Run this as a time-boxed stabilization sprint, not as an open-ended exploratory effort.

Recommended duration:

- 3 to 5 working days

Recommended rule during the sprint:

- no net-new feature work unless a live-data finding clearly exposes a missing blocker behavior
- allow bug fixes, hardening, diagnostics, and documentation corrections

## Primary Questions

The sprint should answer these questions:

1. Can Semantra ingest and normalize the kinds of inputs real projects actually provide?
2. Does the mapping workflow still behave correctly when data is incomplete, schema-only, or partially ambiguous?
3. Are catalog, governance, and reuse features useful on realistic saved artifacts, not only on synthetic fixtures?
4. Are the remaining failures mostly bugs, product gaps, or simply data-quality issues outside Semantra?

## In Scope

Test these implemented flows with realistic anonymized or sanitized project data:

1. Standard row-data source-to-target workflow
2. Schema-spec source and/or target workflow
3. SQL schema snapshot workflow with table selection
4. Canonical-only source-to-concept workflow
5. Manual review and transformation preview workflow
6. Mapping-set save, status update, apply, audit, and diff workflow
7. Catalog search, detail, concept lookup, similar integrations, and reuse workflow

## Out of Scope

Do not treat these as required for sprint success:

1. New connector development
2. Full enterprise security model or production RBAC
3. CMDB-grade catalog identity model
4. Multi-table end-to-end graph mapping beyond current supported table-selection behavior
5. UI redesign or visual polish work unless a usability issue blocks actual pilot usage

## Test Data Requirements

Use realistic but safe pilot inputs.

Preferred dataset types:

1. Real extracts with masking or anonymization
2. Real schema specs from active delivery work
3. Real SQL DDL snapshots from project environments
4. At least one source that has business-like ambiguity in field names
5. At least one case where the target does not exist yet and canonical-only mapping is the correct workflow

Minimum pilot pack:

1. One Standard case with row data on both source and target
2. One schema-spec case where one side is field-per-row metadata only
3. One SQL snapshot case with multiple tables requiring explicit table selection
4. One canonical-only case with source fields mapped only to glossary concepts
5. One saved integration family with at least two mapping-set versions for catalog, audit, diff, and reuse testing

## Environment Prerequisites

Before running the sprint, verify:

1. FastAPI backend starts locally
2. Streamlit UI starts locally
3. The active Python environment is the workspace venv
4. Optional LLM runtime is configured if ambiguity-band validation is part of the test day
5. Pilot files are stored in a stable local folder with a simple naming convention

Recommended runtime commands:

```powershell
cd d:\py_radno\Semantra
d:/py_radno/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
cd d:\py_radno\Semantra
d:/py_radno/.venv/Scripts/python.exe -m streamlit run streamlit_app.py --server.headless true --server.port 8501
```

## Execution Rules

For each scenario:

1. Record exactly which files were used
2. Record whether the case is row-data, schema-spec, SQL snapshot, or canonical-only
3. Save screenshots only for meaningful states or failures
4. Save mapping sets for scenarios that reach review completion
5. Classify every issue immediately as `blocker`, `important`, or `nice-to-have`

Severity meaning:

1. `blocker`: the scenario cannot be completed or produces materially wrong behavior
2. `important`: the scenario completes but with a significant correctness, trust, or usability defect
3. `nice-to-have`: useful improvement, but not a sprint gate for current pilot validation

## Scenario Matrix

### Track A. Ingestion and Profiling

#### A1. Standard row-data upload

Input:

- source CSV/JSON/XML/XLSX with real rows
- target CSV/JSON/XML/XLSX with real rows

Steps:

1. Upload source and target
2. Run profile step
3. Inspect schema profile summaries

Expected outcome:

1. Upload succeeds without format confusion
2. Row counts, sample values, null ratios, and detected patterns are sensible
3. Review step unlocks normally

#### A2. Schema-spec upload

Input:

- source or target file where each row describes one field rather than one business record

Steps:

1. Upload the spec file
2. Confirm spec detection behavior
3. Inspect resulting schema profile

Expected outcome:

1. File is interpreted as schema metadata, not mistaken for raw business rows
2. Column definitions appear in the normalized schema profile
3. Downstream mapping can proceed even when preview rows are empty or limited

#### A3. SQL snapshot with explicit table selection

Input:

- multi-table SQL DDL snapshot

Steps:

1. Upload SQL snapshot
2. Confirm table discovery output
3. Select one table explicitly
4. Continue to mapping

Expected outcome:

1. System identifies available tables
2. The chosen table is profiled correctly
3. Mapping uses the selected table only

### Track B. Mapping Generation

#### B1. Standard mapping generation

Steps:

1. Start from a profiled Standard case
2. Generate mapping
3. Inspect top selected mappings and candidate alternatives

Expected outcome:

1. Strong obvious fields map correctly
2. Ambiguous fields remain reviewable instead of being blindly overcommitted
3. Confidence and explanation patterns remain coherent

#### B2. Canonical-only mapping generation

Steps:

1. Switch to Canonical mode
2. Upload source-only structure
3. Generate canonical mapping

Expected outcome:

1. No real target dataset is required
2. The result uses canonical concept identifiers as virtual targets
3. Canonical concept grouping and coverage are visible in review

#### B3. Ambiguity-band LLM support

Precondition:

- active LLM runtime enabled

Steps:

1. Run a case with realistic ambiguous columns
2. Inspect whether low-to-mid-confidence ambiguity cases receive bounded LLM help
3. Compare outcome with clear deterministic matches

Expected outcome:

1. Obvious cases remain deterministic-first
2. LLM is used only where ambiguity exists
3. The result stays reviewable and explainable

### Track C. Review and Transformation

#### C1. Manual review of accepted, needs-review, and rejected mappings

Steps:

1. Open Review and Decisions tabs
2. Change a subset of field decisions manually
3. Confirm selected mapping, source-to-concept, and concept-to-target views

Expected outcome:

1. Manual changes remain stable across the session
2. Canonical path displays stay coherent after edits
3. Rejected and unmapped states do not collapse into misleading defaults

#### C2. Transformation preview and generated code

Steps:

1. Add or keep at least one transformation case
2. Run preview
3. Generate Pandas code

Expected outcome:

1. Preview output is generated for row-data cases
2. Warnings are understandable when preview cannot fully execute
3. Generated code aligns with current reviewed mapping decisions

### Track D. Mapping-Set Governance

#### D1. Save and version mapping sets

Steps:

1. Save a reviewed mapping set version
2. Save a second version after a controlled change
3. Update status to `review` or `approved`

Expected outcome:

1. Versions increment correctly for the same mapping set name
2. Owner, assignee, and review note metadata persist correctly
3. Status transitions are visible in saved artifacts

#### D2. Apply, audit, and diff

Steps:

1. Load saved mapping sets
2. Apply one version back into Workspace
3. Load audit trail
4. Load diff between two versions

Expected outcome:

1. Apply restores the expected review state
2. Audit records create/status/apply events correctly
3. Diff isolates `Added`, `Removed`, and `Changed` behavior sensibly

### Track E. Catalog and Reuse

#### E1. Catalog browse and search

Precondition:

- at least several saved mapping sets exist across more than one integration family

Steps:

1. Open Catalog tab
2. Load all integrations
3. Search by integration name
4. Search by canonical concept
5. Filter by source system, target system, business domain, owner, status, and artifact type

Expected outcome:

1. The catalog returns usable discovery results without opening every mapping set individually
2. Filters narrow results correctly
3. Standard and canonical-only artifacts both appear appropriately

#### E2. Catalog detail and governance drilldown

Steps:

1. Open one integration detail
2. Inspect versions, latest approved version, and canonical coverage
3. Open selected version
4. Load audit
5. Load diff

Expected outcome:

1. Catalog detail behaves like a gateway to existing governance artifacts
2. It does not create a conflicting parallel review model
3. Version lineage remains understandable on real saved work

#### E3. Similar integrations and concept lookup

Steps:

1. Open an integration with at least one meaningful neighbor in the catalog
2. Inspect Similar Integrations
3. Open the similar integration
4. Run Concept Lookup for a shared business concept such as `customer.id`

Expected outcome:

1. Similarity results are plausible, not random
2. Shared concepts and metadata overlap make sense to an analyst
3. Concept lookup returns reuse evidence across multiple integrations when appropriate

#### E4. Reuse in Workspace

Steps:

1. From Catalog detail, select a concrete version
2. Click `Reuse in Workspace`
3. Move to Workspace Review and Decisions tabs

Expected outcome:

1. The selected mapping-set version appears in active review state
2. Review panels, decisions, and canonical summaries populate coherently
3. The reuse flow behaves as a continuation path, not only as a metadata link

### Track F. Failure and Edge Cases

#### F1. Partial or messy metadata case

Input:

- fields with cryptic ERP names, abbreviations, and sparse descriptions

Expected outcome:

1. System still produces reviewable candidates
2. Weak cases remain visible as ambiguous instead of looking falsely precise

#### F2. Schema-only with no preview rows

Input:

- source or target where no real rows are available

Expected outcome:

1. System still supports profiling and mapping where expected
2. Preview limitations are visible but not misleading

#### F3. Large but still practical pilot file

Input:

- one moderately large source or target file still expected in pilot conditions

Expected outcome:

1. Upload and review remain usable
2. UI does not become misleading or unstable under normal pilot scale

## Daily Execution Cadence

Recommended daily loop:

1. Select 2 to 4 scenarios for the day
2. Run them fully through UI and, when useful, confirm API behavior directly
3. Save all meaningful artifacts in the catalog if the scenario reaches a stable state
4. Record findings immediately
5. Triage findings before starting the next scenario batch

## Result Logging Template

Use one record per scenario.

```markdown
### Scenario ID
- Date:
- Tester:
- Dataset(s):
- Input type: row-data | schema-spec | sql-snapshot | canonical-only
- LLM enabled: yes | no
- Outcome: pass | pass-with-issues | fail
- Severity if failed: blocker | important | nice-to-have
- Observed behavior:
- Expected behavior:
- Screenshot or artifact reference:
- Saved mapping set IDs or catalog integration names:
- Recommendation:
```

## Triage Rules After the Sprint

After the sprint, group findings into these buckets:

1. Product correctness defects
2. Trust/explainability defects
3. Usability friction in review or catalog flows
4. Data-quality issues external to Semantra
5. Feature gaps that should become explicit future epic items

Recommended decision rule:

1. Fix all `blocker` findings before widening pilot scope
2. Fix `important` findings if they affect trust, reuse, or reviewability on recurring project patterns
3. Defer `nice-to-have` findings into roadmap or polish backlog unless they cluster around one recurring pain point

## Exit Criteria

Treat the pilot-validation sprint as successful when all of the following are true:

1. At least one scenario from each track A through E has been executed on realistic data
2. Standard and Canonical-only flows both complete successfully on real project-shaped inputs
3. Save/version/apply/audit/diff flows work on real saved artifacts
4. Catalog search/detail/concept lookup/similarity/reuse flows work on real saved artifacts
5. Remaining open findings are mostly `important` or `nice-to-have`, not `blocker`

## Recommended Next Step After This Plan

Once this live-data sprint completes:

1. run one short defect-fix pass based only on pilot findings
2. reassess whether to open Epic 13D or to prioritize hardening and guardrails first
3. only resume broader feature development after the pilot findings are classified and the blockers are closed# Real-Life Pilot Test Plan

## Purpose

This document defines a practical pilot test for the current Semantra solution before deeper refactoring or the next major feature wave.

The goal is not load testing. The goal is to validate whether the current product shape can handle realistic source-to-target mapping review with real business metadata, ambiguous field names, canonical concept support, and a manageable amount of manual intervention.

## What This Test Should Prove

At the end of the pilot, you should be able to answer these questions:

- Can the current ranking engine produce useful first-pass mappings on realistic schemas?
- Does the trust layer help an analyst understand why a field was matched?
- Does the canonical layer add real value, or just extra noise?
- How much manual correction is still needed?
- Are transformation suggestions practical enough for analyst review?
- Is the current UI still usable when both source and target have several dozen columns?

## Recommended Test Scope

Use one source and one target dataset per scenario.

Recommended shape per dataset:

- 25 to 60 columns per side for the first pass
- 300 to 3,000 rows per side
- Realistic but representative extracts, not full production dumps
- A mix of easy matches, ambiguous matches, mismatches, and transformation-needed fields

Do not start with the largest available extract. Start with a representative slice that preserves naming patterns, value formats, and domain-specific abbreviations.

## Test Scenarios

Run the pilot in three scenarios. If time is limited, Scenario 1 and Scenario 2 are the minimum useful set.

### Scenario 1: Clean Domain Mapping

Purpose:
- Confirm that the current engine handles a realistic but relatively clean mapping case.

Recommended shape:
- 25 to 40 source columns
- 25 to 40 target columns
- Mostly business-friendly names with some aliases

Expected content:
- Customer identifiers
- Customer contact fields
- Address fields
- Sales or invoice fields
- A few date, amount, status, and code fields

Success expectation:
- Many top-1 matches should be obviously correct
- Canonical coverage should be meaningful
- Only a limited set of fields should require manual review

### Scenario 2: Noisy ERP or Legacy Naming

Purpose:
- Test whether metadata knowledge, canonical glossary, and naming heuristics help when names are poor.

Recommended shape:
- 30 to 60 source columns
- 30 to 60 target columns
- Source should include technical or ERP-style names

Expected content:
- Abbreviations such as business short codes or legacy aliases
- Technical column names such as document IDs, order numbers, payment terms, storage locations, shipping points
- A mix of well-known ERP aliases and organization-specific naming

Success expectation:
- Top-1 accuracy will likely drop relative to Scenario 1
- Canonical coverage should still reveal useful concept alignment
- The trust layer should help explain why the engine is leaning toward certain targets

### Scenario 3: Imperfect Real-World Mapping

Purpose:
- Validate behavior when the source and target are not cleanly compatible.

Recommended shape:
- 25 to 50 source columns
- 25 to 50 target columns

Expected content:
- Fields that have no valid target
- Fields that require transformation
- Several one-to-many or many-to-one business interpretation problems
- Partial conceptual overlap between source and target

Success expectation:
- The system should not force false certainty
- More fields should land in `needs_review`
- Unmatched or weakly matched fields should still produce understandable alternatives and explanations

## Field Matrix To Include

Each scenario should contain a deliberate mix of these field types.

### Category A: Straightforward Matches

Examples:
- `customer_id` -> `customer_id`
- `invoice_date` -> `billing_date`
- `phone_number` -> `customer_phone`

Purpose:
- Baseline sanity check for ranking quality

### Category B: Alias or Synonym Matches

Examples:
- `sold_to_party` -> `customer_id`
- `client_mail` -> `customer_email`
- `supplier_no` -> `vendor_id`

Purpose:
- Validate metadata dictionary and canonical glossary influence

### Category C: Technical or ERP Matches

Examples:
- `EBELN`, `VBELN`, `ZTERM`, `WAERS`, `LGORT`, `VSTEL`

Purpose:
- Validate canonical alias coverage and industry shorthand handling

### Category D: Ambiguous Fields

Examples:
- `id`
- `status`
- `date`
- `reference`
- `number`

Purpose:
- Force analyst review and check whether explanations are useful

### Category E: Fields Requiring Transformation

Examples:
- Email to display name extraction
- Date string normalization
- Currency or numeric formatting cleanup
- Combined name or split address patterns

Purpose:
- Validate transformation suggestion and preview flow

### Category F: No-Match Fields

Examples:
- Source-only operational flags
- Temporary integration columns
- Free-text notes with no target equivalent

Purpose:
- Validate that the engine can fail safely and still remain explainable

## Pre-Test Setup Checklist

- Confirm backend starts cleanly
- Confirm Streamlit UI can reach the backend
- Confirm admin token is set if protected flows are needed
- Confirm canonical glossary is loaded
- Confirm no stale overlay is accidentally active unless the scenario explicitly needs it
- Confirm the test datasets do not contain data that cannot be handled in local pilot conditions

Optional but recommended:

- Save each scenario as a named benchmark-friendly artifact
- Prepare one scenario with no overlay and one scenario with a targeted overlay

## Recommended Execution Order

### Pass 1: UI-Led Analyst Review

Use the Streamlit UI first.

Steps:

1. Upload source and target datasets.
2. Review selected mappings in the trust layer.
3. Review ranked candidates for ambiguous fields.
4. Inspect canonical coverage and `source -> concept -> target` views.
5. Mark obvious good matches and list fields that require manual intervention.
6. For a small set of transformation-needed fields, inspect or generate transformation suggestions.
7. Save the first-pass mapping set.

Outcome:
- This pass measures analyst usability and explainability.

### Pass 2: API-Led Payload Inspection

Use the API after the UI pass.

Endpoints to use:

- `POST /upload`
- `POST /mapping/auto`
- `POST /mapping/preview`
- `GET /knowledge/overlays`
- `POST /knowledge/reload`
- `GET /knowledge/canonical-glossary/export`

What to inspect:

- `mappings`
- `ranked_mappings`
- `canonical_details`
- `canonical_coverage`
- explanation lines

Outcome:
- This pass confirms whether the backend payload is structurally useful enough for review and export workflows.

### Pass 3: Overlay-Assisted Rerun

Run one scenario again with a small, deliberate overlay.

Suggested overlay usage:

- 5 to 15 targeted aliases only
- Prefer terms that were weak or ambiguous in Pass 1
- Optionally include `concept_alias` rows for canonical concept extension

Outcome:
- This pass shows whether overlay investment produces measurable improvement.

## Metrics To Record

Track at least these metrics for each scenario.

### Core Mapping Metrics

- Total source fields
- Fields with a valid target in business truth
- Fields with no valid target in business truth
- Top-1 correct matches
- Top-3 contains correct target
- False confident matches
- Fields left in `needs_review`

### Review Efficiency Metrics

- Number of manual target changes
- Number of manually rejected suggestions
- Number of fields that needed transformation review
- Approximate review time per scenario

### Canonical Layer Metrics

- Source canonical coverage ratio
- Target canonical coverage ratio
- Project canonical coverage ratio
- Number of shared concepts
- Number of concept groups that were useful to the analyst

### Trust Layer Quality Metrics

- Explanations judged useful
- Explanations judged weak or generic
- Fields where explanations clearly helped analyst confidence
- Fields where explanations were misleading or noisy

## Success Criteria

Treat these as pilot thresholds, not production SLAs.

### Recommended Thresholds For Scenario 1

- Top-1 accuracy on mappable fields: 70% or more
- Top-3 contains correct target: 85% or more
- False confident matches: low and reviewable
- Canonical coverage: materially useful for at least one-third of the schema
- Analyst can finish first-pass review without losing track of the UI

### Recommended Thresholds For Scenario 2

- Top-1 accuracy on mappable fields: 50% or more
- Top-3 contains correct target: 75% or more
- Canonical coverage should still reveal meaningful shared concepts
- Overlay-assisted rerun should show visible improvement on targeted fields

### Recommended Thresholds For Scenario 3

- System should prefer uncertainty over confident false matches
- `needs_review` behavior should feel appropriate, not excessive noise
- No-match cases should be identifiable without forcing a misleading target

## Failure Patterns To Watch For

Record these explicitly if they appear.

- Over-reliance on lexical similarity when business meaning differs
- Weak handling of generic names such as `id`, `status`, `code`, `number`
- Canonical layer adding labels but not improving decisions
- Explanations that repeat the score instead of explaining the business reason
- Transformation suggestions that are syntactically valid but operationally weak
- UI fatigue when reviewing several dozen fields
- Too much analyst effort to correct obviously related aliases

## Result Logging Template

Use the template below for each scenario.

### Scenario Summary

```md
Scenario Name:
Business Domain:
Source Dataset:
Target Dataset:
Row Counts:
Column Counts:
Overlay Active: yes/no
Canonical Glossary Version Note:

Overall Outcome:
- Useful / Mixed / Not useful

Top Observations:
-
-
-
```

### Field-Level Review Template

```md
| Source Field | Expected Target | Top-1 Suggested | Correct Top-1 | Correct In Top-3 | Confidence Label | Canonical Path Useful | Explanation Useful | Transformation Needed | Manual Change Needed | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| sold_to_party | customer_id | customer_id | yes | yes | high_confidence | yes | yes | no | no | |
| client_mail | customer_email | email | no | yes | medium_confidence | yes | mixed | no | yes | generic lexical bias |
```

### Aggregated Metrics Template

```md
Total Source Fields:
Mappable Fields:
No-Match Fields:
Top-1 Correct:
Top-3 Contains Correct:
Manual Changes Required:
Fields Left In Needs Review:
Source Canonical Coverage:
Target Canonical Coverage:
Project Canonical Coverage:
Shared Concepts:
Review Time:
```

### Refactor Signal Template

After each scenario, answer these directly.

```md
What worked well:
-

What failed repeatedly:
-

What is mainly a model/ranking issue:
-

What is mainly a trust-layer or UI issue:
-

What is mainly a glossary/overlay issue:
-

What should be fixed before broader pilot rollout:
-
```

## Final Recommendation Logic

At the end of all scenarios, classify the current solution into one of these buckets.

### A: Ready For Controlled Pilot

Use this if:

- Scenario 1 is strong
- Scenario 2 is acceptable with overlay help
- Scenario 3 fails safely
- Analysts can complete review without major friction

### B: Good For Demo And Internal Evaluation, Not Yet For External Pilot

Use this if:

- Ranking has promise but needs too many manual fixes
- Canonical layer is informative but not consistently decision-helpful
- UI becomes heavy with several dozen columns

### C: Refactor Before Serious Pilot

Use this if:

- Trust layer is too hard to review at realistic schema size
- False confident matches are common
- Explanations do not help resolve ambiguity
- Overlay and canonical support do not materially improve outcomes

## Recommended Immediate Next Step

Start with one realistic source-target pair in Scenario 1 and one noisy pair in Scenario 2.

If both are promising, continue to Scenario 3.
If either one fails badly, use the logged results to prioritize the refactor phases before expanding the pilot.