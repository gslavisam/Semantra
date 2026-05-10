# Semantra – Aktualni Workflow-i

Ovaj dokument opisuje aktuelne workflow-e koje Semantra danas stvarno podržava.

Namena ovog dokumenta nije da prati stare razvojne faze ili aspiracione epike, nego da praktično pokaže kako se proizvod koristi u trenutnom stanju.

## Pregled proizvoda

Glavne top-level površine su:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

## WF-01 – Standard Source-to-Target Mapping

**Svrha:**
Korisnik ima source i target strukturu i želi objašnjiv predlog mapiranja, review, preview i code generation.

**Ulaz:**

- source row data, schema spec ili SQL snapshot
- target row data, schema spec ili SQL snapshot

**Glavni tok:**

1. U `Workspace > Setup` uploaduj source i target.
2. Po potrebi izaberi `Row data` ili `Schema spec`.
3. Ako SQL fajl sadrži više tabela, izaberi konkretnu tabelu.
4. Klikni `Upload and profile`.
5. Klikni `Generate mapping`.
6. U `Review` proveri trust layer i canonical putanje.
7. U `Decisions` potvrdi, odbij ili ručno promeni odluke.
8. U `Output` koristi preview, pa codegen kada su odluke accepted.

**Važna pravila:**

- confidence je review heuristika, ne verovatnoća
- preview je advisory
- code generation traži accepted aktivne odluke

Za detaljno objašnjenje signala, score formule, confidence pragova i LLM slučajeva vidi `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

## WF-02 – Schema-Spec i SQL Snapshot Workflow

**Svrha:**
Korisnik nema čiste poslovne redove nego specifikaciju šeme ili SQL snapshot.

**Ulaz:**

- field-per-row schema spec
- multi-table SQL DDL snapshot

**Glavni tok:**

1. U `Setup` uploaduj fajl.
2. Ako fajl liči na specifikaciju, izaberi `Schema spec`.
3. Ako je SQL snapshot, izaberi tabelu kada ih ima više.
4. Nastavi na isti mapping tok kao i kod standardnog rada.

**Važna pravila:**

- `Schema spec` gradi `SchemaProfile` i bez row preview-a
- SQL snapshot je schema-only tok, ali i dalje ulazi u isti review model

## WF-03 – Canonical-First Mapping

**Svrha:**
Korisnik nema realan target ili prvo želi semantic normalization kroz canonical layer.

**Ulaz:**

- source row data ili source spec
- aktivan canonical glossary runtime

**Glavni tok:**

1. U `Workspace > Setup` pređi na `Canonical` mod.
2. Uploaduj samo source strukturu.
3. Klikni `Upload and profile`.
4. Klikni `Generate canonical mapping`.
5. U `Review` proveri source -> concept i concept coverage.
6. Ako postoje semantic gap-ovi, nastavi prema `Canonical Console` workflow-u.

**Važna pravila:**

- canonical flow ne traži realan target dataset
- rezultat je source -> business concept mapping
- preview i codegen nisu glavna svrha ovog moda

## WF-04 – Review, Decisions, Preview i Codegen

**Svrha:**
Korisnik proverava kvalitet predloga i pretvara review u upotrebljiv artefakt.

**Glavni tok:**

1. U `Review` proveri selected mappings, signal breakdown i canonical path.
2. Po potrebi ručno promeni target ili status.
3. Dodaj ili izmeni transformation code.
4. U `Output` pokreni `Generate preview`.
5. Kada su odluke accepted, pokreni `Generate Pandas code`.

**Važna pravila:**

- preview ostaje advisory čak i pre finalnog odobravanja
- codegen je governance-sensitive surface
- samo aktivirane transformacije ulaze u preview i codegen

Za detaljan opis preview statusa, klasifikacija, warning kodova i fallback ponašanja vidi `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Za detaljan opis transformation test set strukture, assertion pravila i tumačenja run rezultata vidi `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

## WF-05 – Mapping-Set Save, Review, Approve, Apply

**Svrha:**
Tim želi da review rezultat sačuva kao verzionisani, auditabilni artefakt.

**Glavni tok:**

1. U `Workspace > Decisions` sačuvaj mapping set verziju.
2. Unesi `integration_name`, owner, assignee i review note po potrebi.
3. Pomeri status kroz `draft`, `review`, `approved`, `archived`.
4. Učitaj audit i diff kada porediš verzije.
5. Primeni approved verziju nazad u Workspace kada želiš reuse.

**Važna pravila:**

- apply/reuse radi samo za approved mapping setove
- audit i diff su deo istog governance modela, nisu odvojeni modul

## WF-06 – Canonical Console Stewardship

**Svrha:**
Steward ili napredni BA upravlja canonical registry-jem, gap-ovima i overlay promotion tokovima.

**Glavni tok:**

1. Otvori `Canonical Console`.
2. Pretraži canonical concept registry.
3. Otvori concept detail sa aliasima, usage kontekstom i active overlay entry-jima.
4. Pregledaj canonical gap queue i stewardship item-e.
5. Ako je item spreman, odradi approve/reject/ignore ili promote-to-glossary.

**Važna pravila:**

- ovo je governance površina, ne samo debug ekran
- promotion u stable glossary je eksplicitna akcija
- neke akcije traže admin token

Za detaljan opis canonical runtime-a, overlay lifecycle-a, stewardship stanja i promote-to-glossary pravila vidi `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

