# Vendor Knowledge Ingest And Source Inventory

## Purpose

This document is the first operational reference for the knowledge-expansion wave.

It does three things:

- inventories the vendor knowledge sources already present in the repo
- distinguishes between sources already wired into runtime and sources only available for future ingest
- defines the first staged schema and folder layout for raw, staged, and generated knowledge assets

Use it together with:

- `docs/vision/KNOWLEDGE_EXPANSION_WAVE.md`
- `project_docs/implementation_checklists.md`
- `backend/app/services/metadata_knowledge_service.py`

## Current Source Inventory

### A. Runtime-wired sources already used by `metadata_knowledge_service`

These files are already part of the current knowledge/canonical runtime path.

| Source | Current role | Notes |
|---|---|---|
| `metadata_dict/metadata_dict.csv` | base field alias and multilingual knowledge dictionary | current broad curated base |
| `metadata_dict/metadata_dictionary.xlsx` | workbook-driven enrichment and context import | already read by runtime |
| `metadata_dict/sap_tables_mostUsed.xlsx` | SAP object and field context source | already wired |
| `metadata_dict/qad_tables_mostUsed.xlsx` | QAD object and field context source | already wired |
| `metadata_dict/WD_entities_mostUsed.xlsx` | Workday entity and field context source | already wired |
| `metadata_dict/hrdh_knowledge_overlay.csv` | HRDH overlay source | auto-loaded runtime overlay helper |
| `metadata_dict/canonical_glossary_erp.csv` | canonical business concept registry | canonical source of truth |
| `metadata_dict/canonical_field_context_enrichment.csv` | canonical field context enrichment | canonical context extension |

### B. Repo sources available for staged ingest but not part of the main runtime source stack today

These are valuable wave inputs, but they should be inventoried and staged before becoming runtime-fed knowledge.

| Source | Current role | Notes |
|---|---|---|
| `metadata_dict/QuickBooks_Online_API_Mapping.xlsx` | QuickBooks field/system reference | present locally, not runtime-wired today |
| `metadata_dict/quickbooks_tables_reference.xlsx` | QuickBooks table/field reference | present locally, not runtime-wired today |
| `metadata_dict/hr_wd.xml` | raw Workday XSD-style source | upstream parse source, not direct runtime input |
| `metadata_dict/HRDH_Table_Columns.xlsx` | HR Data Hub database column export | upstream parse source, not direct runtime input |

### C. Existing parser/generator helpers that should be treated as ingestion assets

| Helper | Current output | Notes |
|---|---|---|
| `support/vendor_ingest/parse_workday_xsd.py` | `metadata_dict/wd_hr_knowledge_overlay.csv` | converts Workday XSD into an importable knowledge overlay |
| `support/vendor_ingest/parse_hrdh_columns.py` | `metadata_dict/hrdh_knowledge_overlay.csv` | converts HRDH SQL Server column export into an importable overlay |

These helpers should remain part of the new wave, but their outputs should be tracked through staging and provenance instead of being treated as one-off script side effects.

### D. Existing SAP benchmark fixture families already present in the repo

These fixtures are the first benchmark candidates for the SAP-first wave.

| Fixture family | Likely domain slice | Status |
|---|---|---|
| `ui_fixtures/showcase_supplier_master/` | vendor master / AP master data | already used in recent debugging and scoring work |
| `ui_fixtures/showcase_customer_sales_area/` | SD customer sales-area attributes | available |
| `ui_fixtures/showcase_material_master/` | material master | available |
| `ui_fixtures/showcase_purchasing_info_record/` | purchasing / procurement | available |

The repo also contains `ui_fixtures/showcase_customer_mapping/`, but that fixture family is generic customer/CRM oriented and should stay outside the SAP-only wave.

## Operational Classification Rules

For this wave, every vendor source should be classified as one of:

- `runtime_wired`: already used by `metadata_knowledge_service`
- `available_for_ingest`: present in repo but not yet runtime-wired
- `generated_overlay_source`: script-driven upstream source that can produce knowledge artifacts
- `benchmark_fixture`: used for mapping-quality evaluation rather than direct knowledge ingestion

