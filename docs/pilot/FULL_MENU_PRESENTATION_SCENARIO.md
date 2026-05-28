# Full Menu Presentation Scenario

Ovaj dokument je slide-by-slide scenario za siri prezentacioni prolaz kroz celu Semantra navigaciju.

Nije regression checklist i nije automation runner. Njegova svrha je da ti da kompletan presenterski scenario za svaku glavnu stavku menija i za svaku vaznu podsekciju, tako da od ovoga mozes da napravis deck od najmanje 12 podslajdova.

Najprakticniji format je 16 do 18 slajdova, jer tada svaka zona dobija dovoljno prostora da se ne pretvori u brzinsku demonstraciju bez objasnjenja.

Companion dokumenti za ovaj scenario:

- speaker notes: [docs/pilot/FULL_MENU_PRESENTATION_SPEAKER_NOTES.md](D:/py_radno/Semantra/docs/pilot/FULL_MENU_PRESENTATION_SPEAKER_NOTES.md)
- slide asset map: [docs/pilot/FULL_MENU_PRESENTATION_ASSET_MAP.md](D:/py_radno/Semantra/docs/pilot/FULL_MENU_PRESENTATION_ASSET_MAP.md)

## Cilj prezentacije

Publika treba da razume pet stvari:

1. `Workspace` je radni tok od ingest-a do izlaznog artefakta.
2. `Catalog` cuva reusable integraciono znanje i vodi korisnika nazad u radni kontekst.
3. `Benchmarks` mere kvalitet i daju objasnjivu preporuku za scoring profil.
4. `System` sluzi za runtime administraciju i observability, ne za svakodnevni analiticki rad.
5. `Governance` je odvojeni steward sloj za canonical, knowledge, overlay i stewardship procese.

## Pre-flight pre prezentacije

Uradi ovo pre nego sto otvoris deck ili krenes live:

1. Pokreni lokalni stack.
2. Uveri se da su `API Base URL = http://127.0.0.1:8000` i admin token vec uneti.
3. Ako hoces repeatable demo baseline, pokreni:

```powershell
.\backend\scripts\bootstrap_operational_smoke.ps1 -AdminToken secret-token
```

4. Ako hoces da proveris trio smoke pre publike, pokreni:

```powershell
.\backend\scripts\run_operational_browser_e2e.ps1 -AdminToken secret-token
```

5. Ako hoces da koristiis gotove Workspace medije za slajdove, vec postoje artefakti u:

- `docs/pilot/demo_assets/workspace_recordings_20260527`
- `docs/pilot/demo_assets/manual_live_demo_20260527`

## Preporucena struktura deck-a

Minimalni deck je 12 slajdova, ali preporuka za punu pricu je 17 slajdova:

1. Naslov i problem koji Semantra resava
2. Navigaciona mapa aplikacije
3. Workspace -> Setup
4. Workspace -> Review
5. Workspace -> Decisions
6. Workspace -> Output
7. Catalog -> Search and Discovery
8. Catalog -> Detail, Diff, Reuse, Handoff
9. Benchmarks -> Dataset and Run Management
10. Benchmarks -> Profile Comparison and Explanation
11. System -> Admin
12. System -> Debug
13. Governance overview
14. Governance -> Canonical
15. Governance -> Knowledge
16. Governance -> Overlays & Runtime
17. Governance -> Stewardship

Ako hoces kraci prolaz, mozes spojiti slajdove 7 i 8, spojiti slajdove 9 i 10, i izostaviti poseban governance overview slajd.

## Narativna linija

Jedna recenica koja drzi celu prezentaciju na okupu:

"Semantra vodi korisnika od ucitavanja i review-a mapping-a, preko reuse i quality evidence sloja, do administrativnog i governance upravljanja istim sistemom bez gubitka konteksta."

## Slide scenario

## 1. Naslov i problem

### Sta kazes

"Semantra nije samo mapper. To je radni i governance sistem za data integration: od pripreme mapping-a, preko review-a i odluka, do benchmark merenja, runtime kontrole i stewardship-a."

### Sta publika treba da razume

