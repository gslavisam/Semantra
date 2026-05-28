# Manual Live Demo Script

Ovaj dokument je namenjen za ručnu, uživo prezentaciju Semantra aplikacije pred publikom.

Nije automation runner i nije regression checklist. Njegova svrha je da ti da gotov presenterski tok: šta kažeš, šta klikćeš i šta publika treba da vidi kao dokaz da aplikacija radi.

Najstabilniji live-demo tok koristi već potvrđene operational smoke fixture-e:

- `approved-customer-reuse-smoke`
- `customer-draft-session`
- `browser-diff-focus`
- `stewardship-smoke-sync`
- `operational-smoke-benchmark`

## Cilj demoa

Publika treba da razume tri stvari:

1. Semantra ne počinje svaki put od nule, već ume da koristi već odobrene integracije iz `Catalog`-a.
2. Aktivni analitički rad može da se nastavi kroz `Workspace` bez gubitka konteksta.
3. Kvalitet mapping-a može da se proveri i objasni kroz `Benchmarks`.

## Pre-flight pre prezentacije

Uradi ovo pre nego što podeliš ekran:

1. Pokreni lokalni stack i proveri da su backend i Streamlit živi.
2. Uveri se da je u levom panelu upisan `API Base URL = http://127.0.0.1:8000`.
3. Uveri se da je admin token unet.
4. Ako želiš čist i repeatable start, pokreni:

```powershell
.\backend\scripts\bootstrap_operational_smoke.ps1 -AdminToken secret-token
```

5. Ako želiš i poslednju proveru da je UI stabilan pre publike, pokreni:

```powershell
.\backend\scripts\run_operational_browser_e2e.ps1 -AdminToken secret-token
```

## Preporučeni redosled prezentacije

Za live demo koristi ovaj redosled:

1. `Catalog` reuse
2. `Workspace` resume
3. `Catalog` diff handoff
4. `Catalog` stewardship handoff
5. `Benchmarks` comparison i explanation

Ovim redosledom priča prirodno ide od reusable znanja, preko aktivnog rada, do governance i kvaliteta.

## Kratka narativna mapa

Ako želiš jednu rečenicu koja drži ceo demo na okupu, koristi ovo:

"Semantra koristi prethodno odobreno integraciono znanje iz kataloga, vraća korisnika u aktivni review kontekst bez ručnog rekonstruisanja rada, i na kraju meri i objašnjava kvalitet mapping odluka kroz benchmark evidence."

## Demo script: puni prolaz 10-15 minuta

## 1. Catalog reuse

### Šta kažeš

"Ne želimo da svaki mapping počinje od praznog papira. Prvo ću pokazati da katalog čuva već proverene integracije i da ih možemo ponovo koristiti u aktivnom workspace-u."

### Klikovi

1. Otvori `Catalog` u gornjoj navigaciji.
2. U polje `Search` upiši `approved-customer-reuse-smoke`.
3. Klikni `Run catalog query`.
4. Klikni `Load detail`.
5. Zadrži se kratko na detail pogledu.
6. Klikni `Reuse in Workspace`.

### Expected outcomes

Publika treba da vidi sledeće:

- `Catalog` detail se uspešno otvori bez greške.
- vidi se caption `Latest approved version`
- status je `approved`
- `Reuse in Workspace` je dostupan
- nakon klika pojavi se success/status poruka da je mapping set reused u `Workspace`

### Šta naglašavaš

"Ovo je reuse odobrenog asset-a, ne samo pregled istorije. Time smanjujemo ručni rad i ubrzavamo standardne integracione use case-ove."

## 2. Workspace resume

### Šta kažeš

"Sledeće pitanje je da li korisnik može da nastavi rad tamo gde je stao. Umesto ručnog vraćanja filtera i review stanja, koristimo saved draft session."

### Klikovi

1. Pređi u `Workspace`.
2. U podnavigaciji izaberi `Decisions`.
3. Otvori expander `Mapping Set Versions`.
4. Klikni `Load draft sessions`.
5. U `Select draft session` izaberi `customer-draft-session`.
6. Klikni `Resume draft session`.

### Expected outcomes

Publika treba da vidi sledeće:

- draft session lista se učita
- izabrani session ima ime `customer-draft-session`
- UI se vrati u `Workspace > Review`
- pojavljuju se review elementi kao `Filter by source` i `Review Queue Plan`
- nema runtime greške niti ručnog resetovanja stanja

### Šta naglašavaš

"Ovde ne dokazujemo samo navigaciju, nego continuity rada. To je važno kada analitičar prekine sesiju i mora da nastavi review bez rekonstrukcije konteksta."

## 3. Catalog diff handoff u Workspace review

### Šta kažeš

"Sada ću pokazati da katalog nije pasivna arhiva. Iz diff prikaza možemo direktno da pređemo u review fokus koji odgovara promenama između verzija."

### Klikovi

1. Vrati se u `Catalog`.
2. Klikni `Reset catalog state` ako je potrebno da očistiš prethodni detail.
3. U `Search` upiši `browser-diff-focus`.
4. Klikni `Run catalog query`.
5. Klikni `Load detail`.
6. Klikni `Open selected version`.
7. Klikni `Load version diff`.
8. Zadrži se kratko na diff readout-u.
9. Klikni `Open current diff review focus`.

### Expected outcomes

Publika treba da vidi sledeće:

- diff se učita za izabranu verziju
- vidi se `Selected mapping set diff`
- vidi se CTA `Open current diff review focus`
- nakon klika UI se prebacuje u `Workspace > Review`
- status poruka signalizira `Catalog handoff`
- review fokus je otvoren bez ručnog traženja odgovarajućih promena

### Šta naglašavaš

"Time katalog postaje aktivni ulaz u review rad, a ne samo read-only evidencija. To je posebno korisno kada želimo da pregledamo šta se promenilo između verzija i odmah nastavimo review u pravom kontekstu."

## 4. Catalog stewardship handoff u Governance

### Šta kažeš

"Kada reuse ili diff ukažu na governance follow-up, korisnik ne treba ručno da traži odgovarajući governance ekran. Pokazaću handoff direktno u stewardship tok."

### Klikovi

1. Vrati se u `Catalog`.
2. Klikni `Reset catalog state`.
3. U `Search` upiši `stewardship-smoke-sync`.
4. Klikni `Run catalog query`.
5. Klikni `Load detail`.
6. Klikni `Open selected version`.
7. U `Mapping Set Drilldown` klikni `Open Stewardship`.

### Expected outcomes

Publika treba da vidi sledeće:

- otvara se `Governance`
- aktivna sekcija je `Stewardship`
- vidi se da korisnik nije završio na pogrešnoj governance sekciji
- handoff radi iz konkretnog Catalog konteksta, ne kao opšta navigacija

### Šta naglašavaš

"Ovo pokazuje da governance nije odvojen svet. Kada catalog signalizira stewardship problem, aplikacija vodi korisnika pravo u odgovarajući governance workflow."

## 5. Benchmarks comparison i explanation

### Šta kažeš

"Na kraju pokazujemo da mapping nije samo urađen, nego i procenjen. Benchmarks služe kao quality telemetry sloj: upoređujemo scoring profile i generišemo objašnjenje koje pomaže pri odluci."

### Klikovi

1. Idi u `Benchmarks`.
2. Klikni `Load saved benchmark datasets`.
3. U `Saved dataset` izaberi `operational-smoke-benchmark` ako već nije izabran.
4. Klikni `Compare scoring profiles`.
5. Sačekaj da se pojavi `Scoring Profile Comparison`.
6. Pokaži `Recommended default profile`.
7. Otvori expander `Benchmark Explanation`.
8. Klikni `Generate benchmark explanation`.

### Expected outcomes

Publika treba da vidi sledeće:

- dataset lista se učita
- izabran je `operational-smoke-benchmark`
- pojavljuje se `Scoring Profile Comparison`
- pojavljuje se `Recommended default profile`
- `Benchmark Explanation` se otključava
- posle generisanja se vide sekcije kao `Key findings`, `Risks`, `Next actions`

### Šta naglašavaš

"Ovde ne donosimo mapping odluke, već proveravamo kvalitet i objašnjavamo rezultat. To je korisno kada treba da opravdamo zašto je neki scoring profil ili mapping pristup bolji za dati use case."

## Završna rečenica

Ako želiš čist završetak, zatvori demo ovako:

"Dakle, u jednom toku smo pokazali reuse već odobrenog znanja, nastavak aktivnog review rada bez ručnog resetovanja konteksta, governance handoff kada postoje follow-up obaveze, i benchmark evidence koji objašnjava kvalitet odluka."

## Kratka verzija za 5-7 minuta

Ako nemaš vremena za puni demo, koristi samo ova tri koraka:

1. `Catalog -> approved-customer-reuse-smoke -> Reuse in Workspace`
2. `Workspace -> Decisions -> Mapping Set Versions -> Load draft sessions -> Resume draft session`
3. `Benchmarks -> operational-smoke-benchmark -> Compare scoring profiles -> Generate benchmark explanation`

To je najkraći stabilni demo koji i dalje pokriva reuse, continuity i quality telemetry.

## Rezervni plan ako nešto zastane uživo

Ako se UI ili runtime ponaša sporo, koristi sledeći fallback:

1. resetuj `Catalog` kroz `Reset catalog state` pre sledećeg query-a
2. ako fixture-i deluju prazno, pre prezentacije ponovo pusti bootstrap script
3. ako hoćeš poslednju proveru pred publiku, koristi browser E2E runner iz [docs/pilot/OPERATIONAL_BROWSER_E2E.md](D:/py_radno/Semantra/docs/pilot/OPERATIONAL_BROWSER_E2E.md)

## Šta ne treba raditi u ovom demo-u

Izbegni sledeće tokom prezentacije:

1. da krećeš od upload flow-a ako cilj nije ingestion priča
2. da ručno eksperimentišeš sa nepoznatim fixture-ima izvan operational smoke seta
3. da menjaš scoring profile selekciju bez potrebe
4. da otvaraš sporedne expander-e koji nisu deo glavne priče

## Povezani dokumenti

- full menu presentation scenario: [docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md](D:/py_radno/Semantra/docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md)
- automation smoke: [docs/pilot/OPERATIONAL_BROWSER_E2E.md](D:/py_radno/Semantra/docs/pilot/OPERATIONAL_BROWSER_E2E.md)
- regression subset: [docs/pilot/PILOT_REGRESSION_SUBSET.md](D:/py_radno/Semantra/docs/pilot/PILOT_REGRESSION_SUBSET.md)
- execution reference: [docs/pilot/PILOT_EXECUTION_LOG_2026-05-10.md](D:/py_radno/Semantra/docs/pilot/PILOT_EXECUTION_LOG_2026-05-10.md)