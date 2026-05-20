# Knowledge Expansion Wave

## Purpose

This document proposes the next structured Semantra wave for expanding vendor-specific knowledge coverage and extracting higher-quality canonical concepts from that coverage.

For SAP specifically, the source of truth for this wave is the full workbook inventory in `metadata_dict/sap_tables_mostUsed.xlsx`, not the small showcase fixtures. The showcase fixtures are only benchmark slices used to measure whether the larger SAP ingest and SAP-to-canonical alignment work is improving actual mapping quality.

It is intentionally not a proposal to turn Semantra into a generic ontology or graph program. The goal is narrower and more practical:

- ingest more exact vendor field knowledge
- improve mapping quality on real system-specific schemas
- mine canonical gaps from stronger knowledge coverage
- repeat the same workflow across multiple enterprise systems

## Why Now

Semantra now has enough foundations in place for a larger knowledge-refresh wave to be worth the effort:

- the knowledge runtime and canonical runtime already exist as product surfaces
- canonical stewardship and promotion flows already exist
- recent SAP-specific mapping tuning showed that stronger knowledge coverage has immediate impact on final mapping quality
- the repo already contains SAP, QAD, and Workday knowledge sources, plus a growing set of real fixtures

The next quality gain is therefore not only more engine tuning. It is broader, better-structured knowledge coverage with disciplined canonical extraction.

## Core Boundary

The wave only makes sense if Semantra keeps a clear separation between the knowledge layer and the canonical layer.

### Knowledge layer

The knowledge layer should be broad, system-aware, and exact.

It should contain:

- vendor-specific field names
- object and table context
- field descriptions
- module or functional area context
- multilingual aliases
- exact technical variants from public or curated specifications

It is acceptable for the knowledge layer to be large and uneven as long as provenance is preserved and ingestion is reproducible.

### Canonical layer

The canonical layer should remain narrower, business-normalized, and intentionally curated.

It should contain:

- cross-system business concepts
- durable aliases that generalize beyond one vendor field name
- business-facing meanings that improve reuse across projects and systems

It should not become a dump of every vendor-specific technical field.

## Non-Goals

This wave should not try to do all of the following at once:

- redesign the full persistence model
- replace the current canonical governance workflow
- build a graph database layer
- scrape the public internet without provenance or source discipline
- auto-promote vendor specs directly into the canonical registry

## Proposed Wave Structure

### Phase 0. Source inventory and baseline

Before expanding anything, Semantra should establish a baseline:

- what SAP source artifacts already exist locally
- which of them are authoritative enough to drive refreshes
- what the current coverage baseline is for real SAP fixtures
- which current mappings fail because of missing knowledge vs missing canonical concepts vs assignment/scoring behavior

Primary outputs:

- source inventory
- provenance rules
- baseline coverage and benchmark report

### Phase 1. SAP-first knowledge ingestion

SAP should be the first wave because it has the largest known immediate ROI and the broadest available source set.

The goal is not to manually patch thousands of rows into a single CSV file. The goal is to define a repeatable ingest path from source specs into the Semantra knowledge runtime.

Concretely, that means normalizing the `Tbls_Clm` sheet from `metadata_dict/sap_tables_mostUsed.xlsx` as the primary SAP field inventory. At the moment that sheet contains 10,739 rows of SAP table-column records, which is the real SAP coverage surface for the wave.

Primary outputs:

- SAP field/object/context knowledge pack
- normalized staging format
- generated curated output for matching runtime
- dedupe and alias normalization rules
- SAP field-to-canonical candidate map across the full workbook inventory

### Phase 2. SAP canonical gap mining

Once SAP knowledge coverage is wider, Semantra should explicitly mine canonical candidates from it.

That means separating:

- fields that stay vendor-specific and knowledge-only
- fields that clearly map to already existing canonical concepts
- fields that expose real missing business concepts worth canonical promotion

Primary outputs:

- SAP canonical-gap queue
- promotion candidate shortlist
- explicit reject/keep-in-knowledge decisions

The intended unit of work here is not one fixture at a time. It is the complete SAP workbook inventory, processed into:

- fields that already map cleanly to existing canonical concepts
- fields that remain SAP-specific and should stay knowledge-only
- fields that expose real missing canonical business concepts

### Phase 3. Evaluation and scoring follow-up

