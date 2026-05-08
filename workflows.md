# Semantra – Workflows: Širi scenariji

Ovaj dokument opisuje sve trenutno relevantne workflow-e u Semantra alatu.
Za svaki workflow dat je konkretan poslovni scenario, korak-po-korak tok, grananja (sretan put / problem put),
uloge učesnika i veza sa epikama iz razvojnog plana.

---

## WF-01 – Standard Upload & Mapping

**Opis:** Najosnovniji workflow. Korisnik ima izvorni (source) i ciljni (target) fajl i želi da dobije predlog mapiranja kolona.

**Tipični učesnici:** Business analyst, data engineer, integration consultant.

**Preduvjeti:** Backend i Streamlit su pokrenuti. Admin token je unet (ako je obavezan).

### Korak-po-korak (sretan put)

1. **Setup tabovi – Source upload**
   - Korisnik otvara `Workspace > Setup > Source`.
   - Uploaduje source CSV ili XLSX fajl sa poslovnim podacima.
   - Sistem detektuje layout: ako fajl liči na schema specifikaciju (field-per-row), nudi `Row data` vs `Schema spec` radio izbor.
   - Sistem vraća `SchemaProfile`: lista kolona sa tipovima, null rate-om i sample vrednostima.
   - Korisnik vidi preview profila i potvrđuje.

2. **Setup tabovi – Target upload**
   - Analogno kao source, ali za ciljni sistem.
   - Može biti CSV/XLSX, ali i `.sql` DDL schema dump.
   - Sistem vraća `SchemaProfile` za target.

3. **Run mapping**
   - Korisnik bira `Auto mapping` u Workspace-u.
   - Opciono: čekira `Use LLM validation` za LM Studio/GPT-4 disambiguaciju ambigvitetnih polja.
   - Klika `Run mapping`.
   - Backend pokreće `generate_mapping_candidates()`:
     - Izračunava per-signal score (fuzzy ime, description, tip, knowledge overlay, LLM gate za ambigvitne).
     - Agregira weighted-average score normalizovan na `0..1`.
     - Vraća ranked listu kandidata po svakoj source koloni.

4. **Trust layer review**
   - Korisnik vidi svaki source field sa predloženim target i trust score.
   - Badge: `high_confidence` (≥0.85), `medium_confidence` (≥0.60), `low_confidence` (<0.60).
   - Za svaki red: `Accept`, `Reject`, `Override` (manuelno unese drugi target).
   - Reject → manuelno mapiranje → korisnik bira target iz padajuće liste ili piše custom izraz.
   - Transformacioni expression: `direct copy`, `type cast`, `custom formula` (pandas sintaksa).

5. **Decisions & Save**
   - Korisnik prelazi na `Decisions` tab.
   - Puni metapodatke:
     - `Mapping set name` (npr. `customer-master-sap-to-sf-v1`) – postaje i `integration_name` u Katalogu.
     - `Created by`, `Owner`, `Assignee`.
     - `Version note` (npr. "Inicijalno mapiranje, pilot faza").
     - `Review note` (npr. "Čeka odobrenje od data governance tima").
   - Klika `Save mapping set version`.
   - Sistem kreira mapping set sa statusom `draft`, upisuje audit zapis `create`.

6. **Export / Codegen**
   - Korisnik klika `Generate pandas code`.
   - Sistem generiše Python skriptu sa transformacijama.
   - Korisnik kopira/downloaduje artefakt.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| Source fajl ima neočekivan layout | Sistem predlaže `Schema spec` mode; korisnik bira odgovarajući mode |
| Mnogo low-confidence polja | Korisnik uključuje LLM validation za drugi run |
| LLM timeout | Sistem nastavlja bez LLM za ta polja; korisnik vidi warning badge |
| Korisnik rejektuje > 30% polja | Manuelno mapira; opciono kreira knowledge overlay sa novim aliasima |
| Backend nedostupan | UI prikazuje grešku; korisnik proverava da li je uvicorn aktivan |

