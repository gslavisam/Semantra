# Semantra Plan

Ovaj dokument drži plan i redosled rada.

- Strateški roadmap: kuda proizvod ide.
- Izvršne tehničke faze: kako čistimo arhitekturu i dug.
- Trenutni redosled rada: šta ima prioritet.
- Operativna pravila: kako uvodimo knowledge, canonical i refactor promene.

Detaljni epic backlog je u `epics.md`.
Radne checkliste su u `implementation_checklists.md`.
Završeni slice-ovi su u `completed_slices.md`.
Revizija strategije i trenutnog stanja iz 2026-05-09 je u `strategy_review_2026-05-09.md`.

## Product Roadmap

### Phase 1: Harden Current Alpha

Fokus je da sadašnji proizvod postane stabilan i ponovljiv za demo i pilot upotrebu. Tu spadaju bolji upload flow, knowledge overlay MVP kroz upload, bolji error handling, sigurnije transformation preview/codegen iskustvo, reproducible benchmark skupovi i jasniji trust-layer UI.

Exit kriterijum: korisnik može da uploaduje source/target, dobije ranking, razume zašto je nešto mapirano, doda knowledge overlay i bez ručnih intervencija ponovi isti scenario.

### Phase 2: Learning Mapper

Ovde alat prelazi iz jednokratnog pametnog predloga u sistem koji pamti šta je tim ranije odlučivao. Dodaju se user correction learning loop, knowledge customization UI za male override-e, bolja confidence kalibracija, similar past decisions objašnjenja i mogućnost da trust layer direktno generiše nove synonyms/aliases iz odobrenih odluka.

Exit kriterijum: kvalitet mapiranja raste kroz vreme na osnovu istorije, a ne samo na osnovu statičkog dictionary-ja.

### Phase 3: Semantic Layer

Ovo je najveći product skok. Uvodi se canonical business model i business glossary, tako da alat ne radi samo source -> target, nego i source -> canonical concept -> target. Time Semantra postaje alat za semantičko usaglašavanje, ne samo za fuzzy matching kolona.

Exit kriterijum: korisnik može da mapira na poslovne koncepte kao što su Customer, Vendor, Material, Employee, Invoice i da isti koncept koristi kroz više sistema i projekata.

### Phase 4: Governance and Trust

Kada alat počne da se koristi ozbiljnije, treba mu governance sloj: verzionisanje mapping setova, approval workflow, audit trail, statusi, komentari, ownership, PII/sensitive data detekcija i jasna razlika između predloga, potvrđenih pravila i produkcionih pravila.

Exit kriterijum: Semantra više nije samo analystski alat, nego reviewable i kontrolisani sistem za timski rad.

### Phase 5: Operationalization

Ovde rezultat Semantre postaje izvršiv i integrabilan u realne tokove rada. Dodaju se export u pandas/SQL/dbt/ETL specifikacije, batch execution, run history, schedule, webhook/API triggeri, schema drift monitoring i quality checks nad realnim run-ovima.

Exit kriterijum: alat ne završava na preview-u, nego proizvodi artefakte i procese koji mogu stvarno da se koriste u delivery toku.

## Technical Execution Phases

### Faza 0: Sigurnosni i Refactor Guardrails

Status: open.

Cilj: zatvoriti očigledne rizike i obezbediti da refactor ne promeni ponašanje sistema.

- zaključati admin pristup
- srediti CORS podrazumevane vrednosti
- dopuniti karakterizacione testove nad ključnim payload-ima i Streamlit helper-ima
- ne menjati API shape i persistence model u istoj fazi

### Faza 1: Mali Cleanup Sa Niskim Rizikom

Status: completed on 2026-05-03.

Cilj: ukloniti duplikacije i zajedničke pomoćne funkcije bez menjanja arhitekture.

### Faza 2: Razbijanje Streamlit Monolita

Status: completed on 2026-05-03.

Cilj: izvući state, API i view logiku iz `streamlit_app.py` u jasnije module bez promene UI toka.

### Faza 3: Dekompocija Mapping Engine-a

Status: planned.

Cilj: `mapping_service.py` prestaje da bude god service.

- razdvajanje scoring, explanation, assignment i LLM gate logike
- uvođenje pairwise feature objekta po source-target paru
- zadržavanje kompatibilnih response modela tokom faze

### Faza 4: Razdvajanje Knowledge i Canonical Runtime-a

Status: planned.

Cilj: `metadata_knowledge_service.py` podeliti po odgovornostima.

- odvojiti base metadata knowledge od canonical matching-a
- odvojiti overlay lifecycle od runtime matchinga
- uvesti jasne refresh granice

### Faza 5: Persistence Redesign Bez Menjanja SQLite-a

Status: planned.

