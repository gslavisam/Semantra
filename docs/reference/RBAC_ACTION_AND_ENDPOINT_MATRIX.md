# RBAC Action and Endpoint Matrix

This document turns the current Semantra surface into a concrete RBAC proposal.

It is intentionally split into two views:

- action matrix: what a user is allowed to do in the product
- endpoint matrix: which backend route family should enforce that permission

It also distinguishes between:

- current-state enforcement: what the code enforces today
- target-state RBAC: what roles and scopes should exist before calling RBAC complete

## Current-State Enforcement Baseline

Today the backend has a binary authorization model:

- endpoints without `Depends(require_admin)` are effectively open to any caller that can reach the API
- endpoints with `Depends(require_admin)` require `X-Admin-Token`
- the Streamlit UI forwards `X-Admin-Token` whenever `admin_token` is present in session state

As of 2026-05-29 there is also one implemented pilot RBAC slice:

- `backend/app/models/auth.py` defines the principal and role model
- `backend/app/api/deps.py` now exposes `get_request_principal()` and `require_roles()`
- `mapping/draft-sessions*` and `mapping/sets*` now use the new role layer
- that slice is real, but it does not mean the whole product is already under full RBAC

Relevant current-state anchors:

- `backend/app/api/deps.py`: `require_admin()`
- `backend/app/api/deps.py`: `get_request_principal()` and `require_roles()`
- `backend/app/models/auth.py`: `PrincipalRole`, `AuthenticatedPrincipal`
- `streamlit_ui/api.py`: `api_request()` injects `X-Admin-Token`
- `PROJECT_OVERVIEW.md`: the product explicitly says a multi-step RBAC enterprise workflow model is not yet complete

That means the matrix below is still mostly a design target, with only the first mapping-governance pilot slice now actually implemented.

## Proposed Roles

Use the following six roles as the first explicit model.

| Role | Purpose | Typical scope |
| --- | --- | --- |
| `reader` | Read-only access to approved product views and status surfaces | tenant |
| `analyst` | Run operational workspace flow: upload, map, preview, codegen | own workspace session |
| `reviewer` | Finalize mapping decisions, manage review state, save reusable operational artifacts | team or assigned project |
| `steward` | Own catalog, canonical, knowledge, overlay, and governance authoring | governance domain |
| `benchmark_operator` | Manage benchmark datasets, runs, and comparison jobs | benchmark workspace |
| `platform_admin` | Runtime configuration, reseed, cross-scope audit, operational override | whole deployment |

## Scope Rules

Role checks alone are not enough. The target model also needs resource scope.

| Scope | Meaning |
| --- | --- |
| `own` | created by the current user |
| `team` | visible/editable inside the current team or project |
| `tenant` | visible inside the current tenant |
| `global` | platform-wide operational surface |

Recommended scope rules:

- workspace uploads, mapping jobs, previews, generated artifacts: `own`
- draft sessions: `own` by default, `team` if explicitly shared
- mapping sets: `team` for create/read, `reviewer` or above for status/apply
- catalog, knowledge, canonical, overlays, runtime config: `tenant` or `global`
- observability and audits: `team` read for reviewers, `global` for admins

## Action Matrix

`Y` means the role should be allowed to perform the action.