### Veza sa epikama
- Epic 1, 2 (Knowledge overlay utiče na scoring)
- Epic 3 (Learning from corrections)
- Epic 4 (Transformation safety)
- Epic 7 (Explainability u trust layer-u)

---

## Dodatak S1 – Scoring i Signal Breakdown (A3, A4, A5)

Ovaj dodatak detaljno objašnjava logiku iz prezentacije (`A3`, `A4`, `A5`) kroz realnu implementaciju u backend-u.
Poenta: scoring je deterministički-first, signalno objašnjiv, i AI je strogo ograničen na ambigvitetne situacije.

### A3 – Kako Semantra računa finalni score

Sistem za svaki par `source_field -> candidate_target` računa signalne komponente, pa ih spaja u jedan normalizovan score.

Signali koji postoje u modelu:

- `name` (lexical)
- `semantic`
- `knowledge`
- `canonical`
- `pattern`
- `statistical`
- `overlap`
- `embedding` (opciono)
- `correction`
- `llm` (opciono, tek nakon LLM validacije)

Default težine (`WEIGHTS`) su:

| Signal | Težina |
|---|---|
| name | 0.20 |
| semantic | 0.12 |
| knowledge | 0.10 |
| canonical | 0.05 |
| pattern | 0.20 |
| statistical | 0.15 |
| overlap | 0.10 |
| embedding | 0.12 |
| correction | 0.10 |
| llm | 0.05 |

Važan detalj: score nije prost zbir svih težina, već weighted-average nad **aktivnim signalima**. To znači da signal koji nije relevantan za dati par ne obara rezultat.

Matematički:

$$
	ext{raw\_score} = \sum_{i \in A} (s_i \cdot w_i)
$$

$$
	ext{final\_score} = \text{clamp}\left(\frac{\text{raw\_score}}{\sum_{i \in A} w_i}, 0, 1\right)
$$

gde je $A$ skup aktivnih signala, $s_i \in [0,1]$ vrednost signala, a $w_i$ njegova težina.

Kako nastaju ključni signali:

1. `name`: kombinacija fuzzy sličnosti normalizovanih naziva i token Jaccard-a.
2. `semantic`: Jaccard preko semantičkih tokena, uključujući synonym/abbreviation ekspanziju.
3. `knowledge`: metadata knowledge alignment (`base + overlay` znanje).
4. `canonical`: alignment na isti canonical koncept.
5. `pattern`: sličnost detektovanih pattern-a vrednosti (email, date, id-shape...).
6. `statistical`: kompatibilnost `unique_ratio`, `null_ratio`, prosečne dužine.
7. `overlap`: preklapanje reprezentativnih sample vrednosti (kada oba skupa postoje).
8. `embedding`: semantička embedding sličnost (samo kada je embedding provider omogućen).
9. `correction`: istorijski signal iz accept/reject/override feedback-a.
10. `llm`: dodaje se samo ako bounded LLM validacija potvrdi kandidat.

Special case za canonical lock:

- Ako kandidat ima jak canonical dokaz (`knowledge >= 0.85` i `canonical >= 0.6` za canonical target), sistem može da izbaci `name` signal, a ponekad i `pattern`, da slabo fizičko ime ne razvodni semantički ispravan canonical match.

### A4 – Kako čitati signal breakdown u Trust layer-u

Signal breakdown nije samo "zašto je score visok", nego i **kakve prirode je dokaz**.

Praktično tumačenje:

1. Visok `name` znači da su nazivi/tokene veoma bliski.
2. Visok `semantic` znači da je poslovno značenje blisko i kad nazivi nisu isti.
3. Visok `knowledge` znači da je rečnik/overlay eksplicitno podržao ovaj match.
4. Visok `canonical` znači da su oba polja poravnata na isti poslovni koncept.
5. Visok `pattern` i `statistical` znači da je data-shape kompatibilan, ne samo naziv.
6. Pozitivan `correction` znači da istorija korisničkih odluka gura ovaj kandidat naviše.
7. Pozitivan `llm` znači da je kandidat dodatno potvrđen u zatvorenom kandidat skupu.

