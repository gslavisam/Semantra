# Support Utilities

This folder holds offline helper scripts that are useful for maintenance, ingest preparation, and SAP/vendor knowledge curation, but are not part of the runtime application entrypoints.

Structure:

- `support/sap/` - SAP inventory classification, promotion, queue prioritization, and canonical-context materialization scripts
- `support/quickbooks/` - QuickBooks inventory classification, promotion waves, queue prioritization, context materialization, overlay generation, and canonical enrichment scripts
- `support/vendor_ingest/` - vendor metadata parsers that convert upstream source files into importable overlay artifacts

These scripts are intended to be run from the repo root, typically with `PYTHONPATH=backend` when they import backend services.

## QuickBooks Wave Status: ✅ COMPLETE

The QuickBooks vendor wave is fully implemented and materialized with 5-phase pipeline matching SAP approach.

### QB Wave Output Summary
- **Inventory**: 922 QB table-field rows classified (55 direct, 46 description, 44 strong, 241 weak, 492 unmapped)
- **Wave-1 Promotion**: 101 rows promoted (conservative direct + description matches)
- **Wave-2 Expansion**: 88 rows promoted (strong candidates + knowledge-only concepts)
- **Materialized Contexts**: 101 high-confidence field contexts
- **Knowledge Overlay**: 64 unique concept-alias pairs for runtime discovery
- **Field Context Enrichment**: +55 QB contexts added to canonical enrichment (total: 1,515 entries)
- **Review Queue**: 733 rows prioritized by module (AR: 265, AP: 140, GL: 101, INV: 98, PAY: 89, RPT: 40)

### QB Pipeline Commands

**Phase 1: Classify QB inventory**
```bash
PYTHONPATH=backend python support/quickbooks/generate_quickbooks_tables_inventory.py
```

**Phase 2: Wave-1 conservative promotion**
```bash
PYTHONPATH=backend python support/quickbooks/promote_quickbooks_canonical_matches.py
```

**Phase 3: Wave-2 expansion promotion**
```bash
PYTHONPATH=backend python support/quickbooks/promote_quickbooks_canonical_expansions.py
```

**Phase 4: Prioritize review queue**
```bash
PYTHONPATH=backend python support/quickbooks/prioritize_quickbooks_review_queue.py
```

**Phase 5: Materialize field contexts**
```bash
PYTHONPATH=backend python support/quickbooks/materialize_quickbooks_canonical_contexts.py
```

**Phase 6: Generate knowledge overlay**
```bash
PYTHONPATH=backend python support/quickbooks/generate_qb_knowledge_overlay.py
```

**Phase 7: Enrich canonical field contexts**
```bash
PYTHONPATH=backend python support/quickbooks/enrich_canonical_field_contexts_with_qb.py
```

**Phase 8: Enrich canonical glossary**
```bash
PYTHONPATH=backend python support/quickbooks/enrich_canonical_glossary_with_qb.py
```

### QB Showcase & Documentation
- [QB Entity Mapping Showcase](../ui_fixtures/showcase_quickbooks_entity_mapping.md) — workflow examples and mapping patterns
- [QB Runtime Inventory](../knowledge_sources/generated/runtime/quickbooks/) — all generated artifacts
- [Source Inventory](../knowledge_sources/source_inventory.csv) — QB source registration with runtime wiring status

## Workday HRDH Datahub Wave (Completed)

### Overview
Implemented complete Workday HRDH datahub classification, promotion, materialization, and runtime integration following proven SAP/QB patterns. HRDH is the authoritative Workday HR data ingest layer (central datahub); 1,428 columns across 205 tables classified and promoted.

### Results Summary
- **Input**: HRDH_Table_Columns.xlsx (205 tables, 1,428 columns)
- **Classification**: 1 direct (0.5%), 160 weak (78%), 36 knowledge (18%), 8 unmapped (4%)
- **Wave-1 Promotion**: 1 direct match
- **Wave-2 Promotion**: 196 knowledge + weak (≥0.50 HR-context threshold)
- **Total Promoted**: 197 fields (96% coverage)
- **Materialized Contexts**: 197 field context records
- **Canonical Enrichment**: +197 field contexts, +2 new concepts
- **Knowledge Overlay**: 15 unique concept-alias pairs (auto-loaded at runtime)
- **Review Queue**: 204 candidates (wave-1/wave-2 review + unmapped)

