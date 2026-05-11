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

### Epic 13D: Initial concept and reuse discovery slice

Isporučeno:

- concept-centric reuse pregled u Catalog concept lookup toku
- source-system -> target-system discovery overview nad catalog rezultatima
- basic `similar approved integration exists` hint u catalog result prikazu
- grouped unmatched/low-confidence review attention summary u Workspace review toku

Ishod:

- `13D` više nije samo planirana sledeća tema; osnovni discovery/reuse product sloj je sada isporučen i spreman za dalje hardening/proširenje

### Operational hardening: Stable pilot regression baseline

Isporučeno:

- Workspace više ne pali `Use LLM validation` po default-u u novom pilot toku
- fokusirani `pilot regression subset` dokumentovan u `docs/pilot/PILOT_REGRESSION_SUBSET.md`
- dva realna showcase nalaza zabeležena u `docs/pilot/PILOT_EXECUTION_LOG_2026-05-10.md`
- supplier master deterministic scenario potvrđen kao stabilan `preview ok / codegen blocked` baseline na svežem runtime-u
- `start_semantra.ps1` sada čeka realnu backend/UI spremnost pre prijave endpoint-a, čime se smanjuje false-ready drift u lokalnim pilot prolazima
- Streamlit backend reachability helper više ne lepi prethodni `False` rezultat za isti `api_base_url`, pa svež `8501` load sada uredno prikazuje zdrav runtime status kada se backend vrati
- default `8000/8501` supplier deterministic flow potvrđen live do `Generate preview`, uz očekivani advisory preview i accepted-only codegen gate

Ishod:

- stabilni deterministic-first pilot path je sada jasnije definisan i proverljiv pre demo/pilot isporuke

### Epic 14D follow-up: Description/type benchmark harness slice

Isporučeno:

- evaluation harness sada prenosi `description` i `declared_type` u `ColumnProfile` umesto da ih tiho odbaci
- dodat je uski benchmark test za poređenje istog case-a sa metadata kontekstom i bez njega
- dodat je per-run target embedding cache u mapping engine-u, potkrepljen fokusiranim testom koji pokazuje da se target embedding računa samo jednom po target koloni unutar većeg run-a

Ishod:

- trenutna benchmark-backed odluka je da `description` i `declared_type` za sada ostaju LLM/context signal, jer current deterministic engine daje iste metrike i sa i bez tih polja
- target vector cache je opravdan i uveden u runtime jer merenje pokazuje stvarno uklanjanje redundantnih target embedding izračunavanja bez promene mapping ishoda

### Mapping progress jobs hardening: in-memory lifecycle limits slice

Isporučeno:

- lokalni in-memory/thread job model je zadržan kao runtime za pilot režim, bez uvlačenja persistent queue sloja pre vremena
- `MappingJobStore` sada odbacuje istekle završene jobove preko TTL pravila i ograničava koliko completed/failed statusa ostaje u memoriji
- uveden je cap za broj aktivnih mapping job-ova, uz eksplicitan `429` odgovor na job start endpoint-ima kada je limit dostignut
- dodati su fokusirani servisni i API testovi za active-limit, finished-job pruning i očuvan normalan progress polling tok

Ishod:

- lokalni mapping progress lifecycle je otporniji na pilot runtime akumulaciju i runaway background job stanje, ali bez prelaska na teži multi-user queue model dok za to ne postoji stvarna potreba

### Mapping progress jobs hardening: cancel and retry semantics slice

Isporučeno:

- mapping job status model sada eksplicitno pokriva `cancel_requested` i `canceled`
- dodat je `POST /mapping/jobs/{job_id}/cancel` endpoint za cooperative cancel u postojećem in-memory job modelu
- mapping worker sada zaustavlja run na sledećem progress checkpoint-u kada cancel zahtev stigne, a Streamlit polling helper prepoznaje `canceled` status umesto da čeka timeout
- retry je za trenutni pilot režim definisan kao pokretanje novog `/mapping/.../jobs` zahteva, bez posebnog replay endpoint-a

Ishod:

- lokalni job lifecycle sada ima eksplicitno operativno ponašanje i za overload i za operator interrupt scenario, bez uvlačenja kompleksnijeg queue/replay sloja prerano

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