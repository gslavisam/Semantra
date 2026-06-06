# Semantra Docs

Ovaj folder drži šire product, reference, pilot i wave dokumente koji nisu deo uskog `project_docs/` plan/current-state seta.

Ako ti treba najtačniji trenutni status proizvoda, prvo kreni iz `project_docs/current_state.md`, zatim iz `README.md` i `PROJECT_OVERVIEW.md`. `docs/` drži dublje reference, pilot planove i prezentacione artefakte koji treba da budu usklađeni sa tim kanonskim current-state dokumentima.

Koristi ga za:

- product vision memo dokumente
- detaljne tehničke reference
- pilot i benchmark planove
- veće wave dokumente koji ne treba da opterete kratke project-management dokumente

## Novi knowledge-expansion dokumenti

- `vision/KNOWLEDGE_EXPANSION_WAVE.md`
	- why-now, boundary, phase model i exit criteria za SAP-first vendor knowledge wave
- `vision/WORKSPACE_MODELLING_CONCEPT.md`
	- bounded product memo za novi `Workspace > Modelling` podtab: scope, V1 contract model, izvodljivost i phase plan
- `reference/WORKSPACE_MODELLING_V1_UX_SPEC.md`
	- konkretan V1 UX spec za `derived-first` modelling tab: sekcije, akcije, drift pravila i bounded sync sa Workspace tokom
- `reference/WORKSPACE_BA_MAPPING_REPORT_SPEC.md`
	- ciljna report-first struktura za `Workspace > Modelling Overview`: kako da tab postane `BA Mapping Report` koji se kasnije može eksportovati kao dokument
- `reference/workflows.md`
	- aktuelni produktni workflow dokument koji opisuje review, decisions i output tokove, uključujući manual canonical override i report-aligned behavior
- `reference/VENDOR_KNOWLEDGE_INGEST_AND_SOURCE_INVENTORY.md`
	- konkretan source inventory, staging schema i predloženi folder layout za raw/staged/generated vendor knowledge ingest
- `reference/KNOWLEDGE_CANONICAL_AUTHORITY_MATRIX.md`
	- authority matrix za knowledge/canonical sloj: sta je source-of-truth u fajlovima, sta je runtime snapshot u bazi, i kako radi DB-first reseed logika
- `reference/RBAC_ACTION_AND_ENDPOINT_MATRIX.md`
	- predlozeni RBAC model za Semantra: role, action matrix, endpoint family matrix i razlika izmedju danasnjeg admin-token modela i ciljanog role-plus-scope enforcement-a
- `pilot/SAP_BENCHMARK_MATRIX.md`
	- prvi benchmark matrix za SAP-first coverage i quality merenje nad postojećim fixture porodicama

## Najvredniji dokumenti u trenutnoj fazi

- `../project_docs/current_state.md`
	- kanonski opis šta proizvod danas stvarno podržava i gde su granice
- `../README.md`
	- najkraći ulaz u product surface, runtime posture i immediate next steps
- `../PROJECT_OVERVIEW.md`
	- širi product, governance i architecture pregled
- `presentation/presentation.md`
	- stakeholder story koja mora da ostane usklađena sa realnim current state-om
- `presentation/LIVE_DEMO_RUNBOOK.md`
	- glavni runbook za ponovljiv live demo
- `pilot/MANUAL_LIVE_DEMO_SCRIPT.md`
	- najkraći presenterski tok za ručni live demo kada želiš da pokažeš vrednost bez improvizacije
- `pilot/REAL_LIFE_PILOT_TEST_PLAN.md`
	- najbolji ulaz za manuelno testiranje i proof-of-concept prolaze
- `pilot/PILOT_EXECUTION_LOG_2026-05-29.md`
	- stvarni proof-of-value run kroz glavni demo tok, sa potvrđenim pass koracima i jednim važnim continuity UX nalazom

## Folder roles

- `vision/`
	- veći product i wave memo dokumenti
- `reference/`
	- detaljne tehničke reference i operational model dokumenti
- `pilot/`
	- pilot test planovi, benchmark matrix-i i execution logovi
- `presentation/`
	- stakeholder i demo artefakti
	- `CATALOG_WINDOW_USE_CASE.md` za praktično objašnjenje šta se radi u Catalog prozoru i koja je poslovna vrednost