### Key Differences from QB Wave
- **Classification distribution**: 78% weak candidates vs QB 26% (HR domain has noisier signal)
- **Wave-2 threshold**: ≥0.50 (WD HR context) vs QB ≥0.75 (stricter ERP context)
- **Materialization scope**: All promoted (wave-1 + wave-2) vs QB wave-1 only
- **Concept enrichment**: +2 new concepts (WD HR domain) vs QB +0 (full existing glossary consistency)

### Execution Commands

1. **Classify HRDH tables**:
   ```bash
   PYTHONPATH=backend python support/workday/generate_workday_datahub_inventory.py
   ```
   Output: `workday_datahub_classification.csv` (205 rows × 15 columns)

2. **Wave-1 promotion (direct matches)**:
   ```bash
   PYTHONPATH=backend python support/workday/promote_workday_canonical_matches.py
   ```
   Output: `workday_promoted_canonical_aliases.csv` (1 row)

3. **Wave-2 expansion (knowledge + weak ≥0.50)**:
   ```bash
   PYTHONPATH=backend python support/workday/promote_workday_canonical_expansions.py
   ```
   Output: `workday_wave2_promoted_canonical_expansions.csv` (196 rows)

4. **Materialize field contexts**:
   ```bash
   PYTHONPATH=backend python support/workday/materialize_workday_canonical_contexts.py
   ```
   Output: `workday_materialized_canonical_contexts.csv` (197 rows)

5. **Prioritize review queue**:
   ```bash
   PYTHONPATH=backend python support/workday/prioritize_workday_review_queue.py
   ```
   Output: `workday_priority_review_queue.csv` (204 rows)

6. **Generate knowledge overlay**:
   ```bash
   PYTHONPATH=backend python support/workday/generate_wd_knowledge_overlay.py
   ```
   Output: `wd_datahub_knowledge_overlay.csv` (15 entries)

7. **Enrich canonical field contexts**:
   ```bash
   PYTHONPATH=backend python support/workday/enrich_canonical_field_contexts_with_wd.py
   ```
   Output: Updated `canonical_field_context_enrichment.csv` (+197 entries → 1,712 total)

8. **Enrich canonical glossary**:
   ```bash
   PYTHONPATH=backend python support/workday/enrich_canonical_glossary_with_wd.py
   ```
   Output: Updated `canonical_glossary_erp.csv` (+2 concepts → 484 total)

### Artifacts Generated
- Classification: `workday_datahub_classification.csv`
- Promotions: `workday_promoted_canonical_aliases.csv`, `workday_wave2_promoted_canonical_expansions.csv`
- Materialized: `workday_materialized_canonical_contexts.csv`
- Overlay: `wd_datahub_knowledge_overlay.csv` (runtime auto-loaded)
- Review queues: `workday_promotion_review_queue.csv`, `workday_priority_review_queue.csv`

### Runtime Integration
- **Service**: `backend/app/services/metadata_knowledge_service.py`
- **Auto-loading**: `wd_datahub_knowledge_overlay.csv` loaded during `refresh()` with source hash validation
- **Utilities**: `support/workday/wd_data_entity_helpers.py`
  - `WDEntityResolver` — resolve_field(table, column) → ConceptInfo
  - `WDModuleTaxonomy` — Map tables to HR functional areas (Core HR, Compensation, Staffing, Talent, Benefits)

### Documentation
- Pattern guide: [Workday HRDH Mapping Pattern](../docs/patterns/workday_datahub_mapping.md)
- Entity showcase: [Workday Entity Mapping Showcase](../ui_fixtures/showcase_workday_datahub_mapping.md)
- Authority matrix: [Canonical Authority Matrix](../docs/reference/KNOWLEDGE_CANONICAL_AUTHORITY_MATRIX.md) (updated)

---
