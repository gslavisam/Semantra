# Semantra – Aktualni Workflow-i

Ovaj dokument opisuje workflow-e koje Semantra trenutno stvarno podrzava u pilot-ready stanju.

Namena dokumenta nije da prati stare faze razvoja, nego da prakticno opise kako se danas koristi proizvod kroz aktuelni UI i governance povrsine.

## Kako je proizvod organizovan danas

Aktuelne top-level oblasti u aplikaciji su:

- `Workspace`
- `Catalog`
- `Benchmarks`
- `System`
- `Governance`

Vazna napomena:

- `Canonical Console` je i dalje kljucna korisnicka povrsina, ali se danas nalazi unutar `Governance`, a nije zaseban top-level tab.
- `System` je operativno-administrativna povrsina koja odgovara ranijem `Admin / Debug` opisu.

## Workflow mapa

Najprirodniji nacin da se Semantra cita danas je kroz ove grupe tokova:

1. ingest i setup
2. mapping generation
3. review guidance i human decision loop
4. output, refinement i governed artifacts
5. governance, reuse i quality surfaces

## WF-01 – Standard Source-to-Target Setup i Mapping

**Svrha:**
Korisnik ima source i target strukturu i zeli objasnjiv source-to-target mapping koji moze da review-uje, ispravi, preview-uje i pretvori u artefakt.

**Ulaz:**

- source row data, schema spec ili SQL snapshot
- target row data, schema spec ili SQL snapshot
- opciono source companion metadata
- opciono target companion metadata u standardnom modu

**Glavni tok:**

1. U `Workspace > Setup` uploaduj source i target.
2. Po potrebi izaberi `Row data` ili `Schema spec` mod za svaki fajl.
3. Ako SQL fajl sadrzi vise tabela, izaberi konkretnu tabelu.
4. Klikni `Upload and profile`.
5. Po potrebi dodaj `Source Companion Metadata` i `Target Companion Metadata` da obogatis profile opisima, tipovima ili sample vrednostima.
6. Po potrebi ukljuci `Use LLM validation` ili `Prioritize source descriptions`.
7. Klikni `Generate mapping`.
8. Nastavi u `Review`, `Decisions` i `Output` workflow-e.

**Vazna pravila:**

- confidence je review heuristika, ne verovatnoca
- mapiranje moze da koristi bounded LLM validaciju, ali glavni tok ostaje analyst-controlled
- companion metadata obogacuje profil i trazenje kandidata, ali ne menja governance pravila za kasnije korake