- postoji jasan put od analyst rada do governance rada
- reuse, benchmark i observability nisu naknadni dodaci, vec deo istog proizvoda

### Preporuceni asset

- live pocetni ekran sa top-level navigacijom

## 2. Navigaciona mapa

### Sta kazes

"Na vrhu imamo pet glavnih zona: `Workspace`, `Catalog`, `Benchmarks`, `System` i `Governance`. Samo `Workspace`, `System` i `Governance` imaju dodatne unutrasnje podsekcije, pa je korisnicki tok jasno podeljen po odgovornosti."

### Klikovi

1. Pokazi gornju navigaciju.
2. Kratko predji preko svih pet stavki bez dubokog zadrzavanja.

### Expected outcomes

- publika vidi da aplikacija nije jedan ekran
- jasno je da postoje analyst, observability i stewardship slojevi

## 3. Workspace -> Setup

### Sta kazes

"`Setup` je ulazna tacka za ingestion i interpretaciju fajlova. Ovde biramo standardni two-file mapping ili canonical-only nacin rada."

### Klikovi

1. Otvori `Workspace`.
2. U podnavigaciji izaberi `Setup`.
3. Pokazi `Mapping mode` sa opcijama `Standard` i `Canonical`.
4. Pokazi `Source file` i `Target file` upload za `Standard`.
5. Pokazi `Source mode` i `Target mode` kao `Row data` ili `Schema spec`.
6. Ako hoces puni live primer, ucitaj showcase pair i klikni `Upload and profile`.

### Expected outcomes

- vidi se da Semantra podrzava ingestion i interpretaciju fajla, ne samo review gotovog rezultata
- publika razume razliku izmedju standardnog i canonical toka
- vidi se da spec-like fajlovi mogu biti interpretirani kao schema input

### Sta naglasavas

"Ovde nije poenta samo upload, nego pravilno tumacenje inputa. Time isti proizvod pokriva i data fajlove i spec-driven onboarding."

### Preporuceni asset

- `docs/pilot/demo_assets/workspace_recordings_20260527/01_standard_two_file_mapping/01_standard_two_file_mapping.webm`

## 4. Workspace -> Review

### Sta kazes

"`Review` je trust-layer i analyst radni prostor. Tu se vide kandidati, coverage, LLM i knowledge signali, review queue plan i bounded proposal povrsine."

### Klikovi

1. Prebaci na `Review`.
2. Pokazi `Mapping Trust Layer` i glavne signale.
3. Pokazi `Review Queue Plan`.
4. Pokazi `LLM Decision Proposals` expander.
5. Kratko pokazi `Selected Mapping` i details panele.

### Expected outcomes

- publika vidi da review nije samo tabela source->target
- vidi se da postoje objasnjivi signali i review prioritizacija
- vidi se da LLM ne menja mapping automatski, vec predlaze bounded korake

### Sta naglasavas

"Ovo je analyst-centered review, ne black-box automatsko mapiranje. LLM i knowledge rade kao pomocni sloj, ne kao zamena za review."

### Preporuceni asset

- `docs/pilot/demo_assets/workspace_recordings_20260527/03_llm_decision_flow/03_llm_decision_flow_01.png`

## 5. Workspace -> Decisions

### Sta kazes

"`Decisions` je mesto gde review prelazi u trajne ili polutrajne odluke: manual overrides, import/export, mapping set verzije, draft sessions i correction tokovi."

### Klikovi

1. Otvori `Decisions`.
2. Pokazi `Manual mapping` ili override panel.
3. Pokazi import/export povrsine.
4. Otvori `Mapping Set Versions`.
5. Pokazi `Load draft sessions` i `Resume draft session`.
6. Ako zelis, pokazi da se ovde pojavljuje `Apply safe proposals` kada postoje bezbedni LLM predlozi.

### Expected outcomes

- publika razume da analyst odluke mogu da se sacuvaju i vrate
- vidi se da postoji durable state, a ne samo session-local rad
- jasno je da je Decisions prelaz iz review-a u reusable ili persisted output

### Sta naglasavas

"Ovo je operativni sloj rada. Ovde se odluke cuvaju, verzionisu i vracaju, pa tim ne gubi istoriju ni continuity."

