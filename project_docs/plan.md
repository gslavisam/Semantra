# Semantra Plan

Ovaj dokument je forward-looking plan. Ne koristi se za opisivanje trenutnog stanja proizvoda niti kao hronologija isporuke.

Za to služe:

- `current_state.md` za današnje funkcionalno stanje
- `completed_slices.md` za istoriju isporuke
- `epics.md` za backlog mapu
- `implementation_checklists.md` za aktivne izvršne liste

## Trenutna pozicija proizvoda

Semantra je stigla do pilot-ready faze za glavni analyst + governance tok i zatvorila je još jedan execution wave oko bounded guidance površina:

- upload i schema profiling rade kroz više ulaznih formata
- mapping review, trust layer i transformation authoring su upotrebljivi
- `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit` postoje kao kontrolisane guidance površine
- mapping set governance postoji i backend ga stvarno enforce-uje
- canonical layer i knowledge overlay lifecycle postoje kao product surface, ne samo kao interni runtime
- Canonical Console je pilot-complete za glavni stewardship happy path
- dokumentacija je ponovo usklađena sa realnim stanjem proizvoda

Sledeći korak nije širenje u mnogo pravaca odjednom, već produktizacija novih guidance tokova, reuse discovery i hardening najvrednijih putanja.

## Prioritetni redosled rada

### 1. Produktizacija bounded guidance površina

Prvi sledeći fokus je da novi bounded AI/guidance layer izgleda kao konzistentna porodica funkcija, a ne kao skup izdvojenih eksperimenata.

Fokus:

- uskladiti naming, unlock poruke i expected user journey između `Workspace`, `Benchmarks` i `Catalog`
- potvrditi kroz realne tokove gde korisnik stvarno dobija vrednost od `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit`
- izbeći semantičko preklapanje između postojećeg trust layer-a i novih queue/explanation panela
- zadržati pravilo da nijedna od ovih površina ne radi auto-apply ili auto-approval

### 2. Epic 13D: Concept and reuse discovery expansion

Početni 13D discovery talas je zatvoren kroz concept-centric reuse pregled, viši discovery overview, reuse hint-ove i surfacing ponavljanih review gap-ova. Sada sledi širenje tog sloja.

Fokus:

- bogatiji concept-centric reuse pregled kroz više integracija
- bolji compare/drilldown između sličnih integracija i mapping set verzija
- povezivanje Catalog reuse discovery signala sa Workspace review i canonical gap radom
- jači reuse narativ pre samog `Reuse in Workspace` koraka

### 3. Operational hardening nad postojećim pilot površinama

Ovo ostaje stalni paralelni fokus pre većeg feature širenja.

Fokus:

- stabilniji regression subset za glavne product surface-ove
- browser-level proveru najvažnijih pilot tokova, ne samo helper testove
- dalji governance enforcement tamo gde još postoje advisory ili implicitni prolazi
- UX poliranje zasnovano na realnim pilot prolazima

### 4. Persistence i runtime separation hardening

Ovo je sledeći arhitekturni fokus kada product surface ostane mirniji.

Fokus:

- postepeno razdvajanje canonical authoring/read modela od runtime matching sloja
- SQLite read/write normalizacija samo tamo gde je discovery/governance zaista traže
- jasni okidači za prelaz sa local in-memory job modela na durable job/status backend

### 5. Epic 14A i 14B: performance i signal precomputation

Kada reuse discovery i bounded guidance produktizacija budu stabilni, sledeći racionalan korak je ubrzanje i rasterećenje ranking toka.

Fokus:

- dalje produktizovanje target vector cache pristupa
- stabilni precomputed signali
- jasna granica između runtime scoring-a i keširanih slojeva

### 6. Epic 12B: system-specific virtual targets

Ovaj pravac ima smisla tek kada canonical coverage i governance disciplina budu dovoljno stabilni.

Pravilo:

- canonical-only ostaje baza
- system-specific virtual target ne sme da zamagli current canonical-first model

### 7. Epic 9: data quality intelligence

Ovo ostaje važna, ali sledeća liga prioriteta. Treba ga uvoditi tek kada reuse i operational hardening budu dovoljno zatvoreni.

### 8. Epic 15: derived graph layer

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

Nastaviti disciplinu: malo dokumenata sa jasnim ulogama, bez novih snapshot fajlova koji dupliraju plan ili current-state sadržaj. Posle svakog većeg execution wave-a ažurirati `current_state.md`, `completed_slices.md` i `plan.md` u istom talasu.

## Operativna pravila

- Jedan glavni product fokus u isto vreme; tehničke faze služe kao podrška, ne kao zaseban backlog univerzum.
- Ne raditi veliki UI refactor, persistence redesign i product feature slice u istom talasu.
- Svaka promena mora da se završi fokusiranim testom ili drugim uskim oblikom validacije.
- Kada mapping radi, ali `knowledge` ili `canonical` signal ostaje nizak, prvo proveravati da li je to realan glossary/overlay gap, ne automatski engine bug.
- Nove canonical ili knowledge dopune prvo treba zatvarati overlay-first putem, pa tek kasnije promovisati u stabilni base sloj.