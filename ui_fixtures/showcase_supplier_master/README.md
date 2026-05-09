# Supplier Master Showcase Fixtures

This fixture set is designed for Semantra demos around SAP-like supplier or vendor master mapping.

## Included scenarios

1. CSV source -> JSON target
2. XML source -> CSV target
3. XLSX source -> XLSX target
4. Schema spec CSV source -> Schema spec CSV target
5. Multi-table SQL snapshot source -> Multi-table SQL snapshot target

## Recommended file pairs

- Row data demo: `showcase_supplier_source.csv` with `showcase_supplier_target.json`
- Cross-format row demo: `showcase_supplier_source.xml` with `showcase_supplier_target.csv`
- Spreadsheet demo: `showcase_supplier_source.xlsx` with `showcase_supplier_target.xlsx`
- Spec-to-spec demo: `showcase_supplier_source_spec.csv` with `showcase_supplier_target_spec.csv`
- Multi-table SQL demo:
  - source table: `lfa1_general`
  - target table: `supplier_dim`

## SAP-like source fields covered

- LIFNR
- KTOKK
- NAME1
- LAND1
- REGIO
- ORT01
- PSTLZ
- STRAS
- STCD1
- ZTERM
- AKONT
- SPERR
- LOEVM
- TELF1

## Notes

- All row-data files contain 14 columns and 5 rows.
- SQL snapshots contain multiple tables so the table selector can be exercised.
- Column names are SAP-like on the source side and normalized on the target side.
