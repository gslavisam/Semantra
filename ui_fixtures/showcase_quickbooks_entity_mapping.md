# QuickBooks Data Entity Mapping Showcase

QuickBooks table and field mapping showcase for Semantra canonical discovery pipeline.

## Overview

This fixture demonstrates how QuickBooks data entities can be mapped to canonical business concepts through the knowledge and canonical layers.

## QB Entity Profile Example: Customer

### Source Data
```
Table: Customer
Module: AR (Accounts Receivable)
Fields: Id, FullName, IsActive, Salutation, Email, Phone, CreditLimit, ...
```

### Classification Results
- `Customer.Id` → DIRECT MATCH → `party.id` (confidence: 100%)
- `Customer.FullName` → DIRECT MATCH → `contact.name` (confidence: 100%)
- `Customer.IsActive` → DIRECT MATCH → `account.status` (confidence: 100%)
- `Customer.Email` → DESCRIPTION MATCH → `customer.email` (confidence: 95%)
- `Customer.Phone` → DESCRIPTION MATCH → `customer.phone` (confidence: 95%)
- `Customer.CreditLimit` → STRONG CANDIDATE → `customer.credit_limit` (confidence: 78%)

### Runtime Mapping
Once classified and promoted:
1. High-confidence matches (direct + description) automatically added to knowledge overlay
2. Field contexts materialized to `canonical_field_context_enrichment.csv`
3. Knowledge overlay loaded during runtime refresh
4. QB Customer entity discoverable via canonical concept queries

## Typical QB Ingest Workflow

### Phase 1: Inventory & Classification
```bash
python support/quickbooks/generate_quickbooks_tables_inventory.py
# Output: quickbooks_tables_fields_classification.csv (922 rows classified)
# Results: 55 direct matches, 46 description matches, 241 weak candidates, 492 unmapped
```

### Phase 2: Wave-1 Conservative Promotion
```bash
python support/quickbooks/promote_quickbooks_canonical_matches.py
# Promotes: 101 rows (direct + description matches)
# Output: quickbooks_promoted_canonical_aliases.csv
# Review Queue: 821 rows for steward review
```

### Phase 3: Wave-2 Expansion
```bash
python support/quickbooks/promote_quickbooks_canonical_expansions.py
# Promotes: 88 additional rows (44 strong candidates + 44 knowledge-only)
# Output: quickbooks_wave2_promoted_canonical_expansions.csv
```

### Phase 4: Context Materialization
```bash
python support/quickbooks/materialize_quickbooks_canonical_contexts.py
# Materializes: 101 high-confidence field contexts
# Output: quickbooks_materialized_canonical_contexts.csv
```

### Phase 5: Overlay & Enrichment Integration
```bash
python support/quickbooks/generate_qb_knowledge_overlay.py
# Overlay Generation: 64 unique concept-alias pairs
# Output: qb_knowledge_overlay.csv (auto-loaded by runtime)

python support/quickbooks/enrich_canonical_field_contexts_with_qb.py
# Field Context Enrichment: +55 contexts added
# Canonical enrichment now includes QB table-field mappings

python support/quickbooks/enrich_canonical_glossary_with_qb.py
# Glossary Enhancement: QB aliases added to existing concepts
```

## Data Entity Mapping for Future QB Sources

Once the QB fixture is established, mapping new QB data sources is streamlined:

1. **New QB Data Source** (e.g., QB data export)
   - Extract table + field + description
   - Run against discovery pipeline
   - Use established QB canonical mappings as baseline
   - Reuse qb_knowledge_overlay.csv for fast concept lookups

2. **Field-Level Mapping**
   - QB field → materialized_canonical_contexts lookup
   - Field → canonical concept_id resolution
   - Enable automated field discovery, tagging, lineage

3. **Batch Operations**
   - Bulk QB table imports
   - Leverage existing QB module-to-domain knowledge
   - Fast feedback on mapping confidence

## Key QB Modules Covered

| Module | Rows | Priority |
|--------|------|----------|
| AR (Accounts Receivable) | 265 | High |
| AP (Accounts Payable) | 140 | High |
| GL (General Ledger) | 101 | High |
| INV (Inventory) | 98 | Medium |
| PAY (Payroll) | 89 | Medium |
| RPT (Reporting) | 40 | Low |

## Testing & Validation

Run the QB discovery pipeline dry-run mode to preview:
```bash
python support/quickbooks/promote_quickbooks_canonical_matches.py --dry-run
```

Inspect generated CSVs:
- `quickbooks_priority_review_queue.csv` — steward review candidates
- `quickbooks_canonical_gap_candidates.csv` — unmapped/knowledge-only rows

## Future Enhancements

- QB data source native connector (API polling)
- Real-time field-level discovery from live QB instances
- Automated classification updates when QB schema changes
- QB-specific domain expertise layer (e.g., multi-currency handling, audit trail fields)
- Cross-vendor QB-SAP mapping for master data reconciliation
