# Customer Mapping Showcase Fixtures

This fixture set is designed for Semantra demos, exploratory testing, and end-to-end mapping validation across multiple input formats.

## Included scenarios

1. CSV source -> JSON target
2. XML source -> CSV target
3. XLSX source -> XLSX target
4. Schema spec CSV source -> Schema spec CSV target
5. Multi-table SQL snapshot source -> Multi-table SQL snapshot target

## Recommended file pairs

- Row data demo: `showcase_customer_source.csv` with `showcase_customer_target.json`
- Cross-format row demo: `showcase_customer_source.xml` with `showcase_customer_target.csv`
- Spreadsheet demo: `showcase_customer_source.xlsx` with `showcase_customer_target.xlsx`
- Spec-to-spec demo: `showcase_customer_source_spec.csv` with `showcase_customer_target_spec.csv`
- Multi-table SQL demo:
  - source table: `legacy_customer_master`
  - target table: `customer_dim`
- Contact-focused SQL demo:
  - source table: `legacy_customer_contact`
  - target table: `customer_contact`

## Business concepts covered

- Customer ID / account ID
- Customer name
- Customer email
- Phone number
- Country code
- Created / go-live date
- Customer segment
- Annual revenue / spend

## Notes

- All row-data files contain 8 columns and 5 rows.
- SQL snapshots contain multiple tables on purpose so the UI table selector can be exercised.
- Column names differ enough to make the mapping interesting, but still realistic for showcase use.
