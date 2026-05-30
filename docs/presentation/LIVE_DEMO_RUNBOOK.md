# Semantra Live Demo Runbook

Ovaj dokument je namenjen za glavni live demo u trenutnoj pilot fazi.

Za ovu fazu proizvoda preporučeni demo nije "prođi kroz sve ekrane", nego jedan stabilan proof-of-value scenario koji se može ponavljati pred stakeholder-ima bez improvizacije.

UI orijentacija za ovaj runbook:

- top-level area: `Workspace`, `Catalog`, `Benchmarks`, `System`, `Governance`
- `Workspace` je organizovan kroz `Setup`, `Review`, `Decisions`, `Output`
- `Canonical Console` i `Stewardship` žive unutar `Governance`, a nisu zasebni top-level tabovi

Primarni demo tok je:

1. `Catalog` reuse
2. `Workspace` resume
3. `Catalog` diff handoff
4. `Catalog` stewardship handoff
5. `Benchmarks` comparison and explanation

Prošireni `Workspace -> Setup -> Review -> Decisions -> Output` walkthrough i dalje ima smisla, ali kao sekundarni ili tehnički demo, ne kao glavni stakeholder story.

## 0. Priprema pre demo-a

Pre pocetka uradi sledece:

1. Pokreni aplikaciju kao i inace.
2. U sidebar-u proveri da je `API Base URL` ispravan.
3. Ako backend trazi admin token, unesi ga pre otvaranja `Catalog`, `Governance` i `Benchmarks`.
4. Za glavni tok koristi već potvrđene operational smoke fixture-e:
   - `approved-customer-reuse-smoke`
   - `customer-draft-session`
   - `browser-diff-focus`
   - `stewardship-smoke-sync`
   - `operational-smoke-benchmark`
5. Ako želiš čist repeatable start, pre demo-a pokreni bootstrap script za operational smoke stanje.

## 1. Glavna poruka demoa

Ako želiš jednu rečenicu koja drži ceo demo na okupu, koristi ovo:

"Semantra koristi prethodno odobreno integraciono znanje iz kataloga, vraća korisnika u aktivni review kontekst bez ručnog rekonstruisanja rada, i na kraju meri i objašnjava kvalitet mapping odluka kroz benchmark evidence."

## 2. Primarni stakeholder demo tok

Za glavni live demo koristi ovaj redosled:

1. `Catalog` reuse
2. `Workspace` resume
3. `Catalog` diff handoff
4. `Catalog` stewardship handoff
5. `Benchmarks` comparison and explanation

Ovaj tok je najbolji kada želiš da pokažeš organizacionu vrednost: reuse, continuity, governance handoff i quality evidence.

## 3. Primarni demo koraci

### 3.1 Catalog reuse

1. Otvori `Catalog`.
2. U `Search` upiši `approved-customer-reuse-smoke`.
3. Klikni `Run catalog query`.
4. Klikni `Load detail`.
5. Kratko pokaži `Latest approved version` i `approved` status.
6. Klikni `Reuse in Workspace`.

Naglasak:

- Semantra ne kreće od nule kada već postoji odobreno integraciono znanje.
- Ovo je reuse produkcionog artefakta, ne samo pasivan pregled istorije.

### 3.2 Workspace resume

1. Pređi u `Workspace`.
2. Otvori `Decisions`.
3. U `Mapping Set Versions` klikni `Load draft sessions`.
4. Izaberi `customer-draft-session`.
5. Klikni `Resume draft session`.
6. Pokaži da se UI vraća u review-ready stanje bez ručnog rekonstruisanja konteksta.

Naglasak:

- continuity rada je konkretna vrednost, ne samo UI trik
- draft session ovde služi kao bounded continuity slice, ne kao full collaborative workspace model

Operativna napomena iz live smoke prolaza 2026-05-29:

- ako `Resume draft session` ne vrati UI automatski na `Review`, koristi mali presenterski fallback: ručno klikni `Review` i naglasi da je poenta u očuvanom radnom kontekstu, ne u samoj navigacionoj animaciji
- ovaj fallback je prihvatljiv za trenutni pilot/demo sloj, ali behavior i dalje vredi dodatno harden-ovati pre šireg showcase korišćenja

### 3.3 Catalog diff handoff

