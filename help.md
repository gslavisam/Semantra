# Help: Workspace, Benchmarks i Admin / Debug tab

Ovaj dokument objašnjava upotrebu dugmadi i pomoćnih kontrola na `Workspace`, `Benchmarks` i `Admin / Debug` tabovima u Streamlit aplikaciji Semantra.

Napomena:

- Neke akcije traže admin token.
- Ako backend nema podešen `SEMANTRA_ADMIN_API_TOKEN`, aplikacija trenutno može dozvoliti admin/debug i benchmark akcije i bez tokena.
- Većina akcija prikazuje rezultat odmah u istom tabu, ispod dugmeta koje je pokrenulo poziv.

## Pre nego što kreneš

Preporučeni redosled:

1. Na `Workspace` tabu uploaduj source i target fajlove.
2. Pokreni `Generate mapping`.
3. Tek onda idi na `Benchmarks` ili `Admin / Debug`, jer neke funkcije imaju najviše smisla tek kada već postoji aktivan mapping rezultat.

## Globalne sidebar kontrole

Ove kontrole nisu vezane samo za jedan tab, ali utiču na sve tokove u aplikaciji.

### `API Base URL`

Polje za URL backend API-ja.

Koristi kada:

- backend ne radi na podrazumevanom URL-u
- želiš da usmeriš UI na drugi lokalni ili mrežni backend

Tipično ostaje na lokalnoj vrednosti ako backend radi na istoj mašini.

### `Admin Token`

Polje za unos admin tokena koji backend koristi za zaštićene observability, evaluation i knowledge akcije.

Koristi kada:

- backend traži token za benchmark, correction, mapping set ili knowledge akcije
- želiš da radiš sa admin/debug funkcijama bez 403 grešaka

### `Reset flow`

Šta radi:

- briše aktivno stanje UI toka iz session state-a
- resetuje upload, mapping, preview, codegen i povezane radne podatke

Kada koristiti:

- kada želiš da kreneš iz početka sa novim source/target parom
- kada UI stanje deluje nedosledno posle više eksperimenata

Šta očekivati posle klika:

- aplikacija se vraća u čisto početno stanje
- potrebno je ponovo uploadovati fajlove ako želiš da nastaviš review

## Workspace tab

Svrha ovog taba je da vodi ceo glavni tok rada: upload, profilisanje, generisanje mapping-a, ručni review, transformacije, preview, code generation, import/export odluka, mapping setove i corrections.

Radi preglednosti, `Workspace` je organizovan u 4 unutrašnja pod-taba:

- `Setup` za upload, izbor tabela, profilisanje i pokretanje inicijalnog auto-mapping-a
- `Review` za trust layer, candidate pregled i ručni review po kolonama
- `Decisions` za manual overrides, import/export, mapping setove i corrections
- `Output` za preview i generisanje Pandas koda

## 1. Upload

### `Source file`

File uploader za source dataset.

Podržani su row-based formati kao što su CSV, JSON, XML i XLSX, kao i SQL schema snapshot kada koristiš schema-only tok.

### `Target file`

File uploader za target dataset.

Koristi se isto kao i `Source file`, samo za odredišni model ili šemu prema kojoj mapiraš.

## 2. Select Tables

Ova sekcija je važna samo kada uploadovani SQL fajl sadrži više tabela.

### `Source table`

Dropdown za izbor source tabele iz SQL snapshot-a.

Pojavljuje se samo kada backend iz source SQL fajla otkrije više tabela.

### `Target table`

Dropdown za izbor target tabele iz SQL snapshot-a.

Pojavljuje se samo kada backend iz target SQL fajla otkrije više tabela.

### `Upload and profile`

Šta radi:

- šalje source i target fajlove backend-u
- po potrebi uključuje izabrane source i target tabele
- gradi schema profile za obe strane
- čuva dataset identifikatore i preview podatke u UI stanju

Kada koristiti:

- odmah nakon izbora source i target fajla
- svaki put kada promeniš fajl ili tabelu i želiš svež profil

Preuslovi:

- oba fajla moraju biti izabrana

Šta očekivati posle klika:

- pojavljuju se summary sekcije za `Source` i `Target`
- aplikacija postaje spremna za `Generate mapping`

## 3. Review Mapping

### `Generate mapping`

Šta radi:

- poziva backend auto-mapping tok
- generiše rangirane kandidate i inicijalni odabrani target po source koloni
- inicijalizuje ručno review stanje u UI-ju

Kada koristiti:

- posle uspešnog upload-a i profilisanja

Šta očekivati posle klika:

- pojavljuju se trust layer, review tabele, manual review, corrections i akcije za preview/codegen

## Trust Layer i transformacije

Za svako source polje dobijaš blok sa target predlogom, confidence prikazom i expander sekcijom `Details and Transformation`.

### `Apply this transformation to data`

Checkbox koji aktivira predloženi transformation code ako ga je sistem već izgradio za dati source-target par.

Koristi kada:

- želiš da preview i kasniji codegen zaista koriste prikazani suggested transformation

### `Generate with LLM`

Šta radi:

- poziva runtime LLM da predloži pandas transformaciju za trenutno izabrani source-target par

Kada koristiti:

- kada znaš da je mapiranje ispravno, ali zahteva transformaciju
- kada želiš brži prvi draft transformacionog koda

Preuslovi:

- mora postojati aktivan target za taj source
- LLM runtime mora biti podešen i dostupan

Šta očekivati posle klika:

- u polje za manuelni kod ulazi generisani transformation code
- mogu se pojaviti reasoning i warning poruke uz taj predlog

### `Reusable template for <source>`

Dropdown za izbor gotovog transformation template-a.

Koristi kada:

- želiš standardnu tekstualnu ili formatersku transformaciju bez LLM-a

### `Apply template`

Šta radi:

- uzima izabrani reusable template i materializuje ga za konkretan source-target par

Kada koristiti:

- kada znaš da ti treba standardna transformacija i ne želiš generisanje novog koda

Šta očekivati posle klika:

- template kod se ubacuje u polje za manuelni/custom transformation

### `Define pandas/Python transformation for <source> (optional)`

Text area za ručno pisanje custom transformation koda.

Koristi kada:

- želiš punu kontrolu nad transformacijom
- LLM predlog nije dovoljno dobar
- template nije dovoljan

### `Apply generated/custom transformation`

Checkbox koji aktivira ručno uneti ili LLM/template generisan kod.

Koristi kada:

- želiš da preview i codegen koriste baš ovaj custom/generisani kod

Važno:

- sam unos koda nije dovoljan; checkbox odlučuje da li će se ta transformacija zaista primenjivati

## Review tabele i filteri

### `Filter by status`

Dropdown za filtriranje `Selected Mapping` prikaza po statusu.

### `Filter by confidence label`

Dropdown za filtriranje po confidence label-u.

### `Filter by source`

Dropdown za fokus na jednu source kolonu.

Ove kontrole ne menjaju backend stanje; služe samo za pregled i fokus tokom review-a.

## Manual Review sekcija

Za svaki source red možeš ručno da menjaš target i status.

### `Target for <source>`

Dropdown za ručni izbor target kandidata za dati source.

Koristi kada:

- želiš da zameniš inicijalno odabrani target drugim predlogom iz kandidat liste

### `Status for <source>`

Dropdown sa statusima `accepted`, `needs_review` i `rejected`.

Koristi kada:

- želiš da potvrdiš mapping
- želiš da ostaviš mapping za kasniji review
- želiš da odbiješ mapping

## Add Manual Mapping sekcija

Ova sekcija služi za dodavanje ili override source-target para koji auto-mapper nije predložio ili ga nije dobro rešio.

### `Manual source column`

Dropdown za izbor source kolone koju želiš ručno da dodaš ili override-uješ.

### `Manual target column`

Dropdown za ručni izbor target kolone.

### `Manual status`

Dropdown za status ručno dodate odluke.

### `Add mapping`

Šta radi:

- upisuje ručni source-target par u aktivno review stanje

Kada koristiti:

- kada auto-mapper nije predložio potrebnu vezu
- kada želiš da dopuniš mapping iz poslovnog znanja

Šta očekivati posle klika:

- ručni par se pojavljuje u tabeli `Manual additions and overrides`

### `Remove manual mapping`

Dropdown za izbor ručno dodatog ili override mapiranja koje želiš da ukloniš.

### `Remove`

Šta radi:

- uklanja izabrani ručni mapping iz aktivnog review stanja

Kada koristiti:

- kada si dodao pogrešan ručni par
- kada želiš povratak na sistemski predlog za dati source

## Active Decisions

Ova tabela nema dugmad, ali je važna jer prikazuje trenutno aktivne mapping odluke koje će ići u preview, codegen, export i čuvanje.

Ako ovde ne vidiš ono što očekuješ, prvo ispravi `Manual Review` ili `Add Manual Mapping` sekciju.

## Export / Import Decisions

### `Download mapping JSON`

Šta radi:

- eksportuje trenutno aktivne mapping odluke kao JSON fajl

Kada koristiti:

- za backup review stanja
- za prenos mapping odluka između sesija
- za ručno uređivanje van UI-ja

### `Import mapping JSON`

File uploader za JSON sa `mapping_decisions` payload-om.

### `Apply imported mapping`

Šta radi:

- učitava mapping odluke iz uploadovanog JSON-a u trenutno review stanje

Kada koristiti:

- kada želiš da vratiš ranije eksportovan mapping
- kada dobiješ mapping odluke iz drugog toka rada

Šta očekivati posle klika:

- editor state se ažurira prema importovanom payload-u

## Mapping Set Versioning

Ova sekcija služi da trenutno review stanje sačuvaš kao verzionisani mapping set na backend-u.

### `Mapping set name`

Naziv mapping seta koji čuvaš.

### `Mapping set created by`

Opcioni identifikator osobe ili tima koji čuva mapping set.

### `Mapping set note`

Opciona beleška vezana za tu verziju mapping seta.

### `Save mapping set version`

Šta radi:

- čuva aktivne mapping odluke kao novu verziju mapping seta

Kada koristiti:

- kada želiš review snapshot koji možeš kasnije ponovo učitati
- kada praviš verzionisane iteracije mapping rada

Šta očekivati posle klika:

- success poruka sa imenom i verzijom
- lista mapping setova može odmah biti osvežena

### `Load saved mapping sets`

Šta radi:

- učitava sve sačuvane mapping set verzije iz backend-a

Kada koristiti:

- kada želiš da pregledaš i koristiš ranije sačuvane verzije

### `Select saved mapping set`

Dropdown za izbor konkretne sačuvane mapping set verzije.

### `Apply saved mapping set`

Šta radi:

- učitava izabrani mapping set u trenutno review stanje

Kada koristiti:

- kada želiš da nastaviš raniji review ili testiraš staru verziju odluka

### `Saved mapping set status`

Dropdown za izbor novog statusa izabrane mapping set verzije.

### `Update saved mapping set status`

Šta radi:

- menja status izabrane mapping set verzije na backend-u

Kada koristiti:

- kada mapping set prelazi iz draft u review ili approved stanje

### `Load selected mapping set audit`

Šta radi:

- učitava audit istoriju za izabrani mapping set

Kada koristiti:

- kada želiš da vidiš lifecycle promene te verzije

## Save Corrections sekcija

Ova sekcija služi za snimanje razlika između sistemskog predloga i tvoje konačne review odluke, kao i za rad sa reusable rule kandidatima.

### `Correction note`

Opciona beleška koja se čuva uz svaku snimljenu korekciju.

### `Load reusable rule candidates`

Šta radi:

- učitava kandidate za reusable correction pravila na osnovu ranije istorije korekcija

Kada koristiti:

- kada želiš da vidiš koje korisničke korekcije se dovoljno često ponavljaju da mogu postati pravila

### `Load promoted reusable rules`

Šta radi:

- učitava već promovisana reusable pravila

Kada koristiti:

- kada želiš da proveriš koja pravila već aktivno utiču na ranking

### `Save reviewed corrections`

Šta radi:

- snima trenutne review razlike kao corrections u observability sloj

Kada koristiti:

- kada si završio ručni review i želiš da sistem pamti te odluke

Šta očekivati posle klika:

- success poruka sa brojem sačuvanih korekcija
- sekcija `Last saved corrections` dobija nove podatke

### `Promote reusable rule candidate`

Dropdown za izbor kandidata koji želiš da pretvoriš u reusable pravilo.

### `Promote selected reusable rule`

Šta radi:

- promoviše izabrani correction candidate u trajno reusable pravilo

Kada koristiti:

- kada znaš da se određeni correction obrazac ponavlja i treba snažnije da utiče na buduće ranking odluke

