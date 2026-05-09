# Semantra Epics

Ovaj dokument je epic katalog.

- Strateški plan i redosled rada: `plan.md`
- Detaljne radne checkliste: `implementation_checklists.md`
- Završeni i isporučeni slice-ovi: `completed_slices.md`

## P0 Epics

### Epic 1: Knowledge Overlay MVP

Status: open.

Cilj: korisnik može da doda sopstvene sinonime, skraćenice i aliase bez menjanja baznih fajlova.

Scope summary:

- overlay model i entry model sa verzionisanjem i statusima
- CSV parser i validation preview pre aktivacije
- conflict detection nad base dictionary-jem
- activate/deactivate workflow i runtime reload knowledge sloja
- overlay-aware `metadata_knowledge_service` i audit log za knowledge promene

### Epic 2: Admin Upload UI

Status: open.

Cilj: knowledge upload i aktivacija budu dostupni iz aplikacije, ne samo kroz backend.

Scope summary:

- admin sekcija za knowledge upload
- preview validacije pre potvrde
- prikaz duplikata, konflikata i nevažećih redova
- verzije knowledge sloja i akcije `activate`, `deactivate`, `rollback`
- mali summary i indikator aktivnog režima

### Epic 3: Learning From Corrections

Status: open.

Cilj: sistem uči iz potvrđenih i odbijenih mapping odluka.

Scope summary:

- correction store sa `accepted`, `rejected`, `overridden`
- historical confirmation strength i explanation tragovi
- penalizacija ranije odbijenih targeta
- reusable rule promotion iz ponavljanih korekcija
- benchmark koji meri dobit iz correction learning loop-a

### Epic 4: Transformation Safety and Testing

Status: open.

Cilj: transformacije ne budu samo generisane, nego proverljive i bezbednije.

Scope summary:

- syntax i dry-run validacija
- before/after preview po koloni
- warnings za null expansion, type coercion i row-count mismatch
- transformation test cases po mapping setu
- reusable templates i jači error reporting

## P1 Epics

### Epic 5: Canonical Semantic Layer

Status: implemented MVP slice on 2026-05-02.

Cilj: mapiranje preko poslovnih koncepata, ne samo fizičkih kolona.

Trenutni fokus posle MVP-a:

- prelaz iz `DB-first runtime + file-based reseed source` modela u pravi `DB-only source-of-truth`
- čuvanje canonical glossary i knowledge authoring state-a u normalizovanim SQLite tabelama
- uklanjanje zavisnosti od lokalnih knowledge fajlova kao primarnog izvora istine

Referenca: detalji isporučenog MVP slice-a su u `completed_slices.md`.

### Epic 6: Governance and Versioning

Status: MVP completed on 2026-05-09.

Cilj: mapping rezultat postane reviewable i kontrolisan.

Scope summary:

- mapping set ownership, review metadata i status workflow
- audit trail i diff između verzija
- status gate za export/run putanje
- reviewable workflow bez pune row-level governance složenosti u prvom koraku

Referenca: radna checklist je u `implementation_checklists.md`.

### Epic 7: Explainability and Trust Layer Expansion

Status: open.

Cilj: korisnik bolje razume zašto je sistem izabrao baš taj target.

Scope summary:

- top competing candidates i zašto nisu izabrani
- strukturisani signal breakdown
- `why not this target?` akcija
- simulator promene weight-a ili knowledge uticaja
- badge-evi za historical, knowledge-backed i pattern-backed match-eve

### Epic 8: Benchmark and Quality Analytics

Status: open.

Cilj: svaka promena u heuristici ili knowledge sloju bude merljiva.

Scope summary:

- benchmark dashboards i regression snapshots
- pre/post score za knowledge overlay promene
- poređenje više weight konfiguracija
- run history i ključni quality KPI-jevi

## P2 Epics

### Epic 9: Data Quality Intelligence

Status: open.

Cilj: alat ne mapira samo nazive, nego procenjuje i stvarnu kompatibilnost podataka.

Scope summary:

- candidate key detection
- duplicate/null anomaly hints
- unit/currency/date-format mismatch detekcija
- referential hinting i schema drift signali
- quality warnings u trust layer-u

