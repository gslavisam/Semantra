# Pomoć za Semantra UI

Ovaj dokument je praktični vodič za top-level tokove u Semantra Streamlit aplikaciji. Nije iscrpan popis svakog dugmeta, već vodič kako se aplikacija koristi u stvarnom radu.

## Glavna navigacija

Semantra trenutno ima pet glavnih area:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

Ako prvi put ulaziš u aplikaciju, kreni ovim redom:

1. `Workspace`
2. `Canonical Console` samo ako radiš canonical governance ili overlay rad
3. `Catalog` kada želiš reuse ili pregled postojećih integracija
4. `Benchmarks` kada želiš da sačuvaš ili pustiš merenje
5. `Admin / Debug` za runtime i observability pomoćne tokove

## Sidebar kontrole

### `API Base URL`

Koristi kada backend nije na podrazumevanoj lokalnoj adresi.

### `Admin Token`

Koristi za zaštićene governance, benchmark, catalog i knowledge tokove kada backend traži token.

### `Reset flow`

Briše aktivni Workspace session state i vraća UI u početno stanje. Koristi kada želiš novi scenario bez ostatka starog review state-a.

## Workspace

`Workspace` je glavni analystski tok i ima četiri pod-taba:

- `Setup`
- `Review`
- `Decisions`
- `Output`

### `Setup`

Ovde radiš:

- izbor moda `Standard` ili `Canonical`
- upload source i target fajlova kada radiš standardni mapping
- source-only upload kada radiš canonical-only mapping
- izbor `Row data` ili `Schema spec` kada fajl liči na field-per-row specifikaciju
- izbor tabela kada SQL snapshot sadrži više tabela
- opciono source companion metadata enrichment
- opciono target companion metadata enrichment kada radiš standard source + target tok
- podešavanje `Canonical candidate pool size` u canonical modu

Kada koristiš `Standard`:

- imaš realan source i realan target
- možeš dodati odvojene companion fajlove za source i target kada su row-data uploadi ili SQL DDL nema dovoljno opisa
- kasnije možeš da radiš preview i Pandas code generation

Kada koristiš `Canonical`:

- nemaš još realan target ili želiš prvo semantic normalization pass
- rezultat je source -> canonical concept mapping
- preview nije dostupan jer nema realnog target dataseta
- codegen je i dalje dostupan nad trenutnim source -> canonical odlukama

### `Review`

Ovde vidiš:

- trust-layer objašnjenja za izabrane predloge
- confidence i signal breakdown
- LLM napomene kada je validator korišćen
- per-row `LLM refine` unos za trenutno polje, uključujući meaning/negative/sample/refinement instruction kontekst
- batch low-confidence LLM refine za review red
- accept/revert tok za prihvatanje LLM refined row predloga
- canonical path pregled
- `Mapping Analysis Overview` za tehnički sažetak trenutnog mapping stanja
- opcioni audio narativ za generated mapping analysis
- `Review Queue Plan` za grupisanje review reda po prioritetima i obrascima
- `Source -> Concept View`
- `Concept -> Target View`
- canonical gap suggestion tok za slučajeve gde mapping izgleda dobar, ali canonical path nije popunjen
- `Gap Queue Summary` za queue-level pregled ponavljanih canonical gap familija

Ovo je mesto gde proveravaš da li sistemski predlog ima smisla pre nego što pređeš na persist ili output.

Važna razlika:

- `Mapping Analysis Overview` opisuje trenutno stanje mapping-a kao tehnički readout
- `Review Queue Plan` ne objašnjava mapping globalno, već predlaže kojim redom da rešavaš current review queue
- `Gap Queue Summary` radi isto to, ali samo za canonical gap candidate red

### `Decisions`

Ovde radiš:

- ručne izmene target izbora
- ručno mapiranje i u canonical modu, prema virtual canonical target opcijama
- import/export mapping odluka kao JSON ili Excel
- čuvanje mapping set verzija
- učitavanje i primenu prethodno sačuvanih mapping setova
- corrections tok i reusable learning tok

