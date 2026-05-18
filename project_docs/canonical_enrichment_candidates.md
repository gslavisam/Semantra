# Canonical Enrichment Candidate Report

Generated: 2026-05-17T21:27:48+00:00

This report is a review queue for enriching the canonical concept layer from the approved metadata sources. It does not apply changes to SQLite or seed files. The CSV companion is the working review artifact.

## Companion CSV

- `project_docs/canonical_enrichment_candidates.csv`
- Total candidate rows: 1121

## Source Profile

| Source | Role | Current conclusion |
| --- | --- | --- |
| `metadata_dict/canonical_glossary_erp.csv` | Baseline canonical seed | 466 rows and 466/466 overlap with runtime SQLite concepts. Use as baseline, not as incremental candidate source. |
| `metadata_dict/metadata_dict.csv` | Cross-system naming variants | Use for alias proposals only after unique matching to existing concepts. |
| `metadata_dict/wd_hr_knowledge_overlay.csv` | Workday alias overlay | Good alias/context source, but has two unknown IDs requiring review. |
| `metadata_dict/sap_tables_mostUsed.xlsx#Tbls_Clm` | SAP table/field metadata | Strongest source for `canonical_field_contexts`; many existing concepts can gain SAP table/field evidence. |
| `metadata_dict/quickbooks_tables_reference.xlsx#Tbls_Fields` | QuickBooks table/field metadata | Useful for SME ERP/accounting field contexts; must be table-aware to avoid generic `Name`/`ID` false positives. |

## Candidate Counts

### By Action

- `add_alias`: 743
- `add_field_context`: 372
- `do_not_add_now`: 4
- `map_existing_or_new_decision`: 1
- `new_concept_candidate`: 1

### By Source

- `Cross-system`: 474
- `QuickBooks`: 116
- `SAP`: 260
- `Workday`: 271

### By Priority

- `P0`: 2
- `P1`: 529
- `P2`: 586
- `P3`: 4

## Review Rules

- `P0`: resolve before bulk import or promotion.
- `P1`: high-value enrichment candidates, mostly source field contexts.
- `P2`: useful alias or context candidates that need normal stewardship review.
- `P3`: explicit non-import examples or integration-control fields.

Actions:

- `add_alias`: candidate alias for an existing canonical concept.
- `add_field_context`: candidate source-system table/field context for an existing canonical concept.
- `new_concept_candidate`: candidate canonical concept that appears missing.
- `map_existing_or_new_decision`: source refers to an unknown ID that may map to an existing concept.
- `do_not_add_now`: intentionally captured as a review note, not a recommended import.

## Immediate Decisions

1. `employee.phone` appears in the Workday overlay but is missing from runtime canonical concepts. Recommended decision: add `employee.phone` unless a broader contact model is introduced first. Review phone aliases before promotion.
2. `invoice.currency` appears in the Workday overlay but is missing from runtime canonical concepts. Recommended decision: do not import the aliases directly; first decide whether currency-code rows map to `invoice.document_currency_code`/`currency.code` and whether compensation amount rows are misclassified.
3. Use SAP candidates first for `canonical_field_contexts`; this is the highest-confidence enrichment path.
4. Use QuickBooks candidates only with table-aware review because generic field names are otherwise noisy.
5. Use `metadata_dict.csv` as alias input, not as a source of new canonical concepts.

## Suggested Next Step

Review the two `P0` rows first, then filter the CSV by `action=add_field_context` and `source_system=SAP`. Promote only accepted rows into overlay/import scripts after review.
