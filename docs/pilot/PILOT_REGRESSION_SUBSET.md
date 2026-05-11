# Pilot Regression Subset

Ovaj dokument definiše uski regression subset za demo/pilot isporuke.

Nije zamena za širi test suite. Služi kao praktični minimum koji treba pustiti pre svake pilot ili showcase sesije.

## Cilj

Potvrditi da glavni Semantra pilot tok ostaje stabilan na ključnim površinama:

- Workspace upload/setup i output gating
- Workspace review i attention surfacing
- Catalog reuse/discovery tok
- Canonical Console stewardship tok

## Stabilna pilot preporuka

Za osnovni pilot tok koristi `Use LLM validation = off` kao podrazumevanu postavku, osim kada je cilj sesije eksplicitno LLM ambiguity review ili transformation generation.

Razlog:

- deterministic-first tok je brži i stabilniji za demo/pilot prolaze
- LLM-enabled mapping ostaje koristan, ali nije najbolji default za najkraći regression/prove-it loop

## Pre-flight

1. Pokreni lokalni stack.
	Sačekaj da `start_semantra.ps1` prijavi `Backend is ready` i `Streamlit is ready` pre otvaranja UI-ja.
2. Potvrdi da `Workspace`, `Catalog` i `Canonical Console` otvaraju bez runtime grešaka.
3. Za showcase quick demo koristi `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv` i `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`.

## Regression komande

Pusti ovaj uski subset iz repo root-a:

```powershell
python -m pytest tests/test_streamlit_workspace_views.py tests/test_streamlit_workspace_review_views.py tests/test_streamlit_catalog_views.py tests/test_streamlit_admin_views.py -q
```

Ako želiš i backend mapping minimum:

```powershell
python -m pytest backend/tests/test_mapping_service.py backend/tests/test_spec_upload_service.py -q
```

## Površine koje ovaj subset pokriva

### Workspace

- upload/setup helpers
- companion metadata poruke
- preview advisory i codegen governance gate
- repeated review attention summary

### Catalog

- concept-centric reuse view
- discovery overview matrix
- reuse hint-ovi i mapping-set reuse guard

### Canonical Console

- stewardship queue helper-i
- repeated canonical gap surfacing
- approval/rejection governance helper-i

## Operativna upotreba

Koristi ovaj subset:

1. pre demo/pilot sesije
2. odmah posle manjih UI governance ili discovery izmena
3. kao prvi check pre šireg suite-a kada vreme nije dovoljno za puni prolaz

## Van ovog subset-a

Ovaj paket namerno ne garantuje:

- pun LLM runtime health
- dugačke benchmark tokove
- sve transformation execution edge-case-ove
- multi-user ili dugotrajni job behavior