## Finalne akcije na Workspace tabu

### `Generate preview`

Šta radi:

- izvršava preview aktivnih mapping odluka nad source podacima
- uključuje transformation preview kada su transformacije aktivirane

Kada koristiti:

- kada želiš da vidiš kako bi rezultat izgledao pre codegen-a ili čuvanja

Preuslovi:

- mora postojati barem jedna aktivna mapping odluka

Šta očekivati posle klika:

- pojavljuje se sekcija `Preview`
- mogu se pojaviti unresolved targets i transformation validation detalji

### `Generate Pandas code`

Šta radi:

- generiše Pandas kod na osnovu aktivnih mapping odluka i aktiviranih transformacija

Kada koristiti:

- kada želiš starter artifact za implementaciju mapiranja

Preuslovi:

- mora postojati barem jedna aktivna mapping odluka

Šta očekivati posle klika:

- pojavljuje se sekcija `Generated Pandas Code`
- ako postoje problemi ili fallback situacije, mogu se pojaviti warnings

## Benchmarks tab

Svrha ovog taba je da sačuvaš realan mapping scenario kao benchmark, da ga ponovo pokrećeš kasnije i da meriš uticaj correction learning-a.

### Pomoćna polja i kontrole

#### `Benchmark dataset name`

Ovo je ime pod kojim će se trenutni mapping scenario sačuvati kao benchmark dataset.

Koristi kada:

- želiš da razlikuješ više benchmark scenarija
- želiš verzionisanje benchmark skupova po poslovnom domenu ili test iteraciji

Primeri:

- `customer-master-clean-v1`
- `erp-noisy-aliases-v1`
- `pilot-scenario-2`

#### JSON prikaz ispod naslova `Save Current Mapping As Benchmark`

Ovo nije dugme, ali je važan indikator. Pokazuje tačno koji će benchmark case biti sačuvan ako klikneš `Save current mapping as benchmark`.

Ako ovde ne vidiš ništa korisno, nemoj još čuvati benchmark. Vrati se na `Workspace` tab i proveri da li imaš aktivne mapping odluke.

#### `Saved dataset`

Dropdown lista sa prethodno sačuvanim benchmark datasetima.

Koristi ga da izabereš koji benchmark želiš da pokreneš ili nad kojim želiš da meriš correction impact.

#### `Run selected benchmark with configured LLM`

Checkbox koji određuje da li benchmark treba pokretati samo heuristički ili uz aktivni runtime LLM.

Koristi kada:

- želiš da uporediš ponašanje bez LLM-a i sa LLM-om
- želiš da proveriš da li LLM stvarno popravlja rezultat ili samo uvodi varijacije

Nemoj uključivati ovaj checkbox ako:

- LLM runtime nije podešen
- želiš čisto determinističko poređenje između iteracija

### Dugmad na Benchmarks tabu

#### `Save current mapping as benchmark`

Šta radi:

- uzima trenutni mapping scenario iz aktivnog review stanja
- čuva ga kao benchmark dataset u backend persistence sloju

Kada koristiti:

- kada napraviš scenario koji želiš kasnije ponovo da meriš
- kada želiš da sačuvaš real-life pilot primer kao referentni test

Preuslovi:

- mora postojati barem jedna aktivna mapping odluka
- `Benchmark dataset name` ne sme biti prazan

Šta očekivati posle klika:

- success poruka sa `dataset_id`, imenom i verzijom
- benchmark se kasnije pojavljuje u listi sačuvanih datasetova

Najbolja praksa:

- čuvaj male, reprezentativne benchmark scenarije umesto jednog ogromnog benchmarka

#### `Load saved benchmark datasets`

Šta radi:

- učitava sve ranije sačuvane benchmark datasete iz backend-a

Kada koristiti:

- kada prvi put ulaziš na `Benchmarks` tab
- kada si upravo sačuvao novi benchmark i želiš da osvežiš listu

Šta očekivati posle klika:

- ispod se pojavljuje tabela sa benchmark datasetima
- dropdown `Saved dataset` dobija nove opcije

#### `Load benchmark runs`

Šta radi:

- učitava istoriju ranijih benchmark izvršavanja

Kada koristiti:

- kada želiš da pregledaš prethodne rezultate i porediš iteracije
- kada želiš da proveriš da li je neki refactor ili overlay promenio kvalitet