### Epic 10: Operationalization

Status: open.

Cilj: rezultat Semantre postane upotrebljiv u realnom delivery toku.

Scope summary:

- export u pandas, SQL i dbt-friendly artefakte
- batch run i run history
- webhook/API trigger za automation
- packaging mapping + transformation + metadata u jedan release artifact
- production-ready background jobs za duže mapping/batch procese: persistent queue, progress status, cancellation, retry policy i cleanup umesto samo in-memory lokalnog job store-a

### Epic 11: Schema Specification Upload

Status: completed on 2026-05-04.

Cilj: podržati realne source/target specifikacije gde svaki red opisuje jedno polje, umesto row-data tabele.

Aktuelni status:

- feature slice je završen bez promene downstream mapping contract-a
- `.sql` ostaje zaseban schema snapshot tok
- schema-only rezultat nema business row preview i `Rows` ostaje `0`

Referenca: isporučeni detalji su u `completed_slices.md`.

### Epic 12: Canonical-First Mapping Mode

Status: partially completed on 2026-05-04.

Cilj: omogućiti source-only mapping ka canonical konceptima bez obaveznog target fajla, pa tek zatim opciono mapiranje ka konkretnom sistemu.

#### Epic 12A: Canonical-only mapping

Status: completed on 2026-05-04.

Napomena:

- canonical-only slice je završen i validiran
- transformacije, preview i codegen su namerno isključeni bez realnog target dataseta
- canonical-only LLM rescue treba dodatno auditovati kroz real-world primere

#### Epic 12B: System-specific virtual targets

Status: planned.

Scope summary:

- virtual target schema builder za `SAP`, `Workday`, `QAD`
- `Source -> Canonical concept -> System field` rezultat tek kada je metadata kvalitet dovoljan
- graceful degradation kada system-specific coverage nije dovoljna

Pravilo izvođenja:

- canonical-only reviewable rezultat ostaje baza
- ne širiti canonical flow na transformation generation pre stabilnog system-target slice-a

### Epic 13: Enterprise Integration Catalog

Status: active since 2026-05-05.

Cilj: pretvoriti sačuvane mapping setove i canonical footprint u searchable katalog postojećih integracija i reusable semantičkih mapiranja.

Zašto postoji:

- mapping set workflow već daje review i governance artefakte, ali još ne pravi pravi EA katalog
- canonical-only artefakti treba da budu katalogizovani kao reusable asset-i
- enterprise vrednost je u search/reuse/discovery sloju, ne samo u jednom review session-u

#### Epic 13A: Catalog persistence and backend indexing

Status: active, initial slice delivered.

Cilj: queryable summary sloj nad mapping setovima.

#### Epic 13B: Catalog read APIs

Status: active, initial slice delivered.

Cilj: list/detail/search/concept-centric discovery API sloj.

#### Epic 13C: Streamlit catalog UI

Status: active, initial slice delivered.

Cilj: katalog dobija poseban search/browse/drilldown UI.

#### Epic 13D: Concept and visual discovery

Status: open.

Cilj: concept-centric i vizuelni reuse signal iznad postojećeg kataloga.

Referenca: otvorene checkliste su u `implementation_checklists.md`, a isporučeni slice-ovi u `completed_slices.md`.

### Epic 14: Vectorized Signal Acceleration and LLM Signal Fusion

Status: proposed on 2026-05-08.

Cilj: ubrzati ranking tok i otvoriti put ka bogatijem AI pojačavanju signala bez gubitka explainability sloja.

Napomena:

- postoje optional `embedding` i `llm` signali, ali bez persisted vector/cache sloja i bez signal-aware LLM fusion-a
- epic ne pretpostavlja full vector DB od prvog dana

#### Epic 14A: Target vector cache

Status: backend and initial UI read slice started on 2026-05-09.

Cilj: precomputed target embedding cache za brži similarity signal.

#### Epic 14B: Stable signal precomputation

Status: proposed.

Cilj: izdvojiti stabilne i skupe signal delove u cache/precompute sloj.

#### Epic 14C: LLM-assisted signal fusion

Status: proposed.