## 6. Workspace -> Output

### Sta kazes

"`Output` pretvara aktivno stanje mapping odluka u korisne artefakte: preview, Pandas, PySpark, dbt i LLM refinement kod generatora."

### Klikovi

1. Otvori `Output`.
2. Pokazi `Artifact format`.
3. Pokazi `Generate preview` kada je standardni mapping.
4. Klikni `Generate Pandas code`.
5. Promeni format i klikni `Generate dbt model`.
6. Ako je dostupan refinement, pokazi `Refine with LLM` i potom `Accept refined version` ili `Discard refinement`.

### Expected outcomes

- vidi se da sistem ne staje na review tabeli
- publika dobija dokaz da iz istog workspace stanja nastaju razvojni artefakti
- razume se razlika izmedju preview-a i production-oriented scaffolding-a

### Sta naglasavas

"Time Semantra zatvara krug: od inputa i review-a do artefakta koji razvojni tim stvarno moze da preuzme."

### Preporuceni asset

- `docs/pilot/demo_assets/workspace_recordings_20260527/04_workspace_output_generation/04_workspace_output_generation.webm`

## 7. Catalog -> Search and Discovery

### Sta kazes

"`Catalog` je reuse i discovery sloj. Tu trazimo vec postojeca integraciona resenja po sistemima, domenu, statusu i canonical kontekstima."

### Klikovi

1. Otvori `Catalog`.
2. Pokazi `Search and Filters`.
3. Pokazi filtre `Source system`, `Target system`, `Business domain`, `Owner`, `Status`, `Artifact type`.
4. Klikni `Run catalog query` ili `Load all integrations`.
5. Zadrzi se na `Discovery Overview` i `Integration Results`.

### Expected outcomes

- publika vidi da catalog nije samo lista fajlova
- jasno je da discovery radi po integration-level i governance-level signalima
- vidi se reuse shortlist i pregled system-pair matrice

### Sta naglasavas

"Ovo je biblioteka integracionog znanja sa operativnim signalima, ne samo istorijska arhiva."

## 8. Catalog -> Detail, Diff, Reuse i Handoff

### Sta kazes

"Kada nadjemo relevantnu integraciju, `Catalog` postaje aktivni ulaz u dalji rad: reuse u `Workspace`, diff review handoff i governance handoff."

### Klikovi

1. Pretrazi `approved-customer-reuse-smoke` i pokazi `Reuse in Workspace`.
2. Pretrazi `browser-diff-focus`, ucitaj detail, klikni `Open selected version`, zatim `Load version diff`.
3. Pokazi `Open current diff review focus`.
4. Pretrazi `stewardship-smoke-sync` i pokazi `Open Stewardship`.

### Expected outcomes

- publika vidi reuse, diff i governance handoff iz istog modula
- jasno je da `Catalog` ume da vrati korisnika u pravi radni ili governance kontekst
- vidi se da postoji razlika izmedju detail pregleda i akcijskog handoff-a

### Sta naglasavas

"Najvaznija poruka je da catalog nije pasivan. Iz njega odmah nastavljamo pravi posao."

### Preporuceni asset

- `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm`

## 9. Benchmarks -> Dataset and Run Management

### Sta kazes

"`Benchmarks` pocinju od toga da aktivni mapping sacuvamo kao benchmark case ili da ucitamo vec postojece benchmark dataset-e i run history."

### Klikovi

1. Otvori `Benchmarks`.
2. Pokazi `Save Current Mapping As Benchmark`.
3. Pokazi `Load saved benchmark datasets`.
4. Pokazi `Load benchmark runs`.
5. Izaberi jedan `Saved dataset`.

### Expected outcomes

- publika vidi da benchmark nije samo jednokratni test, nego trajni evaluation asset
- jasno je da se benchmark dataset i runs mogu cuvati i vracati

### Sta naglasavas

"Ovo je quality evidence sloj. Tim moze da meri iste ili slicne slucajeve kroz vreme, ne samo ad hoc."

## 10. Benchmarks -> Profile Comparison and Explanation

### Sta kazes

