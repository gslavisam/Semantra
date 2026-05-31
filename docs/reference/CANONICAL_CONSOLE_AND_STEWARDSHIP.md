# Canonical Console and Stewardship Reference

## Purpose

This document explains how Semantra builds the canonical runtime view, how the Canonical Console is populated, how overlay lifecycle works, and how canonical-gap and overlay-promotion stewardship are governed.

It is grounded in the current implementation, primarily:

- `backend/app/api/routes/knowledge.py`
- `backend/app/models/knowledge.py`
- `backend/app/services/metadata_knowledge_service.py`
- `backend/app/services/knowledge_overlay_service.py`
- `backend/app/services/canonical_gap_service.py`
- `streamlit_ui/admin_views.py`

Use this document when you need to understand:

- what the Canonical Console is actually showing
- how base glossary data and active overlays combine at runtime
- how overlay versions move through validation, activation, archive, and rollback
- how canonical-gap triage and approval work
- how overlay aliases become promotable stewardship items
- how canonical-gap LLM suggestions differ from Workspace LLM decision proposals
- which actions are advisory versus durable governance actions

## Important Framing

The Canonical Console is a governance surface over a DB-first canonical runtime.

It is not only a debug screen, and it is not yet a full ontology-management platform.

Current implementation has two layers:

- durable runtime state loaded from SQLite
- file-backed source inputs that still matter for canonical glossary import/export and reseed workflows

Operational meaning:

- the console works over the active runtime state
- but canonical authoring is not yet purely DB-native end to end

## Where This Behavior Appears

Current implementation exposes canonical behavior through:

- `GET /knowledge/canonical-concepts`
- `GET /knowledge/canonical-concepts/{concept_id}`
- canonical glossary export/import endpoints
- overlay validate/create/list/detail/activate/deactivate/archive/rollback endpoints
- stewardship item list/detail/upsert/status/promotion endpoints
- canonical-gap candidate, suggestion, approval, rejection, and proposal-state endpoints
- the `Governance -> Canonical Console` surface rendered from `streamlit_ui/admin_views.py`

## Canonical Runtime Model

The current runtime status is represented as `KnowledgeRuntimeStatus` with fields such as:

- `mode`
- `active_overlay_id`
- `active_overlay_name`
- `active_entry_count`
- `entry_type_counts`
- `concept_count`
- `canonical_concept_count`

Current runtime modes are:

- `base_only`
- `overlay_active`

Operational meaning:

- `base_only` means only the persisted base canonical glossary/runtime is active
- `overlay_active` means one validated overlay version is currently merged into runtime behavior

## How the Canonical Registry Is Built

The route-local registry builder combines several data sources:

- persisted base canonical concepts and field contexts
- catalog concept usage counts and usage facets
- active overlay entries grouped by canonical concept

For each concept, the registry computes:

- base aliases
- active overlay aliases
- alias count
- field-context count
- usage count
- active overlay entry count
- source-system facets
- business-domain facets

### Source classification

Each concept summary carries a `source` value:

- `base`
- `base_plus_active_overlay`
- `overlay_only`

Interpretation:

- `base` means the concept exists in the base canonical runtime and currently has no active overlay aliases
- `base_plus_active_overlay` means the concept exists in the base runtime and currently has active overlay aliases merged into it
- `overlay_only` means the concept is currently surfaced only through the active overlay layer

### Alias hygiene

Base aliases are filtered through the shared canonical alias sanitizer before they are exposed.

Operational meaning:

- numeric-only alias noise is removed at read time
- promotion/import paths also enforce that same hygiene rule

## Canonical Concept Detail

`GET /knowledge/canonical-concepts/{concept_id}` returns:

- the concept summary
- field contexts
- active overlay entries for that concept
- catalog usage records
- related audit entries for the active overlay when relevant

Operational meaning:

- concept detail is not only glossary text
- it is a stitched governance view that joins canonical runtime, overlay activity, catalog usage, and audit context

