# Showcase Demo Guide

This guide summarizes the recommended file pairs and demo angles for the Semantra showcase fixture sets.

## Customer account mapping

Folder: `showcase_customer_mapping`

- Best quick demo: `showcase_customer_source.csv` -> `showcase_customer_target.json`
- Best spreadsheet demo: `showcase_customer_source.xlsx` -> `showcase_customer_target.xlsx`
- Best SQL demo: source table `crm_customer_core` -> target table `customer_dim`
- Good for: account identifiers, customer names, phones, emails, country mapping

## Material master

Folder: `showcase_material_master`

- Best quick demo: `showcase_material_source.csv` -> `showcase_material_target.json`
- Best spreadsheet demo: `showcase_material_source.xlsx` -> `showcase_material_target.xlsx`
- Best SQL demo: source table `mara_core` -> target table `product_dim`
- Good for: material numbers, units of measure, weights, batch flags, deletion flags

## Supplier master

Folder: `showcase_supplier_master`

- Best quick demo: `showcase_supplier_source.csv` -> `showcase_supplier_target.json`
- Best spreadsheet demo: `showcase_supplier_source.xlsx` -> `showcase_supplier_target.xlsx`
- Best SQL demo: source table `lfa1_general` -> target table `supplier_dim`
- Good for: vendor identity, address, tax, payment terms, posting block, deletion flags

## Customer sales area

Folder: `showcase_customer_sales_area`

- Best quick demo: `showcase_customer_sales_area_source.csv` -> `showcase_customer_sales_area_target.json`
- Best spreadsheet demo: `showcase_customer_sales_area_source.xlsx` -> `showcase_customer_sales_area_target.xlsx`
- Best SQL demo: source table `knvv_sales` -> target table `customer_sales_area_dim`
- Good for: sales organization, distribution channel, division, incoterms, shipping conditions, price list type

## Purchasing info record

Folder: `showcase_purchasing_info_record`

- Best quick demo: `showcase_pir_source.csv` -> `showcase_pir_target.json`
- Best spreadsheet demo: `showcase_pir_source.xlsx` -> `showcase_pir_target.xlsx`
- Best SQL demo: source table `eine_org` -> target table `purchasing_info_record_dim`
- Good for: supplier-material relationships, purchasing organization data, net price, lead time, order units, incoterms

## Suggested walkthrough order

1. Start with customer account mapping for a simple cross-format example.
2. Continue with material master to show SAP-style technical field names.
3. Use supplier master to demonstrate finance and address related mappings.
4. Use customer sales area to show organizational sales attributes.
5. Finish with purchasing info record to demonstrate cross-domain procurement semantics.