Kako se to vidi u explanation linijama:

- "Field names are lexically very similar."
- "Semantic tokens align after abbreviation expansion and synonym enrichment."
- "Strong canonical concept lock detected..."
- "Sample overlap detected..."
- "Similar past decision influenced this ranking..."
- "LLM validator re-ranked this candidate within the closed candidate set."

Primer čitanja jednog kandidata:

- `name=0.42`, `semantic=0.81`, `knowledge=0.75`, `canonical=0.62`, `pattern=0.40`, `statistical=0.78`, `overlap=0.10`, `correction=0.35`
- Zaključak: ovo nije "name-based" match, već semantičko + canonical + istorijsko pojačanje.

To je ključ A4 poruke: dva kandidata mogu imati sličan final score, ali potpuno različit profil rizika i dokazne snage.

### A5 – Uloga LLM-a: bounded validation, ne full mapper

LLM u Semantra tokovima nije glavni generator mapping-a, već validator u ograničenom opsegu.

Pravila bounded LLM validacije:

1. Radi nad `closed candidate set` (tipično top-k kandidata), ne nad svim target kolonama.
2. Mora vratiti jedan od ponuđenih targeta ili `no_match`.
3. Odgovor mora biti validan JSON sa `selected_target`, `confidence`, `reasoning`.
4. Ako confidence nije dovoljan, rezultat se odbacuje ili ide u `no_match` (rescue fallback).

Kada LLM gate pokušava da se aktivira:

1. Standard ambiguity band: top score je u opsegu `llm_gate_min_score < score < llm_gate_max_score` (default `0.3 < score < 0.75`).
2. Canonical rescue: low-mid scenario gde je kandidat canonical naziv, semantika dovoljno jaka, ali nema knowledge/canonical potpore.
3. Close strong canonical competitor: kod jakog canonical lock-a LLM se uključuje samo ako postoji skoro izjednačen jaki canonical challenger (margina < `0.05`).

Kada se LLM ne koristi:

- ako je mapiranje već jako i neambigvitetno,
- ako nema validnog provider-a,
- ako kandidat set nije smislen za arbitražu.

Bitna operativna posledica:

- LLM može da promeni redosled unutar kandidat skupa, ali ne uvodi proizvoljan target van skupa.
- To čuva deterministički tok i auditabilnost, što je centralna poruka A5 slajda.

### Veza sa workflow-ima

Ovaj scoring model direktno utiče na:

- WF-01 Standard Upload & Mapping (rank + trust review)
- WF-03 Canonical Mapping (canonical lock i canonical rescue)
- WF-07 Learning From Corrections (`correction` signal)
- WF-09 Benchmark (pre/post promena signalnih težina i quality metrika)

---

## WF-02 – Schema Specification Upload

**Opis:** Korisnik ima layout specifikaciju (ne stvarne redove podataka), npr. XLSX tabelu gde svaki red opisuje jedno polje: naziv, tip, opis, obavezan/opcioni. Tipično: ERP migration design fajl, Workday XSD→CSV konverzija, API contract spec.

**Tipični učesnici:** Integration architect, senior BA koji prima spec od vendor-a.

**Preduvjeti:** Fajl ima Layout B format (kolone: `Column`, `Description`, `Type`, `Required`, itd.).

### Korak-po-korak

1. **Upload spec fajla**
   - Korisnik ide na `Workspace > Setup > Source` (ili Target).
   - Uploaduje XLSX/CSV koji je field-per-row specifikacija.
   - Sistem poziva `POST /upload/spec/detect` → vraća confidence da li je to spec layout.
   - Ako confidence ≥ threshold, pojavljuje se radio: `Row data | Schema spec`.
   - Korisnik bira `Schema spec`.
   - Sistem poziva `POST /upload/spec` → parsira jedan `ColumnProfile` po redu, gradi `SchemaProfile`.
   - Prikaz: broj detektovanih polja, nema row preview (Rows = 0), prikazuju se names + opisi.

