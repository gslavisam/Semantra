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

### Epic 11B: Bounded upload recovery and structure understanding

Status: first `schema-spec` recovery slice completed, broader expansion open.

Cilj:

- oporaviti ingest za fajlove koji su bliski propisanom upload obrascu, ali ne prolaze današnji deterministički parser bez ručnih hint-ova
- zadržati Semantra princip da je `LLM` bounded recovery pomoćnik, a ne autoritativni upload parser

Trenutno stanje:

- row-data upload, `SQL` snapshot upload i `schema-spec` upload već postoje kroz determinističke parserе
- `schema-spec` već ima heurističku detekciju kolona i ručne override parametre
- `POST /upload/spec/recover` sada vraća bounded recovery predlog za parseable metadata fajlove koji ne prolaze užu layout detekciju
- recovery i dalje prolazi kroz postojeći deterministički `schema-spec` replay pre nego što upload uspe
- `Workspace > Setup` i companion metadata tokovi sada eksplicitno surfacuju recovery predlog, confidence, warnings i ručni override
- bounded alias fallback pokriva uske `schema-spec` header slučajeve kada live `LLM` provider vrati neupotrebljiv odgovor, bez fail-open persistence ponašanja

Otvoreno:

- row-data header recovery izvan uskog `schema-spec` scope-a
- multi-sheet i `record_path` recovery za složenije tabularne izvore
- `SQL` recovery heuristika tek ako stvarni pilot tokovi pokažu potrebu
- eventualni bounded recovery za malformed ili shape-invalid `JSON` / `XML` payloads tek ako realni pilot tokovi pokažu da strict reject više nije dovoljan
- širi recovery telemetry/eval sloj ako bounded upload recovery postane češći pilot pattern

Van scope-a prvog slice-a:

- `PDF`, slike, OCR i proizvoljni nestrukturisani dokumenti
- auto-persist bez korisničke potvrde ili bez replay-validacije
- istovremeno širenje na row-data header recovery i `SQL` recovery heuristiku pre zatvaranja `spec` slice-a

### Epic 5B: Knowledge expansion and canonical coverage

Status: active planning.

Cilj:

- sistematski proširiti vendor/system knowledge coverage i disciplinovano izvući nove canonical gap-ove i canonical promotion kandidate iz SAP-first wave-a

Trenutno stanje:

- `metadata_dict.csv`, workbook contexti i canonical glossary već daju korisne SAP, QAD i Workday signale
- poslednji supplier SAP showcase je pokazao da knowledge coverage direktno podiže mapping quality i da i dalje postoje pravi vendor-specific gap-ovi
- runtime separation, Canonical Console i stewardship tokovi sada daju dovoljno stabilnu osnovu za veći curated refresh wave

Otvoreno:

- staging/provenance pipeline za vendor specifikacije
- SAP-first field/object/context ingest preko 10k+ polja
- canonical gap mining i promotion disciplina iznad proširenog knowledge sloja
- benchmark/eval harness po sistemu i modulu
- proširenje istog modela na Workday, QAD, QuickBooks i druge javno dostupne ERP izvore

### Epic 12B: System-specific virtual targets

Status: planned.

Cilj:

- dodati virtual target sheme za konkretne sisteme kada canonical coverage i metadata kvalitet to opravdaju

Napomena:

- ne gurati ovo pre reuse discovery i operational hardening talasa
- ne širiti ga agresivno pre nego što `Epic 5B` podigne vendor knowledge coverage i canonical gap disciplinu

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

### Epic 16: Transformation Design and Structured Transformation Spec

Status: active planning.

Cilj:

- uvesti jasan produktni sloj za kompleksnu poslovnu transformaciju između source i target strukture, umesto da se takva logika rasipa između ručnih transformacija, output helper-a i prompt-driven generation tokova

Trenutno stanje:

- `Workspace > Decisions` i `Workspace > Output` već pokrivaju mapping odluke, ručne transformacije, transformation generation, preview, starter codegen i artifact refinement
- Semantra već ima korisne output surface-e, ali nema jedan eksplicitan, business-readable `Transformation Design` contract koji opisuje `šta se dešava sa svakim target poljem` i `koja globalna pravila važe za ceo tok`
- složenije transformacije trenutno zahtevaju da korisnik mentalno spaja mapping odluke, transformation code, warning readout i refinement korake bez jedne centralne specifikacije

Otvoreno:

- gde prvi slice živi: kao nova sekcija u `Workspace > Output` ili kao poseban korak između `Decisions` i `Output`
- kako izgleda minimalni `TransformationSpec` contract (`target_grain`, `target_fields`, `field_rules`, `global_rules`, `defaults`, `validation_rules`, `examples`)
- kako bounded `LLM` može da pretvori prirodni jezik u strukturisani predlog bez uvođenja prompt-to-code anti-patterna
- kako `preview`, `Pandas` / `PySpark` / `dbt` generation i refinement prelaze da rade nad potvrđenim spec-om kada on postoji
- kako transformation spec postaje versioned i restore-friendly kroz `draft session`, `mapping set` ili poseban output draft model

Prvi slice treba eksplicitno da zadrži ove granice:

- ne uvoditi slobodan generički chat za transformacije
- ne uvoditi puni orchestration engine, DAG editor ili job scheduler
- ne raditi auto-apply iz `LLM` predloga u transformation spec ili generated artifact
- ne širiti prvi slice istovremeno na full persistence redesign i novi output runtime

Veza sa postojećim epicima:

- ovo nadograđuje `Epic 4: Transformation Safety and Testing`, ne zamenjuje ga
- ovo koristi postojeće output/generation surface-e iz `Epic 10`, ali im dodaje strukturisani design sloj ispred generation koraka

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