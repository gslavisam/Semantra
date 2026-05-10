# Semantra Implementation Checklists

Ovaj dokument sada drži samo aktivne ili neposredno relevantne izvršne checkliste.

Ne koristi se za:

- istoriju isporuke
- opšti backlog pregled
- snapshot opis trenutnog stanja

Za to služe `completed_slices.md`, `epics.md` i `current_state.md`.

## Aktivne checkliste

### Documentation alignment

Status: in progress.

- [x] Uvesti jedan primarni `current_state.md` dokument za realno stanje proizvoda.
- [x] Očistiti `project_docs` tako da se plan, backlog, istorija i checkliste više ne preklapaju.
- [x] Ukinuti zaseban strategy-snapshot dokument iz `project_docs` i apsorbovati njegov koristan sadržaj u aktivne dokumente.
- [ ] Usaglasiti spoljne dokumente sa novim `project_docs` setom:
  - [ ] top-level `README`
  - [ ] `help.md` / `help.en.md`
  - [ ] `PROJECT_OVERVIEW.md`

### Epic 13D: Concept and reuse discovery

Status: active next-step checklist.

- [ ] Dodati concept-centric pregled reuse-a kroz više integracija za isti canonical concept.
- [ ] Dodati bar jedan viši vizuelni pregled, na primer source-system -> target-system matrix ili grouped canonical coverage pregled.
- [ ] Dodati osnovne reuse hint-ove tipa `similar approved integration exists` kada dva artefakta dele značajan canonical footprint.
- [ ] Surfacing ponavljanih unmatched ili low-confidence gap-ova kao input za glossary/knowledge rad.

### Epic 14D / 14A follow-up

Status: active, ali ne ispred 13D i hardening rada.

- [ ] Doneti benchmark-backed odluku da li `description` i `declared_type` ostaju samo LLM/context signal ili ulaze i u deterministic scoring.
- [ ] Dodati uski benchmarking paket za poređenje description-aware i non-description-aware ponašanja na realnijem korpusu.
- [ ] Nastaviti target vector cache samo ako merenje pokaže stvarnu dobit na većim shemama.

### Operational hardening

Status: active.

- [ ] Proći bar 1-2 realna source/target scenarija end-to-end i zabeležiti gde mapping, trust layer ili transformacije pucaju.
- [ ] Potvrditi stabilan regression subset za ključne backend i Streamlit tokove pre svake demo/pilot isporuke.
- [ ] Odraditi kratko UX i docs poliranje zasnovano na realnom pilot toku, ne samo na synthetic fixture-ima.
- [ ] Zadržati jedan jasan pilot narativ: upload -> mapping -> review -> preview -> export/codegen, bez ručne intervencije van standardnog toka.

## Post-pilot hardening checkliste

### Mapping progress jobs

Status: future hardening.

- [ ] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [ ] Pre multi-user ili dužeg execution režima planirati persistent queue/status backend.
- [ ] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [ ] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.

### Persistence and runtime separation

Status: future hardening.

- [ ] Razdvojiti canonical authoring/read modele od runtime matching sloja.
- [ ] Smanjiti oslanjanje na file-based reseed kao deo canonical source-of-truth priče.
- [ ] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.