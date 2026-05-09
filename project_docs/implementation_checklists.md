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

Status: source companion enrichment slice implemented and smoke-validated on 2026-05-09; deterministic score fusion remains deferred pending benchmark evidence.

MVP scope:

- [x] Dodati u `ColumnProfile` najmanje `description` i `declared_type` kao first-class polja.
- [x] Popraviti spec upload tako da `description_col` ide u `description`, a ne da utiče na `normalized_name`.
- [x] Dodati opcioni companion-spec upload samo za source stranu kao prvi slice.
- [x] Vezati companion spec za postojeći dataset handle po nazivu kolone i dopuniti aktivni `SchemaProfile` bez menjanja osnovnog `POST /mapping/auto` contract-a.
- [x] Proširiti LLM validator payload da za source i top target kandidate šalje `description`, `declared_type`, `sample_values` i `detected_patterns` kada su dostupni.
- [x] Zadržati heuristic-only fallback: ako description/context nije dostupan, postojeći mapping tok mora ostati funkcionalno isti.

MVP nije:

- puni document-ingestion ili free-form metadata parser
- obavezni companion schema fajl za svaki row-data upload
- redesign celog persistence modela ili catalog modela u istoj iteraciji

Implementacioni checklist po fajlovima:

- `backend/app/models/schema.py`
  - [x] Dodati `description: str = ""` i `declared_type: str = ""` u `ColumnProfile`.
  - [x] Zadržati backward-compatible default vrednosti da stari upload payload-i i test fixture-i ostanu validni.
- `backend/app/services/spec_upload_service.py`
  - [x] Mapirati `description_col` u `ColumnProfile.description`.
  - [x] Mapirati sirovi tip iz specifikacije u `ColumnProfile.declared_type`, dok `dtype` ostaje normalizovan runtime tip za postojeći engine.
  - [x] Vratiti `normalized_name` na normalizaciju stvarnog naziva kolone, umesto description-derived vrednosti.
  - [x] Ako specifikacija sadrži primer vrednosti, predvideti uski parser hook koji ih puni u `sample_values` bez širenja MVP scope-a.
- `backend/app/services/upload_store.py`
  - [x] Dodati helper za merge companion metadata nad već snimljenim `SchemaProfile` objektom po `column.name` ključu.
  - [x] Obezbediti da merge ne menja `dataset_id`, preview rows ni postojeći row-data contract.
- `backend/app/api/routes/upload.py`
  - [x] Dodati source-side opcioni companion spec put ili proširenje postojećeg upload flow-a tako da row-data dataset može naknadno da primi schema metadata enrichment.
  - [x] Validirati da companion spec može da se veže samo ako postoji jasno poklapanje naziva kolona ili eksplicitno prijaviti nepoklopljena polja.
  - [x] Zadržati postojeći `/upload`, `/upload/handle`, `/upload/spec`, `/upload/spec/detect` behavior kao kompatibilan fallback kada enrichment nije poslat.
- `backend/app/services/mapping_service.py`
  - [x] Proširiti LLM validator input payload da source/target candidate kontekst uključuje `description` i `declared_type` kada postoje.
  - [x] Proširiti explanation trag ili decision log tako da bude jasno kada je description-aware context uticao na LLM odluku.
  - [x] Ne uvoditi novi heuristički signal u prvom koraku osim ako benchmark pokaže da description treba i deterministic scoring tretman.
  - [x] Zadržati odluku da `description` i `declared_type` ostanu LLM/context sloj dok ne postoji benchmark corpus koji pokazuje da deterministic scoring poboljšava kvalitet bez regressions.
- `backend/app/services/llm_service.py`
  - [x] Proširiti `build_validator_prompt()` i `build_transformation_generator_prompt()` da prihvate field description i declared type.
  - [x] Dodati prompt guardrails: truncation/selection pravila za sample values i description tekst.
  - [x] Zadržati closed-set pravilo i postojeći JSON contract kao stabilan output format.
- `streamlit_ui/api.py`
  - [x] Dodati klijentsku podršku za opciono slanje source companion schema fajla i/ili naknadnog enrichment poziva.
  - [x] Obezbediti da postojeći upload tok bez companion fajla ostane nepromenjen.
