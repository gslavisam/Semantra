# Canonical Enrichment Applied Update

Generated: 2026-05-17T21:48:24+00:00

## Applied Scope

- Backup created before initial apply: `backend/backups/semantra.sqlite3.before_canonical_enrichment_20260517_214041.bak`
- Canonical glossary concepts after file update: 467
- Cross-system alias rows retained in base glossary: 474
- Workday generated overlay aliases removed/deferred from base glossary: 266
- `employee.phone` created in glossary: True
- Curated field-context rows retained: 212
- Manual SAP `LSTEL` regression-guard contexts added: 2
- Field-context rows by system: {'QuickBooks': 68, 'SAP': 144}
- QuickBooks noisy generic rows removed during final quality pass: 21
- QuickBooks removal reasons: {'generic IsActive mapped to account.status outside Account table': 13, 'supplier concept mapped to Employee address field': 7, 'supplier invoice posting date mapped to generic journal entry date': 1}
- `invoice.currency` automatic import deferred: True

## Source Files Updated

- `metadata_dict/canonical_glossary_erp.csv`
- `metadata_dict/canonical_field_context_enrichment.csv`

## Deferred Items

- Workday `wd_hr_knowledge_overlay.csv` alias candidates remain review candidates rather than base glossary aliases.
- `invoice.currency` remains deferred because candidate rows mix currency-code and compensation amount semantics.
- Weaker SAP/QuickBooks field-context candidates remain in the review CSV.
- Generic QuickBooks status/supplier-address rows removed in the final quality pass remain reviewable in the candidate CSV.

## Runtime Note

The metadata loader includes `canonical_field_context_enrichment.csv` in its source hash and reseed path, so accepted field-context enrichment survives future DB reseeds.