2. **Downstream isti kao WF-01**
   - Dobijeni `SchemaProfile` ulazi u `POST /mapping/auto` isti kao kod standardnog uploada.
   - Korisnik nastavlja kroz mapping → trust layer → save.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| Sistem nije siguran je li spec ili data | Korisnik dobija radio izbor i odlučuje sam |
| Spec ima nestandardne kolone | Parser uzima dostupne kolone; ostala meta polja se ignorišu |
| `.sql` DDL fajl | Koristi poseban SQL parser tok, ne spec radio |

### Veza sa epikama
- Epic 11 (Schema Specification Upload) – **Completed 2026-05-04**

---

## WF-03 – Canonical Mapping

**Opis:** Umesto da se mapira source direktno na konkretan target fajl, mapira se na kanonski poslovni model (business glossary). Rezultat je: koji poslovni koncepti (Customer, Vendor, Invoice...) su pokriveni u source sistemu i kako.

**Tipični učesnici:** Data governance team, enterprise architect, BA koji radi cross-system semantičku analizu.

**Preduvjeti:** Kanonski rečnik je aktivan u bazi (trenutno: `canonical_glossary_erp.csv`, 463 koncepta).

### Korak-po-korak

1. **Upload source fajla** – analogno WF-01 ili WF-02.

2. **Odabir Canonical mode**
   - Korisnik u Workspace-u bira `Canonical mapping` (umesto `Auto mapping`).
   - Bira `Target system` (npr. `SAP`, `Salesforce`, `Workday`, ili `generic`).
   - Opciono: `Use LLM validation`.
   - Klika `Run canonical mapping`.

3. **Backend tok**
   - `POST /mapping/canonical` poziva `build_virtual_target_schema(target_system)`.
   - Sistem gradi virtualni target iz kanonskog rečnika za dati sistem.
   - `generate_mapping_candidates()` radi source → virtual canonical target.
   - Vraća i `canonical_coverage`: koji koncepti su pokriveni (`matched`), koji nisu (`unmatched_sources`).

4. **Trust layer pregled**
   - Isti UI kao WF-01, ali target kolone su poslovni koncepti iz rečnika, ne fizičke kolone nekog fajla.
   - Vidljivo: source kolona → poslovni koncept (npr. `cust_id` → `Customer.CustomerID`).
   - Coverage metric: `X od Y kanonskih koncepata pokriveno u ovom source-u`.

5. **Save kao canonical artifact**
   - Payload automatski setuje `artifact_type: "canonical-only"`.
   - U Katalogu se može posebno filtrirati po artifact tipu.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| Kanonski rečnik prazan | Backend vraća 400; korisnik mora da unese/aktivira kanonski rečnik |
| Source sistem nema coverage | Rezultat je validan ali `canonical_coverage` nisko; korisnik može da doda aliase kroz Knowledge Overlay |
| LLM gate ne okida | Normalno – LLM se poziva samo za ambigvitetna polja (score 0.4–0.75); jaka poklapanja idu direktno |

### Veza sa epikama
- Epic 5 (Canonical Semantic Layer) – **MVP 2026-05-02, hardening u toku**
- Epic 1, 2 (Knowledge overlay direktno utiče na canonical matching)

---

## WF-04 – Knowledge Overlay Upload i Aktivacija

**Opis:** Admin ili BA želi da doda domenske sinonime, skraćenice ili aliase koji nisu u baznom rečniku – bez menjanja koda ili statičkih fajlova.

**Tipični učesnici:** Domain expert, data steward, senior BA.

**Preduvjeti:** Admin token je unet u Streamlit sidebar.

### Korak-po-korak

1. **Priprema overlay CSV fajla**
   - Format: kolone `canonical_term`, `alias`, `entry_type` (`synonym` / `abbreviation` / `alias`), `domain`, `source_system`, `note`.
   - Primer: `Customer | cust | abbreviation | CRM | SAP | Internal SAP abbreviation`.

2. **Upload u Admin sekciji**
   - Korisnik otvara `Admin > Knowledge Upload`.
   - Uploaduje CSV fajl.
   - Sistem parsira i vraća validation preview:
     - Broj validnih unosa.
     - Duplikati i konflikti sa baznim rečnikom.
     - Nevažeći redovi sa razlogom.