Za detaljno objasnjenje signala, score formule, confidence pragova i bounded LLM validacije vidi `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

## WF-02 – Schema-Spec i SQL Snapshot Varijanta

**Svrha:**
Korisnik nema ciste poslovne redove, nego schema specifikaciju ili SQL DDL snapshot, ali i dalje zeli isti mapping/review loop.

**Ulaz:**

- field-per-row schema spec
- multi-table SQL DDL snapshot
- opciono companion metadata fajl za dodatna objasnjenja i declared tipove

**Glavni tok:**

1. U `Workspace > Setup` uploaduj source i target fajl ili samo source ako radis canonical-first.
2. Ako fajl lici na field specification, koristi `Schema spec`.
3. Ako je SQL snapshot, izaberi tabelu kada ih ima vise.
4. Klikni `Upload and profile`.
5. Po potrebi dodaj companion metadata da obogatis opis kolona koje DDL ili spec ne objasnjavaju dovoljno.
6. Nastavi na isti mapping i review tok kao kod standardnog rada.

**Vazna pravila:**

- `Schema spec` gradi `SchemaProfile` i bez row preview-a
- SQL snapshot je schema-only tok, ali i dalje ulazi u isti review model
- companion metadata je posebno korisna kada tehnicki nazivi kolona nisu dovoljni za kvalitetan ranking

## WF-03 – Canonical-First Mapping

**Svrha:**
Korisnik nema realan target ili prvo zeli semantic normalization kroz canonical layer pre bilo kakvog konkretnog target mapiranja.

**Ulaz:**

- source row data ili source spec
- aktivan canonical glossary runtime
- opciono source companion metadata

**Glavni tok:**

1. U `Workspace > Setup` predji na `Canonical` mod.
2. Uploaduj samo source strukturu.
3. Po potrebi podesi `Canonical candidate pool size`.
4. Klikni `Upload and profile`.
5. Po potrebi dodaj source companion metadata.
6. Klikni `Generate canonical mapping`.
7. U `Review` proveri source -> concept putanje, canonical coverage i eventualne semantic gap-ove.
8. U `Decisions` po potrebi uradi rucne izmene nad source-to-canonical odlukama.
9. Ako postoje semantic gap-ovi, nastavi prema `Governance > Canonical Console` workflow-u.

**Vazna pravila:**

- canonical flow ne trazi realan target dataset
- rezultat je source -> business concept mapping
- canonical mode namerno preskace preview jer ne postoje konkretni target redovi
- canonical mode i dalje podrzava code generation i artifact refinement nad aktivnim source-to-canonical odlukama

## WF-04 – Review Guidance i Trust Analysis

**Svrha:**
Korisnik razume zasto je mapping predlozen, gde su rizici i kojim redom treba da resava review queue.

**Glavni tok:**

1. U `Workspace > Review` proveri `Selected Mapping`, trust layer i canonical path.
2. Ako je potrebno, koristi manualni canonical override u detaljima reda; izabrani canonical koncept se zatim reflektuje u sažetku reda i canonical path tekstu.
3. Po potrebi koristi per-row ili batch `LLM refine` da proveris sporne redove unutar bounded candidate seta.
4. Generisi `Mapping Analysis Overview` za jedan tehnicki sazetak trenutnog mapping stanja.
5. Ako je review red velik ili sumovit, generisi `Review Queue Plan`.
6. Ako radis sa canonical gap kandidatima, generisi `Gap Queue Summary` pre candidate-by-candidate trijaze.
7. Po potrebi materializuj `LLM Decision Proposals` za trenutni `needs_review` slice.

**Vazna pravila:**

- ove guidance povrsine ne auto-approve-uju i ne auto-apply-uju durable promene
- `Mapping Analysis Overview` je globalni readout trenutnog mapping stanja
- `Review Queue Plan` je queue-level prioritetizacija, ne globalno objasnjenje mapping-a
- `Gap Queue Summary` radi isto to, ali samo za canonical gap queue
- `LLM Decision Proposals` ostaju advisory dok ih korisnik eksplicitno ne primeni u `Decisions`

## WF-05 – Decisions, Proposal Apply i Auditabilne Izmene

**Svrha:**
Korisnik zatvara review loop kroz eksplicitne odluke, rucne izmene i kontrolisanu primenu bounded AI predloga.

**Glavni tok:**

1. U `Workspace > Decisions` proveri aktivne odluke.
2. Po potrebi rucno promeni target ili status.
3. Ako postoje `LLM Decision Proposals`, koristi `Apply selected`, `Apply safe` ili dismiss tok.
4. Po potrebi export/import odluka radi checkpoint-a ili analyst handoff-a.
5. Nastavi ka `Output` kada je skup odluka dovoljno stabilan.

**Vazna pravila:**

- `Apply safe` je konzervativni batch mode, ne automatsko siroko prihvatanje AI predloga
- `Active Decisions` mogu da prikazu decision-origin metadata kao sto su `manual_mapping` i `llm_proposal`
- decision-origin audit metadata putuje i kroz JSON export/import tok

## WF-06 – Output, Preview, Codegen i Artifact Refinement

**Svrha:**
Korisnik pretvara review-ovane odluke u upotrebljiv preview, starter kod i refinement kandidata.

**Glavni tok:**

1. U `Workspace > Output` generisi advisory preview nad aktivnim odlukama kada radis standardni source-to-target tok.
2. Dodaj ili izmeni transformation code, ili koristi reusable template / bounded LLM generation gde je to primereno.
3. Kada su aktivne odluke accepted, pokreni `Generate Pandas code` ili `Generate PySpark code`.
4. Po potrebi pokreni `Refine with LLM` nad generisanim artefaktom.
5. Uporedi original i refined verziju, pa eksplicitno izaberi `Accept refined version` ili `Discard refinement`.
6. Po potrebi sacuvaj ili izvrsi transformation test set kada su odluke accepted.

**Vazna pravila:**

- preview ostaje advisory i moze da se koristi pre finalnog odobravanja
- samo aktivirane transformacije ulaze u preview i codegen
- standard-mode codegen je governance-sensitive surface i trazi accepted aktivne odluke
- transformation test sets su governed artefakti i takodje traze accepted aktivne odluke
- canonical mode preskace preview, ali i dalje podrzava codegen i artifact refinement

Za detaljan opis preview statusa, warning kodova, klasifikacija i fallback ponasanja vidi `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Za detaljan opis transformation test set strukture, assertion pravila i tumacenja run rezultata vidi `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

## WF-07 – Mapping-Set Save, Review, Approve i Apply

**Svrha:**
Tim zeli da rezultat review-a sacuva kao verzionisani, auditabilni i reusable artefakt.

**Glavni tok:**

1. U `Workspace > Decisions` sacuvaj mapping set verziju.
2. Unesi `integration_name`, owner, assignee i review note po potrebi.
3. Pomeri status kroz `draft`, `review`, `approved`, `archived`.
4. Pregledaj audit i diff kada poredis verzije.
5. Primeni approved verziju nazad u Workspace kada zelis controlled reuse.

**Vazna pravila:**

- apply/reuse radi samo za approved mapping setove
- audit i diff su deo istog governance modela, nisu odvojeni modul
- ovo je glavna durable granica izmedju session-level rada i governed artefakta

## WF-08 – Governance i Canonical Console Stewardship

**Svrha:**
Steward ili napredni BA upravlja canonical registry-jem, overlay lifecycle-om, gap review-om i promote-to-glossary tokovima.

**Glavni tok:**

1. Otvori `Governance`.
2. Udji u `Canonical Console`.
3. Pretrazi canonical concept registry i otvori concept detail.
4. Pregledaj aliase, usage kontekst, active overlay entry-je i audit reference.
5. Pregledaj canonical gap queue i stewardship item-e.
6. Ako je item spreman, odradi approve/reject/ignore ili `promote-to-glossary`.

**Vazna pravila:**

- ovo je governance povrsina, ne samo debug ekran
- promotion u stable glossary je eksplicitna akcija
- neke write akcije traze admin token
- Workspace `LLM Decision Proposals` nisu isto sto i canonical stewardship write putanje

Za detaljan opis canonical runtime-a, overlay lifecycle-a, stewardship stanja i promote-to-glossary pravila vidi `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

