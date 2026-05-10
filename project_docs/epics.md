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

# Semantra Epics

Ovaj dokument je backlog mapa. Ne služi kao detaljan changelog niti kao opis današnjeg stanja po svim feature-ima.

Koristi zajedno sa:

- `current_state.md` za ono što proizvod danas stvarno podržava
- `completed_slices.md` za istoriju isporuke
- `implementation_checklists.md` za aktivne izvršne korake
- `plan.md` za prioritetni redosled rada

## Implementirana ili pilot-complete baza

Ove epike više nisu glavni backlog fokus, ali ostaju važne za razumevanje osnove proizvoda.

- `Epic 1: Knowledge Overlay MVP`
	- status: implemented MVP
	- runtime overlay lifecycle, validation preview, versioning i audit postoje; veći sledeći korak je DB-only source-of-truth model
- `Epic 2: Admin Upload UI`
	- status: implemented MVP
	- knowledge/canonical authoring i overlay lifecycle su dostupni kroz Canonical Console i Admin surface
- `Epic 3: Learning From Corrections`
	- status: implemented MVP with governance hardening
	- correction history, reusable rules i correction-aware ranking postoje; dalji rad je više quality tuning nego osnovna implementacija
- `Epic 4: Transformation Safety and Testing`
	- status: implemented MVP
	- preview warnings, codegen fallback, templates i transformation test sets postoje; dublji execution safety ostaje future hardening
- `Epic 5: Canonical Semantic Layer`
	- status: implemented MVP
	- canonical concepts, canonical-only mapping i canonical coverage su baza proizvoda
- `Epic 6: Governance and Versioning`
	- status: MVP completed
	- mapping-set governance i veći deo product-level enforcement discipline su uvedeni
- `Epic 7: Explainability and Trust Layer Expansion`
	- status: partially implemented
	- trust layer već postoji, ali dublji why-not/simulator i strukturisani competitor UX ostaju otvoreni
- `Epic 8: Benchmark and Quality Analytics`
	- status: implemented MVP, advanced analytics open
	- benchmark datasets, runs i correction impact postoje; dashboards i dublji KPI sloj su otvoreni
- `Epic 11: Schema Specification Upload`
	- status: completed
- `Epic 12A: Canonical-only mapping`
	- status: completed

## Aktivni epici

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
- `13C` Streamlit catalog UI je isporučen
- `13D` concept and visual discovery ostaje otvoren i predstavlja sledeći visoko-vredni product korak

### Epic 13D: Concept and visual discovery

Status: active next-step epic.

Cilj:

- reuse signal iznad postojećeg kataloga i canonical usage modela
- concept-centric pregled kroz više integracija
- vizuelni discovery sloj za reuse, coverage i slične integracije

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

#### Epic 14E: Canonical Gap Assistant

Status: implemented MVP.

Trenutno stanje:

- candidate extraction, suggestion, approve/reject/ignore i rerun loop postoje
- human-approved overlay-first canonical gap zatvaranje je implementirano

Otvoreno:

- dodatni candidate enrichment i širi non-happy-path coverage

#### Epic 14F: Canonical Concept Management Console

Status: pilot-complete core workflow.

Trenutno stanje:

- top-level Canonical Console, registry/detail/read/write stewardship, overlay promotion i stable glossary execution postoje
- happy-path governance loop je zatvoren za pilot

Otvoreno:

- stabilizacija, bulk-safe UX i dodatna non-happy-path productization pokrivenost

## Planirani i odloženi epici

### Epic 9: Data Quality Intelligence

Status: planned.

Cilj:

- kvalitet i kompatibilnost podataka kao dodatni review signal, ne samo naziv/knowledge matching

### Epic 10: Operationalization

Status: partially implemented foundation, broader scope open.

Već postoji:

- preview
- Pandas codegen
- transformation generation
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

Trenutno isporučeno u početnom UI read slice-u:

- `Canonical Console` read-only subsection u `Admin / Debug` tabu
- concept registry tabela sa osnovnim search/filter ponašanjem
- concept detail panel za aliases, field contexts, active overlay entries, catalog usage i audit references
- fokusirani Streamlit helper testovi potvrđuju filter i registry row prikaz

Otvoreno posle ovog slice-a:

- dalje 14F poliranje može da proširi bulk/safer promotion execution workflow kada se potvrdi governance model
- sledeći viši nivo je concept-centric overlay stewardship poliranje preko više povezanih overlay verzija i eventualni batch execution UX

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