# Material Master Showcase Fixtures

This fixture set is designed for Semantra demos around SAP-like material master mapping.

## Included scenarios

1. CSV source -> JSON target
2. XML source -> CSV target
3. XLSX source -> XLSX target
4. Schema spec CSV source -> Schema spec CSV target
5. Multi-table SQL snapshot source -> Multi-table SQL snapshot target

## Recommended file pairs

- Row data demo: `showcase_material_source.csv` with `showcase_material_target.json`
- Cross-format row demo: `showcase_material_source.xml` with `showcase_material_target.csv`
- Spreadsheet demo: `showcase_material_source.xlsx` with `showcase_material_target.xlsx`
- Spec-to-spec demo: `showcase_material_source_spec.csv` with `showcase_material_target_spec.csv`
- Multi-table SQL demo:
  - source table: `mara_core`
  - target table: `product_dim`

## SAP-like source fields covered

- MATNR
- BISMT
- MTART
- MATKL
- MAKTX
- MEINS
- BRGEW
- NTGEW
- GEWEI
- ERSDA
- XCHPF
- LVORM

## Notes

- All row-data files contain 12 columns and 5 rows.
- SQL snapshots contain multiple tables so the table selector can be exercised.
- Column names are SAP-like on the source side and integration-friendly on the target side.
