# Semantra Plan

Ovaj dokument je forward-looking plan. Ne koristi se za opisivanje trenutnog stanja proizvoda niti kao hronologija isporuke.

Za to služe:

- `current_state.md` za današnje funkcionalno stanje
- `completed_slices.md` za istoriju isporuke
- `epics.md` za backlog mapu
- `implementation_checklists.md` za aktivne izvršne liste

## Trenutna pozicija proizvoda

Semantra je stigla do pilot-ready faze za glavni analyst + governance tok:

- upload i schema profiling rade kroz više ulaznih formata
- mapping review, trust layer i transformation authoring su upotrebljivi
- mapping set governance postoji i backend ga stvarno enforce-uje
- canonical layer i knowledge overlay lifecycle postoje kao product surface, ne samo kao interni runtime
- Canonical Console je pilot-complete za glavni stewardship happy path

Sledeći korak nije širenje u mnogo pravaca odjednom, već konsolidacija, reuse discovery i hardening najvrednijih putanja.

## Prioritetni redosled rada

### 1. Dokumentaciona i release narativ usklađenost

Prvo usaglasiti `project_docs`, a zatim i spoljne dokumente (`README`, `help`, `PROJECT_OVERVIEW`) sa stvarnim stanjem proizvoda.

Exit kriterijum:

- postoji jedan jasan opis šta je implementirano
- backlog, plan i hronologija su razdvojeni
- pilot-complete i active/open statusi su konzistentni kroz dokumentaciju

### 2. Epic 13D: Concept and reuse discovery

Početni 13D discovery talas je sada zatvoren kroz concept-centric reuse pregled, viši discovery overview, reuse hint-ove i surfacing ponavljanih review gap-ova.

Fokus:

- concept-centric reuse pregled kroz više integracija
- osnovni vizuelni discovery prikaz
- hint-ovi tipa `similar approved integration exists`
- surfacovanje ponavljanih gap-ova kao input za canonical i knowledge rad

### 3. Operational hardening nad postojećim pilot površinama

Ovo je sada sledeći glavni izvršni fokus pre daljeg feature širenja.

Fokus:

- stabilniji regression subset za glavne product surface-ove
- dalji governance enforcement tamo gde još postoje advisory ili implicitni prolazi
- pilot/readiness docs i UX poliranje zasnovano na realnim tokovima

### 4. Epic 14A i 14B: performance i signal precomputation

Kada product narrative i reuse discovery budu stabilni, sledeći racionalan korak je ubrzanje i rasterećenje ranking toka.

Fokus:

- target vector cache
- stabilni precomputed signali
- jasna granica između runtime scoring-a i keširanih slojeva

### 5. Epic 12B: system-specific virtual targets

Ovaj pravac ima smisla tek kada canonical coverage i governance disciplina budu dovoljno stabilni.

Pravilo:

- canonical-only ostaje baza
- system-specific virtual target ne sme da zamagli current canonical-first model

### 6. Epic 9: data quality intelligence

Ovo ostaje važna, ali sledeća liga prioriteta. Treba ga uvoditi tek kada reuse i operational hardening budu dovoljno zatvoreni.

### 7. Epic 15: derived graph layer

Graph projekcija ostaje kasniji derived sloj. Ne uvoditi je pre nego što canonical, catalog i usage modeli sazru dovoljno da graf ima stabilan izvor.

## Tehničke teme koje treba vući paralelno, ali kontrolisano

### Mapping engine decomposition

`mapping_service.py` i dalje je preširok i dugoročno ga treba razdvajati na scoring, assignment, explanation i LLM gate slojeve. Ovo je bitno, ali ne sme blokirati svaki novi feature.

### Knowledge and canonical runtime separation

`metadata_knowledge_service.py` i dalje nosi previše odgovornosti. Sledeći refactor treba da odvoji:

- canonical authoring/read model
- overlay lifecycle
- runtime matching
- reseed/refresh mehaniku

### Persistence hardening bez napuštanja SQLite-a

SQLite ostaje prihvatljiv za trenutnu fazu, ali treba postepeno normalizovati queryable read/write modele tamo gde listing, governance i discovery to već traže.

### Background job hardening

Današnji in-memory/thread job store je dobar za lokalni dev i pilot. Za ozbiljniji multi-user ili dugotrajniji execution model biće potreban persistent queue/status sloj.

Minimalni transition plan za tu tačku:

- trigger za prelaz nije "lepa arhitektura" nego operativna potreba: više istovremenih korisnika, job-ovi koji treba da prežive restart procesa ili run-ovi koji redovno traju dovoljno dugo da cooperative local thread model više nije pouzdan
- prvi korak ne treba da bude spoljašnji broker nego persistent job/status model u SQLite-u: job zapis, status tranzicije, retry_count, cancel_requested/canceled_at metadata i append-only progress/event log koji UI može da poll-uje kao i danas
- tek posle toga uvoditi odvojeni worker lease/dequeue sloj, tako da Streamlit i API mogu da zadrže gotovo isti surface (`start job`, `get status`, `cancel job`), dok se backend izvršenje preseli iz process-memory modela u durable queue

### Repo i docs organizacija

Nastaviti disciplinu: malo dokumenata sa jasnim ulogama, bez novih snapshot fajlova koji dupliraju plan ili current-state sadržaj.

## Operativna pravila

- Jedan glavni product fokus u isto vreme; tehničke faze služe kao podrška, ne kao zaseban backlog univerzum.
- Ne raditi veliki UI refactor, persistence redesign i product feature slice u istom talasu.
- Svaka promena mora da se završi fokusiranim testom ili drugim uskim oblikom validacije.
- Kada mapping radi, ali `knowledge` ili `canonical` signal ostaje nizak, prvo proveravati da li je to realan glossary/overlay gap, ne automatski engine bug.
- Nove canonical ili knowledge dopune prvo treba zatvarati overlay-first putem, pa tek kasnije promovisati u stabilni base sloj.