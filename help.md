# Pomoć za Semantra UI

Ovaj dokument je praktični vodič za top-level tokove u Semantra Streamlit aplikaciji. Nije iscrpan popis svakog dugmeta, već vodič kako se aplikacija koristi u stvarnom radu.

## Glavna navigacija

Semantra trenutno ima pet glavnih area:

- `Workspace`
- `Catalog`
- `Benchmarks`
- `System`
- `Governance`

Brza terminološka napomena:

- `Canonical Console` je i dalje ključna governance površina, ali danas živi unutar `Governance`, a nije zaseban top-level tab
- `System` je operativni naslednik ranijeg `Admin / Debug` opisa

Ako prvi put ulaziš u aplikaciju, kreni ovim redom:

1. `Workspace`
2. `Governance` (tu je `Canonical Console`) samo ako radiš canonical governance ili overlay rad
3. `Catalog` kada želiš reuse ili pregled postojećih integracija
4. `Benchmarks` kada želiš da sačuvaš ili pustiš merenje
5. `System` za runtime i observability pomoćne tokove

## Sidebar kontrole

Levi sidebar je sada multi-view support surface kojim upravlja `Sidebar view`.

Dostupni sidebar prikazi:

- `System` za connection settings, runtime status, KPI metrike i status legendu
- `WS Copilot` za read-only Workspace context plus bounded pitanje/odgovor i conversation history
- `WS Brief` za kratak `Now / Risks / Next actions` prikaz trenutnog Workspace stanja
- `Help` za ovaj in-app English reference guide
- `Reference` za dublje tehničke reference učitane iz `docs/reference` plus izabranih presentation dokumenata

### `System`

`System` je operativni sidebar view. U njemu su:

- `API Base URL`
- `Admin Token`
- `Runtime`
- `Operations`
- `Unified Status Legend`
- `Reset flow`

### `API Base URL`

Koristi kada backend nije na podrazumevanoj lokalnoj adresi.

### `Admin Token`

Koristi za zaštićene governance, benchmark, catalog i knowledge tokove kada backend traži token.

### `WS Copilot`

Koristi ovaj sidebar mod kada želiš bounded pomoć za:

- to šta radi koja Semantra area ili Workspace sekcija
- to šta trenutno blokira napredak u Workspace-u
- to koji je sledeći preporučeni korak
- trenutno mapping stanje, kada mapping rezultat već postoji

Ovo je guidance surface, ne freeform autonomous agent. Odgovori su ograničeni na app/workflow guidance i aktivni Workspace context.

### `WS Brief`

Koristi ovaj mod kada želiš najkraći operativni readout trenutne Workspace sesije:

- `Now`
- `Risks`
- `Next actions`

### `Help`

Ovaj sidebar mod prikazuje aktuelni English help vodič direktno u aplikaciji, tako da dokumentacija ostane dostupna dok radiš.

### `Reference`

Ovaj sidebar mod ti omogućava da iz padajućeg menija izabereš dostupan dokument iz `docs/reference` i pročitaš ga direktno u aplikaciji. Uključuje i izabrane presentation-side reference dokumente kao što je `docs/presentation/Conceptualization.md`. Koristi ga za dublje tehničke reference kao što su scoring, preview/codegen warning ponašanje, benchmark metrike, canonical stewardship, catalog reuse, workflows i product framing.

### `Reset flow`

Ova akcija je dostupna samo u `System` sidebar view-u. Briše aktivni Workspace session state i vraća UI u početno stanje. Resetuje tranzijentne Workspace podatke kao što su uploadi, mapping rezultati, analize, generisani artefakti i sidebar copilot chat history. Ne briše backend podatke i ne menja konekciju.

## Workspace

`Workspace` je glavni analystski tok i ima četiri pod-taba:

- `Setup`
- `Review`
- `Decisions`
- `Output`

### `Setup`

Ovde radiš:

- izbor moda `Standard` ili `Canonical`
- izbor `Canonical target intent` u canonical modu kada želiš canonical-only ponašanje ili target-aware projection hint
- upload source i target fajlova kada radiš standardni mapping
- source-only upload kada radiš canonical-only mapping
- izbor `Row data` ili `Schema spec` kada fajl liči na field-per-row specifikaciju
- izbor tabela kada SQL snapshot sadrži više tabela
- opciono source companion metadata enrichment
- opciono target companion metadata enrichment kada radiš standard source + target tok
- uključivanje `Use LLM validation` kada želiš bounded validaciju u ambiguity band-u
- uključivanje `Prioritize source descriptions` kada source description/type metadata treba da ima veći heuristički uticaj
- podešavanje `Canonical candidate pool size` u canonical modu

Kada koristiš `Standard`:

- imaš realan source i realan target
- možeš dodati odvojene companion fajlove za source i target kada su row-data uploadi ili SQL DDL nema dovoljno opisa
- kasnije možeš da radiš preview, Pandas/PySpark/dbt generation i artifact refinement

