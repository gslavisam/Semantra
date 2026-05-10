# Enterprise Integration Catalog Vision

## Purpose

This document explains what the Semantra catalog already is today, what its current operating model is, and what the next meaningful evolution should be.

It is intentionally aligned to the current product state as of 2026-05-10. It is not a greenfield vision for a graph platform or CMDB replacement.

## Why the Catalog Matters

Semantra already does more than generate one-off mapping suggestions.

Today the product can:

- persist reviewed mapping sets with governance metadata
- store canonical-only and standard artifacts
- project saved artifacts into a searchable catalog
- search integrations by metadata and canonical footprint
- open detail views and reuse approved work back into Workspace

That means the catalog is already the first reusable memory layer of the product.

The business question is no longer only "can we map this dataset?".
It is also:

- what has already been mapped
- what is already approved
- which canonical concepts already have reuse evidence
- which integration family should a new analyst start from

## What Exists Today

The current delivered catalog slice already includes:

- integration listing and filtered search
- integration detail drilldown
- concept-centric catalog detail
- similar integration suggestions
- reuse into Workspace from approved mapping-set artifacts
- support for both `standard` and `canonical-only` artifacts

Current implementation anchors:

- `backend/app/api/routes/catalog.py`
- `backend/app/services/persistence_service.py`
- `streamlit_ui/catalog_views.py`
- mapping-set persistence and governance surfaces in `backend/app/api/routes/mapping.py`

## Current Operating Model

The catalog today is not a separate enterprise asset registry. It is a governed projection over saved mapping-set versions.

### Current identity model

The practical identity model today is:

- integration family grouped by `integration_name`
- versioned reviewed artifact represented by saved mapping-set versions
- governance and reuse controlled by mapping-set status and audit metadata

### Current searchable footprint

For each saved version, the catalog can already surface:

- source system
- target system
- business domain
- owner
- artifact type
- version and status context
- canonical concept footprint
- unmatched source indicators
- related mapping-set audit and diff views

### Current reuse model

Reuse today works as a continuation of the reviewed mapping workflow:

- analysts find an existing saved artifact in `Catalog`
- inspect detail and lineage
- load an approved version back into `Workspace`
- continue review and save a new version if needed

This is important: the catalog does not create a second review model. It sits on top of the existing governed mapping-set lifecycle.

## What the Catalog Is Not Yet

The current slice is useful, but still intentionally lightweight.

Current limitations:

- there is no separate long-lived `IntegrationAsset` entity beyond the current `integration_name` grouping
- similarity is still heuristic, mostly based on shared canonical footprint and metadata overlap
- there are no explicit curated reuse links between integrations
- the catalog is not a graph or lineage platform
- there is no independent catalog governance model separate from mapping-set governance
- there is no broad visual discovery layer such as estate maps or concept heatmaps yet

This means the catalog is already real and usable, but it is still a pilot-grade discovery and reuse surface, not a full enterprise metadata product.

## Near-Term Evolution

The next meaningful step is not to replace the current model. It is to deepen reuse discovery on top of what already works.

### Priority 1. Better concept and reuse discovery

Near-term work should focus on:

- stronger concept-centric discovery
- clearer surfacing of shared canonical paths across integrations
- better display of unmatched or repeatedly weak concept coverage
- more useful similar-integration evidence instead of just a ranked list

This aligns with the active post-pilot direction around concept and reuse discovery.

### Priority 2. Clearer integration lineage

The current version model is useful, but the detail view can become easier to reason about by making lineage more explicit:

- latest approved version
- latest overall version
- canonical-only vs standard progression within one family
- stronger diff summaries between versions

### Priority 3. Better decision support for reuse

The catalog should increasingly help answer:

- which approved artifact is safest to reuse
- which integration family already solved this concept problem
- where the same concept still fails repeatedly across projects

That is a higher-value next step than introducing a heavier data model too early.

## Later Evolution

Only after the current discovery and reuse layer is mature should Semantra consider a bigger catalog model.

Possible later evolution:

- a separate stable `IntegrationAsset` entity distinct from mapping-set versions
- explicit `ReuseLink` relationships curated or inferred over time
- richer portfolio views across systems, domains, and canonical concepts
- concept-gap analytics across the saved estate
- stronger catalog-specific governance and stewardship workflows

These are valid directions, but they should be treated as later architecture options, not as immediate requirements.

## Non-Goals for the Current Phase

The current catalog phase should not try to become:

- a CMDB replacement
- a graph database program
- a runtime integration monitoring tool
- a full enterprise architecture repository
- a separate approval workflow disconnected from mapping-set governance

## Recommended Product Framing

The right framing today is:

- the catalog is already the reusable memory layer of Semantra
- it is powered by governed mapping-set artifacts
- it already supports practical search, detail, and reuse workflows
- the next value step is deeper discovery and clearer reuse evidence, not wholesale redesign

## Relationship to the Rest of the Docs

Use this document together with:

- `project_docs/current_state.md` for what exists today across the full product
- `PROJECT_OVERVIEW.md` for the broader product and architecture picture
- `project_docs/plan.md` for the active priority order
- `project_docs/epics.md` for where deeper catalog evolution sits in the backlog
