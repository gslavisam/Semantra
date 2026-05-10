# Semantra Completed Slices

Ovaj dokument je strogo hronološki ledger isporučenih slice-ova i završenih tehničkih faza.

Za današnje stanje proizvoda koristi `current_state.md`.
Za plan i backlog koristi `plan.md` i `epics.md`.

## 2026-05-02

### Epic 5 MVP: Canonical semantic layer

Isporučeno:

- business concept model i canonical glossary runtime
- `source -> concept` i `concept -> target` pregled
- canonical-aware explanation i project-level coverage
- povezivanje knowledge aliasa sa canonical konceptima
- canonical import/export osnova

## 2026-05-03

### Faza 1: Low-risk cleanup

Isporučeno:

- shared helper izdvajanja za parsing i normalizaciju
- konzistentniji utility sloj bez promene ponašanja

### Faza 2: Streamlit monolith split

Isporučeno:

- izdvajanje UI/API/state helper-a iz `streamlit_app.py`
- namenski moduli za workspace, benchmark, catalog i admin/canonical surface

### Additional hardening slice

Isporučeno:

- score normalization na `0..1`
- final clamp posle correction signala
- preview warning scoping popravke
- persistence-backed refresh za decision-log i correction read putanje

## 2026-05-04

### Epic 11: Schema specification upload

Isporučeno:

- `POST /upload/spec/detect` i `POST /upload/spec`
- field-per-row spec parser u `SchemaProfile`
- Streamlit izbor između `Row data` i `Schema spec`
- kompatibilnost sa postojećim mapping contract-om

### Epic 12A: Canonical-only mapping

Isporučeno:

- source-only canonical mapping bez dummy target workaround-a
- `POST /mapping/canonical`
- canonical-only Setup i Review tok
- `Source -> Canonical concept` pregled sa confidence i unmatched signalima

## 2026-05-05

### Epic 13 initial slices: Enterprise Integration Catalog

Isporučeno:

- `13A` queryable catalog persistence i summary sloj
- `13B` list/search/detail/concept read API
- `13C` Streamlit Catalog browse/search/drilldown tok

## 2026-05-09

### Epic 14D: Description-aware context and companion enrichment

Isporučeno:

- `description` i `declared_type` kao first-class polja u `ColumnProfile`
- source-side companion metadata enrichment nad postojećim dataset handle-om
- description/type/sample context u LLM validator i transformation promptovima
- companion/spec parser koji ume da popuni i `sample_values`
- Streamlit Setup hook za companion upload i matched/unmatched summary

Napomena:

- deterministic scoring nije proširen; description/type su ostali LLM/context sloj dok benchmark ne pokaže potrebu za širim fusion-om

### Epic 14E: Canonical Gap Assistant initial MVP

Isporučeno:

- canonical-gap candidate extraction iz mapping rezultata
- LLM-assisted suggestion tok sa controlled JSON contract-om
- approve tok koji upisuje overlay-first canonical dopune
- rerun flow za potvrdu popunjenog canonical path-a
- reject/ignore/proposal-state osnova za governance review

### Epic 6 MVP: Governance and versioning

Isporučeno:

- mapping-set ownership, assignee, review note i status workflow
- audit trail za create/status/apply
- version diff između mapping-set verzija
- approved-only apply/reuse gate za mapping-set workflow
- UI surfacing governance blokada u Workspace i Catalog toku

## 2026-05-10

### Epic 14F: Canonical Console pilot-complete workflow

Isporučeno:

- top-level `Canonical Console` product area
- concept registry, concept detail, overlay summary i usage faceti
- canonical-gap queue mirror u konzoli
- audit-backed proposal triage i stable `source/target` gap identity
- `knowledge_stewardship_items` write model za `canonical_gap` i `overlay_promotion`
- owner/assignee/review-note/status stewardship model u konzoli
- overlay-promotion review i eksplicitni promote-to-glossary execution tok
- support za promotion u postojeći glossary red i kreiranje novog base concept reda za overlay-only koncept
- pilot hardening UX poboljšanja za bootstrap state, selection sync i console rerun ponašanje

Ishod:

- core Canonical Console governance loop tretira se kao pilot-complete

### Product-level governance hardening follow-through

Isporučeno:

- advisory preview uz accepted-only codegen
- accepted-only save/run za transformation test sets
- accepted-only save za `Save current mapping as benchmark`
- closed-review-only save za corrections i reusable learning
- `ready_for_approval` gate za canonical-gap approval
- lifecycle gate za overlay activate/archive putanje

### Canonical registry hardening

Isporučeno:

- filtriranje numeric-only canonical aliasa pri importu/promociji i pri čitanju registry-ja
- cleanup postojećeg persisted canonical alias šuma kroz reseed

## Napomena

- Završeni slice-ovi su namerno odvojeni od backlog-a kako bi `epics.md` ostao pregledan.
- Aktivni naredni rad treba da se vidi u `implementation_checklists.md`, a ne ovde.