1. Vrati se u `Catalog`.
2. Resetuj catalog state ako je potrebno.
3. U `Search` upiši `browser-diff-focus`.
4. Klikni `Run catalog query` i `Load detail`.
5. Otvori izabranu verziju i učitaj diff.
6. Klikni `Open current diff review focus`.

Naglasak:

- Catalog nije samo istorijska arhiva
- diff vodi direktno u pravi review kontekst

### 3.4 Catalog stewardship handoff

1. Vrati se u `Catalog`.
2. Resetuj catalog state.
3. U `Search` upiši `stewardship-smoke-sync`.
4. Klikni `Run catalog query`, `Load detail`, pa `Open selected version`.
5. U `Mapping Set Drilldown` klikni `Open Stewardship`.

Naglasak:

- governance nije odvojeni ostrvski ekran
- reuse i diff mogu direktno da generišu governance follow-up u pravom kontekstu

### 3.5 Benchmarks comparison and explanation

1. Idi u `Benchmarks`.
2. Klikni `Load saved benchmark datasets`.
3. Izaberi `operational-smoke-benchmark`.
4. Klikni `Compare scoring profiles`.
5. Pokaži `Recommended default profile`.
6. U `Benchmark Explanation` klikni `Generate benchmark explanation`.

Naglasak:

- ovde pokazuješ dokaz kvaliteta, ne još jedan mapping editor
- explanation pomaže da se rezultat objasni organizaciji, ne samo da se vidi skor

## 4. Prošireni tehnički demo

Ako publika traži širi product walkthrough ili hoćeš da pokažeš pun analyst lifecycle, koristi sekundarni `Workspace -> Setup -> Review -> Decisions -> Output` tok.

Taj tok je koristan, ali nije preporučeni prvi demo za stakeholder-e u ovoj fazi.

## 5. Prošireni tehnički demo: Workspace -> Setup with one source/target pair

Ovo je prvi demo korak sa slajda.

1. Otvori top-level tab `Workspace`.
2. Ostani u internom tabu `Setup`.
3. U sekciji `1. Upload` ostavi `Mapping mode` na `Standard`.
4. U `Source file` ucitaj `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv`.
5. U `Target file` ucitaj `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`.
6. U sekciji `2. Interpret Files` ostavi:
   - `Source mode` = `Row data`
   - `Target mode` = `Row data`
7. U sekciji `3. Select Tables` ne moras nista dodatno da biras jer su ovo row-data fajlovi.
8. Klikni `Upload and profile`.
9. Kada se pojave summary kartice, kratko naglasi da Semantra odmah profilise source i target strukturu.

Sta da kazes dok radis ovaj korak:

- ovde pokazujem da setup nije vezan za jedan format, nego za source/target par
- source je CSV, target je JSON, dakle cross-format mapping je normalan tok

## 6. Prošireni tehnički demo: Generate mapping -> Review (signal ranking + canonical path)

Ovo je drugi demo korak sa slajda.

1. I dalje u `Workspace > Setup`, pronadji sekciju `3. Review Mapping`.
2. Preporuka za stabilan demo: ostavi `Use LLM validation` iskljucen, osim ako unapred znas da je LLM runtime zelen i stabilan.
3. Klikni `Generate mapping`.
4. Sacekaj da se zavrsi status blok `Mapping activity`.
5. Kada dobijes poruku da je mapping spreman, otvori interni tab `Review`.
6. U `Mapping Trust Layer` prodji makar kroz sledeca polja:
   - `legacy_customer_code`
   - `purchaser`
   - `main_phone`
7. Za svako od njih otvori `Details and Transformation` i pokazi:
   - explanation linije
   - `Signal breakdown`
   - confidence
8. Zatim u delu kandidat-review tabele pokazi da kandidat ima rangiranje, a ne samo jedan black-box odgovor.
9. Na jednom od customer polja naglasi i `Canonical path` kada se prikaze.

Sta da kazes dok radis ovaj korak:

- ovde se vidi da Semantra ne daje samo target, nego i zasto je taj target predlozen
- ranking i canonical path su review materijal za analiticara, nisu skriveni iza modela

## 7. Prošireni tehnički demo: Decisions: one accepted, one manual override