3. **Preview i potvrda**
   - Korisnik pregleda preview tabelu.
   - Može da vidi: `entry_type`, koliko sinonima/skraćenica/aliasa, koji su konflikti.
   - Klika `Confirm & Upload`.

4. **Activate/Deactivate**
   - Sistem kreira novu knowledge verziju sa statusom `inactive`.
   - Korisnik bira verziju i klika `Activate`.
   - Knowledge servis reload-uje combined knowledge = base + active overlay.
   - Indikator u UI pokazuje: `Overlay mode: active (version X)` ili `Base-only mode`.

5. **Rollback**
   - Korisnik može u svakom trenutku da deaktivira overlay i vrati se na base-only.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| CSV ima konflikte sa bazom | Preview prikazuje konflikte; korisnik odlučuje da li da nastavi |
| Nevalidan format kolona | Sistem odbija upload sa listom grešaka po redu |
| Overlay aktivan ali bez efekta | Proveriti `mapping_mode` i da li je knowledge service reloaded |

### Veza sa epikama
- Epic 1 (Knowledge Overlay MVP)
- Epic 2 (Admin Upload UI)

---

## WF-05 – Governance: Status Workflow i Audit

**Opis:** Mapping set kreiran u WF-01/03 prolazi kroz governance lifecycle: `draft → review → approved → archived`. Tim može da prati ko je šta promenio i kada.

**Tipični učesnici:** BA (kreira), reviewer/tech lead (review), data governance owner (approve), arhivista (archive).

**Preduvjeti:** Mapping set je već sačuvan (WF-01 korak 5).

### Korak-po-korak

1. **Pregled sačuvanih mapping setova**
   - Korisnik ide na `Decisions > Load saved mapping sets`.
   - Sistem vraća listu svih verzija sa statusima.
   - Vidljivo: ID, name, version, status, owner, assignee, decision_count.

2. **Pomeranje u review**
   - Korisnik selektuje verziju i bira `Update status → review`.
   - Upisuje `Changed by` i opcioni `Note` (npr. "Prosleđeno tech lead-u na pregled").
   - Sistem upisuje audit zapis: `status_change | draft → review`.

3. **Review i feedback**
   - Reviewer otvara Catalog, pronalazi integraciju, selektuje verziju, klika `Open selected version`.
   - Vidi sve mapping decisions u tabeli.
   - Može da ažurira `review_note` (npr. "3 polja treba revidirati – vidi komentar u Jira-3421").
   - Pomiče status na `approved` ili vraća na `draft`.

4. **Approved → korišćenje**
   - Samo `approved` verzija se smatra produkcionom.
   - (Planirano): Export i run akcije biće blokirane za non-approved verzije (Epic 6 backlog).

5. **Diff između verzija**
   - Korisnik ima v1 i v2 iste integracije.
   - U Catalog drilldown-u bira obe verzije i klika `Load version diff`.
   - Sistem prikazuje: `added_count`, `removed_count`, `changed_count` i tabelu promena po redu.

6. **Audit trail**
   - Klika `Load selected audit`.
   - Vidi hronološki log: ko je kreirao, kada je promenjen status, da li je primenjena (apply) verzija.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| Korisnik pokušava export non-approved verzije | (Planiran) Backend blokira i vraća grešku sa porukom |
| Diff između nekompatibilnih integracija | Backend vraća 400; diff radi samo između verzija iste integration_name |
| Audit log prazan | Verzija je kreirana pre uvođenja audit sloja; normalno ponašanje |

### Veza sa epikama
- Epic 6 (Governance and Versioning) – **Started 2026-05-03**

---

## WF-06 – Catalog: Pretraga i Reuse

**Opis:** Korisnik ne počinje od nule – traži da li je neko u timu već mapirao isti ili sličan sistem. Pronalazi, pregleda, i opciono reuse-uje existing mapping u aktivan Workspace.

