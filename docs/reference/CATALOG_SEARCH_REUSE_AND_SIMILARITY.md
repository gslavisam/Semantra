# Catalog Search, Reuse, and Similarity Reference

## Purpose

This document explains how Semantra's Catalog is populated, how search and concept lookup work, how similar integrations are ranked, and what actually happens when a saved mapping set is reused back into Workspace.

It is grounded in the current implementation, primarily:

- `backend/app/api/routes/catalog.py`
- `backend/app/services/persistence_service.py`
- `backend/app/models/mapping.py`
- `streamlit_ui/catalog_views.py`
- `backend/app/api/routes/mapping.py`

Use this document when you need to understand:

- what the Catalog is actually indexing
- how browse and search differ
- what `latest_version` and `latest_approved_version` mean
- how similar integrations are scored
- what `Reuse in Workspace` really does
- which governance rule blocks reuse

## Important Framing

The Catalog is not a live view over the current Workspace session.

It is a persistence projection over saved mapping sets.

Operational meaning:

- Catalog search works over durable artifacts that have already been saved
- concept usage is derived from those saved artifacts
- reuse starts from a persisted mapping-set version, not from transient review state

## Where This Behavior Appears

Current implementation exposes Catalog behavior through:

- `GET /catalog/integrations`
- `GET /catalog/search`
- `GET /catalog/integrations/{integration_name}`
- `GET /catalog/concepts/{concept_id}`
- the `Catalog` tab in `streamlit_ui/catalog_views.py`

The actual reuse action then crosses back into mapping governance through:

- `POST /mapping/sets/{mapping_set_id}/apply`

## What Gets Indexed Into the Catalog

When a mapping set is saved, Semantra writes a projection into two SQLite-backed catalog tables:

- `mapping_catalog_entries`
- `mapping_catalog_concepts`

The catalog entry projection stores record-level integration metadata such as:

- `mapping_set_id`
- `name`
- `integration_name`
- `version`
- `status`
- `artifact_type`
- `decision_count`
- `source_system`
- `target_system`
- `business_domain`
- `interface_type`
- `description`
- `canonical_concepts`
- `unmatched_sources`
- `owner`
- `assignee`
- `created_at`

The concept projection stores one row per `(mapping_set_id, concept_id)` so concept-centric lookup can work independently of the integration listing.

Important consequence:

- the Catalog is a read model built from mapping-set persistence
- it is not recomputed from the current upload or current review screen unless that work is first saved as a mapping set

## Browse vs Search

### Browse

`GET /catalog/integrations` lists catalog integration versions with optional exact filters over:

- `source_system`
- `target_system`
- `business_domain`
- `owner`
- `status`
- `artifact_type`
- `integration_name`

Results are ordered by:

- `integration_name ASC`
- `version DESC`
- `mapping_set_id DESC`

Operational meaning:

- newer versions of the same integration appear before older ones
- the first record for an integration name is the latest saved version

### Search

`GET /catalog/search` uses a broader text match over:

- `integration_name`
- `name`
- `source_system`
- `target_system`
- `business_domain`
- `interface_type`
- `owner`
- matching concept IDs from `mapping_catalog_concepts`

It then applies the same structured filters and ordering rules.

Operational meaning:

- search is broader than browse
- concept ID matches are first-class search inputs, not only integration-name text hits

## Integration Detail Semantics

`GET /catalog/integrations/{integration_name}` groups all saved versions for the chosen integration name and returns a `CatalogIntegrationDetail`.

Key fields include:

- `latest_version`
- `latest_approved_version`
- `versions`
- `canonical_concepts`
- `unmatched_sources`
- `similar_integrations`

### `latest_version`

This is the first versioned record in the sorted result set for the exact integration name.

In practice, this means:

- highest version first
- newest saved version if versions are ordered normally

### `latest_approved_version`

This is the first exact-match version whose mapping-set status is `approved`.

If no approved version exists, the field is `null`.

Operational meaning:

- `latest_version` answers "what was saved most recently"
- `latest_approved_version` answers "what is the newest governance-approved variant"

### `canonical_concepts`

The detail view merges canonical concepts across all exact-match versions of the integration and normalizes them into a distinct list.

Operational meaning:

- this is an integration-level semantic footprint, not only the footprint of the latest version

### `unmatched_sources`

This is also merged across exact-match versions.

Operational meaning:

- it shows which source fields remained unmatched somewhere in the saved lineage of that integration
- it should not be interpreted as "currently unmatched in the latest version only"

## Similar Integration Ranking

Similarity is currently heuristic and concept-driven.

### Entry conditions

The current integration must have at least one canonical concept in its merged integration-level footprint.

