# Runtime/Persistence Separation Plan

## Scope

This slice clarifies what belongs to canonical authoring, what belongs to runtime matching, and which conditions should force Semantra off the current local in-memory job model.

## Canonical Authoring and Read Model

Owns:
- canonical glossary import/export and promotion flows
- canonical concept registry and Canonical Console read surfaces
- stewardship decisions that stabilize overlay aliases into the base glossary

Current boundary after Run0518 Phase 4:
- canonical glossary changes still write the glossary CSV, which remains the editable authoring artifact for this MVP
- canonical glossary import and overlay-promotion execution no longer need a full metadata/workbook reseed to refresh runtime state
- canonical authoring refresh now rebuilds the canonical slice over persisted knowledge concepts, then syncs only `canonical_concepts` and `canonical_field_contexts` back to SQLite
- targeted repository helpers now front the stewardship queue, catalog discovery read model, mapping-set governance reads, and knowledge runtime snapshot access so routes no longer depend directly on the broad persistence service for these surfaces

Implication:
- full file-based reseed is now reserved for metadata source drift or explicit admin reseed, not for every canonical authoring action

## Runtime Matching Responsibilities

Owns:
- matching-time knowledge concept lookup
- canonical alias lookup and KC -> CC bridge usage
- active overlay application on top of the persisted runtime base
- DB-first runtime bootstrap for local and pilot sessions

Operational contract:
- default runtime source is SQLite when the seed hash matches the source files
- `/knowledge/reload` now exposes `runtime_source`, `source_hash_state`, and seeded row counts so the operator can tell whether runtime is using the cache, a full source-file load, or the canonical authoring sync path
- `/knowledge/reseed` remains the explicit escape hatch when metadata source files change and the cache must be rebuilt from source

## Durable Backend Triggers for Mapping Jobs

Current local contract:
- storage mode: SQLite-backed status persistence with local thread-backed execution
- concurrency limit: 4 active jobs
- retained finished jobs: 32
- finished-job TTL: 900 seconds
- restart-safe: no
- cross-process-safe: no
- retention and age signals are wall-clock based in durable mode so cleanup and observability remain correct across process restarts
- activity polling returns the latest retained event tail, not the oldest retained progress rows

Promote to a durable backend when any of these become true:
1. `active_capacity_reached`
2. `finished_retention_saturated`
3. `long_running_job_exceeds_retention_window`
4. job visibility is required across multiple backend processes or hosts
5. restart-safe retry, audit, or recovery becomes a product requirement

Observability surface:
- `/observability/mapping-jobs/runtime` exposes the live durable-status runtime pressure and the currently met durable-backend triggers

Out of scope for this slice:
- no broker or external scheduler
- no lease/dequeue worker model yet
- no DB-only canonical authoring workflow; the glossary CSV remains the editable source of truth