Cilj: proširiti LLM iz closed-set rerank validatora u reasoning sloj koji može kontrolisano da utiče na signal fusion.

#### Epic 14D: Description-aware LLM context and companion schema ingestion

Status: source companion enrichment slice implemented and smoke-validated on 2026-05-09; deterministic score fusion remains deferred pending benchmark evidence.

Cilj: poboljšati kvalitet mapiranja tako što LLM i scoring sloj dobijaju bogatiji field context od samog naziva kolone, naročito za kratke šifre, interne skraćenice i enterprise oznake.

Napomena:

- `ColumnProfile` sada čuva first-class `description` i `declared_type`, a source companion metadata može da se nakači na već uploadovan dataset handle
- spec upload sada upisuje description odvojeno od `normalized_name`
- row-data upload sada ima tanak source-side companion schema/spec enrichment put bez promene osnovnog mapping contract-a
- schema/spec i companion upload sada mogu da popune i `sample_values` kada spec fajl sadrži primer vrednosti
- odluka trenutnog slice-a je da `description`/`declared_type` ostanu LLM/context input, a ne novi deterministic signal, dok benchmark ne pokaže jasan kvalitetni dobitak bez regressions

Referenca: detaljna MVP i fajl-level checklist su u `implementation_checklists.md`.

#### Epic 14E: Canonical Gap Assistant

Status: initial MVP implemented on 2026-05-09; automated material-master validation completed, pending live UI/LLM validation.

Cilj: pretvoriti prazne ili slabe `canonical_path` rezultate u kontrolisane predloge za canonical glossary/overlay rad, uz LLM kao assistant-a i human approval kao gate.

Scope summary:

- detektovati mapping redove gde je target izabran, confidence/knowledge/semantic signal je dovoljno jak, ali `canonical_path` ili `shared_concepts` nedostaju
- generisati `canonical_gap_candidate` payload iz source field-a, target field-a, signal breakdown-a, sample values, detected patterns i najbližih postojećih canonical concepts
- koristiti LLM samo kao predlagača za postojeći canonical concept, `concept_alias`, ili novi canonical concept proposal
- prikazati predloge u UI kao review queue, sa jasnim reasoning-om i confidence-om
- odobrene predloge upisivati prvo u overlay/canonical alias sloj, ne direktno u base dictionary
- posle odobrenja omogućiti re-run mapping-a da se vidi popunjen `canonical_path`

MVP nije:

- automatska promocija LLM predloga u stabilni `canonical_glossary_erp.csv`
- free-form ontology generator bez closed-review koraka
- zamena postojećeg deterministic canonical matching-a

Referenca: detaljna MVP checklista je u `implementation_checklists.md`.

#### Epic 14F: Canonical Concept Management Console

Status: active, top-level Canonical Console tab with overlay summary, governance authoring UI, and persisted reject/ignore audit delivered on 2026-05-10.

Cilj: pretvoriti Canonical Gap Assistant i postojeći Knowledge/Admin ekran u glavnu konzolu za upravljanje canonical konceptima, aliasima i governance odlukama. Ovo je ključni sloj za Enterprise Architecture, MDM i buduće integracije, jer canonical model postaje kontrolisani poslovni asset, ne samo pomoćni lookup fajl.

Zašto postoji:

- `canonical_path` i concept reuse su srce Semantra vrednosti za enterprise integracije
- EA treba pregled poslovnih koncepata, sistema i integracija koje ih koriste
- MDM treba kontrolisan lifecycle aliasa, koncepta, duplikata i semantic gap-ova
- Canonical Gap Assistant generiše prirodan review queue, ali treba mu centralna konzola za dugoročno upravljanje

Scope summary:

- concept registry: searchable lista canonical concepts sa display name, entity, attribute, data type, aliases i statusom
- concept detail page/panel: aliases, source/target field contexts, linked integrations, mapping set usage i audit trail
- gap queue: predlozi iz mapping review-a, LLM-assisted suggestions, approve/reject/merge workflow
- overlay management: aktivni overlay, staged overlay entries, promotion candidate-i za stable glossary
- impact view: koje integracije i mapping setovi se menjaju ako se doda, spoji ili preimenuje concept/alias
- stewardship metadata: owner, domain, status, review note i created/approved timestamps

