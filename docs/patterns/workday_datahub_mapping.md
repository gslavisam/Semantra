# Workday HRDH Datahub Mapping Pattern

## Overview

Workday HR data flows through a central **HRDH (Harmonized Reporting Data Hub)** datahub, not directly from the `hr_wd.xml` XSD. This pattern demonstrates how to discover, classify, and materialize Workday HRDH field mappings to canonical HR concepts using a repeatable 6-phase workflow.

**Core principle**: HRDH is the authoritative ingest layer; datahub tables and columns represent all HR-related data entities.

## Architecture

### Layers

```
┌─────────────────────────────────────────────────────────┐
│ Workday HRDH Datahub (Source)                          │
│ - 205 tables, ~1,428 columns                           │
│ - Schema-only inventory (HRDH_Table_Columns.xlsx)      │
│ - Domain: Human Capital Management                     │
└──────────────────────┬──────────────────────────────────┘
                       │
            [Phase 1: Classification]
            ↓
        ┌───────────────────────────────────────┐
        │ Classification Buckets (6-bucket      │
        │ taxonomy:                             │
        │ - direct_alias_match (0.5%)           │
        │ - knowledge_only (18%)                │
        │ - weak_canonical_candidate (78%)      │
        │ - unmapped (4%)                       │
        └─────────┬─────────────────────────────┘
                  │
         [Phase 2-3: Promotion Waves]
         ├─ Wave-1: Direct matches only (1 row)
         └─ Wave-2: Knowledge + weak ≥0.50 (196 rows)
                  │
            [Phase 4: Materialization]
            ↓
        ┌────────────────────────────────────────┐
        │ Materialized Contexts (197 field       │
        │ context records for runtime discovery) │
        └─────────┬──────────────────────────────┘
                  │
      [Phase 5: Overlay Generation]
      ├─ Wave-1 overlay entries (1)
      └─ Wave-2 overlay entries (196)
                  │
      [Phase 6: Canonical Enrichment]
      ├─ Field context enrichment (+197 entries)
      └─ Canonical glossary enrichment (+2 new concepts)
                  │
                  ↓
        ┌─────────────────────────────────────┐
        │ Runtime Integration                 │
        │ - metadata_knowledge_service.py     │
        │   auto-loads wd_datahub_overlay.csv │
        │ - WDEntityResolver for field lookup │
        │ - WDModuleTaxonomy for area mapping │
        └─────────────────────────────────────┘
```

### Phase Breakdown

#### Phase 1: Classification
**Script**: `support/workday/generate_workday_datahub_inventory.py`

Reads HRDH_Table_Columns.xlsx (205 tables, 1,428 columns) and classifies each field against:
- Direct field name matches to canonical aliases
- Description matches to canonical concepts
- Knowledge base concepts
- Top canonical match strength (threshold varies by bucket)

**Output**: `workday_datahub_classification.csv` with 6 buckets
```
Classification Bucket Distribution:
  direct_alias_match: 1 (0.5%)
  knowledge_only: 36 (18%)
  weak_canonical_candidate: 160 (78%)
  unmapped: 8 (4%)
Total: 205 rows
```

