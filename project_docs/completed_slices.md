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

## 2026-05-17

### Workspace Output: artifact refinement slice

Isporučeno:

- `POST /mapping/codegen/refine` bounded refinement endpoint
- split-view original/refined artifact prikaz u `Workspace > Output`
- `Accept refined version` i `Discard refinement` UX
- refinement instrukcije, edge cases i reference excerpt inputi

Ishod:

- Output više ne staje na jedan generated artifact; postoji kontrolisan refinement loop bez automatskog overwrite ponašanja

### Guided copilots expansion across Review, Benchmarks, Canonical Gap queue, and Catalog

Isporučeno:

- benchmark explanation surface (`/evaluation/explain` + Benchmarks UI)
- review queue planning surface (`/mapping/review-plan` + Review UI)
- canonical gap queue summary surface (`/knowledge/canonical-gaps/triage-summary` + Review UI)
- catalog workspace reuse-fit surface (`/catalog/reuse-fit` + Catalog UI)

Ishod:

- bounded AI sloj više nije vezan samo za mapping validation i transformation generation; sada pokriva i objašnjenje, triage i reuse-fit readout tokove

### Discoverability and documentation alignment wave

Isporučeno:

- review-plan labeling je pooštren u `Review Queue Plan` da se jasnije razlikuje od `Mapping Analysis Overview`
- `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit` sada imaju vidljive unlock/prazne state poruke umesto da deluju kao sakrivene funkcije
- `project_docs`, `README`, `PROJECT_OVERVIEW` i `help` dokumenti su usklađeni sa trenutnim stanjem proizvoda i novim sledećim koracima

Ishod:

- korisnik sada jasnije vidi gde se nalaze nove bounded guidance površine i kako se razlikuju od postojećih review/explanation tokova

## 2026-05-18

### Workspace review, canonical parity, and setup enrichment wave

Isporučeno:

- per-row `LLM refine` tok u `Workspace > Review` sa transient meaning/negative/sample/refinement instruction kontekstom
- batch low-confidence LLM refine i accept/revert ponašanje za refined row predloge
- ručno mapiranje i u canonical modu kroz virtual canonical target opcije u `Decisions`
- canonical Output sada zadržava code generation i artifact refinement, ali bez preview-a nad nepostojećim target redovima
- standard `Setup` sada eksplicitno podržava i `Source Companion Metadata` i `Target Companion Metadata`
- `Canonical candidate pool size` surfaced u Setup-u, sa podignutim podrazumevanim default-om na `10`
- auto-accept prag vraćen na `>= 0.75`, odvojen od confidence-label bucket-a

Ishod:

- Workspace canonical tok više nije second-class u odnosu na standard Decisions/Output površine, dok Setup i Review jasnije pokrivaju metadata enrichment i row-level LLM refinement rad

### Run0518: Guided productization, reuse expansion, browser hardening, and runtime/persistence prep

Isporučeno:

- bounded guidance productization kroz realni pilot scenario, naming/alignment cleanup i jasnije razdvajanje explanation, triage i refinement surface-a
- `Epic 13D` reuse/discovery proširenje kroz bogatiji compare/drilldown, workspace-aware reuse fit snapshot i konkretne Catalog -> Workspace / Canonical Console handoff signale
- browser-level hardening i regression discipline kroz proširen `docs/pilot/PILOT_REGRESSION_SUBSET.md`, live Catalog reuse / Benchmarks explanation smoke prolaze i zatvorene UX prepreke iz realnog pilot toka
- runtime/persistence separation priprema kroz zaseban slice plan, ciljano canonical authoring osvežavanje bez full metadata reseed puta i eksplicitne durable-backend trigger-e za lokalni mapping job runtime

Ishod:

- bounded guidance, reuse i governance surface-i su productized i pilot-hardened kao jedan završen execution wave, a naredni rad se vraća na uži post-pilot hardening backlog umesto na isti Run0518 checklist

## 2026-05-19

### Persistence and runtime separation hardening: durable mapping job status slice

Isporučeno:

- mapping job runtime sada čuva status, progress tail i cancel state u SQLite-u, uz isti `start / poll / cancel` API contract i lokalni thread-backed execution model
- uveden je state-store sloj iznad job runtime-a tako da isti service surface može da radi nad in-memory i SQLite-backed status store-om
- zadržani su active-job cap, finished-job TTL i retention cap, ali durable cleanup i observability u SQLite modu sada računaju wall-clock starost umesto perzistiranog monotonic sata
- startup recovery sada prebacuje prekinute aktivne job-ove u `failed`, a activity polling vraća najnoviji zadržani event tail
- observability runtime surface prijavljuje `sqlite_status` storage mode i iste durable-backend trigger-e kao pre ovog refactora

Ishod:

- mapping progress lifecycle je sada durable na nivou status/progress read modela za lokalni i pilot režim, bez prerane introdukcije lease/dequeue ili spoljnog brokera

### Persistence and runtime separation hardening: targeted SQLite normalization slice

Isporučeno:

- canonical authoring sync više ne radi full knowledge runtime rewrite kada se menja samo glossary/promoted canonical slice, nego osvežava samo canonical runtime tabele nad postojećim persisted knowledge snapshot-om
- uvedeni su uski repository slojevi za knowledge runtime snapshot, stewardship queue, catalog discovery i mapping-set governance surface-e
- route i service call-site-ovi za Canonical Console, stewardship, catalog i mapping-set governance više ne zavise direktno od širokog persistence service surface-a za ove ciljane read modele
- dodati su fokusirani backend testovi za canonical authoring sync bez full runtime replace-a, stewardship queue filter read model i catalog projection posle governance update-a

Ishod:

- persistence separation wave je zatvoren za trenutni pilot scope: canonical authoring, governance i discovery sada imaju jasnije SQLite read/write granice, dok lease/dequeue i širi DB-only authoring ostaju sledeća faza kada zaista zatrebaju

## 2026-05-22

### Review -> Decisions LLM proposal productization and audit persistence

Isporučeno:

- `LLM Decision Proposals` surface za `needs_review` redove u `Workspace > Review`
- opcioni live bounded LLM fill za redove bez cached proposition-a
- `Decisions` apply/dismiss workflow za predloge, uključujući konzervativni `Apply safe` batch mode
- decision-origin audit surfacing u `Active Decisions` (`manual_mapping`, `llm_proposal`)
- decision-origin audit persistence kroz JSON export/import decision checkpoint-a

Ishod:

- LLM predlog sada ima kompletan put od advisory review signala do kontrolisanog apply toka sa vidljivim poreklom odluke i handoff-friendly persistence slojem

### Sidebar guidance shell and canonical metrics parity

Isporučeno:

- `Operations` KPI strip i `Unified Status Legend` premešteni u sidebar kao stalni navigacioni/orijentacioni sloj
- compact operations strip formatiran kao 2x3 grid za bolju preglednost
- onboarding hints po glavnim površinama (`Workspace`, `Governance`, `Catalog`, `Benchmarks`, `System`)
- Canonical tab summary dopunjen metrikama broja koncepata u stilu Knowledge registra (`Filtered`, `Total`, `With active overlay`, `With context`)

Ishod:

- UX je konzistentniji i ozbiljniji kroz sve glavne tokove, uz bolju discoverability i parity između canonical i knowledge pregleda

### Documentation sync wave

Isporučeno:

- usklađeni `README.md`, `help.md`, `help.en.md`, `PROJECT_OVERVIEW.md`
- osveženi `project_docs/current_state.md`, `project_docs/completed_slices.md` i planning smernice u `project_docs/plan.md`

Ishod:

- dokumentacija sada odražava aktuelno implementirano ponašanje (proposals, audit, sidebar guidance, continuity boundary) i sledeći design fokus

## 2026-05-26

### Bounded guidance productization follow-through

Isporučeno:

- svih pet bounded guidance panela sada dele isti `LLM` / `Fallback` header-detail obrazac
- `Benchmark Explanation` i `Workspace Reuse Fit` više ne mešaju `summary` i `explanation` u action/empty-state copy-ju
- success/error copy je poravnat na obrazac `Generated ...` / `... generation failed: ...` kroz `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit`
- read-only intro caption i unlock copy su poravnati kroz `Workspace`, `Benchmarks` i `Catalog`
- output-section heading pattern je poravnat kroz guidance surface-e uz zadržanu domen-specifičnu terminologiju (`Key matches`, `Key findings`, `Risks`, `Next actions`)
- `Workspace Reuse Fit` generation metadata više ne koristi poseban metric tretman, već isti caption obrazac kao `Workspace` i `Benchmarks`
- `implementation_checklists.md` je proširen punom guidance matricom i ažuriran kroz šest uzastopnih productization slice-ova

Ishod:

- bounded guidance family sada deluje kao jedan koherentan product surface na helper/test nivou, a sledeći korak prelazi sa copy/alignment cleanup-a na browser-level pilot proveru discoverability-ja

## 2026-05-27

### Epic 13D completion wave: discovery/reuse handoffs, CTA clarity, and live governance smoke

Isporučeno:

- field-scoped Catalog reuse discovery je proširen compare-before-import, parcijalnim importom i undo putanjom
- `Catalog` sada pokriva compare -> detail drilldown za peer integracije i version baseline poređenja umesto da staje na summary readout-u
- `Catalog` version diff readout sada direktno otvara `Workspace Review` sa source-scoped fokusom za changed rows
- `Catalog` governance handoff sada otvara uži `Canonical` ili `Stewardship` landing umesto generičkog console ulaza, uz reset stale filtera pre preuzimanja novog fokusa
- diff CTA copy i glavni drilldown CTA copy sada eksplicitno kažu da li vode u `Canonical review` ili `Stewardship`
- live browser smoke je potvrđen i za current diff `Canonical` handoff i za unmatched-source `Stewardship` handoff nad seeded catalog zapisom

Ishod:

- `Epic 13D` je zatvoren kao trenutni feature wave; sledeći aktivni execution fokus vraćen je na uži operational hardening i regression capture nad pilot površinama

### dbt Output enablement and runtime hardening follow-through

Isporučeno:

- `dbt` je dodat kao treći Output artifact mode uz `Pandas` i `PySpark`, uključujući `sql-dbt` generated artifact surface u `Workspace > Output`
- live browser smoke je potvrdio čist `Catalog -> Workspace reuse -> Output -> Generate dbt model -> Refine with LLM` tok nad svežim `8001` backendom i seeded approved mapping set-om
- promena `API Base URL` u sidebar-u sada resetuje transient backend-bound session state i vraća UI na `Workspace > Setup`, čime se sprečava mešanje starih dataset handle-ova, generated artifacts i handoff fokusa preko backend granice
- `dbt` artifact refinement parser je hardenovan za LM Studio near-JSON/prompt-echo odgovore koji rewritten artifact vraćaju kroz `current_code` i `response_format`, uključujući malformed JSON shape koji je ranije izazivao `502` na `/mapping/codegen/refine`

Ishod:

- `dbt` Output slice više nije samo helper/API capability; potvrđen je i na browser nivou, a promena backend endpoint-a više ne ostavlja UI u stale cross-runtime stanju

## Napomena

- Završeni slice-ovi su namerno odvojeni od backlog-a kako bi `epics.md` ostao pregledan.
- Aktivni naredni rad treba da se vidi u `implementation_checklists.md`, a ne ovde.