## WF-09 – Catalog Search, Reuse Fit i Reuse

**Svrha:**
Korisnik zeli da proveri da li slicna integracija vec postoji i koliko je dobra za reuse u trenutnom Workspace context-u.

**Glavni tok:**

1. Otvori `Catalog`.
2. Uradi browse ili search po sistemu, domenu, owner-u ili canonical konceptu.
3. Otvori integration detail i pregledaj verzije, latest approved i canonical footprint.
4. Po potrebi koristi `Workspace Reuse Shortlist` za activity-level shortlist prema trenutnom Workspace context-u.
5. Ako te zanima samo podskup source polja, koristi `Field Reuse Search` da pretrazis approved integracije po izabranim workspace poljima i pregledas field overlap pre reuse-a.
6. Po potrebi generisi `Workspace Reuse Fit` za izabranu version.
7. Klikni `Reuse in Workspace` kada zelis da nastavis od postojeceg approved artefakta.

**Vazna pravila:**

- Catalog radi nad sacuvanim artefaktima, ne nad live session state-om
- `Workspace Reuse Shortlist` rangira kandidate na nivou cele trenutne aktivnosti
- `Field Reuse Search` radi field-scoped discovery nad izabranim source poljima, ali ne apply-je nista automatski
- `Workspace Reuse Fit` je bounded explanation surface; ne apply-je nista sam
- reuse je nastavak istog review loop-a, ne paralelni workflow
- similarity je trenutno heuristicki, ne rucno kuriran reuse model