Kada koristiš `Canonical`:

- nemaš još realan target ili želiš prvo semantic normalization pass
- rezultat je source -> canonical concept mapping
- i dalje možeš birati target intent tako da canonical-first mapping ostane canonical-only ili dobije system-aware projection hint
- preview nije dostupan jer nema realnog target dataseta
- codegen i artifact refinement su i dalje dostupni nad trenutnim source -> canonical odlukama, uključujući Pandas, PySpark i dbt-style outpute

### `Review`

Ovde vidiš:

- glavni `Workspace Copilot` panel sa sekcijskim pitanjima kao što su `Summarize current mapping state` i `Summarize Review -> Decisions risks`
- trust-layer objašnjenja za izabrane predloge
- confidence i signal breakdown
- repeated-attention grupisanje za šumovite ili ponavljane review paterne
- LLM napomene kada je validator korišćen
- per-row `LLM refine` unos za trenutno polje, uključujući meaning/negative/sample/refinement instruction kontekst
- batch low-confidence LLM refine za review red
- accept/revert tok za prihvatanje LLM refined row predloga
- `LLM Decision Proposals` panel za `needs_review` redove
	- može da materijalizuje predloge iz postojećeg LLM traga
	- opciono može da uradi live bounded LLM fill za redove bez cached proposition-a
	- ne menja odluke dok ne odeš na apply u `Decisions`
- canonical path pregled
- `Mapping Analysis Overview` za tehnički sažetak trenutnog mapping stanja
- opcioni audio narativ za generated mapping analysis
- `Review Queue Plan` za grupisanje review reda po prioritetima i obrascima
- `Selected Mapping Details`, uključujući canonical mismatch detalje, source-side concept redove i target-side concept redove
- canonical gap suggestion tok za slučajeve gde mapping izgleda dobar, ali canonical path nije popunjen
- `Gap Queue Summary` za queue-level pregled ponavljanih canonical gap familija

Ovo je mesto gde proveravaš da li sistemski predlog ima smisla pre nego što pređeš na persist ili output.

Važna razlika:

- `Mapping Analysis Overview` opisuje trenutno stanje mapping-a kao tehnički readout
- `Review Queue Plan` ne objašnjava mapping globalno, već predlaže kojim redom da rešavaš current review queue
- `Gap Queue Summary` radi isto to, ali samo za canonical gap candidate red
- `Selected Mapping Details` je mesto gde se pojavljuju source-side i target-side concept tabele; nisu zasebni top-level review tabovi
- `LLM Decision Proposals` ostaju advisory dok ih eksplicitno ne apply-uješ u `Decisions`
- `Workspace Copilot` u glavnom panelu sada može i direktno da te prebaci u `Decisions` bez pucanja stranice na Streamlit rerun-u

### `Decisions`

Ovde radiš:

- koristiš glavni `Workspace Copilot` panel za pitanja kao što su `What still needs a decision?` i `Am I ready for Output?`
- ručne izmene target izbora
- ručno mapiranje i u canonical modu, prema virtual canonical target opcijama
- import/export mapping odluka kao JSON ili Excel
- apply/dismiss tok za `LLM Decision Proposals` kroz `Apply safe proposals`, `Proposal source`, `Apply selected proposal` i `Dismiss selected proposal`
- kreiranje, nastavljanje i ažuriranje draft session tokova za shared review/decision persistence
- čuvanje mapping set verzija
- učitavanje i primenu prethodno sačuvanih mapping setova
- corrections tok i reusable learning tok

Važna pravila:

- mapping set reuse nazad u Workspace radi samo za `approved` mapping setove
- corrections se čuvaju samo kada je review ishod zatvoren, ne dok je odluka još nerešena
- `Apply safe proposals` je konzervativni batch mode za proposal apply, ne široko automatsko prihvatanje AI predloga
- `Apply selected proposal` je single-proposal akcija za trenutno izabrani `Proposal source`
- `Active Decisions` sada prikazuje i decision-origin metadata (`manual_mapping`, `llm_proposal`) kada je dostupna
- decision-origin audit metadata je uključena i u decision JSON export/import tok
- draft session-i ti omogućavaju da sačuvaš review filtere, aktivne odluke i section context pre povratka kasnije
- ako `Workspace Copilot` predloži handoff nazad ka `Review` ili napred ka `Output`, taj handoff sada koristi pending navigation pattern i bezbedan je kroz rerun/hot-reload cikluse

### `Output`

Ovde radiš:

- koristiš glavni `Workspace Copilot` panel za `Why is codegen blocked?` i `Explain output gating and warning priority`
- `Generate preview`
- `Generate Pandas code`, `Generate PySpark code` ili `Generate dbt model`
- `Refine with LLM` nad već generisanim artefaktom
- save/list/run transformation test set tokove kada su odluke accepted