The knowledge refresh wave must stay benchmark-driven.

For each major SAP domain slice, Semantra should track:

- coverage rate of `knowledge` signal
- coverage rate of `canonical` signal
- top-1 ranking accuracy
- final one-to-one assignment accuracy
- reduction in low-confidence mappings

This phase is where score-fusion or assignment tweaks should be justified by measured outcomes rather than intuition.

### Phase 4. Extend the same pipeline to other systems

Only after the SAP-first model works should the same approach be applied to:

- Workday
- QAD
- QuickBooks
- other already collected vendor sources in the repo

The goal is not to hand-craft a new workflow for every system. The goal is to prove one ingestion, provenance, evaluation, and promotion model that can be reused.

### Phase 5. External/public spec expansion

After internal and already-collected assets are stabilized, Semantra can widen its source base with public vendor references and exact public specifications.

This should only happen with explicit provenance rules.

## Ingestion Rules

### Raw vs staged vs curated

The wave should distinguish between three levels:

- raw source files from vendors or collected references
- staged normalized records with provenance metadata
- curated runtime outputs that Semantra actually uses for matching

This separation matters because it keeps future refreshes reproducible.

### Provenance metadata

Every staged record should preserve at least:

- system
- module or domain
- object or table
- field name
- field description
- source artifact
- source type
- whether the source is public or internal
- last verification date

### Avoid manual bulk editing

Manual row-by-row editing of `metadata_dict.csv` is still acceptable for small targeted fixes.

It is not the right operating model for a 10k+ SAP field refresh.

Bulk knowledge refreshes should move through generated or semi-generated ingest steps so the refresh can be rerun later.

## Canonical Promotion Rules

Canonical promotion should stay stricter than knowledge ingestion.

Promote to canonical only when at least one of the following is true:

- the concept is clearly business-facing and cross-system
- the same concept appears across multiple vendors or datasets
- the concept materially improves reuse, governance, or concept-centric discovery

Keep in knowledge-only when the field is:

- too technical
- too vendor-specific
- configuration-specific without cross-system reuse value
- ambiguous without stronger business framing

## Evaluation Rules

The wave should be measured with a stable KPI set.

Recommended KPIs:

- percent of benchmark fields with non-zero `knowledge`
- percent of benchmark fields with non-zero `canonical`
- top-1 candidate accuracy
- final selected mapping accuracy
- percent of mappings above auto-accept threshold
- percent of failures attributable to missing knowledge
- percent of failures attributable to missing canonical concepts
- percent of failures attributable to assignment or score-fusion behavior

## Initial Backlog for the Wave

### SAP-first backlog

- inventory existing SAP source artifacts already present in the repo or nearby inputs
- define one staged schema for vendor field records and provenance
- generate a first SAP knowledge pack from the existing sources
- generate SAP-to-canonical candidate mappings across the full `sap_tables_mostUsed.xlsx` inventory
- classify the SAP inventory into mapped-to-existing-canonical, knowledge-only, and canonical-gap buckets
- run benchmark slices only as regression measurement for supplier, customer, material, finance, and HR fixtures
- produce a first SAP canonical-gap report backed by the full workbook inventory rather than only by fixtures

### Multi-system extension backlog

- inventory Workday, QAD, and QuickBooks source assets already collected
- normalize them into the same staging model
- compare concept overlap and gaps against the SAP-first wave
- identify where canonical concepts generalize across vendors vs remain vendor-local

### External source backlog

- document which public sources are legally and operationally safe to use
- capture provenance in the same staging model
- avoid unverified or weakly structured sources until the ingestion model is stable

## Exit Criteria for the First Wave

The first wave should be considered successful when all of the following are true:

- SAP knowledge ingestion is repeatable and not dependent on ad hoc CSV editing
- SAP benchmark fixtures show a measurable coverage and quality increase
- canonical-gap candidates can be produced from the expanded SAP layer in a controlled way
- the same workflow is ready to be reused for Workday, QAD, and QuickBooks

## Relationship to Other Docs

Use this document together with:

- `project_docs/plan.md` for the active priority order
- `project_docs/implementation_checklists.md` for execution tracking
- `project_docs/epics.md` for backlog placement
- `docs/reference/MAPPING_SIGNALS_AND_SCORING.md` for the current scoring model