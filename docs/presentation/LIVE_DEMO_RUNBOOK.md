# Semantra Live Demo Runbook

Ovaj dokument je namenjen za live demo prema osam stavki sa slajda.

Ideja je da koristis jedan glavni scenario kroz `Workspace`, zatim da iz istog rada predjes u `Catalog`, `Canonical Console` i `Benchmarks`.

## 0. Priprema pre demo-a

Pre pocetka uradi sledece:

1. Pokreni aplikaciju kao i inace.
2. U sidebar-u proveri da je `API Base URL` ispravan.
3. Ako backend trazi admin token, unesi ga pre otvaranja `Catalog`, `Canonical Console` i `Benchmarks`.
4. Za glavni tok koristi ove fajlove:
   - `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv`
   - `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`
5. Za Canonical Console overlay deo koristi ovaj fajl:
   - `ui_fixtures/knowledge_demo_overlay.csv`

## 1. Workspace -> Setup with one source/target pair

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

## 2. Generate mapping -> Review (signal ranking + canonical path)

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

## 3. Decisions: one accepted, one manual override

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

## 4. Output: advisory preview + accepted-only codegen gate

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

## 5. Save mapping set and move to approved

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

## 6. Catalog: detail, latest approved version, Reuse in Workspace

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

## 7. Canonical Console: concept detail + stewardship action

Za ovaj deo koristi `ui_fixtures/knowledge_demo_overlay.csv`.

Ako backend trazi admin token, proveri da je unet pre ulaska u tab.

### 7A. Concept detail

1. Otvori top-level tab `Canonical Console`.
2. Klikni `Load canonical concept registry` ako vec nije ucitan.
3. U polju `Canonical concept search` unesi `customer`.
4. U `Canonical concept detail` izaberi concept koji zelis da pokazes.
5. Klikni `Load canonical concept detail`.
6. U detalju koncepta pokazi:
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

- ovo nije debug-only povrsina, nego governance povrsina za canonical runtime
- promene nad knowledge slojem su eksplicitne i auditabilne

## 8. Benchmarks: run + correction-impact check

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

## Preporuceni redosled live demo-a

Ako zelis da sve ide glatko, drzi se ovog reda:

1. `Workspace > Setup`
2. `Workspace > Review`
3. `Workspace > Decisions`
4. `Workspace > Output`
5. `Workspace > Decisions` za save + approve
6. `Catalog`
7. `Canonical Console`
8. `Benchmarks`

## Brzi fallback ako vreme krene da curi

Ako moras da skratis demo, zadrzi sledece:

1. `Workspace > Setup` sa quick demo parom
2. `Generate mapping` + jedan trust-layer primer
3. Jedan accepted i jedan manual-review primer
4. `Generate preview` + codegen gate
5. `Save mapping set version` + status `approved`
6. `Catalog > Reuse in Workspace`

To ti pokriva glavni lifecycle bez dubljeg governance i benchmark dela.