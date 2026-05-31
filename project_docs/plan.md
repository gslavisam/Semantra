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
- dokumentacija treba da ostane stalno usklađena sa realnim stanjem proizvoda, jer je to trenutno veća vrednost od daljeg feature širenja

Sledeći korak nije nasumično širenje u mnogo pravaca odjednom. U ovoj fazi najveću vrednost ima da proizvod bude precizno dokumentovan, manuelno proveren, dokazano koristan u realnim tokovima i spreman za jasne prezentacije i ponovljive live demo prolaze. Tek posle toga ima smisla zatvarati širi enterprise-wide app talas.

## Prioritetni redosled rada

### 1. Dokumentacija i truth-aligned product narrative

Prvi fokus je da svi glavni entry-point dokumenti pričaju istu, tačnu priču o tome šta proizvod danas jeste, šta još nije, i gde je trenutni dokaz vrednosti.

Fokus:

- držati `README`, `PROJECT_OVERVIEW`, `project_docs/current_state.md`, `project_docs/completed_slices.md` i relevantne reference dokumente u istom realnom stanju
- jasno razdvojiti pilot-complete surface-e od otvorenih enterprise tema
- dokumentovati ne samo capability-je, nego i boundary-je, enforcement model i known limitations
- izbeći situaciju u kojoj je prezentaciona priča ispred stvarnog proizvoda ili obrnuto

### 2. Manualno testiranje, proof of concept i value proof

Drugi fokus je da se postojeći proizvod dokaže kroz realne prolaze, a ne da se prerano širi novim capability-jima.

Fokus:

- proći glavne analyst i governance tokove ručno više puta sa realističnim ulazima
- potvrditi gde `Workspace`, `Catalog`, `Benchmarks` i `Canonical Console` zaista dodaju vrednost organizaciji
- izdvojiti konkretne use case-eve gde proizvod skraćuje review, povećava reuse ili pojačava governance kontrolu
- pretvoriti te nalaze u jasan proof-of-concept i dokaz poslovne vrednosti

### 3. Prezentacije, demo assets i ponovljiv live demo

Treći fokus je da validated product story bude lako prenosiva prema stakeholder-ima.

Fokus:

- ažurirati prezentacije, live demo runbook-e i asset mapu tako da prate stvarni current state
- držati jedan glavni demo tok koji je pouzdan, vrednosno jasan i lako ponovljiv
- koristiti screenshot, recording i runbook materijale kao dokaz da proizvod nije samo lokalni eksperiment
- vezati prezentacionu priču za konkretne pilot nalaze i value proof, ne za buduće feature nade

### 4. Produktizacija bounded guidance površina

Ovaj fokus i dalje ima smisla, ali tek nakon što validation i demo sloj potvrde gde guidance stvarno pomaže.

Fokus:

- uskladiti naming, unlock poruke i expected user journey između `Workspace`, `Benchmarks` i `Catalog`
- potvrditi kroz realne tokove gde korisnik stvarno dobija vrednost od `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit`
- izbeći semantičko preklapanje između postojećeg trust layer-a i novih queue/explanation panela
- zadržati pravilo da nijedna od ovih površina ne radi auto-apply ili auto-approval

### 4A. Epic 11B: bounded upload recovery and structure understanding

Prvi uski `schema-spec` recovery slice ovog pravca je sada zatvoren. Semantra već ume da oporavi parseable metadata fajl čiji su headeri bliski očekivanom obrascu, ali ne prolaze užu determinističku detekciju, uz bounded predlog i obavezni deterministički replay pre upload uspeha.

Pravila koja ostaju i za svaki sledeći nastavak:

- deterministički ingest ostaje authoritative putanja
- bounded `LLM` sme da se koristi samo kao recovery sloj za razumevanje strukture kada postojeći upload ili `spec` detekcija ne uspeju
- `LLM` nikada ne sme direktno da persistira dataset handle ili da zameni replay-validaciju postojećim parserima

Zatvoreni prvi slice:

- bounded recovery contract, recovery endpoint, `Workspace`/companion UX i fokusirana test mreža postoje za `schema-spec` metadata fajlove
- live smoke je potvrdio source-only recovery affordance, eksplicitno prihvatanje predloga i uspešan upload/profile ishod nad realnim recovery fixture-om

