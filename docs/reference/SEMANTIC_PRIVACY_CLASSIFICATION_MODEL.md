# Semantic Privacy Classification Model

## Goal

Add canonical-level privacy metadata that Semantra can carry through the semantic layer so Governance users can see whether a concept is personal data, whether it falls into a GDPR special category, and which privacy tags apply.

## Minimal Model

The first slice keeps classification at the canonical concept level and adds four source-of-truth fields:

- `is_pii`: boolean flag for direct or indirect personal data
- `is_gdpr_special_category`: boolean flag for GDPR Article 9 style special-category data
- `pii_categories`: comma-separated taxonomy tags such as `direct_identifier`, `financial`, `employment`, `health`
- `data_subject_types`: comma-separated taxonomy tags such as `customer`, `employee`, `vendor`, `candidate`

This is intentionally narrow. It does not yet attempt policy enforcement, row-level tagging, jurisdiction-specific obligations, or automatic masking rules.

## Source Of Truth

Canonical authoring in Semantra is still file-backed, so the privacy metadata must live in the canonical glossary CSV contract, not only in SQLite.

Recommended CSV columns:

```text
concept_id,entity,attribute,display_name,description,data_type,aliases,is_pii,is_gdpr_special_category,pii_categories,data_subject_types
```

Backward compatibility rule:

- Existing glossary files without the new columns remain valid.
- Missing privacy columns are treated as unclassified defaults.

## Runtime Propagation

The canonical privacy metadata should flow through these layers:

1. `metadata_dict/canonical_glossary_erp.csv`
2. `metadata_knowledge_service.py` glossary loader and in-memory canonical concept model
3. `persistence_service.py` canonical runtime cache in SQLite
4. `knowledge.py` API models and canonical concept routes
5. Governance UI canonical concept detail in `streamlit_ui/admin_views.py`

That gives Semantra one stable semantic tag surface that later features can reuse.

## Current First Slice

The initial implementation should do the following:

1. Load and persist the four canonical privacy fields.
2. Default missing values safely.
3. Show the classification in Governance canonical concept detail.
4. Allow enriched glossary CSV imports to populate the metadata.

The initial implementation should not yet do the following:

1. Enforce privacy-aware matching behavior.
2. Block mappings based on privacy class.
3. Require overlay authors to provide privacy tags.
4. Infer privacy automatically from field names alone.

## Migration Notes

SQLite runtime cache should add nullable-safe columns with defaults so existing installations do not require a manual reset:

- `is_pii INTEGER NOT NULL DEFAULT 0`
- `is_gdpr_special_category INTEGER NOT NULL DEFAULT 0`
- `pii_categories_json TEXT NOT NULL DEFAULT '[]'`
- `data_subject_types_json TEXT NOT NULL DEFAULT '[]'`

Because canonical authoring is file-backed, the database cache is a projection, not the durable source of truth.

## Future Extensions

If this proves useful, the next step should be a second layer of privacy metadata on mapping outputs or field contexts, for example:

- lawful basis hints
- retention class
- masking recommendation
- cross-border transfer sensitivity
- steward approval requirements

Those should build on the canonical concept tags instead of bypassing them.