Šta očekivati posle klika:

- ispod se pojavljuje tabela `Benchmark Run History`

#### `Run selected benchmark`

Šta radi:

- pokreće izabrani benchmark dataset kroz evaluation backend
- koristi heuristiku ili heuristiku + LLM, u zavisnosti od checkbox-a

Kada koristiti:

- kada želiš da vidiš trenutni kvalitet sistema na sačuvanom benchmarku
- kada proveravaš da li nova promena u sistemu popravlja ili kvari mapping kvalitet

Šta očekivati posle klika:

- ispod se pojavljuje `Last Benchmark Result`
- rezultat je prikazan kao JSON payload sa metrikama

Kako tumačiti:

- fokusiraj se na accuracy, top-1 accuracy i ukupni broj correct matches

#### `Measure correction impact`

Šta radi:

- meri razliku između baseline rezultata i correction-aware rezultata
- pokazuje da li istorija korekcija i reusable rules stvarno popravljaju mapping kvalitet

Kada koristiti:

- kada već imaš sačuvane corrections i želiš da vidiš njihov efekat
- kada procenjuješ da li learning loop vredi dalje razvijati

Šta očekivati posle klika:

- pojavljuje se tabela `Correction Impact`
- prikazuje baseline accuracy, correction-aware accuracy i razliku između njih

Kako tumačiti:

- pozitivan `accuracy_delta` znači da istorija korekcija pomaže
- mali ili nulti pomak znači da još nema dovoljno kvalitetne feedback istorije ili da pravila nisu dobro pogođena

## Admin / Debug tab

Svrha ovog taba je da učita runtime stanje backend-a, knowledge sloj, audit tragove, glossary stanje i pomoćne dijagnostičke podatke.

Ako vidiš poruku da je admin token obavezan, prvo ga unesi u sidebar polje `Admin Token`.

### Gornji skup dugmadi

#### `Load runtime config`

Šta radi:

- učitava runtime konfiguraciju backend-a preko observability endpointa

Kada koristiti:

- kada proveravaš koji LLM provider je aktivan
- kada proveravaš da li je admin token podešen
- kada proveravaš gate pragove i druge aktivne runtime postavke

Šta očekivati posle klika:

- ispod se pojavljuje sekcija `Runtime Config` u JSON formatu

#### `Load decision logs`

Šta radi:

- učitava decision log zapise koje backend beleži tokom mapping odluka

Kada koristiti:

- kada želiš da pregledaš kako je sistem donosio odluke
- kada istražuješ neočekivano mapiranje

Šta očekivati posle klika:

- pojavljuje se tabela `Decision Logs`

#### `Load saved corrections`

Šta radi:

- učitava sve sačuvane user corrections iz sistema

Kada koristiti:

- kada proveravaš da li je correction history stvarno snimljen
- kada želiš da proceniš kvalitet learning podataka

Šta očekivati posle klika:

- pojavljuje se tabela `Saved Corrections`

#### `Load benchmark runs`

Šta radi:

- učitava istoriju evaluation run-ova iz backend-a

Kada koristiti:

- kada benchmark istoriju želiš da vidiš iz debug perspektive, bez odlaska na `Benchmarks` tab

Šta očekivati posle klika:

- pojavljuje se tabela `Evaluation Runs`

### Knowledge Overlays sekcija

Ova sekcija služi za pregled i upravljanje knowledge overlay verzijama.

#### `Load knowledge overlays`

Šta radi:

- učitava listu svih sačuvanih overlay verzija

Kada koristiti:

- kada želiš da vidiš koje overlay verzije postoje
- kada planiraš aktivaciju, deaktivaciju ili pregled detalja

Šta očekivati posle klika:

- ispod se pojavljuje tabela overlay verzija
- dropdown `Overlay version` dobija opcije

#### `Reload knowledge`

Šta radi:

- prisiljava backend da ponovo učita knowledge runtime sloj

Kada koristiti:

- posle aktivacije ili import-a knowledge/glossary podataka
- kada sumnjaš da backend runtime nije osvežen

Šta očekivati posle klika:

- pojavljuje se ili osvežava summary o `Knowledge mode`, aktivnom overlay-u i broju aktivnih entiteta

#### `Load active knowledge status`

Šta radi:

- praktično učitava trenutno aktivno runtime stanje knowledge sloja

