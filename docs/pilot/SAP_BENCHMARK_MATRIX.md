# SAP Benchmark Matrix

## Purpose

This document defines the first benchmark matrix for the SAP-first knowledge expansion and canonical coverage wave.

It is intentionally based on fixture families that already exist in the repo so the wave can begin with measurable baselines instead of synthetic backlog planning.

These benchmark fixtures are not the SAP source inventory for the wave. They are only a measurement harness. The actual SAP source inventory is the `Tbls_Clm` sheet in `metadata_dict/sap_tables_mostUsed.xlsx`, which currently contains 10,739 SAP table-column rows that need SAP-to-knowledge and SAP-to-canonical classification.

Use it together with:

- `docs/vision/KNOWLEDGE_EXPANSION_WAVE.md`
- `docs/reference/VENDOR_KNOWLEDGE_INGEST_AND_SOURCE_INVENTORY.md`
- `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`

## KPI Set For The First Wave

Each benchmark slice should capture at least:

- percent of source fields with `knowledge > 0`
- percent of source fields with `canonical > 0`
- top-1 candidate accuracy
- final selected mapping accuracy after one-to-one assignment
- percent of mappings at or above auto-accept threshold
- percent of low-confidence mappings
- percent of errors caused by missing knowledge
- percent of errors caused by missing canonical concepts
- percent of errors caused by assignment or score-fusion behavior

## Priority Slice Matrix

### Slice 1. Supplier master

- Fixture family: `ui_fixtures/showcase_supplier_master/`
- Domain: vendor master / AP master data
- Current value: already used as a real diagnostic case and now a baseline regression anchor
- Focus fields: `LIFNR`, `KTOKK`, `NAME1`, `LAND1`, `REGIO`, `ORT01`, `PSTLZ`, `STRAS`, `STCD1`, `ZTERM`, `AKONT`, `SPERR`, `LOEVM`, `TELF1`
- Wave question: how much coverage and quality can be raised by broader supplier/AP SAP knowledge without over-promoting vendor-specific concepts into canonical

### Slice 2. Customer sales area

- Fixture family: `ui_fixtures/showcase_customer_sales_area/`
- Domain: SD customer sales-area / commercial setup
- Focus goal: sales-area and distribution/channel style attributes that often blur the line between business concepts and SAP configuration fields
- Wave question: which fields should remain knowledge-only and which deserve canonical promotion

### Slice 3. Material master

- Fixture family: `ui_fixtures/showcase_material_master/`
- Domain: material master / product master
- Focus goal: material identity, engineering aliases, lifecycle, stock and classification semantics
- Wave question: how much current material coverage already exists and where SAP-specific material/admin fields still dominate

### Slice 4. Purchasing info record

- Fixture family: `ui_fixtures/showcase_purchasing_info_record/`
- Domain: procurement / purchasing
- Focus goal: vendor-material purchasing semantics, pricing, and procurement context
- Wave question: what additional procurement-specific knowledge is needed before broader AP/MM SAP refreshes are considered strong

## Execution Order

Recommended order for the first wave:

1. Supplier master
2. Customer sales area
3. Material master
4. Purchasing info record

Reason:

- supplier master provides the cleanest early signal for business-facing SAP knowledge gains
- material master already has meaningful curated coverage and is a good mid-wave validation slice
- customer sales area and purchasing info record are better later tests because they include more system-specific or configuration-heavy semantics

## Baseline Measurement Rules

For every slice, capture two baselines before major ingest changes:

### Baseline A. Current default runtime

Run the fixture with the current production-default mapping behavior.

### Baseline B. Controlled diagnostic mode

Run the same fixture with any temporary diagnostic settings needed to understand whether misses come from:

- no knowledge support
- no canonical support
- good ranking but wrong final assignment
- weak score fusion despite valid knowledge support

Diagnostic settings should not become permanent product behavior without measured gains.

## Result Template

Each benchmark result should capture:

| Field | Meaning |
|---|---|
| `benchmark_id` | unique run identifier |
| `system` | `SAP` |
| `slice` | supplier_master, customer_sales_area, material_master, purchasing_info_record |
| `fixture_path` | repo path to the fixture family |
| `source_format` | csv, xml, xlsx, sql, spec |
| `target_format` | csv, json, xlsx, sql, spec |
| `source_field_count` | source column count |
| `mapped_field_count` | final selected mapping count |
| `knowledge_coverage_ratio` | percent of fields with `knowledge > 0` |
| `canonical_coverage_ratio` | percent of fields with `canonical > 0` |
| `top1_accuracy` | accuracy of first-ranked candidate |
| `final_accuracy` | accuracy after one-to-one assignment |
| `auto_accept_ratio` | percent at or above auto-accept threshold |
| `low_confidence_ratio` | percent still marked low confidence |
| `primary_failure_mode` | missing_knowledge, missing_canonical, assignment, score_fusion, mixed |
| `notes` | human review notes |

## Exit Condition For SAP-First Benchmarking

The first SAP benchmark loop should be considered good enough to widen when:

- all four SAP-like slice families have a recorded baseline
- at least supplier, customer sales area, and material slices show measurable gains from the first knowledge refresh wave
- the remaining misses are categorized clearly enough to separate true knowledge gaps from scoring or assignment issues

This benchmark exit condition does not mean the SAP wave is complete. It only means the measurement harness is ready. The main SAP wave is complete only after the full workbook inventory has been processed into:

- matched existing canonical concepts
- knowledge-only SAP-specific fields
- canonical gap candidates requiring stewardship

## Follow-On Extension

After the SAP baseline matrix is stable, create equivalent matrices for:

- Workday HR and HRDH-derived fixtures
- QAD-heavy inventory or manufacturing fixtures
- QuickBooks accounting and customer/vendor fixtures