**Tipični učesnici:** BA koji kreće novi projekat, integration consultant, governance team.

**Preduvjeti:** Postoje sačuvani mapping setovi u bazi (iz prethodnih WF-01/03 sesija).

### Korak-po-korak

1. **Otvaranje Catalog stranice**
   - Korisnik ide na `Catalog` tab u Streamlit navigaciji.

2. **Pretraga ili Browse**
   - `Search` mode: full-text pretraga po imenu integracije, sistemu, owneru, domenu, kanonskim konceptima.
   - `Browse` mode: lista svih integracija sa filterima (source system, target system, business domain, owner, status, artifact type).
   - Klika `Run catalog query` ili `Load all integrations`.

3. **Pregled rezultata**
   - Tabela sa: `integration_name`, `version`, `status`, `source_system`, `target_system`, `business_domain`, `owner`, `decision_count`, `canonical_concepts`.
   - Korisnik bira integraciju iz dropdown-a i klika `Load detail`.

4. **Integration Detail drilldown**
   - Vidi sve verzije iste integracije (v1, v2, v3...).
   - Metrike: latest version, broj verzija, pokriveni kanonski koncepti, unmatched sources.
   - `latest_approved_version` je posebno istaknuta.
   - Klikovi: `Open selected version`, `Load selected audit`, `Open approved version`.

5. **Mapping set drilldown**
   - Po otvaranju verzije: decision_count, status, owner, assignee, review_note.
   - Tabela svih mapping decisions: source_column → target_column, score, status, transformation.

6. **Reuse u Workspace**
   - Korisnik klika `Reuse in Workspace`.
   - Sistem učitava decisions iz sačuvane verzije kao aktivan review context.
   - Korisnik može da modifikuje i sačuva kao novu verziju (v2, v3...).

7. **Similar integrations**
   - Sistem prikazuje slične integracije rangirane po:
     - Broju zajedničkih kanonskih koncepata.
     - Istom source/target sistemu.
     - Istom business domenu.
   - Korisnik može da otvori sličnu integraciju i poredi.

### Grananje – Problem put

| Situacija | Šta se dešava |
|---|---|
| Nema rezultata | Pretraga je prazna; korisnik menja filter ili pokušava `Load all integrations` |
| Admin token nije unet | Catalog endpointi vraćaju 403; UI prikazuje warning |
| Reuse iz draft verzije | Dozvoljeno; ali korisnik treba da zna da nije approved |

### Veza sa epikama
- Epic 5 (Canonical concepts u catalog search)
- Epic 6 (Status, audit, diff u catalog drilldown)
- Epic 10 (Planiran: batch run iz approved catalog verzije)

---

## WF-07 – Learning From Corrections (Parcijalno implementirano)

**Opis:** Sistem pamti svaku korisnički odbijenu, prihvaćenu ili prepisanu (override) odluku i koristi taj signal pri sledećim mapiranjima da poboljša ranking.

**Status:** Correction store postoji; learning signal je u razvoju (Epic 3).

### Scenario (planirani tok)

1. U Trust layer review-u korisnik odbija predlog (`Reject`) i bira drugi target (`Override`).
2. Sistem upisuje u correction store: `{ source_field, rejected_target, accepted_target, reason, project, timestamp }`.
3. Pri sledećem mapiranju istog source sistema:
   - Ranije odbijeni target dobija penalizaciju u scoring-u.
   - Ranije prihvaćeni target dobija promotion signal.
   - U trust layer-u se prikazuje badge: `"Historical decision influenced ranking"`.
4. Ponavljane korekcije (≥ N potvrda) mogu biti promovisane u reusable rule unutar knowledge overlay-a.

### Grananje

| Situacija | Šta se dešava |
|---|---|
| Korisnik uvek prihvata sve predloge | Correction store ostaje prazan; learning nema efekata |
| Iste korekcije od više korisnika | Snažniji signal; viši confidence u promotion na reusable rule |

### Veza sa epikama
- Epic 3 (Learning From Corrections)

---

## WF-08 – Transformation Preview i Codegen