- `streamlit_ui/workspace_views.py`
  - [x] Dodati minimalistički UI hook za opcioni source companion schema/spec upload u Setup toku.
  - [x] Prikazati kratku potvrdu koliko kolona je enrichment-ovano i koliko ih nije upareno.
- `backend/tests/*` i `tests/*`
  - [x] Dodati fokusirane testove za schema model backward compatibility.
  - [x] Dodati test za spec upload koji čuva `description` odvojeno od `normalized_name`.
  - [x] Dodati test za row-data + companion spec merge i za LLM payload enrichment bez loma starog contract-a.
  - [x] Potvrditi lokalni browser smoke za source row-data + companion spec Setup tok i rerun canonical mapping-a.

API promene za MVP:

- [x] Zadržati postojeći `POST /upload/spec` response shape, ali obogatiti `SchemaProfile.columns[*]` novim metadata poljima.
- [x] Uvesti jedan uski source-side enrichment put umesto velikog redesign-a.
- [ ] Izabrati jednu od dve opcije:
  - [ ] proširenje `POST /upload/handle` sa opcionim companion spec fajlom za source dataset
  - [x] ili novi tanak endpoint tipa `POST /upload/handle/metadata` koji enrich-uje već uploadovan dataset po `dataset_id`
- [x] `POST /mapping/auto`, `POST /mapping/canonical` i `POST /mapping/transformation/generate` ne treba da menjaju spoljašnji contract u prvom slice-u.
- [x] Streamlit upload klijent treba da ostane backward-compatible: bez companion fajla šalje isti payload kao danas.

Validation note:

- Lokalni browser smoke na `http://127.0.0.1:8501` potvrđen za source row-data + source companion spec tok: enrichment `3/3` matched, zatim canonical mapping završen bez loma Setup/Review flow-a.
- Deterministic scoring ostaje nepromenjen: u trenutnom engine-u `compute_signals()` već ima stabilan fusion za knowledge/canonical/pattern/statistics, dok description/type trenutno najbolje služe kao closed-set LLM tie-break context za kratke ili višeznačne enterprise nazive.

### Epic 14E: Canonical Gap Assistant

Status: initial MVP implemented; pending real UI/LLM validation and candidate enrichment.

Problem koji rešava:

- Mapping može biti ispravan, ali `canonical_path` ostaje prazan jer canonical glossary nema odgovarajući concept ili alias.
- Primer: `NTGEW -> net_weight` može imati jak knowledge/semantic match, ali bez `material.net_weight` canonical concept-a nema pun canonical path.
- Cilj je da Semantra tokom review-a sama prepozna takve rupe i predloži kontrolisanu dopunu canonical/knowledge sloja.

MVP scope:

- [x] Dodati backend helper koji iz `AutoMappingResponse` izdvaja `canonical_gap_candidates`.
- [x] Kandidat uključuje `source`, `target`, `confidence`, `signals`, `explanation` i postojeće canonical details.
- [ ] Obogatiti kandidata sa `sample_values`, `detected_patterns` i najbližim canonical concepts u samom response payload-u, ne samo u LLM suggestion koraku.
- [x] Definisati threshold pravila za gap kandidat, npr. target postoji, confidence >= 0.65 ili knowledge/semantic jak, a `shared_concepts`/`canonical_path` su prazni.
- [x] Dodati LLM prompt za canonical gap suggestion sa strogim JSON outputom.
- [x] LLM output treba da podrži tri ishoda: `existing_concept_alias`, `new_canonical_concept`, `no_action`.
- [x] LLM ne sme direktno da menja base glossary; rezultat ide u review queue.
- [x] Dodati Streamlit UI panel za `Canonical Gap Suggestions` u Review toku.
- [ ] Mirror-ovati/premestiti queue u buduću Canonical Console/Admin toku.
- [x] Omogućiti approve predloga i upis approved stavki u overlay/canonical alias sloj.
- [ ] Dodati eksplicitan reject/ignore state za predloge, pored `no_action` i neodobravanja.
- [x] Posle approve akcije prikazati jasan re-run mapping hint da korisnik vidi popunjen `canonical_path`.

