# Material master transformation design example

This example has been moved to the reference documentation set and is now maintained at [Semantra/docs/reference/material_master_transformation_design_example.md](Semantra/docs/reference/material_master_transformation_design_example.md).

It shows how a complex business object such as a material master can be expressed through Transformation Design as a structured, reviewable contract.

## Business context
A target object named Material Master should contain one row per material. The values are populated from multiple source tables and systems.

Typical source tables:
- MARA: basic material attributes
- MAKT: language-specific material descriptions
- MARC: plant-level attributes
- MBEW: valuation and accounting attributes
- MVKE: sales-related attributes
- MARM: unit-of-measure information

## Target grain
One row per material number.

## Global rules
- Use the most reliable source for each attribute.
- If a primary source is empty, fall back to an alternate source.
- Standardize codes to uppercase where appropriate.
- Trim whitespace and remove empty placeholders.
- For descriptions, prefer the active language version; otherwise use a fallback description.

## Defaults
- If the description is missing, use the material number as a temporary description.
- If lifecycle status is missing, default to ACTIVE.
- If a plant-specific value is missing, keep it empty rather than inventing a value.

## Example
Example target row:
- material_number = M-1001
- material_description = "Widget A"
- material_group = "FG"
- base_uom = "EA"
- industry_sector = "MECH"
- lifecycle_status = "ACTIVE"
- plant = "1000"
- valuation_class = "3000"
- gross_weight = 12.5
- net_weight = 11.8
- weight_uom = "KG"
- procurement_type = "F"
- purchasing_group = "001"
- sales_org = "1000"
- storage_condition = "DRY"

## Example transformation spec

```json
{
  "target_grain": "One row per material number",
  "global_rules": "Use the most reliable source per field, fallback when empty, standardize codes, and prefer active-language descriptions.",
  "defaults": "If description is missing, use material number as fallback. If lifecycle status is missing, default to ACTIVE.",
  "examples": "Example: material M-1001 with plant 1000, base UoM EA, lifecycle ACTIVE.",
  "target_fields": [
    "material_number",
    "material_description",
    "material_group",
    "base_uom",
    "industry_sector",
    "lifecycle_status",
    "plant",
    "valuation_class",
    "gross_weight",
    "net_weight",
    "weight_uom",
    "procurement_type",
    "purchasing_group",
    "sales_org",
    "storage_condition"
  ],
  "field_rules": [
    {
      "target_field": "material_number",
      "rule": "Use the canonical material identifier from the core material table.",
      "source_fields": ["MARA.MATNR"]
    },
    {
      "target_field": "material_description",
      "rule": "Prefer the active-language description from MAKT; if missing, use a fallback description from MARA.",
      "source_fields": ["MAKT.MAKTX", "MARA.MAKTX"]
    },
    {
      "target_field": "material_group",
      "rule": "Take the material group from the basic material master data.",
      "source_fields": ["MARA.MATKL"]
    },
    {
      "target_field": "base_uom",
      "rule": "Use the base unit of measure from the material master; if missing, derive from the unit table.",
      "source_fields": ["MARA.MEINS", "MARM.MEINS"]
    },
    {
      "target_field": "industry_sector",
      "rule": "Take the industry sector from the basic material attributes.",
      "source_fields": ["MARA.BRGEW"]
    },
    {
      "target_field": "lifecycle_status",
      "rule": "Use the lifecycle status from plant-level data; if absent, default to ACTIVE.",
      "source_fields": ["MARC.LVORM", "MARC.STPRS"]
    },
    {
      "target_field": "plant",
      "rule": "Take the plant code from plant-level table rows.",
      "source_fields": ["MARC.WERKS"]
    },
    {
      "target_field": "valuation_class",
      "rule": "Derive the valuation class from accounting data for the material and plant.",
      "source_fields": ["MBEW.BKLAS", "MBEW.WERKS"]
    },
    {
      "target_field": "gross_weight",
      "rule": "Use the gross weight from the material master and convert it to the target unit if needed.",
      "source_fields": ["MARA.BRGEW", "MARM.GEWEI"]
    },
    {
      "target_field": "net_weight",
      "rule": "Use the net weight from the material master when available; otherwise derive from gross weight minus packaging assumptions.",
      "source_fields": ["MARA.NTGEW", "MARA.BRGEW"]
    },
    {
      "target_field": "weight_uom",
      "rule": "Use the standard weight unit from the unit conversion table.",
      "source_fields": ["MARM.GEWEI"]
    },
    {
      "target_field": "procurement_type",
      "rule": "Use the procurement type from plant data and normalize it to a concise code.",
      "source_fields": ["MARC.EKGRP", "MARC.DISMM"]
    },
    {
      "target_field": "purchasing_group",
      "rule": "Take the purchasing group from plant-level purchasing attributes.",
      "source_fields": ["MARC.EKGRP"]
    },
    {
      "target_field": "sales_org",
      "rule": "Use the sales organization from sales-view data when present.",
      "source_fields": ["MVKE.VKORG"]
    },
    {
      "target_field": "storage_condition",
      "rule": "Use the storage condition from plant-level logistics data if available; otherwise leave empty.",
      "source_fields": ["MARC.LGPRO", "MARC.LGPBE"]
    }
  ]
}
```