Važna razlika:

- preview je advisory i možeš ga koristiti i pre finalnog odobravanja, da vidiš trenutno ponašanje mapping-a
- standard code generation je governance-sensitive surface i traži accepted aktivne odluke
- transformation test sets su governed artefakti i traže accepted aktivne odluke
- u canonical modu preview nije dostupan, ali code generation i artifact refinement rade nad aktivnim source -> canonical odlukama

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

## Governance

`Governance` je top-level area za canonical i knowledge governance.

Glavni panel unutar ovog dela je `Canonical Console`, koji je centralno mesto za canonical governance.

`Canonical Console` trenutno ima četiri pod-taba:

- `Canonical`
- `Knowledge`
- `Overlays & Runtime`
- `Stewardship`

### Canonical / Knowledge / Overlay Cheat Sheet

Brzi mentalni model:

- `Canonical` = stabilan poslovni jezik (šta pojam znači na nivou firme, nezavisno od sistema)
- `Knowledge` = sistemsko-vendorski prevod (kako se isti pojam pojavljuje u SAP/Workday/QAD nazivima)
- `Overlay` = kontrolisana dopuna (brzi patch aliasa/konteksta bez trajnog menjanja baze)
- `Runtime` = aktivna kompozicija koju mapping engine stvarno koristi u tom trenutku

Hijerarhija i prioritet pri preporukama:

1. `Canonical` je semantički autoritet
2. `Knowledge` vezuje sistemske termine za canonical koncepte
3. `Active Overlay` ima prioritet u runtime-u nad baznim knowledge unosima
4. `Runtime` je efektivno stanje za scoring, candidate ranking i explainability

Kada šta koristiš:

- koristi `Canonical` kada definišeš trajne, business-normalized koncepte
- koristi `Knowledge` kada modeluješ sinonime i varijante po sistemu/domenima
- koristi `Overlay` kada brzo zatvaraš konkretan gap bez full canonical promene
- proveri `Overlays & Runtime` kada želiš da potvrdiš šta je trenutno aktivno u engine-u

U procesu preporuka (praktično):

- tokom candidate/ranking faze knowledge i canonical signali ulaze u finalni score zajedno sa lexical/semantic signalima
- `Overlay` može odmah da promeni kvalitet preporuke jer menja aktivni runtime signal
- ako nema dovoljno canonical pokrivenosti, red tipično ostaje `needs_review` i ulazi u canonical gap tok
- u canonical-only modu canonical signal ima veću operativnu važnost jer nema realnog target dataseta

Tipične odluke:

- lokalni, sistemski problem: prvo `Overlay`
- stabilan i opšti biznis pojam: `Canonical`
- vendor-specifičan naziv/sinonim: `Knowledge`
- kada je predlog neočekivan: prvo proveri runtime/active overlay pa tek onda engine tuning

Ovde možeš:

- pregledati canonical concept registry
- videti canonical concept count metrika (`Filtered`, `Total`, `With active overlay`, `With context`), u skladu sa Knowledge registrom
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

`Catalog` trenutno nema interne tabove; organizovan je kroz sekcije (`Search and Filters`, `Discovery Overview`, `Integration Results`, `Integration Detail`, `Concept Detail`, `Mapping Set Detail`).

Ovde možeš:

- listati i pretraživati integracije
- gledati `Discovery Overview` nad source-system -> target-system parovima
- otvarati integration detail
- gledati concept-centric detail iz kataloga
- učitati mapping set detail, audit i diff
- videti hint tipa `similar approved integration exists`
- generisati `Workspace Reuse Shortlist` za trenutni Workspace context
- koristiti `Field Reuse Search` za pretragu samo nad izabranim source poljima iz aktivnog Workspace-a
- pokrenuti `Workspace Reuse Fit` za izabranu catalog verziju
- reuse-ovati odobren mapping set nazad u Workspace

Važno:

- Catalog radi nad sačuvanim mapping set i catalog projekcijama, nije zamena za live review tok
- reuse nazad u Workspace je governance-gated i zavisi od statusa mapping seta
- `Workspace Reuse Shortlist` radi na nivou cele trenutne aktivnosti, ne na nivou pojedinačnog field subset-a
- `Field Reuse Search` radi field-scoped shortlist i pregled preklapanja po source poljima, ali ne radi selektivni pull odluka sam po sebi
- `Workspace Reuse Fit` je bounded explanation layer; ne apply-je ništa automatski, već objašnjava da li je selected version dobar kandidat za trenutni Workspace context