## Canonical Glossary Import and Export

The current base glossary can be:

- exported through `GET /knowledge/canonical-glossary/export`
- imported through `POST /knowledge/canonical-glossary/import`

Import behavior is durable and audited.

Operational meaning:

- base glossary changes are explicit
- they are not the same thing as activating an overlay

## Overlay Validation and Create Flow

Overlay uploads follow a validation-first path.

### Validate

`POST /knowledge/overlays/validate` parses the CSV payload and returns a `KnowledgeOverlayValidationResult` with:

- total, valid, and invalid row counts
- duplicate/conflict/warning counts
- normalized row preview

### Create

`POST /knowledge/overlays` reruns validation and blocks save if any invalid rows exist.

If validation succeeds:

- a new overlay version is saved with status `validated`
- normalized valid rows are materialized as overlay entries
- an audit entry is appended

Operational meaning:

- invalid overlays never become durable runtime candidates
- the first saved state of a valid overlay is already `validated`, not `draft`

## Overlay Lifecycle Rules

Current overlay version statuses are:

- `draft`
- `validated`
- `active`
- `archived`

In practice, the create flow currently writes validated overlays directly, so `draft` exists in the model but is not the usual first saved state for uploaded overlays.

### Activate

Only `validated` overlay versions can be activated.

Activation:

- updates the persisted active overlay version
- refreshes the metadata knowledge runtime
- appends an audit entry

### Deactivate

Deactivation removes the active overlay from runtime and refreshes the knowledge runtime.

### Archive

Only `validated` or `active` overlay versions can be archived.

### Rollback

Rollback reverts the active runtime to the previous overlay version or to base-only mode when appropriate.

Operational meaning:

- overlay lifecycle is runtime-affecting governance, not just metadata bookkeeping

## Reload vs Reseed

### Reload

`POST /knowledge/reload` refreshes the in-memory knowledge runtime from current persisted state.

### Reseed

`POST /knowledge/reseed` forces a reload from the source knowledge files and re-persists them into SQLite.

Operational meaning:

- reload is a runtime refresh
- reseed is a stronger source-of-truth reconciliation action

## Canonical Gap Workflow

Canonical-gap governance has three distinct layers:

- candidate extraction
- suggestion and triage
- durable approval or rejection

### Candidate extraction

`POST /knowledge/canonical-gaps/candidates` extracts gap candidates from a mapping response.

This is how the Canonical Console can mirror gap state discovered in Workspace review.

### Suggestion

`POST /knowledge/canonical-gaps/suggest` uses nearest concepts plus the configured LLM provider.

If no usable response is returned, the API emits a safe `no_action` result instead of pretending a good suggestion exists.

### LLM proposal boundary (important)

There are two different LLM-assisted proposal surfaces in the product, and they should not be conflated:

- canonical-gap suggestion in this governance flow (`POST /knowledge/canonical-gaps/suggest`)
- Workspace decision proposals in the review/decision flow (`LLM Decision Proposals` in `streamlit_ui/workspace_review_views.py` and `streamlit_ui/workspace_decision_views.py`)

Operational distinction:

- canonical-gap suggestions are concept-level governance inputs that can end in overlay updates and stewardship state changes
- Workspace decision proposals are row-level mapping suggestions (`llm_proposal` origin in decision audit) and do not mutate canonical runtime or stewardship state by themselves
- durable canonical changes still require explicit governance actions (canonical-gap approve into overlay, or overlay-promotion promote-to-glossary)

### Proposal triage states

Current proposal triage states are:

- `new`
- `needs_review`
- `ready_for_approval`

These are persisted through stewardship items keyed by the gap candidate identity.

### Approval gate

Canonical-gap approval is blocked unless the current proposal state is `ready_for_approval`.

This is enforced at the API layer before the approval action runs.

### Approval behavior

When approved, the suggestion is materialized through `approve_canonical_gap_suggestion(...)` and written into an overlay flow rather than silently mutating the base glossary.