Bitna napomena: per-field override se radi u `Review > Manual Review`, a zatim se rezultat prikazuje u `Decisions`.

Preporuceni prolaz:

1. Ostani u `Workspace > Review`.
2. Skroluj do sekcije `Manual Review`.
3. Za `legacy_customer_code` ostavi target `account_id` i postavi status na `accepted`.
4. Za `annual_spend_usd` iskoristi ga kao primer ljudske intervencije:
   - ako je target vec `annual_revenue_usd`, ostavi target ali status postavi na `needs_review` da pokazes da covek ne mora automatski da prihvati semanticki blizak predlog
   - ako zelis jaci override demo, promeni target, pa ga vrati na onaj koji zelis da demonstriras kao finalnu odluku
5. Posle toga otvori interni tab `Decisions`.
6. U `Active Decisions` pokazi da se sada vide i accepted i manual-review odluke.

Ako zelis jos direktniji override demo:

1. U `Review > Manual Review` nadji red za `annual_spend_usd`.
2. Promeni status iz `accepted` ili `needs_review` u ono sto zelis da demonstriras.
3. Objasni da operator ima poslednju rec i da confidence nije automatsko odobrenje.

## 8. Prošireni tehnički demo: Output: advisory preview + accepted-only codegen gate

Ovo je cetvrti demo korak sa slajda i idealno je da ga odradis dok jos postoji makar jedna odluka koja nije `accepted`.

1. Otvori `Workspace > Output`.
2. Klikni `Generate preview`.
3. Pokazi da preview radi i kada sve odluke jos nisu potpuno odobrene.
4. Skreni paznju na advisory poruku ispod preview akcije ako postoji.
5. Zatim pokazi dugme `Generate Pandas code`.
6. Ako jos postoji neka odluka koja nije `accepted`, naglasi da je code generation blokiran dok sve aktivne odluke ne budu prihvacene.
7. Vrati se zatim u `Review > Manual Review` ili `Decisions` i prebaci preostale vazne odluke na `accepted`.
8. Po povratku u `Output`, pokazi da je gate uklonjen kada su aktivne odluke prihvacene.

Sta da kazes dok radis ovaj korak:

- preview je savetodavan i sluzi za proveru
- codegen je striktno governance-gated i trazi accepted aktivne odluke

## 9. Prošireni tehnički demo: Save mapping set and move to approved

Ovo je peti demo korak sa slajda.

1. Vrati se u `Workspace > Decisions`.
2. U sekciji za mapping set popuni sledeca polja:
   - `Mapping set name`: predlog `demo-customer-account`
   - `Mapping set created by`: npr. `live-demo`
   - `Mapping set owner`: npr. `data-governance`
   - `Mapping set assignee`: npr. `ba-team`
   - `Version note`: npr. `Initial live demo version`
   - `Review note`: npr. `Reviewed during PMO walkthrough`
3. Klikni `Save mapping set version`.
4. Klikni `Load saved mapping sets`.
5. U `Select saved mapping set` izaberi upravo sacuvanu verziju.
6. U `Saved mapping set status` promeni status na `approved`.
7. Klikni `Update saved mapping set status`.
8. Kratko pokazi da je isti mapping sada durable artefakt, a ne samo session state.

## 10. Prošireni tehnički demo: Catalog: detail, latest approved version, Reuse in Workspace

Ovo je sesti demo korak sa slajda i direktno se nastavlja na prethodni.

1. Otvori top-level tab `Catalog`.
2. Ako je potrebno, klikni `Load all integrations`.
3. Ako zelis uzi prikaz, u `Search` unesi ime mapping seta, na primer `demo-customer-account`, pa klikni `Run catalog query`.
4. U delu `Integration Results` pronadji svoju integraciju.
5. U `Integration detail` izaberi tu integraciju i klikni `Load detail`.
6. U `Integration Detail` pokazi:
   - `Latest version`
   - `Latest approved version`
   - listu verzija
   - canonical concepts i unmatched sources ako postoje
7. U `Catalog version drilldown` izaberi approved verziju.
8. Klikni `Open approved version` ako zelis da prvo pokazes detalj verzije.
9. Zatim klikni `Reuse in Workspace`.
10. Posle uspeha vrati se u `Workspace > Review` ili `Workspace > Decisions` i pokazi da je stanje vraceno u workspace kao reviewed artefakt.

