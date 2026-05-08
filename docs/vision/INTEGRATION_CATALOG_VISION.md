# Enterprise Integration Catalog Vision

## Why this matters

Semantra already has two important building blocks:

- reviewed mappings can be persisted as versioned mapping sets
- canonical mode can express source-to-concept alignment even before a concrete target schema exists

The next enterprise step is not only better ranking. It is a searchable memory of what the organization has already mapped.

That means turning per-session mapping output into an integration catalog that can answer questions such as:

- Which integrations already map customer concepts?
- Where is `customer.id` already used across SAP, Workday, QAD, and local systems?
- Which approved mapping set should a new project reuse instead of starting from scratch?
- Which canonical concepts remain repeatedly unmapped across projects?

## Current gap

Today Semantra already persists mapping sets, audits status changes, and supports version diff review. That is a strong governance baseline, but it is not yet a true enterprise catalog.

Current limitations:

- saved mapping sets are listed mainly as version records, not as integration assets
- canonical coverage is visible inside the active review session, not as a reusable estate-level inventory
- there is no cross-project search by canonical concept, source system, target system, owner, lifecycle, or business domain
- there is no visual overview of existing integration relationships and reusable mappings

## Target operating model

The catalog should treat a reviewed mapping not only as a file-like artifact, but as an enterprise integration record with a stable identity, lifecycle, and semantic footprint.

### Core entities

`IntegrationAsset`

- stable business identifier for the integration or interface
- fields such as `integration_name`, `source_system`, `target_system`, `business_domain`, `interface_type`, `owner`, `lifecycle_status`, `description`

`MappingSetVersion`

- versioned reviewed decisions already supported by the current mapping-set workflow
- remains the reviewable artifact, but becomes one version under an integration asset instead of the only catalog object

`CanonicalCoverageSnapshot`

- searchable summary of which canonical concepts are covered, shared, source-only, target-only, or unmapped for a given integration version
- must support canonical-only sessions where no real target dataset exists yet

`MappingActivityIndex`

- flattened, queryable rows such as `source_field -> canonical_concept -> target_field`
- searchable by field name, concept id, confidence label, mapping method, and status

`ReuseLink`

- explicit or derived relation between two integrations that share canonical concepts, mapping patterns, or approved rules
- used for reuse suggestions such as "similar approved integration exists"

`GovernanceMetadata`

- ownership, assignee, review note, created_by, approval status, timestamps, and optional release note metadata

### Primary search and discovery questions

The catalog should support at least these lookup modes:

- search by integration name or system pair
- filter by source system, target system, owner, domain, and lifecycle status
- browse by canonical concept such as `customer.id`, `invoice.date`, `vendor.name`
- inspect all approved mappings touching one canonical concept across projects
- find unmapped or repeatedly low-confidence concepts across saved integration versions

### Visual views

Useful enterprise views are not limited to a flat table.

Recommended first-class views:

- integration list with filters and quick metadata badges
- integration detail view with source/target summary, canonical coverage, and latest approved mapping set
- concept-centric view showing all integrations that use a given canonical concept
- source system to target system matrix showing where reviewed integrations already exist
- reuse hints panel showing similar integrations and shared canonical paths

## Minimal MVP on top of the current product

This capability can start as an extension of the existing mapping-set model, not as a full redesign.

### MVP scope

1. Extend saved mapping-set metadata with integration-level descriptors.

- `integration_name`
- `source_system`
- `target_system`
- `business_domain`
- `interface_type`
- optional `description`

2. Persist a queryable catalog summary for each saved mapping-set version.

- decision count
- canonical concept ids used in the version
- unmatched source fields
- source-only canonical concepts
- target-only canonical concepts when a target exists
- whether the artifact is `standard` or `canonical-only`

3. Add read APIs for discovery.

- `GET /catalog/integrations`
- `GET /catalog/integrations/{integration_id}`
- `GET /catalog/concepts/{concept_id}`
- `GET /catalog/search?q=...`

4. Add a Streamlit catalog view.

- searchable table of saved integrations
- filters by system pair, status, owner, and domain
- detail panel with canonical coverage and latest approved version
- drilldown from one integration into the underlying mapping set versions and diffs

5. Support canonical-first reuse.

- canonical-only mapping results must be catalogable even when no target dataset exists yet
- later standard runs can attach a concrete target schema to the same integration asset lineage

### MVP non-goals

The first slice should not try to become a full CMDB or enterprise architecture suite.

Out of scope for MVP:

- multi-hop lineage across runtime jobs and execution history
- automatic synchronization from external EA tools
- full graph analytics or impact analysis
- row-level approval workflows beyond the current mapping-set governance slice

## Suggested implementation anchors

Likely implementation anchors for the MVP:

- `backend/app/services/persistence_service.py`
- `backend/app/api/routes/mapping.py` or a dedicated catalog route module
- `backend/app/models/mapping.py` or a dedicated catalog model module
- `streamlit_ui/workspace_decision_views.py`
- a future `streamlit_ui/catalog_views.py`

## Product outcome

If this slice is delivered, Semantra stops being only a smart review surface and starts becoming a reusable semantic integration memory.

That is the point where canonical functionality becomes enterprise-visible: not only through one successful mapping session, but through searchable evidence of what the organization already knows.