**Key decisions**:
- Threshold for weak candidates: ≥0.50 (lower than QB's ≥0.75)
  - Rationale: Workday HR domain allows more lenient matching; 78% of rows are weak candidates
- Schema-only defaults: dtype="object", null_ratio=0.5 (nullable), unique_ratio=0.5

#### Phase 2: Wave-1 Promotion (Conservative)
**Script**: `support/workday/promote_workday_canonical_matches.py`

Promotes only `direct_alias_match` rows: high confidence, no risk.

**Output**: 1 promoted row, 204 in review queue

#### Phase 3: Wave-2 Expansion (HR-Context Aware)
**Script**: `support/workday/promote_workday_canonical_expansions.py`

Promotes `knowledge_only` + `weak_canonical_candidate` (≥0.50 strength) rows.
- **Knowledge-only**: Concept exists in knowledge base but no canonical match strength available → PROMOTE
- **Weak candidates ≥0.50**: Canonical match signal exists but below QB threshold → PROMOTE (HR context justifies inclusion)

**Output**: 196 promoted rows (36 knowledge + 160 weak candidates)

#### Phase 4: Materialization
**Script**: `support/workday/materialize_workday_canonical_contexts.py`

Extracts field contexts for all promoted rows (wave-1 + wave-2) as durable discovery records:
```
concept_id, system, object_name, field_name, category, field_description, note
```

**Category**: Always "HR" for HRDH (Human Capital Management domain)
**Confidence levels** (encoded in note):
- High: from direct_alias_match
- Medium: from knowledge_only
- Low: from weak_canonical_candidate

**Output**: 197 materialized field contexts

#### Phase 5: Overlay Generation
**Script**: `support/workday/generate_wd_knowledge_overlay.py`

Converts promoted rows into knowledge overlay entries for runtime auto-loading:
```
entry_type, canonical_term, canonical_concept_id, alias, domain, source_system, note
```

Runtime loads overlay via `metadata_knowledge_service.refresh()`, enabling instant field alias discovery without re-classification.

**Output**: 15 unique concept-alias pairs (Wave-1 + Wave-2 deduped)

#### Phase 6: Canonical Enrichment
**Scripts**:
- `support/workday/enrich_canonical_field_contexts_with_wd.py`
- `support/workday/enrich_canonical_glossary_with_wd.py`

Merges WD-sourced concepts and field contexts into authoritative canonical layers:
- **Field context enrichment**: +197 rows to `canonical_field_context_enrichment.csv` (QB: +55, HRDH earlier: many)
- **Canonical glossary enrichment**: +2 new concepts to `canonical_glossary_erp.csv` (QB: +0, SAP: many)

**Deduplication**: Skips rows already present in canonical layer.

---

## Quick Mapping Example

### Scenario: Map Workday employee ID to canonical concept

```python
from support.workday.wd_data_entity_helpers import WDEntityResolver

resolver = WDEntityResolver()

# Resolve field
concept = resolver.resolve_field("EMPLOYEE_PROFILE", "EMPLOYEE_ID")
if concept:
    print(f"Concept: {concept.concept_id}")
    print(f"Confidence: {concept.confidence}")
    print(f"Source: {concept.source_system}")
else:
    print("Field not mapped")

# List available tables
tables = resolver.list_tables()

# List fields in a table
fields = resolver.list_table_fields("EMPLOYEE_PROFILE")
```

### Scenario: Navigate by HR functional area

```python
from support.workday.wd_data_entity_helpers import WDModuleTaxonomy

# Get functional area for a table
area = WDModuleTaxonomy.get_functional_area("EMPLOYEE_PROFILE")
# Output: "Core HR"

# List all Core HR tables
tables = WDModuleTaxonomy.get_tables_for_area("Core HR")
# Output: ["CR_DIM_EMPLOYEE", "CR_DIM_POSITION", ...]

# Enumerate all areas
all_areas = WDModuleTaxonomy.list_functional_areas()
```

---

## Workday Data Entity Workflow

### For New Workday Data Sources

If a new Workday data source appears (e.g., new custom HRDH table or external WD API):

1. **Ingest**: Add table-column definitions to HRDH_Table_Columns.xlsx (Overview sheet) or create new source inventory
2. **Classify**: Run `generate_workday_datahub_inventory.py` to classify against canonical
3. **Promote**: Run promotion waves (wave-1, wave-2) based on confidence thresholds
4. **Materialize**: Extract field contexts and overlay entries
5. **Enrich**: Merge into canonical field context + glossary
6. **Register**: Update `metadata_knowledge_service.py` to auto-load overlay
7. **Consume**: Use `WDEntityResolver` or `WDModuleTaxonomy` for runtime field lookups

---

## Generated Artifacts

### Classification & Promotion
- `workday_datahub_classification.csv` - Initial 6-bucket classification (205 rows)
- `workday_promoted_canonical_aliases.csv` - Wave-1 direct matches (1 row)
- `workday_wave2_promoted_canonical_expansions.csv` - Wave-2 knowledge + weak (196 rows)

### Materialization & Overlay
- `workday_materialized_canonical_contexts.csv` - 197 field context records
- `wd_datahub_knowledge_overlay.csv` - 15 concept-alias pairs (auto-loaded at runtime)

### Canonical Enrichment
- `canonical_field_context_enrichment.csv` - Updated: +197 WD entries (1,712 total)
- `canonical_glossary_erp.csv` - Updated: +2 WD concepts (484 total)

### Review & Prioritization
- `workday_promotion_review_queue.csv` - Wave-1 review candidates (204 rows)
- `workday_wave2_review_queue.csv` - Wave-2 review candidates (9 rows)
- `workday_priority_review_queue.csv` - Sorted by table volume

---

## Confidence Levels & Workflow Logic

### Classification Buckets → Promotion Rules

| Bucket | Count | Promotion | Confidence | Rationale |
|--------|-------|-----------|------------|-----------|
| direct_alias_match | 1 | Wave-1 | High | Exact field name match to canonical alias |
| knowledge_only | 36 | Wave-2 | Medium | Concept exists in knowledge base; promote for HR domain |
| weak_canonical_candidate | 160 | Wave-2 (≥0.50) | Low→Medium | Canonical match <0.75; HR context + higher threshold = safe inclusion |
| unmapped | 8 | Review | N/A | No signal; requires manual review or external enrichment |

### Confidence Encoding in Runtime

Field context `note` field encodes source confidence:
- `"direct_alias_match"` → confidence=high
- `"knowledge_only"` → confidence=medium
- `"weak_canonical_candidate"` → confidence=low

Runtime consumers can filter by confidence thresholds (e.g., only use high+medium for strict pipelines, all three for exploratory discovery).

---

## Runtime Integration Details

### Auto-Loading During Startup

`metadata_knowledge_service.refresh()` executes this sequence:

```python
# Load existing overlays
self._load_csv_knowledge_overlay(DEFAULT_HRDH_OVERLAY_PATH, source_tag="HRDH")
self._load_csv_knowledge_overlay(DEFAULT_WD_DATAHUB_OVERLAY_PATH, source_tag="Workday_HRDH")
self._load_csv_knowledge_overlay(DEFAULT_QB_OVERLAY_PATH, source_tag="QuickBooks")

# Load enrichment layer
self._load_canonical_field_context_enrichment(DEFAULT_CANONICAL_FIELD_CONTEXT_ENRICHMENT_PATH)
```

Cache validation: If any source file (HRDH_Table_Columns.xlsx, wd_datahub_knowledge_overlay.csv) changes, hash mismatch triggers full reseed.

### Field Resolution Flow

```
User queries: resolve_field("EMPLOYEE_PROFILE", "EMPLOYEE_ID")
  ↓
1. Check materialized contexts (fast lookup)
   → Found: return ConceptInfo with confidence=high/medium/low
2. If not found, check knowledge overlay
   → Found: return ConceptInfo via alias
3. If still not found, return None
```

---

## Future Extensions

1. **Custom HRDH Tables**: Add new HRDH table definitions, run classifier, promote via same workflow
2. **External WD APIs**: If Workday API exposes new entities, import as CSV, ingest like HRDH step 1
3. **Cross-Vendor Mapping**: Workday→QB, Workday→SAP discovered via shared canonical concepts
4. **Threshold Tuning**: Adjust wave-2 threshold (currently ≥0.50) based on domain requirements

---

## See Also

- [Workday Entity Showcase](../../ui_fixtures/showcase_workday_datahub_mapping.md)
- [Canonical Authority Matrix](../../docs/reference/KNOWLEDGE_CANONICAL_AUTHORITY_MATRIX.md)
- [QB Data Entity Mapping](./quickbooks_data_entity_mapping.md)
- [WD Helper Utilities](../../support/workday/wd_data_entity_helpers.py)