| Product action | Reader | Analyst | Reviewer | Steward | Benchmark Operator | Platform Admin | Scope | Backend route family |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| View help, reference, and passive runtime status | Y | Y | Y | Y | Y | Y | tenant | UI only or read-only endpoints |
| Upload and profile source/target datasets | - | Y | Y | - | - | Y | own | `/upload*` |
| Generate mapping or canonical mapping | - | Y | Y | - | - | Y | own | `/mapping/auto`, `/mapping/auto/jobs`, `/mapping/canonical`, `/mapping/canonical/jobs`, `/mapping/jobs/*` |
| Cancel an in-flight mapping job | - | Y | Y | - | - | Y | own | `/mapping/jobs/{job_id}/cancel` |
| Run mapping refine, review plan, analysis summary, narration, audio | - | Y | Y | - | - | Y | own | `/mapping/refine`, `/mapping/review-plan`, `/mapping/analysis/*` |
| Accept/reject/manual override review decisions | - | - | Y | - | - | Y | own or team | workspace state today, later persisted via draft or set endpoints |
| Generate preview and code artifacts | - | Y | Y | - | - | Y | own | `/mapping/preview`, `/mapping/codegen`, `/mapping/codegen/refine` |
| Save and read source field hints | - | Y | Y | - | - | Y | team | `/mapping/source-field-hints` |
| Save and update draft sessions | - | Y | Y | - | - | Y | own or team | `/mapping/draft-sessions*` |
| Save mapping sets for governed reuse | - | - | Y | Y | - | Y | team | `/mapping/sets*` |
| Apply, diff, or audit mapping sets | - | - | Y | Y | - | Y | team | `/mapping/sets/{id}/apply`, `/audit`, `/diff`, `/status` |
| Browse reusable transformation templates | Y | Y | Y | Y | Y | Y | tenant | `/mapping/transformation/templates` |
| Generate one bounded transformation suggestion | - | Y | Y | - | - | Y | own | `/mapping/transformation/generate` |
| Manage saved transformation test sets | - | - | Y | - | Y | Y | team | `/mapping/transformation/test-sets*` |
| Search catalog and compare reuse candidates | Y | Y | Y | Y | - | Y | tenant | `/catalog/*` |
| Run ad hoc benchmark metrics | - | - | Y | - | Y | Y | team | `/evaluation/benchmark`, `/evaluation/run` |
| Explain benchmark result or compare scoring profiles | - | - | - | - | Y | Y | team | `/evaluation/explain`, `/evaluation/datasets/*/compare-profiles` |
| Manage saved benchmark datasets and runs | - | - | - | - | Y | Y | team or tenant | `/evaluation/datasets*`, `/evaluation/runs` |
| View knowledge and canonical read models | Y | - | Y | Y | - | Y | tenant | `/knowledge/canonical-concepts*`, `/knowledge/concepts*`, selected stewardship read endpoints |
| Create overlays, triage canonical gaps, manage stewardship items | - | - | - | Y | - | Y | tenant | `/knowledge/overlays*`, `/knowledge/canonical-gaps*`, `/knowledge/stewardship-items*` |
| Promote knowledge or overlay output into glossary | - | - | - | Y | - | Y | tenant | `/knowledge/concepts/promote-to-glossary`, `/knowledge/stewardship-items/{id}/promote-to-glossary` |
| Import or export governance registries | - | - | - | Y | - | Y | tenant | `/knowledge/base-registry/*`, `/knowledge/canonical-glossary/*` |
| View audit logs, corrections, reusable rule candidates | - | - | Y | Y | Y | Y | team or tenant | `/observability/decision-logs`, `/observability/corrections*` |
| Promote reusable correction rules | - | - | Y | - | Y | Y | tenant | `/observability/corrections/reusable-rules/promote` |
| Change runtime scoring profile or reload config | - | - | - | - | - | Y | global | `/observability/config*` |
| Reload or reseed knowledge runtime | - | - | - | - | - | Y | global | `/knowledge/reload`, `/knowledge/reseed` |

## Backend Endpoint Matrix

This table is the route-level implementation target. Wildcards mean the full route family.

