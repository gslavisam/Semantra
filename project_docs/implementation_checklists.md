# Semantra Implementation Checklists

Ovaj dokument drži radne checkliste.

- Aktivni MVP checklists po epicima
- Release-readiness checklist
- Implementacioni detalji koji su previše operativni za `epics.md`

Strateški plan je u `plan.md`.
Epic backlog je u `epics.md`.
Završeni slice-ovi su u `completed_slices.md`.

## Active Epic Checklists

### Epic 6: Governance and Versioning MVP

Status: active.

- [x] Proširiti model mapping seta sa `owner` / `assignee` poljima na nivou celog mapping seta.
- [x] Dodati `review_note` ili `comment` na nivou mapping set verzije.
- [x] Zadržati i učiniti eksplicitnim status workflow: `draft`, `review`, `approved`, `archived`.
- [ ] Dodati backend pravilo da export/run akcije mogu da koriste samo `approved` mapping set ili da eksplicitno prijave blokadu.
- [x] Dodati audit zapis za kreiranje verzije, promenu statusa i primenu sačuvane verzije.
- [x] Dodati jednostavan diff između dve verzije mapping seta: added, removed, changed source-target-status-transformation odluke.
- [x] Prikazati diff i audit u Streamlit UI bez menjanja osnovnog review toka.
- [x] Pokriti status gate i version diff fokusiranim backend testovima.

Van prvog MVP opsega:

- komentar po svakom pojedinačnom mapping redu
- approval workflow sa više koraka ili više reviewer-a
- fina row-level ownership pravila
- puna governance pravila nad transformation test case-ovima i release paketima

### Epic 13: Enterprise Integration Catalog MVP

Status: active.

- [x] 13A backend/persistence slice završen
- [x] 13B read API slice u funkcionalnom početnom obliku
- [x] 13C Streamlit catalog UI početni slice završen
- [ ] 13D concept and visual discovery slice završen

Otvoreni rad za 13D:

- [ ] Dodati concept-centric view: gde je isti canonical concept već mapiran kroz različite integracije.
- [ ] Dodati bar jedan vizuelni pregled višeg nivoa, na primer source-system -> target-system matrix ili grouped canonical coverage pregled.
- [ ] Dodati osnovne reuse hint-ove tipa similar approved integration exists kada dve integracije dele značajan canonical footprint.
- [ ] Prikazati ponavljane unmatched ili low-confidence canonical gap-ove kao input za glossary/knowledge rad.

### Epic 14D: Description-aware LLM Context and Companion Schema Ingestion

Status: proposed MVP checklist.

MVP scope:

- [ ] Dodati u `ColumnProfile` najmanje `description` i `declared_type` kao first-class polja.
- [ ] Popraviti spec upload tako da `description_col` ide u `description`, a ne da utiče na `normalized_name`.
- [ ] Dodati opcioni companion-spec upload samo za source stranu kao prvi slice.
- [ ] Vezati companion spec za postojeći dataset handle po nazivu kolone i dopuniti aktivni `SchemaProfile` bez menjanja osnovnog `POST /mapping/auto` contract-a.
- [ ] Proširiti LLM validator payload da za source i top target kandidate šalje `description`, `declared_type`, `sample_values` i `detected_patterns` kada su dostupni.
- [ ] Zadržati heuristic-only fallback: ako description/context nije dostupan, postojeći mapping tok mora ostati funkcionalno isti.

MVP nije:

- puni document-ingestion ili free-form metadata parser
- obavezni companion schema fajl za svaki row-data upload
- redesign celog persistence modela ili catalog modela u istoj iteraciji

Implementacioni checklist po fajlovima:

- `backend/app/models/schema.py`
  - [ ] Dodati `description: str = ""` i `declared_type: str = ""` u `ColumnProfile`.
  - [ ] Zadržati backward-compatible default vrednosti da stari upload payload-i i test fixture-i ostanu validni.
- `backend/app/services/spec_upload_service.py`
  - [ ] Mapirati `description_col` u `ColumnProfile.description`.
  - [ ] Mapirati sirovi tip iz specifikacije u `ColumnProfile.declared_type`, dok `dtype` ostaje normalizovan runtime tip za postojeći engine.
  - [ ] Vratiti `normalized_name` na normalizaciju stvarnog naziva kolone, umesto description-derived vrednosti.
  - [ ] Ako specifikacija sadrži primer vrednosti, predvideti uski parser hook koji ih puni u `sample_values` bez širenja MVP scope-a.