MVP nije:

- potpuni enterprise ontology editor
- automatsko spajanje canonical concepts bez review-a
- direktan write u base glossary bez promotion workflow-a

Prvi praktični slice:

- izdvojiti `Canonical Console` kao zaseban Streamlit tab ili Admin subsection
- prikazati concept registry iz runtime canonical glossary-ja
- prikazati active overlay entries po concept-u
- prikazati canonical gap suggestions kao read-only review queue mirror
- omogućiti approve/reject i audit iz iste konzole, uz postojeći overlay-first persist pristup

Trenutno isporučeno:

- `Canonical Console` kao zaseban top-level Streamlit tab, uz informativni fallback u `Admin / Debug`
- active overlay summary metrics i concept focus filter direktno u konzoli
- canonical glossary import/export i overlay lifecycle authoring UI premešteni iz `Admin / Debug` u konzolu
- concept registry search/filter, tabela i detail panel
- active overlay entries, field contexts, catalog usage i audit references po concept-u
- read-only mirror `Canonical Gap Suggestions` queue-a iz Review taba, uključujući suggestion status, concept proposal i reasoning/risk detalje
- approve akcija iz konzole za već generisane cached suggestion-e, uz refresh runtime/concept state-a
- session-scoped `ignore/restore` stanje u konzoli za gap queue, bez brisanja Review tab suggestion state-a
- persisted `reject` audit tok iz konzole preko `knowledge_audit_logs`, sa reviewer/note tragom
- persisted `ignore` audit tok iz konzole preko `knowledge_audit_logs`, uz direktan gap audit reference prikaz u queue detail-u

Trenutno isporučeno u prvom backend read slice-u:

- `GET /knowledge/canonical-concepts`
- `GET /knowledge/canonical-concepts/{concept_id}`
- payload spaja base canonical glossary, active overlay aliases, field contexts, catalog usage count i knowledge audit reference gde postoji aktivni overlay
- fokusirani backend smoke test potvrđuje registry/detail read bez promene runtime state-a

Trenutno isporučeno u početnom UI read slice-u:

- `Canonical Console` read-only subsection u `Admin / Debug` tabu
- concept registry tabela sa osnovnim search/filter ponašanjem
- concept detail panel za aliases, field contexts, active overlay entries, catalog usage i audit references
- fokusirani Streamlit helper testovi potvrđuju filter i registry row prikaz

### Epic 15: Graph Projection, Lineage and Reuse Analysis

Status: proposed on 2026-05-08.

Cilj: uvesti graph-shaped pogled nad postojećim Semantra artefaktima kako bi canonical putanje, lineage, reuse i impact analysis postali queryable i vizuelno pregledni, bez zamene postojećeg mapping engine-a i persistence sloja.

Napomena:

- graf je ovde sekundarni semantički i query sloj, ne primarna baza
- `Epic 14D` ostaje prioritetniji za kvalitet mapping odluka

#### Epic 15A: Graph domain model and projection layer

Status: proposed.

Cilj: definisati derived graph model nad postojećim artefaktima.

#### Epic 15B: Lineage and impact analysis

Status: proposed.

Cilj: omogućiti pitanje šta sve pogađa promena X i kako se artefakti propagiraju kroz mapping putanje.

#### Epic 15C: Reuse and catalog graph discovery

Status: proposed.

Cilj: pojačati reuse discovery u katalogu preko graph traversal pogleda.

#### Epic 15D: Visualization and graph runtime evaluation

Status: proposed.

Cilj: dati korisniku graph pregled i proceniti da li derived layer ostaje dovoljan ili treba poseban graph store.

## Working Rules For This Backlog

- `epics.md` drži backlog i scope, ne radne checkliste i ne hronologiju isporuke.
- `implementation_checklists.md` drži MVP korake, release gate-ove i fajl-level izvršne zadatke.
- `completed_slices.md` drži isporučene slice-ove i završene tehničke faze.
- `plan.md` drži redosled rada, tehničke faze i operativna pravila evolucije sistema.