Za detaljan opis catalog search-a, similarity formule i `Reuse in Workspace` ponasanja vidi `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## WF-10 – Benchmarks, Quality Check i Correction Impact

**Svrha:**
Tim zeli da meri kvalitet mapping-a, poredi profile i prati efekat correction learning-a.

**Glavni tok:**

1. Otvori `Benchmarks`.
2. Sacuvaj trenutni mapping kao benchmark dataset kada su odluke accepted.
3. Pokreni benchmark run.
4. Po potrebi pokreni scoring-profile comparison ili correction-impact run.
5. Generisi `Benchmark Explanation` nad trenutno ucitanim benchmark evidence skupom.
6. Pregledaj run history.

**Vazna pravila:**

- benchmark save trazi accepted aktivne odluke
- benchmark surface sluzi za merenje kvaliteta i regresija, ne za osnovni daily review
- `Benchmark Explanation` je readout surface i ne menja runtime scoring state

Za detaljan opis benchmark metrika, confidence bucket tumacenja i correction-impact delta vidi `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

## WF-11 – Corrections i Reusable Learning

**Svrha:**
Sistem iz zatvorenih review odluka gradi trajnu povratnu memoriju i reusable rule signal za buduce run-ove.

**Glavni tok:**

1. Tokom review-a zatvori odluke nad spornim poljima.
2. Sacuvaj corrections kada je review outcome konacan.
3. Pregledaj correction history i reusable-rule candidate-e.
4. Promovisi stabilne obrasce u reusable rule kada imaju smisla.
5. Posmatraj uticaj tog signala u narednim mapping run-ovima i benchmark rezultatima.

**Vazna pravila:**

- durable corrections se cuvaju samo posle zatvorenog review-a
- reusable learning je governed, nije implicitno automatsko samoucenje
- legacy override istorija nije zamena za zatvoren review outcome

## WF-12 – System i Runtime Operacije

**Svrha:**
Tim proverava runtime stanje, config, observability i operativne signale sistema.

**Glavni tok:**

1. Otvori `System`.
2. Proveri runtime config i decision logs.
3. Pregledaj correction i reusable-rule stanje kada treba dijagnostika.
4. Po potrebi proveri knowledge/runtime status i druge operativne informacije.
5. Koristi ovu povrsinu za operativni pregled, ne za glavni analyst workflow.

**Vazna pravila:**

- `System` nije zamena za `Governance > Canonical Console`
- koristi se za operativni i observability sloj
- write governance akcije ostaju u zasebnim workflow-ima

## Preporuceni radni redosled

Za tipican standardni projekat najprakticniji redosled je:

1. `WF-01` ili `WF-02`
2. `WF-04`
3. `WF-05`
4. `WF-06`
5. `WF-07`
6. po potrebi `WF-09`, `WF-10`, `WF-11`, `WF-12`

Za canonical-first projekat najprakticniji redosled je:

1. `WF-03`
2. `WF-04`
3. `WF-05`
4. `WF-06`
5. po potrebi `WF-08`, `WF-10`, `WF-11`, `WF-12`

## Granice trenutnog proizvoda

Ovi workflow-i ne znace da Semantra danas vec jeste:

- produkcioni ETL runtime
- scheduler ili orkestrator
- connector-heavy integration platform
- graph-native metadata platform
- durable multi-user job runtime sa punom queue semantikom

Semantra je danas najjaca kao semantic mapping, review, governance i reuse workbench sa bounded AI guidance povrsinama.