Za detaljan opis catalog search-a, similarity heuristike i `Reuse in Workspace` ponašanja pogledaj `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## Benchmarks

`Benchmarks` služi za merljivo poređenje mapping kvaliteta.

`Benchmarks` trenutno nema interne tabove; organizovan je kroz sekcije (`Save Current Mapping As Benchmark`, `Saved Benchmark Datasets`, run/comparison akcije, `Benchmark Explanation`, istorija run-ova).

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

## System

`System` je pomoćna administrativna i observability površina.

`System` ima dva pod-taba:

- `Admin`
- `Debug`

Ovde tipično proveravaš:

- runtime config
- decision logs
- corrections i reusable rule stanje
- pomoćne knowledge/runtime informacije koje nisu deo glavnog Canonical Console toka

Koristi ovaj ekran kada ti treba operativni pregled sistema, a ne kada radiš glavni mapping ili canonical stewardship tok.

Važno:

- `System` nije zamena za `Governance > Canonical Console`
- write governance akcije ostaju u zasebnim workflow-ima

## Preporučeni tok rada

### Standard mapping tok

1. U `Workspace > Setup` uploaduj source i target.
2. Po potrebi izaberi tabele ili `Schema spec` mod i dodaj source/target companion fajlove.
3. Klikni `Upload and profile`.
4. Klikni `Generate mapping`.
5. U `Review` po potrebi generiši `Mapping Analysis Overview`, koristi per-row ili batch `LLM refine`, zatim proveri trust layer, canonical path i eventualne canonical gap predloge.
6. Ako review red deluje velik ili šumovit, koristi `Review Queue Plan` i po potrebi `Gap Queue Summary`.
7. U `Decisions` unesi ručne izmene, po potrebi apply-uj `LLM Decision Proposals`, sačuvaj draft session ako želiš da pauziraš ili podeliš stanje, eksportuj checkpoint ili sačuvaj mapping set.
8. U `Output` koristi preview, zatim codegen kada su odluke accepted, a po potrebi i transformation test set tok.
9. Ako generated artifact treba poliranje, koristi `Refine with LLM`, pa onda `Accept refined version` ili `Discard refinement`.

### Canonical-first tok

1. U `Workspace > Setup` pređi na `Canonical` mod.
2. Uploaduj source row-data ili source spec i po potrebi podesi `Canonical candidate pool size`.
3. Po potrebi dodaj source companion metadata, pa klikni `Upload and profile`, zatim `Generate canonical mapping`.
4. U `Review` proveri source -> canonical path i po potrebi koristi per-row `LLM refine`.
5. U `Decisions` možeš ručno mapirati na canonical opcije i po potrebi zatvoriti advisory proposal tokove.
6. U `Output` možeš generisati kod i raditi artifact refinement bez preview-a.
7. Ako postoje semantic gap-ovi, po potrebi ih prebaci u canonical governance tok kroz `Governance` (`Canonical Console`).

### Canonical governance tok

1. Otvori `Governance` pa `Canonical Console`.
2. Učitaj ili osveži registry, overlay state i stewardship queue.
3. Otvori concept detail ili gap/promotion item koji te zanima.
4. Proveri status, audit i impact preview.
5. Odradi approve/reject/ignore ili promote-to-glossary kada je item spreman.

## Kratke napomene

- Confidence score je heuristika za review prioritet, ne verovatnoća.
- Score `>= 0.75` trenutno auto-prihvata mapping iako confidence label može ostati `medium_confidence`.
- Preview je namerno advisory; ne znači da je mapping finalno odobren.
- Durable i execution-like površine su strože governed od samog preview-a.
- Sidebar `WS Copilot` i `WS Brief` surface-i su guidance layer-i; ne rade automatske durable write operacije.
- Nove bounded AI sekcije u Review, Benchmarks i Catalog takođe ne rade automatske write operacije; služe za objašnjenje, trijažu i pripremu ljudske odluke.
- Ako UI stanje deluje čudno posle više eksperimenata, `Reset flow` u `System` sidebar view-u je često najbrži oporavak.
- In-app `Help` sidebar view prikazuje ovaj English vodič direktno iz repository help fajla.
- `Dismiss` dugme na onboarding hint-u samo sakriva hint za tekuću sesiju i ne menja podatke.
- Zatvaranje browsera ne vraća automatski ceo Workspace state sledećeg dana; nastavak rada ide kroz draft session, sačuvan mapping set ili import checkpoint-a.

Za detaljan opis signala, score formule, confidence pragova i bounded LLM slučajeva pogledaj `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

Za detaljan opis preview statusa, warning kodova, klasifikacija i fallback ponašanja pogledaj `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Za detaljan opis benchmark metrika, confidence bucket tumačenja i correction-impact delta pogledaj `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

Za detaljan opis transformation test set strukture, assertion pravila i tumačenja run rezultata pogledaj `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

Za detaljan opis Catalog reuse i similarity heuristike pogledaj `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

Za detaljan opis Canonical Console runtime-a, overlay lifecycle-a i stewardship pravila pogledaj `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.
