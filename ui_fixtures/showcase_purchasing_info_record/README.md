# Purchasing Info Record Showcase Fixtures

This fixture set is designed for Semantra demos around SAP-like purchasing info record mapping.

## Included scenarios

1. CSV source -> JSON target
2. XML source -> CSV target
3. XLSX source -> XLSX target
4. Schema spec CSV source -> Schema spec CSV target
5. Multi-table SQL snapshot source -> Multi-table SQL snapshot target

## Recommended file pairs

- Row data demo: `showcase_pir_source.csv` with `showcase_pir_target.json`
- Cross-format row demo: `showcase_pir_source.xml` with `showcase_pir_target.csv`
- Spreadsheet demo: `showcase_pir_source.xlsx` with `showcase_pir_target.xlsx`
- Spec-to-spec demo: `showcase_pir_source_spec.csv` with `showcase_pir_target_spec.csv`
- Multi-table SQL demo:
  - source table: `eine_org`
  - target table: `purchasing_info_record_dim`

## SAP-like source fields covered

- INFNR
- LIFNR
- MATNR
- EKORG
- WERKS
- ESOKZ
- NETPR
- WAERS
- PEINH
- MINBM
- APLFZ
- INCO1
- INCO2
- BPRME

## Notes

- All row-data files contain 14 columns and 5 rows.
- SQL snapshots contain multiple tables so the table selector can be exercised.
- The set combines supplier, material, and purchasing-organization aspects typical for SAP info records.
