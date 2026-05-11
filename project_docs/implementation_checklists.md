# Semantra Implementation Checklists

Ovaj dokument je primarno mesto za izvršni redosled aktivnog rada.

Drži samo aktivne ili neposredno relevantne izvršne checkliste.

Ne koristi se za:

- istoriju isporuke
- opšti backlog pregled
- snapshot opis trenutnog stanja

Za to služe `completed_slices.md`, `epics.md` i `current_state.md`.

## Aktivne checkliste

### Documentation alignment

Status: completed.

- [x] Uvesti jedan primarni `current_state.md` dokument za realno stanje proizvoda.
- [x] Očistiti `project_docs` tako da se plan, backlog, istorija i checkliste više ne preklapaju.
- [x] Ukinuti zaseban strategy-snapshot dokument iz `project_docs` i apsorbovati njegov koristan sadržaj u aktivne dokumente.
- [x] Usaglasiti spoljne dokumente sa novim `project_docs` setom:
  - [x] top-level `README`
  - [x] `help.md` / `help.en.md`
  - [x] `PROJECT_OVERVIEW.md`

### Epic 13D: Concept and reuse discovery

Status: completed in current execution wave.

- [x] Dodati concept-centric pregled reuse-a kroz više integracija za isti canonical concept.
- [x] Dodati bar jedan viši vizuelni pregled, na primer source-system -> target-system matrix ili grouped canonical coverage pregled.
- [x] Dodati osnovne reuse hint-ove tipa `similar approved integration exists` kada dva artefakta dele značajan canonical footprint.
- [x] Surfacing ponavljanih unmatched ili low-confidence gap-ova kao input za glossary/knowledge rad.

### Epic 14D / 14A follow-up

Status: completed in current execution wave.

- [x] Doneti benchmark-backed odluku da li `description` i `declared_type` ostaju samo LLM/context signal ili ulaze i u deterministic scoring.
- [x] Dodati uski benchmarking paket za poređenje description-aware i non-description-aware ponašanja na realnijem korpusu.
- [x] Nastaviti target vector cache samo ako merenje pokaže stvarnu dobit na većim shemama.

### Operational hardening

Status: completed in current execution wave.

- [x] Proći bar 1-2 realna source/target scenarija end-to-end i zabeležiti gde mapping, trust layer ili transformacije pucaju.
- [x] Potvrditi stabilan regression subset za ključne backend i Streamlit tokove pre svake demo/pilot isporuke.
- [x] Odraditi kratko UX i docs poliranje zasnovano na realnom pilot toku, ne samo na synthetic fixture-ima.
- [x] Zadržati jedan jasan pilot narativ: upload -> mapping -> review -> preview -> export/codegen, bez ručne intervencije van standardnog toka.

## Post-pilot hardening checkliste

### Mapping progress jobs

Status: future hardening after completed local pilot slice.

- [x] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [ ] Pre multi-user ili dužeg execution režima planirati persistent queue/status backend.
- [x] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [x] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.

### Persistence and runtime separation

Status: future hardening.

- [ ] Razdvojiti canonical authoring/read modele od runtime matching sloja.
- [ ] Smanjiti oslanjanje na file-based reseed kao deo canonical source-of-truth priče.
- [ ] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.

## Appendix: Open after current execution wave

- `Operational hardening` više nije otvoren glavni talas: realni scenario prolazi, regression subset postoji, startup readiness je očvrsnut, a default `8000/8501` listener sada daje čist supplier deterministic flow do preview-a.
- Potvrđen je uski `pilot regression subset`, a Workspace sada kreće sa `Use LLM validation = off` kao stabilnijim pilot default-om.
- Drugi realni scenario (`showcase supplier master`) sada je potvrđen i na podrazumevanom lokalnom listener-u kada backend zaista radi; runtime drift je sveden na startup sequencing i `start_semantra.ps1` sada čeka realnu backend/UI spremnost pre završetka.
- Uklonjen je i lažni `backend unavailable` sticky-state za svež `8501` load kada se backend vrati; `backend_is_reachable()` sada ponovo proverava prethodno neuspešan reachability umesto da negativan rezultat ostavi zalepljenim.
- `Epic 14D / 14A follow-up` više nema otvoreno pitanje oko `description` / `declared_type` deterministic scoring-a u trenutnom engine-u: evaluation harness sada prenosi ta polja, a uski benchmark je potvrdio da aktuelni deterministic rezultat ostaje isti sa i bez tog metadata konteksta, pa ona za sada ostaju LLM/context signal.
- `Epic 14D / 14A follow-up` više nema ni otvoren target vector cache preduslov: fokusirano merenje nad višekolonskim embedding run-om pokazalo je da se isti target embedding bespotrebno ponavlja po source koloni, pa je dodat per-run target cache bez promene mapping rezultata.
- `Mapping progress jobs` lokalni pilot slice je završen: in-memory/thread model ostaje zadržan za sada, a runtime sada ima TTL cleanup za završene jobove, cap na broj zadržanih completed/failed statusa, limit za aktivne jobove, kontrolisan `429` odgovor i eksplicitnu cancel/retry semantiku.
- `Mapping progress jobs` više nema aktivan implementation talas; preostaje samo future architectural stavka za persistent queue/status backend kada se pojavi realna potreba za multi-user, restart-resilient ili dužim execution režimom.
- `Post-pilot hardening` teme i dalje ostaju ograničene na male operativne slice-ove dok pilot tokovi i regression subset ne budu stabilniji.