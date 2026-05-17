# Semantra Implementation Checklists

Ovaj dokument je primarno mesto za izvršni redosled aktivnog rada.

Drži samo aktivne ili neposredno relevantne izvršne checkliste.

Ne koristi se za:

- istoriju isporuke
- opšti backlog pregled
- snapshot opis trenutnog stanja

Za to služe `completed_slices.md`, `epics.md` i `current_state.md`.

## Aktivne checkliste

### Guided copilots productization

Status: active.

- [ ] Proći jedan realni pilot scenario kroz `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit` i zabeležiti gde je guidance stvarno korisna, a gde deluje redundantno.
- [ ] Uskladiti poruke, label-e i empty/unlock state između novih bounded guidance panela.
- [ ] Dodati bar jedan browser-level smoke koji potvrđuje discoverability novih guidance površina, ne samo helper testove.

### Epic 13D: Concept and reuse discovery expansion

Status: active.

- [ ] Dodati bogatiji compare/drilldown tok između sličnih integracija ili mapping set verzija.
- [ ] Povezati Catalog discovery signale sa review i canonical governance kontekstom tako da reuse signal vodi do sledeće konkretne akcije.
- [ ] Potvrditi da `Workspace Reuse Fit` koristi dovoljno dobar workspace snapshot u realnim reuse scenarijima.

### Operational hardening

Status: active.

- [ ] Proširiti regression subset tako da pokrije i novije bounded guidance i refinement tokove.
- [ ] Odraditi bar jedan browser-level end-to-end prolaz za Catalog reuse i jedan za Benchmarks explanation tok.
- [ ] Nastaviti UX poliranje zasnovano na realnom pilot toku, ne samo na synthetic fixture-ima.

### Persistence and runtime separation

Status: future hardening with preparatory work.

- [ ] Razdvojiti canonical authoring/read modele od runtime matching sloja.
- [ ] Smanjiti oslanjanje na file-based reseed kao deo canonical source-of-truth priče.
- [ ] Definisati jasan transition kriterijum za durable job/status backend umesto postojećeg in-memory modela.

## Post-pilot hardening checkliste

### Mapping progress jobs

Status: future hardening after completed local pilot slice.

- [x] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [ ] Pre multi-user ili dužeg execution režima planirati persistent queue/status backend.
- [x] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [x] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.

### SQLite read/write normalization

Status: future hardening.

- [ ] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.

## Appendix: Open after current execution wave

- Dokumentaciona usklađenost je završena u ovom execution wave-u: `project_docs`, `README`, `PROJECT_OVERVIEW` i `help` sada opisuju aktuelne bounded guidance, Catalog reuse i Output refinement tokove.
- Novi bounded guidance paneli više nisu skriveni samo iza uskih state uslova; Benchmark, Catalog i Canonical Gap red sada imaju vidljive unlock/discoverability poruke.
- `Epic 14D / 14A follow-up` više nema otvoreno pitanje oko `description` / `declared_type` deterministic scoring-a u trenutnom engine-u: evaluation harness sada prenosi ta polja, a uski benchmark je potvrdio da aktuelni deterministic rezultat ostaje isti sa i bez tog metadata konteksta, pa ona za sada ostaju LLM/context signal.
- Fokusirano merenje nad višekolonskim embedding run-om pokazalo je da se isti target embedding bespotrebno ponavlja po source koloni, pa je dodat per-run target cache bez promene mapping rezultata.
- `Mapping progress jobs` lokalni pilot slice je završen: in-memory/thread model ostaje zadržan za sada, a runtime sada ima TTL cleanup za završene jobove, cap na broj zadržanih completed/failed statusa, limit za aktivne jobove, kontrolisan `429` odgovor i eksplicitnu cancel/retry semantiku.