Prompt guardrails:

- [x] Slati LLM-u samo top relevantne postojeće canonical concepts, ne ceo glossary.
- [x] Tražiti kratak reasoning: zašto postojeći concept odgovara ili zašto je potreban novi concept.
- [x] Zabraniti izmišljanje source/target kolona koje nisu u payload-u.
- [x] Zahtevati `confidence` i `risk_notes` za svaki predlog.
- [x] Ako je predlog generički ili nesiguran, vratiti `no_action`.

Implementacioni checklist po fajlovima:

- `backend/app/models/mapping.py`
  - [x] Dodati modele za `CanonicalGapCandidate`, `CanonicalGapSuggestion`, `CanonicalGapSuggestionRequest/Response`.
- `backend/app/services/mapping_service.py` ili novi `canonical_gap_service.py`
  - [x] Implementirati extraction helper za gap candidates iz mapping response-a.
  - [x] Dodati ranking najbližih canonical concepts po target/source tokenima i signalima za LLM suggestion kontekst.
  - [ ] Izložiti nearest concepts i enrichment polja u candidates API response-u za UI pregled bez LLM poziva.
- `backend/app/services/llm_service.py`
  - [x] Dodati `call_canonical_gap_assistant()` sa closed JSON contract-om.
  - [x] Klasifikovati invalid JSON / hallucinated concept / low-confidence predloge kao rejected/no-action suggestion, ne runtime crash.
- `backend/app/api/routes/knowledge.py` ili nova uska ruta
  - [x] Dodati endpoint za generisanje canonical gap suggestions.
  - [x] Dodati endpoint za approve i persistovanje approved alias/concept predloga.
  - [ ] Dodati reject endpoint ili persisted reject/ignore audit ako realni review tok pokaže potrebu.
- `streamlit_ui/workspace_review_views.py` ili `admin_views.py`
  - [x] Prikazati redove sa praznim `canonical_path` kao gap candidates.
  - [x] Dodati dugme `Suggest canonical concept` po redu.
  - [x] Prikazati LLM proposal u compact review formi: proposed action, concept id, display name, aliases, reasoning, confidence, risk notes.
  - [ ] Dodati batch suggestion/approval tek nakon realnog single-row UI testiranja.
- `backend/tests/*` i `tests/*`
  - [x] Testirati extraction za slučaj `NTGEW -> net_weight` bez shared canonical concept-a.
  - [ ] Testirati da LLM suggestion ne prihvata hallucinated target/source.
  - [x] Testirati approve flow koji upisuje concept alias u overlay i refresh-uje canonical matcher.
  - [ ] Dodati browser/UI smoke test za Review panel kada dev server bude stabilno pokrenut.

MVP nije:

- automatski update `metadata_dict/canonical_glossary_erp.csv`
- masovno generisanje ontology-ja iz celog dataset-a bez review-a
- uklanjanje deterministic canonical matcher-a

### Epic 14F: Canonical Concept Management Console

Status: proposed next slice after 14E validation.

Cilj:

- Napraviti centralnu konzolu za canonical concepts, aliase, gap suggestions i overlay lifecycle.
- Konzola treba da bude korisna za EA, MDM i integration timove: jedan pregled gde se vidi šta je canonical model, gde se koristi i šta čeka review.

MVP scope:

- [ ] Dodati `Canonical Console` kao zaseban Streamlit tab ili jasno odvojenu Admin subsection.
- [ ] Dodati backend read endpoint za concept registry: concept id, entity, attribute, display name, data type, aliases, source `base/overlay`, usage count ako postoji.
- [ ] Dodati concept detail endpoint/panel: aliases, overlay entries, field contexts, linked mapping sets/catalog integrations, audit entries.
- [ ] Premestiti ili mirror-ovati `Canonical Gap Suggestions` queue iz Review taba u Canonical Console.
- [ ] Omogućiti approve/reject iz konzole uz postojeći overlay-first persist pristup.
- [ ] Prikazati aktivni overlay status i entry breakdown uz concept-centric filter.
- [ ] Dodati search/filter po concept id-u, display name-u, aliasu, domain/entity i source system-u.
- [ ] Dodati lightweight impact preview: pre approve-a prikazati koje trenutne mapping/gap redove bi novi alias ili concept mogao da popravi.

