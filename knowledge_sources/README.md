# Knowledge Sources

This folder is the working area for vendor knowledge ingest, staging, and generated artifacts that support runtime enrichment.

Use it as a pipeline, not as a second unmanaged dump of `metadata_dict/`.

## Layout

- `source_inventory.csv` is the main index of important source files, generated overlays, and benchmark fixtures.
- `raw/` holds upstream or near-upstream source artifacts copied without manual normalization.
- `staged/` is reserved for normalized row-oriented records with provenance and rerunnable refresh inputs.
- `generated/overlays/` holds generated overlay candidates derived from vendor ingest helpers.
- `generated/runtime/` holds generated runtime-facing review artifacts, currently centered on the SAP classification and promotion flow.

## Current practical use

Today this area mainly supports three kinds of work:

- preserving raw vendor references such as SAP, QAD, Workday, and QuickBooks source files
- preparing generated overlay candidates from offline vendor ingest helpers in `support/vendor_ingest/`
- storing generated SAP runtime artifacts produced by the offline utilities in `support/sap/`

## What lives where

### `raw/`

Examples:

- SAP workbook sources
- Workday XML/XSD and HRDH exports
- QAD workbook references
- QuickBooks reference workbooks

Rule: keep files close to the upstream source and do not hand-edit them into normalized forms here.

### `staged/`

This layer is intentionally sparse right now.

Use it only for normalized vendor records when you need a durable, row-oriented refresh input with provenance and diff-friendly structure.

### `generated/overlays/`

Use this for generated overlay-ready CSV artifacts, such as Workday or HRDH overlay candidates created by the vendor ingest helpers.

### `generated/runtime/`

Use this for runtime-facing generated artifacts that are meant for review, promotion, or controlled import.

The detailed SAP artifact list and rerun commands live in `generated/runtime/README.md`.

## Guidance

- If you need to know what files matter, start with `source_inventory.csv`.
- If you need to regenerate SAP runtime artifacts, use the scripts under `support/sap/`.
- If you need to regenerate vendor overlay candidates, use the scripts under `support/vendor_ingest/`.
- If a folder here needs its own README again in the future, add it only when it carries folder-specific rules that are not obvious from this file.