Važna pravila:

- mapping set reuse nazad u Workspace radi samo za `approved` mapping setove
- corrections se čuvaju samo kada je review ishod zatvoren, ne dok je odluka još nerešena

### `Output`

Ovde radiš:

- `Generate preview`
- `Generate Pandas code` ili `Generate PySpark code`
- `Refine with LLM` nad već generisanim artefaktom

Važna razlika:

- preview je advisory i možeš ga koristiti i pre finalnog odobravanja, da vidiš trenutno ponašanje mapping-a
- standard code generation je governance-sensitive surface i traži accepted aktivne odluke
- u canonical modu preview nije dostupan, ali code generation radi nad aktivnim source -> canonical odlukama

Ako koristiš refinement:

- originalni i refined artifact se prikazuju paralelno
- `Accept refined version` zamenjuje aktivni generated artifact refinement kandidatom
- `Discard refinement` odbacuje refinement i zadržava originalni artifact
- refinement ne menja ništa trajno dok ga eksplicitno ne prihvatiš

Ako koristiš transformacije:

- možeš uključiti suggested transformation
- možeš generisati transformation code preko LLM-a kada je runtime podešen
- možeš koristiti reusable template ili ručno uneti kod
- preview i codegen koriste samo transformacije koje su eksplicitno aktivirane

## Canonical Console

`Canonical Console` je centralno mesto za canonical governance.

Ovde možeš:

- pregledati canonical concept registry
- pretraživati koncepte po nazivu, aliasima, source system-u i business domain-u
- otvoriti concept detail sa aliasima, field context-ima, active overlay entry-jima, usage kontekstom i audit referencama
- pratiti active overlay summary i overlay lifecycle
- pregledati canonical gap queue mirror iz Workspace review toka
- raditi sa stewardship item-ima za `canonical_gap` i `overlay_promotion`
- promovisati overlay alias u stable glossary kada je item `ready_for_approval`

Važno:

- ovo više nije debug-only ekran, već glavna governance konzola za canonical sloj
- LLM može da predloži, ali persist i promotion i dalje zahtevaju eksplicitnu ljudsku akciju
- neke akcije su zaštićene admin tokenom

Za detaljan opis canonical runtime-a, overlay lifecycle-a, stewardship stanja i promote-to-glossary pravila pogledaj `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

## Catalog

`Catalog` služi za pregled i reuse već sačuvanih integracija i njihovih canonical footprint-ova.

Ovde možeš:

- listati i pretraživati integracije
- gledati `Discovery Overview` nad source-system -> target-system parovima
- otvarati integration detail
- gledati concept-centric detail iz kataloga
- učitati mapping set detail, audit i diff
- videti hint tipa `similar approved integration exists`
- pokrenuti `Workspace Reuse Fit` za izabranu catalog verziju
- reuse-ovati odobren mapping set nazad u Workspace

Važno:

- Catalog radi nad sačuvanim mapping set i catalog projekcijama, nije zamena za live review tok
- reuse nazad u Workspace je governance-gated i zavisi od statusa mapping seta
- `Workspace Reuse Fit` je bounded explanation layer; ne apply-je ništa automatski, već objašnjava da li je selected version dobar kandidat za trenutni Workspace context

Za detaljan opis catalog search-a, similarity heuristike i `Reuse in Workspace` ponašanja pogledaj `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## Benchmarks

`Benchmarks` služi za merljivo poređenje mapping kvaliteta.

Ovde možeš:

- sačuvati trenutni mapping kao benchmark dataset
- učitati ranije sačuvane benchmark datasetove
- pustiti benchmark run
- uporediti scoring profile
- izmeriti correction impact
- generisati `Benchmark Explanation` nad trenutno učitanim benchmark evidence skupom
- pregledati benchmark run history

Važno:

- `Save current mapping as benchmark` traži accepted aktivne odluke
- benchmark surface je namenjen proveri kvaliteta, ne svakodnevnom review-u svake sesije
- `Benchmark Explanation` ne menja score niti runtime config; samo objašnjava trenutno učitane benchmark rezultate i rizike

## Admin / Debug

`Admin / Debug` je pomoćna administrativna i observability površina.

Ovde tipično proveravaš:

- runtime config
- decision logs
- corrections i reusable rule stanje
- pomoćne knowledge/runtime informacije koje nisu deo glavnog Canonical Console toka

Koristi ovaj ekran kada ti treba operativni pregled sistema, a ne kada radiš glavni mapping ili canonical stewardship tok.

## Preporučeni tok rada

### Standard mapping tok

1. U `Workspace > Setup` uploaduj source i target.
2. Po potrebi izaberi tabele ili `Schema spec` mod i dodaj source/target companion fajlove.
3. Klikni `Upload and profile`.
4. Klikni `Generate mapping`.
5. U `Review` po potrebi generiši `Mapping Analysis Overview`, koristi per-row ili batch `LLM refine`, zatim proveri trust layer, canonical path i eventualne canonical gap predloge.
6. Ako review red deluje velik ili šumovit, koristi `Review Queue Plan` i po potrebi `Gap Queue Summary`.
6. U `Decisions` unesi ručne izmene, eksportuj checkpoint ili sačuvaj mapping set.
7. U `Output` koristi preview, pa zatim codegen kada su odluke accepted.
8. Ako generated artifact treba poliranje, koristi `Refine with LLM`, pa onda `Accept refined version` ili `Discard refinement`.

### Canonical-first tok

1. U `Workspace > Setup` pređi na `Canonical` mod.
2. Uploaduj source row-data ili source spec i po potrebi podesi `Canonical candidate pool size`.
3. Po potrebi dodaj source companion metadata, pa klikni `Upload and profile`, zatim `Generate canonical mapping`.
4. U `Review` proveri source -> canonical path i po potrebi koristi per-row `LLM refine`.
5. U `Decisions` možeš ručno mapirati na canonical opcije.
6. U `Output` možeš generisati kod i bez preview-a.
7. Ako postoje semantic gap-ovi, po potrebi ih prebaci u canonical governance tok kroz `Canonical Console`.

### Canonical governance tok

1. Otvori `Canonical Console`.
2. Učitaj ili osveži registry, overlay state i stewardship queue.
3. Otvori concept detail ili gap/promotion item koji te zanima.
4. Proveri status, audit i impact preview.
5. Odradi approve/reject/ignore ili promote-to-glossary kada je item spreman.

## Kratke napomene

- Confidence score je heuristika za review prioritet, ne verovatnoća.
- Score `>= 0.75` trenutno auto-prihvata mapping iako confidence label može ostati `medium_confidence`.
- Preview je namerno advisory; ne znači da je mapping finalno odobren.
- Durable i execution-like površine su strože governed od samog preview-a.
- Nove bounded AI sekcije u Review, Benchmarks i Catalog ne rade automatske write operacije; služe za objašnjenje, trijažu i pripremu ljudske odluke.
- Ako UI stanje deluje čudno posle više eksperimenata, `Reset flow` je često najbrži oporavak.

Za detaljan opis signala, score formule, confidence pragova i bounded LLM slučajeva pogledaj `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

Za detaljan opis preview statusa, warning kodova, klasifikacija i fallback ponašanja pogledaj `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Za detaljan opis benchmark metrika, confidence bucket tumačenja i correction-impact delta pogledaj `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

Za detaljan opis transformation test set strukture, assertion pravila i tumačenja run rezultata pogledaj `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

Za detaljan opis Catalog reuse i similarity heuristike pogledaj `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

Za detaljan opis Canonical Console runtime-a, overlay lifecycle-a i stewardship pravila pogledaj `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.