| Endpoint pattern | Methods | Current-state guard | Target roles | Target scope | Notes |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | public | `reader+` | tenant | health/info only |
| `/upload/sql/tables` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | SQL discovery for active workspace |
| `/upload/spec/detect` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | upload interpretation helper |
| `/upload/spec` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | spec upload |
| `/upload/handle` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | dataset handle creation |
| `/upload/handle/metadata` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | metadata enrichment |
| `/upload` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | main upload/profile call |
| `/mapping/auto` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | synchronous mapping |
| `/mapping/auto/jobs` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | async mapping start |
| `/mapping/canonical` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | synchronous canonical mapping |
| `/mapping/canonical/jobs` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | async canonical mapping start |
| `/mapping/jobs/{job_id}` | GET | public | `analyst`, `reviewer`, `platform_admin` | own | job polling must become owner-scoped |
| `/mapping/jobs/{job_id}/cancel` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | owner or admin only |
| `/mapping/target-fields` | GET | public | `analyst`, `reviewer`, `platform_admin` | own | target exploration helper |
| `/mapping/target-intents` | GET | public | `reader+` | tenant | target intent lookup |
| `/mapping/refine` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | per-row mapping refine |
| `/mapping/preview` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | output preview |
| `/mapping/analysis/summary` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | bounded summary |
| `/mapping/analysis/narration` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | bounded narration |
| `/mapping/analysis/audio` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | generated audio |
| `/mapping/review-plan` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | queue plan |
| `/mapping/source-field-hints` | GET, POST | public | `analyst`, `reviewer`, `platform_admin` | team | should become reusable team hint surface |
| `/mapping/codegen` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | code artifact generation |
| `/mapping/codegen/refine` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | artifact refinement |
| `/mapping/draft-sessions*` | GET, POST, PUT | admin token | `analyst`, `reviewer`, `platform_admin` | own or team | today too coarse; should not need full admin |
| `/mapping/sets*` | GET, POST | admin token | `reviewer`, `steward`, `platform_admin` | team | governed reusable mapping assets |
| `/mapping/sets/{id}/status` | POST | admin token | `reviewer`, `steward`, `platform_admin` | team | approval/status transition |
| `/mapping/sets/{id}/apply` | POST | admin token | `reviewer`, `steward`, `platform_admin` | team | apply approved version |
| `/mapping/sets/{id}/audit` | GET | admin token | `reviewer`, `steward`, `platform_admin` | team | governance audit |
| `/mapping/sets/{id}/diff` | GET | admin token | `reviewer`, `steward`, `platform_admin` | team | governance comparison |
| `/mapping/transformation/templates` | GET | public | `reader+` | tenant | safe read-only catalog |
| `/mapping/transformation/generate` | POST | public | `analyst`, `reviewer`, `platform_admin` | own | bounded transformation generation |
| `/mapping/transformation/test-sets*` | GET, POST | admin token | `reviewer`, `benchmark_operator`, `platform_admin` | team | saved assertion assets |
| `/catalog/*` | GET, POST | admin token | `reader`, `analyst`, `reviewer`, `steward`, `platform_admin` | tenant | likely too restricted today |
| `/evaluation/benchmark` | GET | public | `reader+` | tenant | read benchmark summary |
| `/evaluation/run` | POST | public | `reviewer`, `benchmark_operator`, `platform_admin` | team | benchmark execution |
| `/evaluation/explain` | POST | admin token | `benchmark_operator`, `platform_admin` | team | bounded explanation |
| `/evaluation/datasets*` | GET, POST | admin token | `benchmark_operator`, `platform_admin` | team or tenant | benchmark asset management |
| `/evaluation/runs` | GET | admin token | `benchmark_operator`, `platform_admin` | team or tenant | benchmark history |
| `/observability/decision-logs` | GET | admin token | `reviewer`, `steward`, `platform_admin` | team or tenant | read audit trail |
| `/observability/corrections` | GET, POST | admin token | `reviewer`, `benchmark_operator`, `platform_admin` | team | correction log |
| `/observability/corrections/reusable-rules` | GET | admin token | `reviewer`, `benchmark_operator`, `platform_admin` | tenant | candidate rules |
| `/observability/corrections/reusable-rules/active` | GET | admin token | `reviewer`, `benchmark_operator`, `platform_admin` | tenant | active reusable rules |
| `/observability/corrections/reusable-rules/promote` | POST | admin token | `reviewer`, `benchmark_operator`, `platform_admin` | tenant | promotion action |
| `/observability/config` | GET | admin token | `platform_admin` | global | runtime config visibility |
| `/observability/config/scoring-profile` | POST | admin token | `platform_admin` | global | runtime mutation |
| `/observability/config/reload` | POST | admin token | `platform_admin` | global | runtime mutation |
| `/observability/mapping-jobs/runtime` | GET | admin token | `platform_admin` | global | cross-job operational status |
| `/knowledge/canonical-concepts*` | GET | admin token | `reader`, `reviewer`, `steward`, `platform_admin` | tenant | should likely split read from write |
| `/knowledge/concepts*` | GET, PUT, POST | admin token | `steward`, `platform_admin` for write; `reader`, `reviewer` for read | tenant | read/write should not share one guard |
| `/knowledge/base-registry/export` | GET | admin token | `steward`, `platform_admin` | tenant | controlled export |
| `/knowledge/base-registry/import` | POST | admin token | `steward`, `platform_admin` | tenant | controlled import |
| `/knowledge/canonical-glossary/export` | GET | admin token | `steward`, `platform_admin` | tenant | controlled export |
| `/knowledge/canonical-glossary/import` | POST | admin token | `steward`, `platform_admin` | tenant | controlled import |
| `/knowledge/overlays/validate` | POST | admin token | `steward`, `platform_admin` | tenant | validation before create |
| `/knowledge/overlays` | GET, POST | admin token | `steward`, `platform_admin` for write; `reader`, `reviewer` for read | tenant | split read/write |
| `/knowledge/overlays/{overlay_id}` | GET | admin token | `reader`, `reviewer`, `steward`, `platform_admin` | tenant | detail read |
| `/knowledge/overlays/{overlay_id}/activate` | POST | admin token | `steward`, `platform_admin` | tenant | state transition |
| `/knowledge/overlays/{overlay_id}/deactivate` | POST | admin token | `steward`, `platform_admin` | tenant | state transition |
| `/knowledge/overlays/{overlay_id}/archive` | POST | admin token | `steward`, `platform_admin` | tenant | state transition |
| `/knowledge/overlays/rollback` | POST | admin token | `platform_admin` | global | stronger than normal stewardship |
| `/knowledge/audit` | GET | admin token | `steward`, `platform_admin` | tenant | governance audit |
| `/knowledge/stewardship-items*` | GET, POST | admin token | `steward`, `platform_admin` | tenant | stewardship queue |
| `/knowledge/stewardship-items/{id}/promote-to-glossary` | POST | admin token | `steward`, `platform_admin` | tenant | approved promotion only |
| `/knowledge/canonical-gaps/*` | GET, POST | admin token | `steward`, `platform_admin` | tenant | gap triage and approval |
| `/knowledge/reload` | POST | admin token | `platform_admin` | global | runtime reload |
| `/knowledge/reseed` | POST | admin token | `platform_admin` | global | file-to-db reseed |