Kada koristiti:

- kada te zanima samo status runtime-a, ne i kompletan reload workflow sa drugim akcijama

Napomena:

- trenutno koristi isti backend poziv kao `Reload knowledge`, pa je efekat sličan

#### `Load knowledge audit log`

Šta radi:

- učitava audit log za knowledge lifecycle akcije

Kada koristiti:

- kada želiš da vidiš ko je i kada radio create, activate, deactivate, archive ili import operacije

Šta očekivati posle klika:

- pojavljuje se tabela `Knowledge Audit Log`

### Kontrole za upload knowledge overlay fajla

#### `Knowledge overlay CSV`

File uploader za CSV sa overlay entry-jima.

Koristi ga kada želiš da uneseš:

- abbreviations
- synonyms
- field aliases
- concept aliases

#### `Overlay version name`

Naziv nove overlay verzije.

Preporuka:

- koristi ime koje jasno opisuje domen i verziju, na primer `sales-domain-overlay-v1`

#### `Created by`

Opciono polje za evidenciju ko je napravio overlay.

Korisno je za audit i timski rad.

#### `Validate knowledge CSV`

Šta radi:

- proverava CSV bez čuvanja kao novu overlay verziju

Kada koristiti:

- uvek pre `Save overlay version`, posebno za veće CSV-ove

Šta očekivati posle klika:

- pojavljuje se validation summary
- pojavljuje se tabela preview redova sa statusom, normalizacijom i eventualnim problemima

Kako tumačiti:

- `valid` znači da je red spreman za čuvanje
- `invalid` znači da postoji greška koju treba ispraviti u CSV-u
- conflicts i duplicates treba pregledati pre snimanja

#### `Save overlay version`

Šta radi:

- čuva uploadovani knowledge CSV kao novu overlay verziju

Kada koristiti:

- kada je validacija prošla ili kada svesno želiš da sačuvaš sadržaj zajedno sa validation rezultatom

Šta očekivati posle klika:

- success poruka sa nazivom verzije i brojem sačuvanih entry-ja
- automatski refresh liste overlay verzija
- validation rezultat ostaje dostupan za pregled

### Canonical Glossary sekcija

Ova sekcija služi za import i export canonical glossary CSV fajla.

#### `Canonical glossary CSV`

File uploader za canonical glossary import.

Koristi ga kada želiš da ubaciš novu glossary verziju iz CSV-a.

#### `Load canonical glossary export`

Šta radi:

- učitava trenutni glossary CSV iz backend-a u memoriju UI-ja

Kada koristiti:

- kada želiš da preuzmeš aktuelni glossary za pregled, backup ili izmenu

Šta očekivati posle klika:

- pojavljuje se dugme `Download canonical glossary CSV`

#### `Import canonical glossary`

Šta radi:

- importuje uploadovani canonical glossary CSV u backend
- zatim osvežava knowledge runtime

Kada koristiti:

- kada želiš da zameniš ili osvežiš canonical glossary

Šta očekivati posle klika:

- success poruka
- summary sa brojem importovanih redova i canonical concepts
- osvežen knowledge runtime status

Važno:

- ovo menja file-backed canonical glossary, zato koristi pažljivo i poželjno sa kontrolisanom CSV verzijom

#### `Download canonical glossary CSV`

Šta radi:

- preuzima glossary koji je prethodno učitan klikom na `Load canonical glossary export`

Kada koristiti:

- za lokalni backup
- za ručnu doradu glossary-ja pre novog import-a

### Overlay verzije i lifecycle akcije

Ove kontrole postaju korisne kada je lista overlay verzija već učitana.

#### `Overlay version`

Dropdown za izbor konkretne overlay verzije nad kojom radiš sledeću akciju.

#### `Load details`

Šta radi:

- učitava detalje izabrane overlay verzije, uključujući njene entry-je

Kada koristiti:

- kada želiš da proveriš tačan sadržaj određene overlay verzije

Šta očekivati posle klika:

- pojavljuje se `Overlay detail` summary
- pojavljuje se tabela sa entry-jima te verzije

#### `Activate selected overlay`

Šta radi:

- aktivira izabranu overlay verziju kao runtime overlay

Kada koristiti:

- kada želiš da mapping engine i trust layer koriste baš tu overlay verziju