Sledeći legitimni nastavak, ali ne automatski sledeći prioritet:

- row-data header recovery za neusaglašene poslovne recordset fajlove
- multi-sheet i `record_path` heuristika za složenije tabularne izvore
- `SQL` recovery heuristika tek kada za to postoji stvarni pilot pritisak
- recovery telemetry/eval readout ako se pokaže da recovery ulazi u širu pilot upotrebu

Fokus:

- definisati strogo strukturisan fallback contract (`detected_mode`, `sheet_name`, `header_row_index`, `record_path`, `name_col`, `description_col`, `type_col`, `sample_values_col`, `selected_table`, `confidence`, `warnings`)
- analizirati samo minimizovan strukturni uzorak fajla kad god je to dovoljno, umesto da se modelu šalje ceo payload
- obavezno odraditi deterministički replay nad postojećim upload parserima pre bilo kakvog save koraka
- izložiti korisniku predlog, confidence i ručni override umesto tihog auto-prihvatanja
- logovati razlog fallback-a, prihvaćenu interpretaciju i replay ishod kao audit signal za kasniju evaluaciju

Granice koje i dalje važe:

- ne širiti recovery pravac na `PDF`, slike, OCR ili proizvoljne nestrukturisane dokumente pod istim ingest contract-om
- ne dozvoliti auto-persist ili fail-open ponašanje samo zato što recovery postoji
- malformed ili shape-invalid `JSON` / `XML` payload-i ostaju strict parser boundary: advisory detect za njih sme da vrati samo `hint=None`, dok pravi upload/recovery i dalje mora da vrati jasan reject dok se ne pojavi stvarni pilot razlog za bounded fallback i na toj strani

### 5. Session continuity and resume-by-design (ne uvoditi na brzinu)

Sledeći UX/produkt fokus koji treba osmisliti pažljivo pre implementacije je nastavak rada nakon zatvaranja browser-a ili narednog dana.

Fokus:

- definisati šta je tačno `draft session` jedinica (scope po workspace-u, korisniku i setu učitanih artefakata)
- odvojiti automatski restore UI stanja od governance artefakata koji već postoje (`mapping set`, decision checkpoint export/import)
- definisati konflikt pravila kada postoji više paralelnih checkpoint-a ili promene backend podataka
- uključiti decision/audit semantiku u resume tok da poreklo odluka ostane jasno
- ažurirati `README`, `help`, `PROJECT_OVERVIEW` i `project_docs` zajedno sa implementacijom da behavior bude transparentan

### 6. SAP-first knowledge expansion i canonical coverage wave

Posle poslednjih SAP mapping poboljšanja postalo je jasno da sledeći veliki kvalitetni dobitak više nije samo engine tuning, nego sistematsko širenje knowledge pokrivenosti i disciplinovano izvlačenje canonical gap-ova iz postojećih vendor specifikacija.

Fokus:

- inventarisati i normalizovati postojeće SAP field specifikacije kao reproducibilan knowledge source, ne kao ručni CSV patch backlog
- uvesti staging i provenance disciplinu između raw vendor spec izvora, curated knowledge runtime sloja i canonical promotion kandidata
- izvući SAP canonical gap backlog pre širenja na Workday, QAD i QuickBooks
- definisati benchmark/eval slice-ove i KPI-jeve za coverage, top-1 tačnost, final assignment tačnost i prisustvo `knowledge` / `canonical` signala
- posle SAP pilot faze primeniti isti ingest/eval/promocija model na Workday, QAD, QuickBooks i druge javno dostupne ERP specifikacije

Detaljniji radni okvir za ovaj talas je u `docs/vision/KNOWLEDGE_EXPANSION_WAVE.md`.

### 7. Epic 13D: Concept and reuse discovery expansion

Početni 13D discovery talas je zatvoren kroz concept-centric reuse pregled, viši discovery overview, reuse hint-ove i surfacing ponavljanih review gap-ova. Sada sledi širenje tog sloja.

Fokus:

