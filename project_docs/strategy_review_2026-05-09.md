# Semantra Strategy Review - 2026-05-09

## Executive assessment

The current direction is sound: Semantra is moving from a one-off schema mapping helper toward a governed semantic integration workbench. The strongest path is to make the canonical layer the center of the product: mapping review discovers semantic facts, the canonical console governs them, and the catalog turns approved mappings into reusable enterprise knowledge.

The work delivered so far supports that path. The system already has the foundations needed for the next stage: canonical mapping payloads, knowledge overlays, mapping set governance, an integration catalog, LLM-assisted review, and now canonical gap approval into overlay. The main risk is not that the direction is wrong; the risk is spreading work across too many epics before closing the governance and canonical source-of-truth gaps.

## What is already aligned with the target product

- Canonical semantic layer exists in runtime and response payloads: `canonical_details`, source/target/shared concepts, and project coverage.
- Knowledge overlay lifecycle exists: validate, save version, activate/deactivate/rollback, audit and runtime reload.
- Mapping set governance exists in an initial form: owner/assignee/review note, statuses, audit trail and version diff.
- Enterprise catalog exists as a reuse/discovery layer over mapping sets and canonical footprints.
- Canonical-only mapping exists as a source-to-business-concept path.
- Canonical Gap Assistant initial MVP exists: detect gaps, ask LLM for controlled suggestion, approve into overlay, refresh runtime.
- Mapping job progress improves review usability for long-running mapping/LLM flows.

These are the right building blocks for EA/MDM/integration governance.

## Main plan corrections

### 1. Treat the canonical model as the product spine

The plan should continue to position canonical concepts as the stable business abstraction between physical systems. This is the right product bet for enterprise value because it enables reuse, impact analysis, glossary governance and cross-system integration memory.

### 2. Keep Canonical Gap Assistant small

Epic 14E should remain a review-side discovery and approval feature. It should not become the full concept management experience. Its job is to produce high-quality, human-reviewed canonical improvement candidates.

### 3. Make Epic 14F the governance console

The new Canonical Concept Management Console should become the main place for:

- concept registry
- aliases and field contexts
- gap review queue
- active overlay status
- usage across catalog/mapping sets
- audit and stewardship metadata
- promotion candidates from overlay to stable glossary

This is the correct direction for EA and MDM users.

### 4. Close Epic 6 before expanding operational features

The remaining approved-only export/run gate should be closed soon. Without it, the product has governance labels but not governance enforcement.

### 5. Do not jump to graph storage yet

Epic 15 is valuable, but it should stay derived and later. First make canonical concepts, catalog usage and overlays queryable enough in SQLite. A graph projection becomes useful after those artifacts are stable.

## Recommended next order

1. Finish Epic 6 status gate for export/run actions over mapping sets.
2. Validate Epic 14E end-to-end with the material master case, including LLM suggestion, approve, rerun mapping and filled canonical path.
3. Implement the first Epic 14F slice: Canonical Console read experience.
4. Complete Epic 13D concept/reuse discovery using the same concept usage data that 14F needs.
5. Add Epic 14D companion schema/description context to improve mapping quality for real enterprise fields.
6. Revisit Epic 12B system-specific virtual targets only after canonical coverage and metadata quality are strong enough.
7. Keep Epic 15 graph projection as a derived analysis layer after canonical console and catalog usage mature.

## Immediate 14F MVP shape

Backend:

- `GET /knowledge/canonical-concepts`
- `GET /knowledge/canonical-concepts/{concept_id}`
- include aliases, base/overlay source, field contexts, active overlay entries, usage count and audit references where available

UI:

- add a Canonical Console tab or product-style Admin subsection
- show concept registry with search/filter
- show concept detail panel
- show active overlay summary
- mirror canonical gap suggestions as a review queue

Governance:

- overlay-first daily changes
- no direct base glossary writes from LLM
- audit every approved alias/concept
- promotion from overlay to stable glossary remains explicit and separate

## Risks and mitigations

- Risk: too many parallel epics. Mitigation: only one primary product slice at a time; keep technical phases as support work.
- Risk: overlay becomes the real source of truth without promotion workflow. Mitigation: add promotion status/reporting before heavy pilot use.
- Risk: canonical concepts duplicate or drift. Mitigation: concept registry must show aliases, usage and near-duplicate candidates before adding merge/rename tools.
- Risk: LLM suggestions feel magical or unsafe. Mitigation: keep closed JSON, candidate context, risk notes and human approve gate.
- Risk: current DB JSON blobs limit discovery. Mitigation: normalize only the read paths needed for 14F/13D, not a full persistence rewrite.

## Bottom line

The plan is the right path. The delivered system is not throwaway work; it is a credible foundation for the EA/MDM direction. The next move should be consolidation: close governance enforcement, validate the canonical gap loop, and turn canonical management into a real console before adding broader automation or graph ambitions.
