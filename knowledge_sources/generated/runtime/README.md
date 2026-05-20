# Generated Runtime Candidates

Place generated runtime-facing knowledge artifacts here.

Examples:

- curated metadata dictionary refresh candidates
- generated CSVs prepared for controlled runtime import or review

Current SAP inventory outputs live under `knowledge_sources/generated/runtime/sap/`:

- `sap_full_inventory_classification.csv` — full SAP table-column inventory classified against the current canonical runtime
- `sap_canonical_gap_candidates.csv` — filtered subset containing `knowledge_only` and `unmapped` rows
- `sap_full_inventory_summary.csv` — aggregate counts by classification bucket and SAP module
- `sap_promoted_canonical_aliases.csv` — SAP aliases and canonical contexts promoted into the canonical layer by the safe batch promotion flow
- `sap_promotion_review_queue.csv` — remaining SAP rows that still require steward review instead of auto-promotion
- `sap_promotion_summary.csv` — summary of promotion outcomes and review reasons
- `sap_wave2_promoted_canonical_expansions.csv` — second-wave SAP promotions for curated `knowledge_only` and `strong_canonical_candidate` families
- `sap_wave2_promotion_summary.csv` — summary of the wave-2 promotion run; idempotent reruns report `no_changes`
- `sap_priority_review_queue.csv` — post-promotion SAP review queue sorted by module volume and review priority
- `sap_priority_review_summary.csv` — per-module rollup of the prioritized review queue
- `sap_materialized_canonical_contexts.csv` — durable SAP table-field contexts materialized from high-confidence `direct_alias_match` and `description_alias_match` rows without widening global canonical aliases
- `sap_materialized_canonical_contexts_summary.csv` — summary of the context-only SAP materialization run

Rerun the SAP export from repo root with:

- `PYTHONPATH=backend python support/sap/generate_sap_canonical_inventory.py`

Execute the conservative SAP canonical promotion flow from repo root with:

- `PYTHONPATH=backend python support/sap/promote_sap_canonical_matches.py`

Execute the second-wave SAP canonical expansion flow from repo root with:

- `PYTHONPATH=backend python support/sap/promote_sap_canonical_expansions.py`

Rebuild the prioritized post-promotion SAP review queue from repo root with:

- `PYTHONPATH=backend python support/sap/prioritize_sap_review_queue.py`

Materialize high-confidence SAP canonical contexts from the current classification from repo root with:

- `PYTHONPATH=backend python support/sap/materialize_sap_canonical_contexts.py`

Current QuickBooks inventory outputs live under `knowledge_sources/generated/runtime/quickbooks/`:

- `quickbooks_tables_fields_classification.csv` — full QuickBooks table-field inventory classified against the current canonical runtime
- `quickbooks_canonical_gap_candidates.csv` — filtered subset containing `knowledge_only` and `unmapped` rows
- `quickbooks_tables_fields_summary.csv` — aggregate counts by classification bucket and QuickBooks module

Generate the QuickBooks inventory classification from repo root with:

- `PYTHONPATH=backend python support/quickbooks/generate_quickbooks_tables_inventory.py`

Execute the conservative QuickBooks canonical promotion flow from repo root with:

- `PYTHONPATH=backend python support/quickbooks/promote_quickbooks_canonical_matches.py`

Execute the second-wave QuickBooks canonical expansion flow from repo root with:

- `PYTHONPATH=backend python support/quickbooks/promote_quickbooks_canonical_expansions.py`

Rebuild the prioritized post-promotion QuickBooks review queue from repo root with:

- `PYTHONPATH=backend python support/quickbooks/prioritize_quickbooks_review_queue.py`

Materialize high-confidence QuickBooks canonical contexts from the current classification from repo root with:

- `PYTHONPATH=backend python support/quickbooks/materialize_quickbooks_canonical_contexts.py`

Generate QuickBooks knowledge overlay (runtime-wired) from promotion waves from repo root with:

- `PYTHONPATH=backend python support/quickbooks/generate_qb_knowledge_overlay.py`

## Workday HRDH Datahub Inventory

### Paths
- **Input**: `metadata_dict/HRDH_Table_Columns.xlsx` (Overview sheet, 205 tables)
- **Classification**: `workday/workday_datahub_classification.csv` (6 buckets)
- **Gap Candidates**: `workday/workday_datahub_gap_candidates.csv` (knowledge_only + unmapped)
- **Summary**: `workday/workday_datahub_summary.csv` (bucket distribution)

### Materialized Contexts
- **Source**: Workday HRDH materialized from wave-1 + wave-2 promoted rows
- **Path**: `workday/workday_materialized_canonical_contexts.csv` (197 rows)
- **Category**: All "HR" (Human Capital Management domain)
- **Format**: concept_id, system, object_name, field_name, category, field_description, note

### Overlay (Auto-Loaded at Runtime)
- **Source**: Generated from promotion waves (wave-1: 1, wave-2: 196)
- **Path**: `../../wd_datahub_knowledge_overlay.csv` (15 unique concept-alias pairs)
- **Format**: entry_type, canonical_term, canonical_concept_id, alias, domain, source_system, note
- **Loading**: Automatically loaded by `metadata_knowledge_service.refresh()` with source hash validation

### Promotion Wave Artifacts
**Wave-1 Promotion** (conservative, direct matches only):
```bash
PYTHONPATH=backend python ../../support/workday/promote_workday_canonical_matches.py
Output: workday_promoted_canonical_aliases.csv (1 row)
```

**Wave-2 Expansion** (HR-context aware, knowledge + weak ≥0.50):
```bash
PYTHONPATH=backend python ../../support/workday/promote_workday_canonical_expansions.py
Output: workday_wave2_promoted_canonical_expansions.csv (196 rows)
```

### Materialization & Enrichment
**Materialize contexts** (both wave-1 + wave-2):
```bash
PYTHONPATH=backend python ../../support/workday/materialize_workday_canonical_contexts.py
Output: workday_materialized_canonical_contexts.csv (197 rows)
```

**Generate overlay** (runtime auto-loading):
```bash
PYTHONPATH=backend python ../../support/workday/generate_wd_knowledge_overlay.py
Output: ../../wd_datahub_knowledge_overlay.csv (15 entries)
```

**Enrich canonical layers**:
```bash
PYTHONPATH=backend python ../../support/workday/enrich_canonical_field_contexts_with_wd.py
PYTHONPATH=backend python ../../support/workday/enrich_canonical_glossary_with_wd.py
Output: Updated canonical_field_context_enrichment.csv (+197), canonical_glossary_erp.csv (+2)
```

### Discovery & Resolution
**Query Workday fields at runtime**:
```python
from support.workday.wd_data_entity_helpers import WDEntityResolver, WDModuleTaxonomy

resolver = WDEntityResolver()
concept = resolver.resolve_field("EMPLOYEE", "EMPLOYEE_ID")
# → ConceptInfo(concept_id="employee_id", confidence="high", source_system="Workday_HRDH")

# Browse by functional area
tables = WDModuleTaxonomy.get_tables_for_area("Core HR")
# → ["CR_DIM_EMPLOYEE", "CR_DIM_POSITION", ...]
```

### Coverage
- **Tables**: 205 total; 197 promoted (96% coverage)
- **Columns**: 1,428 total; distributed across 6 classification buckets
- **Functional Areas**: Core HR, Compensation, Staffing, Talent Management, Benefits
- **Review Candidates**: 204 rows (wave-1/wave-2 review + unmapped)

---