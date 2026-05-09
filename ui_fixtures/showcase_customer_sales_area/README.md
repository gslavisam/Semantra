# Customer Sales Area Showcase Fixtures

This fixture set is designed for Semantra demos around SAP-like customer master and sales area mapping.

## Included scenarios

1. CSV source -> JSON target
2. XML source -> CSV target
3. XLSX source -> XLSX target
4. Schema spec CSV source -> Schema spec CSV target
5. Multi-table SQL snapshot source -> Multi-table SQL snapshot target

## Recommended file pairs

- Row data demo: `showcase_customer_sales_area_source.csv` with `showcase_customer_sales_area_target.json`
- Cross-format row demo: `showcase_customer_sales_area_source.xml` with `showcase_customer_sales_area_target.csv`
- Spreadsheet demo: `showcase_customer_sales_area_source.xlsx` with `showcase_customer_sales_area_target.xlsx`
- Spec-to-spec demo: `showcase_customer_sales_area_source_spec.csv` with `showcase_customer_sales_area_target_spec.csv`
- Multi-table SQL demo:
  - source table: `knvv_sales`
  - target table: `customer_sales_area_dim`

## SAP-like source fields covered

- KUNNR
- NAME1
- VKORG
- VTWEG
- SPART
- KDGRP
- BZIRK
- VSBED
- INCO1
- INCO2
- WAERS
- ZTERM
- KALKS
- PLTYP

## Notes

- All row-data files contain 14 columns and 5 rows.
- SQL snapshots contain multiple tables so the table selector can be exercised.
- The target side keeps customer identity plus sales-area attributes in normalized column names.
