# Semantra Epics

Ovaj dokument je backlog mapa. Ne služi kao detaljan changelog niti kao opis današnjeg stanja po svim feature-ima.

Koristi zajedno sa:

- `current_state.md` za ono što proizvod danas stvarno podržava
- `completed_slices.md` za istoriju isporuke
- `implementation_checklists.md` za aktivne izvršne korake
- `plan.md` za prioritetni redosled rada

## Implementirana ili pilot-complete baza

Ove epike više nisu glavni backlog fokus, ali ostaju važne za razumevanje osnove proizvoda.

### Epic 1: Knowledge Overlay MVP

Status: implemented MVP.

Trenutno stanje:

- runtime overlay lifecycle, validation preview, versioning i audit postoje
- veći sledeći korak je DB-only source-of-truth model

### Epic 2: Admin Upload UI

Status: implemented MVP.

Trenutno stanje:

- knowledge/canonical authoring i overlay lifecycle su dostupni kroz Canonical Console i Admin surface

### Epic 3: Learning From Corrections

Status: implemented MVP with governance hardening.

Trenutno stanje:

- correction history, reusable rules i correction-aware ranking postoje
- dalji rad je više quality tuning nego osnovna implementacija

### Epic 4: Transformation Safety and Testing

Status: implemented MVP.

Trenutno stanje:

- preview warnings, codegen fallback, templates i transformation test sets postoje
- dublji execution safety ostaje future hardening

### Epic 5: Canonical Semantic Layer

Status: implemented MVP.

Trenutno stanje:

- canonical concepts, canonical-only mapping i canonical coverage su baza proizvoda

### Epic 6: Governance and Versioning

Status: MVP completed.

Trenutno stanje:

- mapping-set governance i veći deo product-level enforcement discipline su uvedeni

### Epic 8: Benchmark and Quality Analytics

Status: implemented MVP, advanced analytics open.

Trenutno stanje:

- benchmark datasets, runs, profile comparison i correction impact postoje
- dublji dashboard/KPI sloj ostaje otvoren

### Epic 11: Schema Specification Upload

Status: completed.

### Epic 12A: Canonical-only mapping

Status: completed.

### Epic 14E: Canonical Gap Assistant

Status: implemented MVP.

Trenutno stanje:

- candidate extraction, suggestion, approve/reject/ignore i rerun loop postoje
- queue-level summary je dodat kao bounded guidance sloj

### Epic 14F: Canonical Concept Management Console

Status: pilot-complete core workflow.

Trenutno stanje:

- top-level Canonical Console, registry/detail/read/write stewardship, overlay promotion i stable glossary execution postoje
- happy-path governance loop je zatvoren za pilot

Otvoreno:

- stabilizacija, bulk-safe UX i dodatna non-happy-path productization pokrivenost

## Aktivni epici

### Epic 7: Explainability and Guided Copilots

Status: active, partial implementation delivered.

Cilj:

- proširiti objašnjivost proizvoda iz trust layer-a u strogo kontrolisane review, benchmark, output i reuse guidance površine

Trenutno stanje:

- trust layer već postoji u `Workspace > Review`
- `Mapping Analysis Overview` i audio naracija postoje
- `Review Queue Plan` postoji za queue-level review guidance
- `Benchmark Explanation` postoji u Benchmarks toku
- `Gap Queue Summary` postoji za canonical gap red
- `Workspace Reuse Fit` postoji u Catalog toku
- output artifact refinement postoji u Workspace Output toku

Otvoreno:

- konzistentniji naming i user journey između ovih površina
- jasnije surfacing razlike između explanation, triage i refinement tokova
- širi pilot feedback o tome koji od ovih guidance panela stvarno menjaju odluke korisnika

### Epic 12B: System-specific virtual targets

Status: planned.

Cilj:

- dodati virtual target sheme za konkretne sisteme kada canonical coverage i metadata kvalitet to opravdaju

Napomena:

- ne gurati ovo pre reuse discovery i operational hardening talasa

### Epic 13: Enterprise Integration Catalog

Status: active.

Trenutno stanje:

- `13A` persistence/backend indexing je isporučen
- `13B` read API je isporučen
- `13C` Streamlit Catalog UI je isporučen
- `13D` initial concept/reuse discovery slice je isporučen
- reuse-fit explanation slice je dodat kao bounded catalog guidance sloj

### Epic 13D: Concept and visual discovery

Status: initial slice completed, broader expansion open.

Cilj:

- reuse signal iznad postojećeg kataloga i canonical usage modela
- concept-centric pregled kroz više integracija
- vizuelni discovery sloj za reuse, coverage i slične integracije

Trenutno stanje:

- concept-centric reuse pregled postoji u Catalog concept lookup toku
- source-system -> target-system discovery overview postoji nad catalog rezultatima
- basic `similar approved integration exists` hint postoji u catalog result view-u
- grouped unmatched/low-confidence review attention summary postoji u Workspace review toku

Otvoreno:

- bogatiji compare i drilldown između sličnih integracija
- jače povezivanje catalog discovery signala sa review i canonical governance tokovima

### Epic 14: Performance, vector/cache acceleration, and richer AI signal fusion

Status: partially active.

Napomena:

- embedding i LLM signali postoje u engine-u, ali bez punog cache/precompute sloja i bez šireg signal fusion modela

#### Epic 14A: Target vector cache

Status: started, not productized.

Cilj:

- keširan embedding/vector sloj za target stranu radi ubrzanja similarity rada

#### Epic 14B: Stable signal precomputation

Status: planned.

Cilj:

- izdvojiti stabilne i skupe signalne delove iz request-time toka

#### Epic 14C: LLM-assisted signal fusion

Status: proposed.

Cilj:

- proširiti LLM iz closed-set validatora u strogo kontrolisan reasoning/fusion sloj bez gubitka explainability discipline

#### Epic 14D: Description-aware context and companion schema ingestion

Status: implemented MVP, follow-up open.

Trenutno stanje:

- source companion enrichment i description-aware LLM context su isporučeni
- deterministic score fusion ostaje otvoren samo ako benchmark pokaže jasan dobitak bez regressions

## Planirani i odloženi epici

### Epic 9: Data Quality Intelligence

Status: planned.

Cilj:

- kvalitet i kompatibilnost podataka kao dodatni review signal, ne samo naziv/knowledge matching

### Epic 10: Operationalization

Status: partially implemented foundation, broader scope open.

Već postoji:

- preview
- Pandas/PySpark starter codegen
- transformation generation i refinement
- transformation test sets
- benchmark run history

Otvoreno ostaje:

- release artifacts
- batch/runtime execution model
- trigger/schedule sloj
- persistent background execution infrastruktura

### Epic 15: Graph Projection, Lineage, and Reuse Analysis

Status: proposed.

Cilj:

- derived graph pogled nad canonical, catalog i usage podacima

Pravilo:

- ne otvarati ozbiljno pre stabilizacije canonical, catalog i discovery read modela

## Pravila za ovaj backlog

- `epics.md` drži backlog mapu i status po epicima, ne detaljnu hronologiju.
- Kada epic dobije veliki isporučeni slice, istorijski detalji idu u `completed_slices.md`.
- Kada epic ima aktivan izvršni rad, konkretni checkbox koraci žive u `implementation_checklists.md`.