## WF-07 – Catalog Search i Reuse

**Svrha:**
Korisnik želi da vidi da li slična integracija već postoji i da li može da je reuse-uje.

**Glavni tok:**

1. Otvori `Catalog`.
2. Uradi browse ili search po sistemu, domenu, owner-u ili canonical konceptu.
3. Otvori integration detail.
4. Pogledaj verzije, latest approved, canonical footprint i slične integracije.
5. Klikni `Reuse in Workspace` kada želiš da nastaviš od postojećeg artefakta.

**Važna pravila:**

- Catalog radi nad sačuvanim artefaktima, ne nad live session state-om
- reuse je nastavak istog review loop-a, ne paralelni workflow
- trenutno je similarity heuristički, ne ručno kuriran reuse model

Za detaljan opis catalog search-a, similarity formule i `Reuse in Workspace` ponašanja vidi `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## WF-08 – Benchmark i Quality Check

**Svrha:**
Tim želi da meri kvalitet mapping-a i efekat correction learning-a.

**Glavni tok:**

1. Otvori `Benchmarks`.
2. Sačuvaj trenutni mapping kao benchmark dataset kada su odluke accepted.
3. Pokreni benchmark run.
4. Po potrebi pokreni correction-impact run.
5. Pregledaj run history.

**Važna pravila:**

- benchmark save traži accepted aktivne odluke
- benchmark surface služi za merenje kvaliteta i regresija, ne za osnovni daily review

Za detaljan opis benchmark metrika, confidence bucket tumačenja i correction-impact delta vidi `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

## WF-09 – Corrections i Reusable Learning

**Svrha:**
Sistem iz review odluka gradi trajnu povratnu memoriju.

**Glavni tok:**

1. Tokom review-a zatvori odluke nad spornim poljima.
2. Sačuvaj corrections kada je review outcome konačan.
3. Pregledaj correction history i reusable-rule candidate-e.
4. Promoviši stabilne obrasce u reusable rule kada imaju smisla.
5. Posmatraj uticaj tog signala u narednim mapping run-ovima i benchmark rezultatima.

**Važna pravila:**

- durable corrections se čuvaju samo posle zatvorenog review-a
- reusable learning je governed, nije implicitno automatsko samoučenje

## WF-10 – Admin i Runtime Operacije

**Svrha:**
Tim proverava runtime stanje, config i operativne signale sistema.

**Glavni tok:**

1. Otvori `Admin / Debug`.
2. Proveri runtime config i decision logs.
3. Pregledaj correction i reusable-rule stanje kada treba dijagnostika.
4. Koristi ovu površinu za operativni pregled, ne za glavni analyst workflow.

**Važna pravila:**

- `Admin / Debug` nije zamena za `Canonical Console`
- koristi se za operativni i observability sloj

## Preporučeni Radni Redosled

Za tipičan projekat najpraktičniji redosled je:

1. `WF-01` ili `WF-02`
2. po potrebi `WF-03`
3. `WF-04`
4. `WF-05`
5. `WF-07`
6. po potrebi `WF-06`, `WF-08`, `WF-09`, `WF-10`

## Granice Trenutnog Proizvoda

Ovi workflow-i ne znače da Semantra danas već jeste:

- produkcioni ETL runtime
- scheduler ili orkestrator
- connector-heavy integration platform
- graph-native metadata platform

Semantra je danas najjači kao semantic mapping, review, governance i reuse workbench.