**Opis:** Nakon odobrenog mapiranja, korisnik želi da dobije izvršivi Python (pandas) kod koji primenjuje sve transformacije iz mapping seta.

**Status:** Codegen i preview su implementirani; transformation test cases su u razvoju (Epic 4).

### Korak-po-korak

1. **Preview**
   - Korisnik u Workspace-u klika `Preview mapping`.
   - Sistem uzima aktivan set decisions i source rows.
   - `build_preview()` primenjuje transformacije na sample redove.
   - Prikaz: before/after tabela po koloni; warnings za null expansion, type coercion, row-count mismatch.

2. **Codegen**
   - Korisnik klika `Generate pandas code`.
   - `generate_pandas_code()` gradi Python skriptu sa `df[...] = ...` izrazima.
   - Korisnik kopira ili downloaduje skriptu.

3. **Planirano: Dry-run i test cases (Epic 4)**
   - Syntax validation generisanog koda pre prikazivanja korisniku.
   - Dry-run nad punim sample datasetom.
   - Transformation test cases: korisnik definiše input row → expected output row par.
   - Risk badge po transformaciji: `direct`, `safe`, `risky`, `custom`.

### Veza sa epikama
- Epic 4 (Transformation Safety and Testing)

---

## WF-09 – Benchmark i Quality Analytics (U razvoju)

**Opis:** Tim želi da meri kako promene u knowledge overlay-u ili scoring konfiguraciji utiču na kvalitet mapiranja – bez ručnog poređenja.

**Status:** Osnova postoji; dashboards su u razvoju (Epic 8).

### Planirani scenario

1. Korisnik kreira benchmark case za konkretni dataset: definiše "zlatni standard" mapiranja (ručno verifikovana odluka).
2. Posle svake promene knowledge overlay-a ili scoring weight-a, pokreće benchmark run.
3. Sistem prikazuje: pre/post score po polju, acceptance rate, correction rate, average confidence.
4. Export benchmark report-a za dokumentaciju i prezentacije.

### Veza sa epikama
- Epic 8 (Benchmark and Quality Analytics)

---

## WF-10 – Operationalization / Export (Planirano)

**Opis:** Finalni korak u delivery toku – approved mapping set se pakuje u artefakt koji može da se koristi u ETL, SQL ili dbt procesu.

**Status:** Planiran (Epic 10).

### Planirani scenario

1. Korisnik otvara approved mapping set iz Kataloga.
2. Bira export format: `pandas job`, `SQL mapping spec`, `dbt model`.
3. Sistem generiše artifact fajl.
4. Opciono: batch run nad celim production datasetom.
5. Webhook/API trigger za automatsko pokretanje pri novom uploadu source fajla.
6. Run history: svaki run se loguje sa statusom, trajanjem, brojem transformisanih redova.

### Veza sa epikama
- Epic 10 (Operationalization)
- Epic 6 (Uslov: samo approved verzije mogu da se pokreću)

---

## Pregled statusa svih workflow-a

| Workflow | Status | Ključna epika |
|---|---|---|
| WF-01 Standard Upload & Mapping | ✅ Implementirano | Epic 1, 3, 4, 7 |
| WF-02 Schema Spec Upload | ✅ Implementirano | Epic 11 |
| WF-03 Canonical Mapping | ✅ MVP | Epic 5 |
| WF-04 Knowledge Overlay Upload | ✅ MVP | Epic 1, 2 |
| WF-05 Governance Status & Audit | 🔄 U toku | Epic 6 |
| WF-06 Catalog Pretraga i Reuse | ✅ Implementirano | Epic 5, 6 |
| WF-07 Learning From Corrections | ⬜ Parcijalno | Epic 3 |
| WF-08 Transformation Preview & Codegen | 🔄 Delimično | Epic 4 |
| WF-09 Benchmark & Quality Analytics | ⬜ U razvoju | Epic 8 |
| WF-10 Operationalization / Export | ⬜ Planirano | Epic 10 |

---

*Poslednje ažuriranje: 2026-05-07*