## How this is done in the application
In the app, this example is built in the Output -> Transformation Design section.

### 1. Define the target grain
- Target grain:
- One row per material number

### 2. Define global rules
- Global rules:
- Use the most reliable source per attribute
- If a primary source is empty, use fallback
- Standardize codes and trim whitespace

### 3. Define defaults and fallback behavior
- Defaults:
- If description missing, use material number
- If lifecycle status missing, default to ACTIVE

### 4. Add field-level rules
- Field rules:
- material_number → use MARA.MATNR
- material_description → use MAKT.MAKTX, fallback to MARA.MAKTX
- material_group → use MARA.MATKL
- base_uom → use MARA.MEINS, fallback to MARM.MEINS
- plant → use MARC.WERKS
- valuation_class → use MBEW.BKLAS
- gross_weight → use MARA.BRGEW
- net_weight → use MARA.NTGEW
- lifecycle_status → use MARC.LVORM, fallback to ACTIVE

### 5. Review the structured spec
The app stores the transformation contract as a structured spec and uses it for:
- preview context,
- generated code annotations,
- and downstream BA-report style explanation.

This means the material master case is not only a mapping exercise, but a governed transformation design workflow that can be reviewed before code generation.

## UI-ready version
This is a more compact version that can be copied directly into the Transformation Design form in the application.

A ready-to-edit JSON template is also available at [Semantra/docs/pilot/material_master_transformation_spec_template.json](Semantra/docs/pilot/material_master_transformation_spec_template.json).

In the app, you can now paste that JSON into the new "Import transformation spec JSON" field inside Output -> Transformation Design and click "Apply JSON spec".

- Target grain:
- One row per material number

- Global rules:
- Use the most reliable source per attribute
- If a primary source is empty, use fallback
- Standardize codes and trim whitespace

- Defaults:
- If description missing, use material number
- If lifecycle status missing, default to ACTIVE

- Field rules:
- material_number → use MARA.MATNR
- material_description → use MAKT.MAKTX, fallback to MARA.MAKTX
- material_group → use MARA.MATKL
- base_uom → use MARA.MEINS, fallback to MARM.MEINS
- plant → use MARC.WERKS
- valuation_class → use MBEW.BKLAS
- gross_weight → use MARA.BRGEW
- net_weight → use MARA.NTGEW
- lifecycle_status → use MARC.LVORM, fallback to ACTIVE

## Why this use case is strong
This example is useful because it shows the real challenge of transformation design:
- one target object,
- many source tables,
- several fields that are derived from more than one source,
- and clear business rules that are reviewable before code generation.

In practice, this is exactly the kind of case where Semantra can move from simple mapping to a structured, explainable design contract.