Sta da kazes dok radis ovaj korak:

- Catalog nije live session view, nego reuse sloj nad sacuvanim artefaktima
- Reuse vraca odobrenu verziju nazad u Workspace, ne rerun-uje mapper od nule

## 11. Prošireni tehnički demo: Governance > Canonical Console: concept detail + stewardship action

Za ovaj deo koristi `ui_fixtures/knowledge_demo_overlay.csv`.

Ako backend trazi admin token, proveri da je unet pre ulaska u tab.

### 7A. Concept detail

1. Otvori top-level tab `Governance`.
2. Ostani u sekciji `Canonical Console`.
3. Klikni `Load canonical concept registry` ako vec nije ucitan.
4. U polju `Canonical concept search` unesi `customer`.
5. U `Canonical concept detail` izaberi concept koji zelis da pokazes.
6. Klikni `Load canonical concept detail`.
7. U detalju koncepta pokazi:
   - usage
   - field contexts
   - active overlay aliases
   - aliases
   - catalog usage

### 7B. Stewardship / overlay action

1. Skroluj do `Overlay Management`.
2. U `Knowledge overlay CSV` ucitaj `ui_fixtures/knowledge_demo_overlay.csv`.
3. U `Overlay version name` unesi npr. `demo-customer-overlay`.
4. U `Created by` unesi npr. `live-demo`.
5. Klikni `Validate knowledge CSV`.
6. Kada se pojavi validation summary, klikni `Save overlay version`.
7. Klikni `Load knowledge overlays` ako lista nije vec osvezena.
8. U padajucem izboru `Overlay version` izaberi novu verziju.
9. Klikni `Load details` ako zelis da prvo pokazes entries.
10. Klikni `Activate selected overlay`.
11. Vrati pogled na `Overlay Summary` i objasni da je canonical runtime sada osvezen eksplicitnom governance akcijom.

Sta da kazes dok radis ovaj korak:

- ovo nije debug-only povrsina, nego governance povrsina unutar `Governance` area za canonical runtime
- promene nad knowledge slojem su eksplicitne i auditabilne

## 12. Prošireni tehnički demo: Benchmarks: run + correction-impact check

Ovo je osmi demo korak sa slajda.

Pre ovog koraka proveri da su aktivne odluke koje hoces da benchmark-ujes u prihvatljivom stanju. Najstabilnije je da budu `accepted`.

1. Otvori top-level tab `Benchmarks`.
2. U `Benchmark dataset name` unesi npr. `demo-customer-account-benchmark`.
3. Klikni `Save current mapping as benchmark`.
4. Klikni `Load saved benchmark datasets`.
5. U `Saved dataset` izaberi benchmark koji si upravo sacuvao.
6. Za stabilan demo ostavi `Run selected benchmark with configured LLM` iskljucen, osim ako unapred znas da je LLM runtime stabilan.
7. Klikni `Run selected benchmark`.
8. Pokazi `Last Benchmark Result`.
9. Zatim klikni `Measure correction impact`.
10. Pokazi correction-impact rezultat kao poseban quality/progression signal.
11. Ako hoces da zatvoris pricu merenjem kroz vreme, klikni i `Load benchmark runs`.

Sta da kazes dok radis ovaj korak:

- Benchmarks nisu analyst review ekran, nego quality measurement povrsina
- correction impact pokazuje da sistem moze da meri efekat governovanog ucenja

## Preporuceni redosled za prošireni tehnički demo

Ako zelis da sve ide glatko, drzi se ovog reda:

1. `Workspace > Setup`
2. `Workspace > Review`
3. `Workspace > Decisions`
4. `Workspace > Output`
5. `Workspace > Decisions` za save + approve
6. `Catalog`
7. `Governance > Canonical Console`
8. `Benchmarks`

## Brzi fallback ako vreme krene da curi

Ako moras da skratis demo, zadrzi sledece:

1. `Catalog -> approved-customer-reuse-smoke -> Reuse in Workspace`
2. `Workspace -> Resume draft session`
3. `Benchmarks -> operational-smoke-benchmark -> Compare scoring profiles -> Generate benchmark explanation`

To ti pokriva reuse, continuity i quality evidence, što je trenutno najjača kratka priča.