- bogatiji concept-centric reuse pregled kroz više integracija
- bolji compare/drilldown između sličnih integracija i mapping set verzija
- povezivanje Catalog reuse discovery signala sa Workspace review i canonical gap radom
- jači reuse narativ pre samog `Reuse in Workspace` koraka

### 8. Operational hardening nad postojećim pilot površinama

Ovo ostaje stalni paralelni fokus pre većeg feature širenja, ali sa jasnim Workspace-first prioritetom.

Operativna odluka za naredni period:

- `Workspace` je glavni end-user proizvodni sloj i praktično čini oko 80% onoga što krajnji korisnik vidi kao samu aplikaciju
- `Governance` nije paralelni korisnički centar težišta, nego veza ka upravljačkim dimenzijama organizacije (`EA`, `MDM`, integration dev team, data governance)` koje usmeravaju, odobravaju ili promovišu rezultate Workspace rada
- ostale površine (`Catalog`, `Benchmarks`, `Governance`, `System`) tretirati prvenstveno kao podršku, handoff ili nadzor nad istim Workspace životnim ciklusom
- kada postoji izbor između novog cross-surface polish-a i jačeg `Workspace > Setup -> Review -> Decisions -> Output` toka, prednost ima Workspace

Fokus:

- stabilniji regression subset za `Workspace` happy-path i njegove glavne failure/gate slučajeve
- browser-level proveru najvažnijih Workspace tokova, ne samo helper testove
- dalji governance enforcement tamo gde `Workspace` i dalje ima advisory ili implicitne prolaze
- UX poliranje zasnovano na realnim Workspace pilot prolazima
- session continuity, draft resume, reuse handoff i output generation tretirati kao produžetke Workspace toka, ne kao odvojene UX ostrvske površine

Future external API integration smer:

- pošto se zajedno sa aplikacijom podiže i backend API, treba planirati i spoljašnji integration-ready surface za klijente koji neće koristiti Streamlit UI nego direktno HTTP pozive
- taj budući sloj ne treba da bude samo izlaganje internih workflow koraka jedan-po-jedan, nego tanak orchestration contract nad postojećim upload/profile/mapping capability-jima
- dva glavna spoljašnja use-case-a koja vredi zatvoriti su:
	- `source recordset/spec -> canonical concepts overview`
	- `source + target -> flattened mapping overview` sa `source field`, `canonical concept`, `target field`, confidence procentima, signal breakdown-om i `LLM` odgovorom kada postoji
- ciljni oblik ovog future slice-a treba da bude jedan ili mali broj stabilnih endpoint-a namenjenih integraciji, umesto da eksterni klijent mora da poznaje ceo interni Workspace/API workflow
- ovaj pravac ima smisla tek kada pilot validation i value proof potvrde da surface treba produktizovati za širu sistemsku integraciju, a ne samo za lokalni analyst workflow

Workspace copilot smer za sledeći UX/productization slice:

- ne dodavati novi generički chat koji živi pored proizvoda, nego objediniti postojeće bounded `LLM` / `Fallback` capability-je u jedan stalno dostupan `Workspace Copilot` sloj unutar glavnog analyst toka
- primarni cilj nije više capability coverage, jer su `LLM refine`, guidance summary, decision proposals i output refinement već prisutni; cilj je da korisnik više ne mora da zna koji panel otvara za koju vrstu pitanja ili provere
- prvi slice treba da ostane bez većeg backend refaktora: desni sidebar ili ekvivalentni stalni shell treba da orkestrira postojeće `Review`, `Decisions` i `Output` capability-je nad aktivnim Workspace kontekstom
- copilot mora da ostane bounded, audit-friendly i bez auto-apply ponašanja; njegov posao je da skrati put do postojećih akcija i da objasni trenutno stanje bez izbacivanja korisnika u eksterni LLM interfejs
- detaljniji UX model i tehnička mapa za ovaj smer su u `project_docs/workspace_copilot_concept.md`

### 9. Persistence i runtime separation hardening

Prvi lokalni/pilot slice ovog fokusa je zatvoren. Sledeći rad ovde više nije osnovno razdvajanje, nego tek naredna faza kada se pojavi stvarna operativna potreba.

Fokus:

- zadržati trenutni SQLite-backed status backend za mapping jobs dok god je izvršenje i dalje lokalno/thread-backed
- ne uvoditi lease/dequeue ili broker dok cross-process execution, restart-safe retries ili multi-host visibility stvarno ne uđu u product scope
- širiti DB-normalized read/write modele samo na nove governance/discovery surface-e koji pokažu realan query pressure, ne kao globalni persistence redesign
- nastaviti postepeno odvajanje canonical authoring od runtime matching sloja tek kada bude potreban širi DB-only authoring model

### 10. Epic 14A i 14B: performance i signal precomputation

Kada reuse discovery i bounded guidance produktizacija budu stabilni, sledeći racionalan korak je ubrzanje i rasterećenje ranking toka.

Fokus:

- dalje produktizovanje target vector cache pristupa
- stabilni precomputed signali
- jasna granica između runtime scoring-a i keširanih slojeva

### 11. Epic 12B: system-specific virtual targets

Ovaj pravac ima smisla tek kada canonical coverage i governance disciplina budu dovoljno stabilni.

Pravilo:

- canonical-only ostaje baza
- system-specific virtual target ne sme da zamagli current canonical-first model

### 12. Epic 9: data quality intelligence

Ovo ostaje važna, ali sledeća liga prioriteta. Treba ga uvoditi tek kada reuse i operational hardening budu dovoljno zatvoreni.

### 13. Epic 15: derived graph layer

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

### Vendor knowledge ingestion i canonical gap mining

Sledeći veći knowledge talas ne treba voditi kroz ručno dopisivanje stotina ili hiljada redova, nego kroz kontrolisan ingestion model.

Potrebno je odvojiti:

- raw vendor specifikacije i public-source artefakte
- staging/generated knowledge sloj sa provenance metapodacima
- curated runtime knowledge koji ulazi u matching
- canonical gap candidate set koji ide u stewardship, a ne direktno u canonical registry

### Persistence hardening bez napuštanja SQLite-a

SQLite ostaje prihvatljiv za trenutnu fazu, ali treba postepeno normalizovati queryable read/write modele tamo gde listing, governance i discovery to već traže.

Sledeći korak ovde treba formulisati preciznije: cilj nije da "sve iz UI-ja završava u bazi", nego da svi domenski entiteti koji nose ownership, audit, resume, collaboration ili lifecycle semantiku imaju backend identitet i DB model.

DB-first target za sledeću fazu:

- workspace kao trajni backend entitet, ne samo skup session-local upload/mapping objekata
- upload dataset handle i schema-profile lineage kao persistirani workspace resursi
- review queue / proposal queue / decision workspace kao persistiran radni kontekst, ne samo `st.session_state` projekcija
- transformation artifact drafts i accepted outputs kao versioned backend artefakti
- canonical and knowledge authoring kao DB-native write path, dok file import postaje samo ingest mehanizam, ne source-of-truth authoring surface
- overlay lifecycle, stewardship, catalog, benchmarks, mapping sets i jobs ostaju u DB modelu i dalje se produbljuju, ne vraćaju se u file/session obrasce

Šta može legitimno da ostane van baze i kasnije:

- čisto UI izbori kao otvoren tab, lokalni filter toggle, privremeno proširen expander, trenutno selektovan red u tabeli
- tehnički connection convenience state kao lokalni API URL i kratkotrajni reachability cache

Drugim rečima: treba prebaciti sve business-grade entitete u bazu, ali ne treba nasilno persitirati svaki prolazni UI signal.

### Background job hardening

Današnji lokalni thread-backed worker runtime uz SQLite-persistiran job status je dobar za lokalni dev i pilot. Za ozbiljniji multi-user ili dugotrajniji execution model biće potreban durable queue/status sloj.

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
- Masovne vendor knowledge refresh-eve ne raditi ad hoc ručnim editovanjem `metadata_dict.csv`, nego staged/generated ingest putem sa provenance i eval gate-ovima.
- Vendor-specifične tehničke ili administrativne field-ove ne promovisati automatski u canonical sloj; canonical ostaje uži, business-normalized registry.