Operational meaning:

- canonical gaps are triaged before they become durable runtime additions
- approval is explicit and governance-aware

### Reject and ignore

Rejection and ignore actions append audit entries describing:

- source and target
- disposition
- suggestion action
- reviewer identity
- optional concept and note context

## Stewardship Items

Current stewardship item types are:

- `canonical_gap`
- `overlay_promotion`

Current stewardship statuses are:

- `new`
- `needs_review`
- `ready_for_approval`
- `approved`
- `rejected`
- `ignored`
- `promoted`

Stewardship items can carry:

- `owner`
- `assignee`
- `review_note`
- payload snapshots for candidates, suggestions, or overlay entries

Operational meaning:

- the stewardship table is the durable governance ledger for canonical review state
- UI console state alone is not the source of truth once an item has been persisted

## Overlay Promotion Workflow

Overlay promotion is a separate governed flow from canonical-gap approval.

It starts from overlay alias entries that are turned into `overlay_promotion` stewardship items.

### Promotion execution rules

`POST /knowledge/stewardship-items/{item_id}/promote-to-glossary` only allows promotion when:

- the item type is `overlay_promotion`
- the item status is `ready_for_approval` or already `promoted`

Promotion then:

- extracts concept and alias data from the overlay payload
- calls `metadata_knowledge_service.promote_overlay_alias_to_canonical_glossary(...)`
- updates the stewardship item status to `promoted`
- appends an audit entry

The response explicitly tells the caller whether:

- the alias was newly added
- a new concept had to be created

Operational meaning:

- overlay aliases do not automatically become part of the stable base glossary
- promote-to-glossary is a deliberate second governance step

## What the Canonical Console UI Actually Shows

The Streamlit `Canonical Console` is assembled from several API-backed slices.

### Registry and filters

The console supports:

- free-text concept search across concept metadata and aliases
- scope filtering by `source_system` and `business_domain`
- focus filtering such as `active_overlay`, `overlay_only`, `in_use`, `with_context`, and `base_only`

Operational meaning:

- the console is meant for semantic narrowing and stewardship triage, not just static glossary browsing

### Overlay summary

The UI builds an overlay summary from runtime status plus overlay version records, including metrics such as:

- active entry count
- concept-alias entry count
- total versions
- active versions
- validated versions
- archived versions

### Concept detail

The concept-detail area can surface:

- aliases and overlay aliases
- field contexts
- integration usage records
- concept-linked overlay-promotion items
- audit context

### Canonical gap review queue

The UI mirrors Workspace gap candidates and enriches them with:

- suggestion action
- proposal state
- stewardship status
- owner and assignee
- impact preview
- related audit entries

Operational meaning:

- the console is where canonical-gap work becomes durable governance state

## Important Boundaries

Current boundaries to keep in mind:

- the runtime is DB-first, but canonical authoring still includes file-backed reseed inputs
- only one active overlay runtime is surfaced at a time through the current runtime-status model
- LLM support is bounded to suggestion; persistence, approval, and promotion remain explicit human actions
- Workspace `LLM Decision Proposals` are intentionally outside canonical stewardship write paths; they update mapping decisions, not canonical runtime state
- overlay activation and archive rules are hard backend constraints, not only UI hints

## Practical Reading Guide

### `base_plus_active_overlay`

Typical meaning:

- the base concept exists in the stable runtime
- and the active overlay is currently extending it with additional alias coverage

### `overlay_only`

Typical meaning:

- the concept currently appears only because of the active overlay layer
- it has not yet been promoted into the stable base glossary

### Canonical gap in `ready_for_approval`

Typical meaning:

- triage is complete
- governance can now approve the overlay-oriented canonical addition

### Overlay promotion in `ready_for_approval`

Typical meaning:

- the alias is already a durable stewardship candidate
- but it still has not been written into the stable canonical glossary until the explicit promote action runs