## What Must Change in Code to Enforce This

1. Introduce an authenticated principal dependency.
   - Example fields: `user_id`, `tenant_id`, `team_ids`, `roles`
   - Replace binary admin-token checks with `require_roles()` and `require_scope()` helpers

2. Add ownership and tenancy fields to persisted resources.
   - draft sessions: `owner_user_id`, `team_id`, `tenant_id`, `shared_with_team`
   - mapping sets: `owner_team_id`, `tenant_id`, `status_changed_by`
   - benchmark datasets and runs: `team_id`, `tenant_id`, `created_by`
   - correction rules and observability records: `tenant_id`, `team_id`

3. Split read permissions from write permissions.
   - `catalog`, `knowledge`, and parts of `observability` are currently admin-only even for read access
   - those surfaces should expose read-safe routes to `reader` or `reviewer` roles without granting write access

4. Add owner-scoped checks to all long-running workspace resources.
   - mapping jobs
   - previews and generated artifacts if persisted
   - draft sessions

5. Keep a small number of truly global admin routes.
   - runtime config mutation
   - full reseed and rollback
   - cross-tenant operational inspection, if Semantra becomes multi-tenant

## Recommended Implementation Order

1. Replace `require_admin` with a principal model and role enum, while keeping the admin token as a bootstrap identity source.
2. Convert `mapping/draft-sessions*` and `mapping/sets*` first, because they are the clearest pilot cases for role-plus-scope enforcement.
3. Split `catalog` and `knowledge` read routes from write routes.
4. Lock down `observability` into reviewer, operator, and admin slices.
5. Move benchmark asset management to `benchmark_operator` and `platform_admin` only.

## Practical Current-State Summary

If you need one short sentence for planning:

- Semantra already has a meaningful protected-vs-unprotected route split
- but it is still a binary admin-token model, not a true multi-role RBAC system
- this document is the concrete bridge from the current codebase to that fuller model