"Kada dataset postoji, mozemo da uporedimo scoring profile, izaberemo preporuceni default i generisemo explanation koji tu preporuku cini razumljivom."

### Klikovi

1. U `Benchmarks` izaberi `Profiles to compare`.
2. Klikni `Compare scoring profiles`.
3. Pokazi `Scoring Profile Comparison`.
4. Pokazi `Recommended default profile`.
5. Otvori `Benchmark Explanation` i klikni `Generate benchmark explanation`.

### Expected outcomes

- vidi se profilno poredjenje po accuracy/top1 metrikama
- publika dobija preporuceni profil i razlog za preporuku
- explanation izlistava findinge, rizike i sledece korake

### Sta naglasavas

"Ovde ne govorimo samo koji profil je pobedio, nego i zasto je preporuka doneta."

### Preporuceni asset

- `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/05_benchmarks_explanation_01.png`

## 11. System -> Admin

### Sta kazes

"`System` nije analyst radni ekran. `Admin` tab sluzi za runtime kontrolu: konfiguracija, scoring profil, saved corrections i benchmark run history."

### Klikovi

1. Otvori `System`.
2. Ostani na tabu `Admin`.
3. Pokazi dugmad `Load runtime config`, `Load saved corrections`, `Load benchmark runs`.
4. Pokazi blok `Scoring Runtime`.
5. Pokazi `Active scoring profile` i `Apply scoring profile`.
6. Ako je vec ucitano, pokazi `Runtime Config`, `Saved Corrections` i `Evaluation Runs`.

### Expected outcomes

- publika vidi da runtime ima administrativni sloj
- jasno je da scoring profil moze da se menja centralno
- vidi se da corrections i evaluation runs nisu sakriveni po backend logovima

### Sta naglasavas

"Ovo je operativna kontrola sistema, ne mesto gde analyst donosi mapping odluke."

## 12. System -> Debug

### Sta kazes

"`Debug` je observability povrsina. Tu gledamo decision logs, aktivni knowledge runtime, audit log i canonical coverage insighte nad trenutnim mapping stanjem."

### Klikovi

1. Prebaci na tab `Debug`.
2. Pokazi `Load decision logs`.
3. Pokazi `Load active knowledge status`.
4. Pokazi `Load knowledge audit log`.
5. Ako postoji mapping state, pokazi `Canonical Coverage` i `Knowledge and Canonical Match Insights`.

### Expected outcomes

- publika vidi da debug nije genericki dump nego strukturirani observability panel
- jasno je da knowledge runtime i audit mogu da se inspektuju iz UI-ja
- coverage i match insights ostaju kompatibilni sa review podacima

### Sta naglasavas

"Ovaj ekran sluzi za troubleshooting i transparentnost, ne za normalan poslovni rad."

## 13. Governance overview

### Sta kazes

"`Governance` je odvojena steward konzola. Ima cetiri sekcije: `Canonical`, `Knowledge`, `Overlays & Runtime` i `Stewardship`. Svaka ima drugaciju odgovornost."

### Klikovi

1. Otvori `Governance`.
2. Pokazi radio `Governance section`.
3. Kratko prodji preko sva cetiri izbora.

### Expected outcomes

- publika razume da governance nije jedan monolitni ekran
- vidi se da postoje registry, overlay i queue odgovornosti

## 14. Governance -> Canonical

### Sta kazes

"`Canonical` je stabilni glossary sloj. Ovde se upravlja canonical konceptima, njihovim aliasima, kontekstom, coverage-om i promotion kandidatima."

### Klikovi

1. Izaberi `Canonical`.
2. Pokazi `Canonical Glossary`.
3. Pokazi filtere i selected concept detalje.
4. Ako postoji promotion context, pokazi concept-linked promotion ili overlay-promotion signal.

### Expected outcomes

- publika vidi da canonical nije samo spisak termina
- jasno je da postoji lifecycle oko koncepata, aliasa i promotion-ready stanja

### Sta naglasavas

"Canonical je stabilna meta-ravnina sistema. Promene ovde imaju dugorocan efekat."

## 15. Governance -> Knowledge

### Sta kazes