Šta očekivati posle klika:

- runtime status pokazuje novi aktivni overlay
- lista overlay verzija se osvežava
- detalji izabrane verzije se ponovo učitavaju

#### `Deactivate selected overlay`

Šta radi:

- deaktivira izabranu overlay verziju

Kada koristiti:

- kada želiš povratak sa aktivne overlay varijante na validated, ali neaktivno stanje

Šta očekivati posle klika:

- runtime status se osvežava
- overlay više nije aktivan u knowledge runtime-u

#### `Archive selected overlay`

Šta radi:

- arhivira izabranu overlay verziju

Kada koristiti:

- kada overlay više ne želiš da koristiš operativno, ali želiš da ostane u istoriji

Šta očekivati posle klika:

- status verzije prelazi u arhivirano stanje
- lista i detalji se osvežavaju

Napomena:

- arhiviranje nije isto što i brisanje; to je lifecycle status promena

#### `Rollback active overlay`

Šta radi:

- vraća runtime knowledge sloj na prethodno aktivnu overlay verziju
- ako nema prethodne, može vratiti sistem na base-only režim

Kada koristiti:

- kada nova aktivna overlay verzija pogorša mapping rezultate
- kada želiš brz povratak na ranije stabilno stanje

Šta očekivati posle klika:

- runtime status se menja
- lista overlay verzija se osvežava
- detalji aktivne verzije se ponovo učitavaju

### Dijagnostičke sekcije ispod dugmadi

Ove sekcije nisu dugmad, ali su važne za tumačenje rezultata:

#### `Knowledge mode ...`

Pokazuje:

- da li backend radi u `base_only` ili `overlay_active` režimu
- koji overlay je trenutno aktivan
- broj aktivnih entry-ja i knowledge concept count

#### `Validation summary`

Pokazuje:

- ukupan broj redova iz upload CSV-a
- koliko je validnih, nevalidnih, duplikata i konflikata

#### `Canonical Coverage`

Pojavljuje se samo ako već postoji `mapping_response` iz `Workspace` taba.

Koristi se da vidiš:

- coverage source strane
- coverage target strane
- project-level canonical coverage za aktivni mapping context

#### `Knowledge and Canonical Match Insights`

Pomaže da pregledaš:

- knowledge signal
- canonical signal
- confidence
- explanation detalje za svaki source-target par

## Preporučeni praktični tokovi

### Tok 1: Provera benchmark kvaliteta

1. Na `Workspace` tabu uploaduj source i target.
2. Klikni `Generate mapping`.
3. Idi na `Benchmarks`.
4. Unesi ime u `Benchmark dataset name`.
5. Klikni `Save current mapping as benchmark`.
6. Klikni `Load saved benchmark datasets`.
7. Izaberi dataset iz `Saved dataset`.
8. Klikni `Run selected benchmark`.
9. Po potrebi klikni `Measure correction impact`.

### Tok 2: Uvoz i aktivacija knowledge overlay-a

1. Idi na `Admin / Debug`.
2. Uploaduj fajl kroz `Knowledge overlay CSV`.
3. Klikni `Validate knowledge CSV`.
4. Pregledaj `Validation summary` i preview redove.
5. Klikni `Save overlay version`.
6. Klikni `Load knowledge overlays`.
7. Izaberi verziju u `Overlay version`.
8. Klikni `Activate selected overlay`.
9. Klikni `Reload knowledge` ili proveri runtime status.

### Tok 3: Export i import canonical glossary-ja

1. Klikni `Load canonical glossary export`.
2. Klikni `Download canonical glossary CSV` da sačuvaš postojeće stanje.
3. Pripremi novu CSV verziju.
4. Uploaduj je kroz `Canonical glossary CSV`.
5. Klikni `Import canonical glossary`.
6. Proveri import summary i knowledge runtime status.

## Brzi saveti

- Pre benchmark rada uvek proveri da li je aktivan overlay koji očekuješ.
- Pre import-a canonical glossary-ja napravi export kao backup.
- `Validate knowledge CSV` koristi kao obavezan korak, ne kao opciju.
- `Measure correction impact` ima smisla tek kad sistem već ima sačuvane corrections.
- Ako rezultati deluju čudno, prvo koristi `Load runtime config`, `Load knowledge overlays` i `Load active knowledge status` pre dubljeg debug-a.