This classification matters because not every file in `metadata_dict/` should immediately become a runtime source.

## Proposed Folder Layout

The wave should stop relying on one flat vendor-source bucket under `metadata_dict/` for every new large ingest.

Proposed operational layout:

```text
knowledge_sources/
  raw/
    sap/
    workday/
    qad/
    quickbooks/
  staged/
    sap/
    workday/
    qad/
    quickbooks/
  generated/
    runtime/
    overlays/

benchmarks/
  vendor_coverage/
    sap/
    workday/
    qad/
    quickbooks/
```

### Intent of each layer

#### `knowledge_sources/raw/`

Holds source-of-record raw vendor assets or exact copied internal/public references.

Examples:

- raw SAP table or field workbooks
- raw Workday XSD or entity exports
- raw QuickBooks mapping references

#### `knowledge_sources/staged/`

Holds normalized row-oriented staged records with provenance.

These are the key refresh inputs that can be regenerated from raw sources.

#### `knowledge_sources/generated/`

Holds generated artifacts intended to feed runtime or import flows.

Examples:

- generated CSVs for curated knowledge refreshes
- generated overlays
- generated canonical-gap candidate exports

#### `benchmarks/vendor_coverage/`

Holds evaluation definitions and measured outcomes tied to vendor-specific waves.

This keeps the wave benchmark-driven instead of purely ingestion-driven.

## First Staged Record Schema

The first staging model should be vendor-agnostic enough to support SAP first and then Workday, QAD, and QuickBooks.

Recommended staged columns:

| Field | Meaning |
|---|---|
| `system` | vendor/system name such as `SAP`, `Workday`, `QAD`, `QuickBooks` |
| `module` | functional module or business area |
| `object_name` | table, entity, API object, or business object |
| `object_description` | human-readable description of the object |
| `field_name` | exact vendor field or attribute name |
| `field_description` | vendor field description |
| `normalized_field_name` | normalized alias text used during ingest/dedupe |
| `data_type` | vendor-reported type if present |
| `length_or_format` | length, scale, or display format if present |
| `sample_value` | optional representative example value |
| `domain` | Semantra business domain category |
| `source_artifact` | originating file name or source identifier |
| `source_type` | workbook, xsd, csv, api_ref, db_export, manual_curation |
| `source_scope` | `public`, `internal`, `partner`, or `unknown` |
| `parser_name` | helper that produced the staged row if generated |
| `last_verified_at` | last review or verification timestamp |
| `candidate_concept_id` | optional canonical concept hint if confidence is already strong |
| `promotion_status` | `knowledge_only`, `candidate`, `promoted`, `rejected` |
| `notes` | ingest comments, ambiguity warnings, or curation notes |

## Generated Runtime Output Expectations

The first wave should not directly replace `metadata_dict/metadata_dict.csv` with raw staged output.

Instead, staged inputs should generate one or more curated runtime artifacts such as:

- curated metadata dictionary refresh candidates
- overlay import candidates
- canonical-gap candidate exports
- benchmark-side coverage summaries

That gives Semantra a cleaner separation between source collection and runtime matching.

## Immediate Repo Baseline

Based on the current repo state, the first execution baseline should assume:

- SAP is the highest-priority system because it already has the broadest fixture set and an explicit `sap_tables_mostUsed.xlsx` runtime source
- Workday has both runtime-fed sources and upstream parser inputs already present locally
- QAD has a runtime-fed workbook source but no equally visible fixture family yet
- QuickBooks already has source assets locally, but they are not yet part of runtime ingest and therefore are better treated as phase-two staged inputs

## Immediate Next Steps

1. Move the known raw vendor assets into the new `knowledge_sources/raw` structure without changing runtime behavior yet.
2. Define the first staged CSV schema and one generated output contract for SAP-first refresh work.
3. Create one benchmark manifest per SAP fixture family under `benchmarks/vendor_coverage/sap/`.
4. Only after that begin any broader generated refresh of the live knowledge runtime.