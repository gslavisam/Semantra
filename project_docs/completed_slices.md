# Semantra Completed Slices

Ovaj dokument drži isporučene slice-ove i završene tehničke faze.

Aktivni backlog je u `epics.md`.
Plan i redosled rada su u `plan.md`.
Otvorene checkliste su u `implementation_checklists.md`.

## Delivered Product Slices

### 2026-05-02: Epic 5 MVP slice

Canonical semantic layer MVP je isporučen.

- uveden `business concept` model i glossary
- podržan `source -> concept` i `concept -> target` pregled
- dodat concept-aware explanation i project-level concept coverage
- knowledge aliasi mogu da se vežu za canonical concept
- concept import/export je dodat

Otvoreno ostaje dalji prelaz ka DB-only source-of-truth modelu za canonical i knowledge runtime.

### 2026-05-03: Epic 6 governance MVP initial slice

Isporučen je prvi review/governance slice nad mapping set workflow-om.

- metadata `owner`, `assignee`, `review_note`
- eksplicitan status workflow
- audit trail za create/status/apply
- version diff između mapping set verzija
- diff i audit prikaz u Streamlit UI

Otvoren ostaje export/run gate za `approved` mapping setove.

### 2026-05-03: Additional hardening slice

Dodatni hardening završen uz governance rad.

- score normalization na `0..1`
- finalni clamp posle correction signala
- preview warning scoping popravka
- persistence-backed refresh za decision log i correction store read put

### 2026-05-04: Epic 11 schema specification upload

Spec upload je uveden bez promene downstream mapping contract-a.

- `POST /upload/spec/detect` i `POST /upload/spec`
- parser field-per-row layout-a u `SchemaProfile`
- Streamlit `Row data` vs `Schema spec` izbor u upload toku
- kompatibilnost sa postojećim `POST /mapping/auto` tokom

### 2026-05-04: Epic 12A canonical-only mapping

Canonical-first source-only slice je isporučen.

- source-only upload tok bez dummy target workaround-a
- `POST /mapping/canonical`
- canonical-only Setup i Review UI tok
- `Source -> Canonical concept` pregled sa confidence i unmatched signalima

Otvoreno ostaje `Epic 12B` za system-specific virtual target-e.

### 2026-05-05: Epic 13 initial catalog slices

Prvi veliki katalog slice-ovi su isporučeni.

- 13A: queryable persistence/catalog summary sloj
- 13B: detail/search/concept-centric read API početni sloj
- 13C: Streamlit Catalog tab sa browse/search/drilldown/reuse tokom

Otvoren ostaje 13D concept and visual discovery slice.

### 2026-05-09: Epic 14D description-aware context and companion enrichment slice

Isporučen je prvi praktični 14D slice koji povezuje schema metadata enrichment sa mapping tokom bez promene osnovnog API contract-a.

- `description` i `declared_type` uvedeni su kao first-class polja u `ColumnProfile`
- spec upload više ne prepisuje `normalized_name` opisom kolone
- LLM validator i transformation prompt sada dobijaju description/type/sample context uz guardrails
- dodat je source-side companion metadata enrichment nad već uploadovanim dataset handle-om
- companion/spec parser sada ume da popuni i `sample_values` kada fajl sadrži primer vrednosti
- Streamlit Setup dobio je minimalistički source companion upload i summary o matched/unmatched kolonama
- lokalni browser smoke potvrđen nad canonical Setup tokom: source row-data upload, companion enrichment `3/3`, pa uspešan rerun canonical mapping-a

Svesna odluka ovog slice-a je da description/type još ne ulaze u deterministic scoring. Trenutni `compute_signals()` ostaje nepromenjen dok ne postoji benchmark corpus koji pokazuje da description-aware score fusion poboljšava kvalitet bez regresije nad postojećim knowledge/canonical signalima.

## Completed Technical Phases

### 2026-05-03: Faza 1

Mali cleanup sa niskim rizikom je završen.

- izdvojeni shared helper-i za nullish/tabular normalizaciju
- bolja konzistentnost parsing/normalization pomoćnih funkcija
- klasifikovan LLM warning/logging trag bez promene glavnog ponašanja

### 2026-05-03: Faza 2

Streamlit monolit split je završen.

- API helpers izdvojeni u `streamlit_ui/api.py`
- shared prikazi u `streamlit_ui/shared_views.py`
- mapping state/helpers u namenskim modulima
- workspace/admin/benchmark celine izdvojene iz `streamlit_app.py`
- regression subset potvrđen fokusiranim testovima

## Notes

- Završeni slice-ovi su namerno odvojeni od backlog-a da `epics.md` ostane planerski dokument, a ne hronologija isporuke.
- Otvorene stavke iz ovih slice-ova su prebačene u `epics.md` i `implementation_checklists.md`.