Governance pravila:

- [ ] Base glossary import/export ostaje admin operacija; konzola radi overlay-first za dnevni review.
- [ ] LLM može da predlaže, ali samo korisnik odobrava persist.
- [ ] Novi concept i alias moraju imati audit trail: ko je odobrio, kada, iz kog mapping/gap konteksta.
- [ ] Za promotion iz overlay-ja u stable glossary tražiti poseban status ili ručnu export/import odluku.
- [ ] Concept merge/rename ostaviti van prvog MVP-a ili tretirati kao proposal bez automatske primene.

Implementacioni checklist po fajlovima:

- `backend/app/models/knowledge.py`
  - [ ] Dodati response modele za concept registry row, concept detail i concept usage summary.
- `backend/app/services/metadata_knowledge_service.py`
  - [ ] Dodati read helper koji vraća canonical concepts sa aliasima i overlay/source informacijom.
  - [ ] Dodati helper za concept detail i alias lookup.
- `backend/app/services/persistence_service.py`
  - [ ] Iskoristiti postojeće mapping catalog i knowledge audit tabele za usage/audit prikaz.
  - [ ] Ne uvoditi novi write model dok overlay-first approve tok ne pokaže gde su stvarne rupe.
- `backend/app/api/routes/knowledge.py`
  - [ ] Dodati `GET /knowledge/canonical-concepts` i `GET /knowledge/canonical-concepts/{concept_id}`.
  - [ ] Dodati opcioni query/filter parametar za alias/domain/source/system.
- `streamlit_ui/admin_views.py` ili novi `streamlit_ui/canonical_console_views.py`
  - [ ] Izvući canonical glossary i overlay UI iz debug osećaja u product-style console.
  - [ ] Prikazati concept registry tabelu, detail panel i gap review queue.
  - [ ] Dodati approve/reject akcije iz iste konzole.
- `backend/tests/*` i `tests/*`
  - [ ] Testirati registry endpoint sa base concept-ima i active overlay aliasima.
  - [ ] Testirati concept detail za overlay-only concept nastao iz Canonical Gap Assistant-a.
  - [ ] Testirati da console read endpoint ne menja runtime state.

MVP nije:

- kompletan ontology/semantic graph editor
- complex stewardship workflow sa više approval nivoa
- automatski merge/rename canonical concepts
- zamena Enterprise Integration Catalog-a; konzola treba da linkuje catalog usage, ne da ga duplira

## Release Readiness Checklist

## Post-Beta Operational Hardening Checklist

### Mapping progress jobs

Status: future hardening.

- [ ] Zadržati trenutni in-memory/thread mapping job progress kao lagan lokalni/demo UX sloj dok je opterećenje malo.
- [ ] Pre multi-user/production režima zameniti ili dopuniti job store persistent queue/status backend-om (`Redis/RQ/Celery` ili ekvivalent).
- [ ] Dodati TTL cleanup za završene/failed jobove i limit za broj aktivnih jobova po procesu ili korisniku.
- [ ] Definisati cancel/retry semantiku za duge mapping i batch run procese.
- [ ] Izmeriti polling overhead i latenciju na većim schema parovima pre release odluke.

### Beta -> v1 release-readiness

- [ ] Proći bar 1-2 realna source/target scenarija end-to-end i zabeležiti gde mapping, trust layer ili transformacije pucaju.
- [ ] Zatvoriti preostali `Epic 6` status gate za export/run akcije nad `approved` mapping setovima.
- [ ] Završiti bar prvi praktični slice iz `Epic 9` nad data-quality signalima koji direktno pomažu review-u.
- [ ] Potvrditi da ključni backend i Streamlit regression subset prolazi stabilno pre svake demo/pilot isporuke.
- [ ] Odigrati kratko UX i docs poliranje na osnovu realnog pilot toka, ne samo synthetic fixture-a.
- [ ] Imati jedan jasan pilot narrative: upload -> mapping -> review -> preview -> export, bez ručne intervencije van standardnog toka.