- `backend/app/services/upload_store.py`
  - [ ] Dodati helper za merge companion metadata nad već snimljenim `SchemaProfile` objektom po `column.name` ključu.
  - [ ] Obezbediti da merge ne menja `dataset_id`, preview rows ni postojeći row-data contract.
- `backend/app/api/routes/upload.py`
  - [ ] Dodati source-side opcioni companion spec put ili proširenje postojećeg upload flow-a tako da row-data dataset može naknadno da primi schema metadata enrichment.
  - [ ] Validirati da companion spec može da se veže samo ako postoji jasno poklapanje naziva kolona ili eksplicitno prijaviti nepoklopljena polja.
  - [ ] Zadržati postojeći `/upload`, `/upload/handle`, `/upload/spec`, `/upload/spec/detect` behavior kao kompatibilan fallback kada enrichment nije poslat.
- `backend/app/services/mapping_service.py`
  - [ ] Proširiti LLM validator input payload da source/target candidate kontekst uključuje `description` i `declared_type` kada postoje.
  - [ ] Proširiti explanation trag ili decision log tako da bude jasno kada je description-aware context uticao na LLM odluku.
  - [ ] Ne uvoditi novi heuristički signal u prvom koraku osim ako benchmark pokaže da description treba i deterministic scoring tretman.
- `backend/app/services/llm_service.py`
  - [ ] Proširiti `build_validator_prompt()` i `build_transformation_generator_prompt()` da prihvate field description i declared type.
  - [ ] Dodati prompt guardrails: truncation/selection pravila za sample values i description tekst.
  - [ ] Zadržati closed-set pravilo i postojeći JSON contract kao stabilan output format.
- `streamlit_ui/api.py`
  - [ ] Dodati klijentsku podršku za opciono slanje source companion schema fajla i/ili naknadnog enrichment poziva.
  - [ ] Obezbediti da postojeći upload tok bez companion fajla ostane nepromenjen.
- `streamlit_ui/workspace_views.py`
  - [ ] Dodati minimalistički UI hook za opcioni source companion schema/spec upload u Setup toku.
  - [ ] Prikazati kratku potvrdu koliko kolona je enrichment-ovano i koliko ih nije upareno.
- `backend/tests/*` i `tests/*`
  - [ ] Dodati fokusirane testove za schema model backward compatibility.
  - [ ] Dodati test za spec upload koji čuva `description` odvojeno od `normalized_name`.
  - [ ] Dodati test za row-data + companion spec merge i za LLM payload enrichment bez loma starog contract-a.

API promene za MVP:

- [ ] Zadržati postojeći `POST /upload/spec` response shape, ali obogatiti `SchemaProfile.columns[*]` novim metadata poljima.
- [ ] Uvesti jedan uski source-side enrichment put umesto velikog redesign-a.
- [ ] Izabrati jednu od dve opcije:
  - [ ] proširenje `POST /upload/handle` sa opcionim companion spec fajlom za source dataset
  - [ ] ili novi tanak endpoint tipa `POST /upload/handle/metadata` koji enrich-uje već uploadovan dataset po `dataset_id`
- [ ] `POST /mapping/auto`, `POST /mapping/canonical` i `POST /mapping/transformation/generate` ne treba da menjaju spoljašnji contract u prvom slice-u.
- [ ] Streamlit upload klijent treba da ostane backward-compatible: bez companion fajla šalje isti payload kao danas.

## Release Readiness Checklist

### Beta -> v1 release-readiness

- [ ] Proći bar 1-2 realna source/target scenarija end-to-end i zabeležiti gde mapping, trust layer ili transformacije pucaju.
- [ ] Zatvoriti preostali `Epic 6` status gate za export/run akcije nad `approved` mapping setovima.
- [ ] Završiti bar prvi praktični slice iz `Epic 9` nad data-quality signalima koji direktno pomažu review-u.
- [ ] Potvrditi da ključni backend i Streamlit regression subset prolazi stabilno pre svake demo/pilot isporuke.
- [ ] Odigrati kratko UX i docs poliranje na osnovu realnog pilot toka, ne samo synthetic fixture-a.
- [ ] Imati jedan jasan pilot narrative: upload -> mapping -> review -> preview -> export, bez ručne intervencije van standardnog toka.