"`Knowledge` cuva radni registry poslovnih i tehnickih pojmova sa vezama prema canonical sloju. Ovo je bridge izmedju operativnog znanja i stabilnog glossarya."

### Klikovi

1. Izaberi `Knowledge`.
2. Pokazi `Knowledge Registry` i `Knowledge Concept Registry`.
3. Pokazi linked canonical informacije i promotion readiness.
4. Ako je prikladno, pokazi odabrani knowledge concept detail.

### Expected outcomes

- publika vidi da knowledge i canonical nisu ista stvar
- jasno je da knowledge concepts mogu imati razlicit stepen povezanosti sa canonical slojem

### Sta naglasavas

"Knowledge je fleksibilniji i blizi realnim integracionim izrazima, dok je canonical stabilniji i stroze upravljan."

## 16. Governance -> Overlays & Runtime

### Sta kazes

"`Overlays & Runtime` je mesto za kontrolisane, reverzibilne promene znanja koje uticu na runtime bez direktnog menjanja stabilnog canonical glossarya."

### Klikovi

1. Izaberi `Overlays & Runtime`.
2. Pokazi `Overlay Summary`.
3. Pokazi `Overlay Management`.
4. Pokazi akcije tipa ucitavanje overlay verzija, aktivacija, arhiviranje ili rollback gde su dostupne.
5. Pokazi runtime caption sa `mode`, `runtime_source` i `active_overlay_name`.

### Expected outcomes

- publika vidi da postoji bezbedan mehanizam za runtime promene
- jasno je da overlay nije isto sto i trajna glossary promena
- vidi se auditabilan lifecycle verzija

### Sta naglasavas

"Ovo je eksperimentalni i operativni sloj znanja: brzo, reverzibilno i kontrolisano."

## 17. Governance -> Stewardship

### Sta kazes

"`Stewardship` je aktivna radna lista governance follow-up stavki: gapovi, predlozi, queue statusi, review note i odluke za promociju, odbijanje ili ignorisanje."

### Klikovi

1. Izaberi `Stewardship`.
2. Ako imas catalog handoff primer, dodji ovde preko `Open Stewardship` iz `Catalog`-a.
3. Pokazi stewardship queue i selected item detail.
4. Pokazi status/proposal-state caption i review note prostor.
5. Pokazi da postoje approve/reject/ignore tokovi kada je predlog spreman.

### Expected outcomes

- publika vidi da governance follow-up nije apstraktan koncept nego stvaran queue
- jasno je da stewardship vodi odluke do auditabilnog ishoda

### Sta naglasavas

"Stewardship je most izmedju otkrivenog problema i trajne governance odluke."

## Zavrsni slajd

### Sta kazes

"Ako krenemo od vrha navigacije do dna governance sloja, Semantra pokriva ceo zivotni ciklus: ingestion, review, decisions, output, reuse, benchmark evidence, runtime kontrolu i steward upravljanje znanjem."

### Zavrsna poruka

"Najvaznije je da ove povrsine nisu nepovezane. `Catalog` vraca u `Workspace`, `Benchmarks` objasnjava kvalitet odluka, `System` nadzire runtime, a `Governance` pretvara operativne signale u trajno upravljano znanje." 

## Kako da od ovoga napravis deck

Ako zelis PowerPoint ili Canva strukturu, koristi ovo pravilo:

1. jedan slajd = jedna meni zona ili jedan podmeni
2. na svakom slajdu drzi samo tri stvari: sta je ovo, zasto postoji, koji je dokaz u UI-ju
3. za `Workspace`, `System` i `Governance` koristi po vise slajdova, jer su to viseslojne povrsine
4. za `Catalog` i `Benchmarks` mozes po potrebi spojiti u po 1 ili 2 slajda

## Preporuceni mediji po sekciji

- `Workspace`: `docs/pilot/demo_assets/workspace_recordings_20260527`
- `Catalog` i `Benchmarks`: `docs/pilot/demo_assets/manual_live_demo_20260527`
- ako radis staticki deck, izvuci po jedan screenshot po slajdu iz tih foldera
- ako radis live deck, koristi ovaj scenario kao govorni tok a recording-e kao fallback