If the reference integration has no canonical concepts, Semantra returns no similar integrations.

Candidate integrations are considered only if they share at least one of those canonical concepts.

### Factors used

For each candidate integration, Semantra computes:

- number of shared canonical concepts
- whether the latest candidate version has the same `source_system`
- whether the latest candidate version has the same `target_system`
- whether the latest candidate version has the same `business_domain`
- whether the latest candidate version has the same `artifact_type`

### Score formula

Current implementation uses:

$$
max\_score = (|reference\_concepts| \cdot 3) + 4
$$

$$
weighted\_score = (|shared\_concepts| \cdot 3) + same\_source + same\_target + same\_domain + same\_artifact\_type
$$

$$
similarity\_score = round\left(\frac{weighted\_score}{max\_score}, 3\right)
$$

Where each of the `same_*` factors contributes either `0` or `1`.

Interpretation:

- shared canonical concepts dominate the score
- system/domain/artifact alignment acts as tie-strengthening evidence
- this is a transparent heuristic, not a learned reuse model

### Sorting

Similar integrations are sorted by:

- `similarity_score DESC`
- `shared_concept_count DESC`
- `integration_name ASC`

Operational meaning:

- two integrations with similar normalized score are still biased toward the one sharing more concepts

## Concept Lookup

`GET /catalog/concepts/{concept_id}` returns a `CatalogConceptDetail` built from concept usage rows, optionally filtered by:

- `source_system`
- `target_system`
- `status`
- `artifact_type`

This is a concept-centric way to answer:

- where this canonical concept appears across saved mapping artifacts
- which integrations currently carry it
- whether it appears mostly in `approved` or non-approved artifacts

Important distinction:

- integration detail starts from an integration name and expands to concepts
- concept detail starts from a concept and expands to matching saved integration versions

## What `Reuse in Workspace` Actually Does

The Catalog UI does not directly rebuild a mapping by re-running the engine.

Instead it:

1. calls `POST /mapping/sets/{mapping_set_id}/apply`
2. receives the persisted mapping-set detail
3. converts it into a synthetic Workspace `mapping_response`
4. restores mapping editor state, including saved transformation code

### Workspace response construction

The Streamlit helper `_build_catalog_reuse_mapping_response(...)` assigns reused rows a synthetic reviewed payload.

Current behavior:

- reused mappings use method `manual_review`
- confidence is `0.95` when a target exists and status is `accepted`
- confidence is `0.7` when a target exists but status is not `accepted`
- confidence is `0.35` when no target exists
- saved `transformation_code` is carried into the restored editor state

For `canonical-only` artifacts, the helper also injects a simple canonical signal and shared-concept detail when the target is one of the artifact's canonical concepts.

Operational meaning:

- reuse is a state restoration path, not a remapping run
- the analyst continues from reviewed persisted decisions rather than recomputing candidates from source and target schemas

## Governance Rule for Reuse

Catalog reuse is governance-gated by mapping-set status.

The UI blocks reuse unless the selected version is `approved`, and the backend apply endpoint enforces the same contract.

If a mapping set is not approved, the backend returns a `409` conflict and the UI explains that only approved mapping sets can be reused in Workspace flows.

Operational meaning:

- Catalog is a discovery surface over many artifact versions
- Workspace reuse is intentionally limited to approved artifacts

## Relationship to Version Drilldown

The Catalog UI lets the user inspect:

- selected mapping-set detail
- audit log
- diff against another version of the same mapping-set name

This is important because reuse is not a blind copy action.

The user can inspect:

- exact reviewed mapping decisions
- review notes
- owner and assignee
- changed targets, statuses, and transformation code between versions

before deciding to reuse.

## Important Boundaries

Current boundaries to keep in mind:

- similarity is heuristic and fully transparent, not learned from prior reuse success
- Catalog search/discovery is API-first and admin-gated in the current product surface
- concept lookup is based on saved artifact projection, not on raw canonical glossary state
- reuse continues the same Workspace review loop; it is not a parallel orchestration or deployment flow

## Practical Reading Guide

### High similarity score

Typical meaning:

- many canonical concepts overlap
- and the candidate likely matches the same integration family or business area

It does not guarantee:

- that the selected mapping-set version is approved
- that its transformation logic is still appropriate for the current dataset

### `latest_version` present but no `latest_approved_version`

Typical meaning:

- the integration family exists in the Catalog
- but no currently approved saved version exists for safe Workspace reuse

### Concept usage without strong similarity

Typical meaning:

- the same business concept appears elsewhere in the repository
- but the broader integration shape is not especially close on systems/domain/artifact type

That is still useful for semantic discovery, but weaker as a direct reuse signal.