# Workspace Demo Recordings

Ovaj folder sadrzi workspace-focused Semantra demo recording artefakte generisane automatizovanim browser tokom.

## Scenario Index

## 01. Standard Two-File Mapping

Upload a source and target pair, profile them, generate mapping, and land in Workspace review.

Folder: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\01_standard_two_file_mapping`

Video: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\01_standard_two_file_mapping\01_standard_two_file_mapping.webm`

Screenshots:

- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\01_standard_two_file_mapping\screenshots\01_standard_two_file_mapping_01.png`

Summary:

```json
{
  "fixture": {
    "source": "D:\\py_radno\\Semantra\\ui_fixtures\\showcase_customer_mapping\\showcase_customer_source.csv",
    "target": "D:\\py_radno\\Semantra\\ui_fixtures\\showcase_customer_mapping\\showcase_customer_target.json"
  },
  "mapping_ready": true,
  "screenshots": [
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\01_standard_two_file_mapping\\screenshots\\01_standard_two_file_mapping_01.png"
  ]
}
```

## 02. Canonical Source Mapping

Run a canonical-only source mapping and show canonical review plus canonical-mode code generation.

Folder: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\02_canonical_source_mapping`

Video: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\02_canonical_source_mapping\02_canonical_source_mapping.webm`

Screenshots:

- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\02_canonical_source_mapping\screenshots\02_canonical_source_mapping_01.png`
- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\02_canonical_source_mapping\screenshots\02_canonical_source_mapping_02.png`

Summary:

```json
{
  "fixture": {
    "source": "D:\\py_radno\\Semantra\\ui_fixtures\\showcase_customer_mapping\\showcase_customer_source.csv",
    "target": "canonical"
  },
  "review_ready": true,
  "pandas_generated": true,
  "screenshots": [
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\02_canonical_source_mapping\\screenshots\\02_canonical_source_mapping_01.png",
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\02_canonical_source_mapping\\screenshots\\02_canonical_source_mapping_02.png"
  ]
}
```

## 03. LLM Decision Flow

Generate bounded LLM decision proposals from review and show the downstream Decisions workflow.

Folder: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\03_llm_decision_flow`

Video: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\03_llm_decision_flow\03_llm_decision_flow.webm`

Screenshots:

- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\03_llm_decision_flow\screenshots\03_llm_decision_flow_01.png`

Summary:

```json
{
  "fixture": {
    "source": "D:\\py_radno\\Semantra\\ui_fixtures\\showcase_customer_mapping\\showcase_customer_source.csv",
    "target": "D:\\py_radno\\Semantra\\ui_fixtures\\showcase_customer_mapping\\showcase_customer_target.json"
  },
  "proposals_generated": true,
  "safe_proposals_applied": false,
  "screenshots": [
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\03_llm_decision_flow\\screenshots\\03_llm_decision_flow_01.png"
  ]
}
```

## 04. Workspace Output Generation

Show Pandas and dbt generation plus LLM refinement from an accepted Workspace mapping state.

Folder: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\04_workspace_output_generation`

Video: `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\04_workspace_output_generation\04_workspace_output_generation.webm`

Screenshots:

- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\04_workspace_output_generation\screenshots\04_workspace_output_generation_01.png`
- `D:\py_radno\Semantra\docs\pilot\demo_assets\workspace_recordings_20260527\04_workspace_output_generation\screenshots\04_workspace_output_generation_02.png`

Summary:

```json
{
  "fixture": {
    "mapping_source": "approved-customer-reuse-smoke"
  },
  "pandas_generated": true,
  "dbt_generated": true,
  "refinement_generated": true,
  "screenshots": [
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\04_workspace_output_generation\\screenshots\\04_workspace_output_generation_01.png",
    "D:\\py_radno\\Semantra\\docs\\pilot\\demo_assets\\workspace_recordings_20260527\\04_workspace_output_generation\\screenshots\\04_workspace_output_generation_02.png"
  ]
}
```