Cilj: zadržati SQLite, ali ukloniti najveće slabosti JSON-blob pristupa.

- normalizovati queryable metadata gde listing i versioning to traže
- izbaciti obrasce učitaj sve pa izračunaj u Python-u
- dodati lagane migration korake

### Faza 6: Performance, Observability i Repo Organizacija

Status: planned.

Cilj: meriti trošak po request-u, učiniti module preglednijim i srediti docs/test strukturu.

## Current Recommended Order

Trenutni preporučeni redosled rada:

1. Validirati `Epic 14E` Canonical Gap Assistant kao praktični beta slice: prazni `canonical_path` i jaki mapping signali postaju LLM-assisted, human-approved predlozi za canonical overlay.
2. Izdvojiti `Epic 14F` Canonical Concept Management Console kao glavni governance ekran za canonical concepts, aliases, gap queue, overlay status i EA/MDM reuse pregled.
3. Nastaviti `Epic 13D` discovery i reuse slice nad postojećim katalogom, koristeći iste usage/read modele koje 14F traži.
4. Ispratiti `Epic 14D` description-aware context i companion schema kao najdirektniji kvalitetni dobitak za mapping odluke.
5. Posle stabilnog context sloja razmotriti `Epic 12B` system-specific virtual target-e tamo gde metadata kvalitet to opravdava.
6. `Epic 15` graph projection uvoditi kao derived sloj posle sazrevanja canonical, catalog i description-aware context rada.
7. Faze 3-6 koristiti kao ciljane tehničke talase, ne kao blokadu za svaki novi feature.

Detaljna release i MVP checklista je u `implementation_checklists.md`.

## Dictionary and Canonical Evolution Rules

Pravila tokom beta validacije:

- Kada mapping uspešno prolazi, ali `knowledge` ostaje `0`, tretirati to prvo kao knowledge gap kandidat, ne kao automatski bug.
- Kada mapping uspešno prolazi, ali `canonical` ostaje `0`, tretirati to prvo kao canonical glossary gap kandidat, ne kao automatski bug.
- Nove alias/synonym/concept gap-ove prvo upisivati kroz knowledge overlay, ne direktno u base dictionary.
- Nove canonical concept gap-ove prvo pokrivati kroz canonical glossary i `concept_alias` overlay putanju, ne kao ad hoc workaround u scoring-u.
- LLM može da predlaže canonical concept/alias popune za gap-ove, ali ne sme automatski da ih promoviše u base dictionary ili stabilni glossary bez review-a.
- Tek kada se isti unos pokaže korisnim kroz više realnih datasetova ili više projekata, promovisati ga iz overlay sloja u base dictionary ili stabilni canonical glossary sloj.
- Ako je unos lokalno specifičan za jedan klijent, jedan source sistem ili jedan pilot tok, ostaviti ga u overlay sloju.
- Canonical concept management treba tretirati kao product konzolu za EA/MDM/integration governance, ne kao debug/admin pomoćni ekran.

## Post-Beta Scaling and Debt Backlog

Ove stavke jesu realan tehnički dug, ali nisu prioritet ispred real-data validacije, preostalog `Epic 6` gate-a i prvih visoko-vrednih feature slice-ova.

Preporučeni redosled:

1. Mali SQLite hardening korak (`WAL`, `busy_timeout`, osnovno merenje contention-a) pre većeg persistence redesign-a.
2. Razdvajanje knowledge runtime-a tako da overlay lifecycle ne tera puni runtime rebuild za svaku activation/deactivation promenu.
3. Kasnije uklanjanje AST-test-driven adapter workaround-a iz `streamlit_app.py` kada novi test/setup režim bude spreman.
4. Produkcioni hardening mapping progress jobova: trenutni in-memory/thread job status je dovoljno lagan za lokalni demo/dev tok, ali za multi-user ili dugotrajne run-ove treba planirati persistent queue/status sloj (`Redis/RQ/Celery` ili ekvivalent), TTL cleanup, retry/cancel semantiku i merenje overhead-a.

Konkretne debt stavke:

- `metadata_knowledge_service.refresh()` danas radi full rebuild knowledge i canonical runtime-a pri overlay lifecycle promenama.
- `persistence_service.py` otvara novu SQLite konekciju po operaciji; pratiti potrebu za concurrency hardening-om.
- `streamlit_app.py` i dalje koristi thin adapter pattern zbog AST-based regression testova; čistiti tek kada postoji stabilna zamena.

## Execution Principles

- Jedna faza, jedan PR ili jedan logički commit niz.
- Ne raditi Streamlit split i persistence redesign u isto vreme.
- Svaka faza mora da završi sa uskim test subset-om, ne sa ručnim utiskom da radi.
- API shape i DB schema ne menjati u istoj fazi osim ako je to baš svrha te faze.