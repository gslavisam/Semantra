# QuickBooks Data Entity Mapping Pattern

## Overview

This document describes the standard pattern for mapping QuickBooks data sources to canonical business concepts within Semantra, enabling fast field-level discovery and concept resolution.

## Architecture

The QB mapping pattern consists of 4 layers:

1. **Source Layer** (QB data)
   - QB table schema export (Tbls_Fields sheet from quickbooks_tables_reference.xlsx)
   - Table name, field name, description, data type

2. **Classification Layer** (inventory)
   - Classification script analyzes QB fields against knowledge/canonical
   - Produces 6 buckets: direct_match, description_match, strong/weak candidates, knowledge_only, unmapped
   - ~12% direct confidence, ~35% weak/unmapped requiring review

3. **Promotion Layer** (wave-based)
   - Wave-1: Conservative promotion of direct + description matches (101 rows)
   - Wave-2: Expansion promotion of strong candidates + knowledge-only (88 rows)
   - Produces canonical concept mappings ready for runtime

4. **Runtime Layer** (enriched canonical)
   - Knowledge overlay (64 concept-alias pairs) auto-loaded during refresh
   - Materialized field contexts (101 entries) support field-level discovery
   - Canonical glossary enriched with QB-sourced concepts
   - Field context enrichment enables batch operations

## Quick Mapping: New QB Data Source

### Step 1: Extract QB Schema
```python
# Parse QB data export
# Extract: table_name, field_name, field_description, data_type
qb_fields = [
    {"table": "Customer", "field": "FullName", "description": "Customer name", "type": "String"},
    {"table": "Invoice", "field": "DueDate", "description": "Invoice due date", "type": "Date"},
    ...
]
```

### Step 2: Resolve to Canonical
```python
from support.quickbooks.qb_data_entity_helpers import QBEntityResolver

resolver = QBEntityResolver()

for field in qb_fields:
    info = resolver.resolve_field(field["table"], field["field"])
    if info:
        print(f"{field['table']}.{field['field']} → {info['concept_id']}")
        print(f"  Confidence: {info['confidence']}")
        print(f"  Source: {info['source']}")
```

### Step 3: Batch Operations
```python
# Resolve all fields in a QB export
mapped_fields = []
for field in qb_fields:
    info = resolver.resolve_field(field["table"], field["field"])
    if info:
        mapped_fields.append({
            "qb_table": field["table"],
            "qb_field": field["field"],
            "canonical_concept": info["concept_id"],
            "confidence": info["confidence"],
            "description": field["description"],
        })

# Export for use in downstream discovery/lineage
```

### Step 4: Handle Unmapped Fields
```python
# Fields not in resolver:
unmapped = [f for f in qb_fields if not resolver.resolve_field(f["table"], f["field"])]

# Options:
# A. Run through classification pipeline for review
# B. Defer to future wave expansion
# C. Manual steward review
```

## QB Module-Based Organization

QuickBooks is organized into 6 functional modules:

| Module | Domain | Primary Objects | Typical Rows |
|--------|--------|---|---|
| AR | Accounts Receivable | Customer, Invoice, SalesReceipt, Payment | 265 |
| AP | Accounts Payable | Vendor, Bill, Check, PurchaseOrder | 140 |
| GL | General Ledger | Account, JournalEntry, Class | 101 |
| INV | Inventory | Item, InventoryAdjustment, Assembly | 98 |
| PAY | Payroll | Employee, Paycheck, Deduction | 89 |
| RPT | Reporting | Report metadata, Query results | 40 |

### Module-Specific Lookup
```python
resolver = QBEntityResolver()

# Get all AR fields with mappings
ar_fields = resolver.list_module_fields("AR")
print(f"AR has {len(ar_fields)} materialized field mappings")

# Module summary
modules = resolver.list_modules()
for module, count in sorted(modules.items()):
    print(f"{module}: {count} fields")
```

## Confidence Levels

### High (95%+)
- **direct_alias_match**: QB field name exactly matches canonical alias
- **description_alias_match**: QB field description mentions canonical concept term

### Medium (70-90%)
- **strong_canonical_candidate**: Top canonical match strength ≥ 0.75
- **knowledge_overlay**: Field resolved via knowledge concept

### Low (<70%)
- **weak_canonical_candidate**: Top canonical match strength < 0.75
- **knowledge_only**: Knowledge concept exists but no canonical mapping

## Generated Artifacts for QB Wave

All outputs in `knowledge_sources/generated/runtime/quickbooks/`:

| Artifact | Purpose | Rows | Use Case |
|---|---|---|---|
| `quickbooks_tables_fields_classification.csv` | Full inventory | 922 | Baseline classification |
| `quickbooks_promoted_canonical_aliases.csv` | Wave-1 promotions | 101 | High-confidence mappings |
| `quickbooks_wave2_promoted_canonical_expansions.csv` | Wave-2 promotions | 88 | Expanded mappings |
| `quickbooks_materialized_canonical_contexts.csv` | Field contexts | 101 | Runtime field discovery |
| `quickbooks_priority_review_queue.csv` | Review candidates | 733 | Steward triage |
| `qb_knowledge_overlay.csv` | Knowledge overlay | 64 | Runtime alias resolution |

## Runtime Integration

### Auto-Loading
QB overlay is automatically loaded during `metadata_knowledge_service.refresh()`:
1. Checks source hash (metadata_dict/quickbooks_tables_reference.xlsx + overlay file)
2. If hash matches cache, loads from SQLite
3. If hash changed, reseeds from QB materialized + overlay files
4. QB concept aliases now available for all knowledge queries

### Field-Level Lookups
```python
service = metadata_knowledge_service
canonical_matches = service.match_canonical_concepts(
    ColumnProfile(
        name="FullName",
        description="Customer full name",
    ),
    prefer_metadata_text=True
)
# Returns: contact.name (confidence ~95%) from QB wave

field_contexts = service.get_field_contexts("contact.name")
# Returns: QB materialized contexts + existing SAP/Workday contexts
```

## Future QB Data Sources

For new QB data ingests:

1. **Extract schema** (table + field + description)
2. **Use QBEntityResolver** to resolve known fields
3. **For unmapped**: run new export through classification if significant volume
4. **Leverage module taxonomy** for intelligent batching/prioritization
5. **Re-export and overlay refresh** triggers runtime cache invalidation

This pattern enables:
- ✅ Fast QB field → canonical resolution (lookup, batch)
- ✅ Module-aware field organization
- ✅ Confidence-based filtering
- ✅ Easy addition of new QB data sources
- ✅ Seamless runtime integration via knowledge/canonical layers

## See Also

- [QB Showcase](../../ui_fixtures/showcase_quickbooks_entity_mapping.md) — workflow examples
- [QBEntityResolver API](../../support/quickbooks/qb_data_entity_helpers.py) — helper utilities
- [QB Runtime Artifacts](../../knowledge_sources/generated/runtime/quickbooks/) — generated outputs
