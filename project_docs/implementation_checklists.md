# Semantra Implementation Checklists

Ovaj dokument je primarno mesto za izvršni redosled aktivnog rada.

Drži samo aktivne ili neposredno relevantne izvršne checkliste.

Ne koristi se za:

- istoriju isporuke
- opšti backlog pregled
- snapshot opis trenutnog stanja

Za to služe `completed_slices.md`, `epics.md` i `current_state.md`.

## Aktivne checkliste

Poslednji završeni execution wave-ovi i stariji delivery detalji prate se u `completed_slices.md`.

Ovaj dokument sada služi kao operativni tracker za aktuelnih 7 otvorenih pravaca.

Trenutno izabrani naredni portfolio fokus:

- `Session continuity / draft session model` kao sledeći discovery/design wave
- `Operational hardening nad ključnim pilot tokovima` kao stalni paralelni execution tok

## Operativni protokol po pravcu

Za svaki pravac radimo istim redosledom:

1. proveriti trenutno stanje u kodu, dokumentaciji i testovima
2. definisati uzak plan aktivnosti za sledeći slice
3. realizovati slice uz fokusiranu validaciju
4. ažurirati `current_state.md`, `completed_slices.md` i ovaj dokument kada se zatvori značajan talas

## Trenutni operativni tracker

### 1. Produktizacija bounded guidance površina

Status: pilot-validated; carry-forward only if new browser smoke or pilot runs expose drift.

Napomena:

- glavni guidance paneli postoje, ali naming, unlock poruke i user journey još nisu potpuno ujednačeni
- već isporučene površine ne treba ponovo izmišljati; fokus je produktizacija i pilot signal

Operativna matrica trenutnog stanja:

| Surface | Area | Panel noun | Header detail | Unlock / prerequisite | Primary action label | Success message | Empty / locked state | User-journey role | Output shape |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Mapping Analysis Overview` | `Workspace > Review` | `Overview` | `LLM` / `Fallback` | current workspace mapping state must exist | `Generate mapping overview` / `Refresh mapping overview` | `Generated mapping analysis overview for the current review state.` | `No mapping overview has been generated yet. Use this panel to create a technical readout of the current mapping state.` | pre-row technical readout before trust-layer drilldown | health metrics, summary, strongest matches, risks, next actions, optional narration/audio |
| `Review Queue Plan` | `Workspace > Review` | `Plan` | `LLM` / `Fallback` | filtered review set must exist | `Generate review plan` / `Refresh review plan` | `Generated review queue plan for the current review set.` | `No review queue plan has been generated yet for the current filters.` | queue-order planning before row-level decision changes | queue summary, cluster rows, risks, next actions |
| `Gap Queue Summary` | `Workspace > Review` | `Summary` | `LLM` / `Fallback` | canonical gap candidates must already be loaded | `Generate gap summary` / `Refresh gap summary` | `Generated gap queue summary for the current canonical-gap queue.` | locked: `Run 'Find canonical gaps' first to unlock the queue-level summary.`; empty: `No queue-level canonical-gap triage summary has been generated yet.` | queue-level triage before candidate-by-candidate canonical gap review | triage summary, grouped rows, risks, next actions |
| `Benchmark Explanation` | `Benchmarks` | `Explanation` | `LLM` / `Fallback` | loaded benchmark evidence: benchmark result, correction impact, or profile comparison | `Generate benchmark explanation` / `Refresh benchmark explanation` | `Generated benchmark explanation for ...` | locked: `Run a benchmark, correction-impact check, or scoring-profile comparison first to unlock benchmark explanation.`; empty: `No benchmark explanation has been generated yet for the loaded benchmark evidence.` | bounded readout before changing scoring assumptions | summary, key findings, risks, next actions |
| `Workspace Reuse Fit` | `Catalog` | `Fit` | `fit label + LLM/Fallback` | selected catalog version must be opened for fit review and current workspace snapshot must exist | `Generate reuse-fit explanation` / `Refresh reuse-fit explanation` | `Generated workspace reuse-fit explanation for the selected catalog mapping set.` | locked: `Open the selected catalog version first to unlock reuse-fit review against the current workspace snapshot.`; empty: `No workspace reuse-fit explanation has been generated yet for the selected version.` | bounded reuse assessment before `Reuse in Workspace` | fit metrics, summary, key matches, risks, next actions |

Rezime matrice posle pet productization slice-ova:

- header detail pattern je sada ujednačen na `LLM` / `Fallback`, uz dodatni `fit label` samo tamo gde `Workspace Reuse Fit` to stvarno traži
- `Benchmark Explanation` i `Workspace Reuse Fit` više ne mešaju `summary` i `explanation` u action i empty-state copy-ju
- success/error poruke su poravnate na obrazac `Generated ...` / `... generation failed: ...` kroz svih pet guidance panela
- caption/unlock copy je poravnat tako da read-only uloga i unlock uslov budu eksplicitni i konzistentni kroz `Workspace`, `Benchmarks` i `Catalog`
- output-section heading pattern je poravnat na isti vizuelni obrazac kroz `Workspace`, `Benchmarks` i `Catalog`, uz zadržanu domen-specifičnu terminologiju (`Key matches`, `Key findings`, `Risks`, `Next actions`)
- generation metadata više ne koristi poseban metric tretman u `Catalog`, već isti caption obrazac kao `Workspace` i `Benchmarks`
- `Workspace` paneli i dalje koriste različite panel noun-ove po nameni (`Overview`, `Plan`, `Summary`), što je ispravno jer označava različitu vrstu guidance-a
- browser-level smoke je potvrđen nad živim lokalnim stack-om za `Benchmark Explanation`, `Workspace Reuse Fit`, `Mapping Analysis Overview`, `Review Queue Plan` i `Gap Queue Summary`, uključujući unlock/discoverability stanja

Preostale razlike koje još imaju smisla za sledeći UX slice:

- `Mapping Analysis Overview` i dalje ima dodatni audio podtok koji ga prirodno odvaja od ostalih guidance panela i treba ga tretirati kao kontrolisani izuzetak, ne kao bug
- sledeći rad za ovaj pravac više nije mali UI copy slice, već eventualni follow-up samo ako novi pilot smoke prijavi realan drift

Izabrani sledeći mali UX slice iz matrice:

- bounded guidance pravac je zatvoren za trenutni wave; sledeći aktivni execution fokus prelazi na `Epic 13D` ili `Operational hardening`

- [x] Potvrditi trenutno stanje i granice između `Mapping Analysis Overview`, `Review Queue Plan`, `Gap Queue Summary`, `Benchmark Explanation` i `Workspace Reuse Fit`.
- [x] Isporučiti prvi guidance productization slice: uskladiti summary/generation labeling i read-only messaging za `Benchmark Explanation` i `Workspace Reuse Fit`.
- [x] Isporučiti drugi guidance productization slice: standardizovati guidance header detail pattern na `LLM` / `Fallback` kroz `Workspace`, `Benchmarks` i `Catalog` guidance panele.
- [x] Napraviti operativnu matricu naming/unlock/user-journey razlika između `Workspace`, `Benchmarks` i `Catalog`.
- [x] Izabrati sledeći najmanji slice za ujednačavanje guidance UX-a i validacije pilot vrednosti.
- [x] Isporučiti treći guidance productization slice: poravnati panel noun copy u `Benchmark Explanation` i `Workspace Reuse Fit` action/empty-state tekstovima.
- [x] Isporučiti četvrti guidance productization slice: poravnati success/error copy obrazac na `Generated ...` i `... generation failed: ...` kroz svih pet guidance panela.
- [x] Isporučiti peti guidance productization slice: poravnati caption/unlock copy za read-only guidance role kroz `Workspace`, `Benchmarks` i `Catalog`.
- [x] Isporučiti šesti guidance productization slice: poravnati output-section heading pattern i metadata presentation kroz `Workspace`, `Benchmarks` i `Catalog`.
- [x] Preći na browser-level bounded guidance pilot proveru i zabeležiti rezultat.

### 2. Session continuity and resume-by-design

Status: selected next discovery/design focus.

Napomena:

- ovo je izabrani sledeći produktni pravac jer najviše utiče na stvarnu svakodnevnu upotrebljivost Semantre kroz duže BA radne tokove
- ovo još nije implementacioni wave; prvo treba zatvoriti model `draft session` jedinice i restore konflikata

Discovery nalazi koji trenutno ograničavaju continuity:

- `mapping set` persistence danas čuva `mapping_decisions`, governance metadata i određene coverage/reuse signale, ali ne čuva `upload_response`, dataset handle-ove, aktivni Workspace section, generated artifact state, niti bounded guidance rezultate
- JSON export/import danas služi kao `decision transport`, ne kao `workspace restore`: import ume da primeni odluke samo preko već učitanog `upload_response` i validnih source kolona u trenutnom session state-u
- `Catalog` / `saved mapping set` apply/reuse putanja ume da rekonstruiše `mapping_response` i `mapping_editor_state`, ali namerno resetuje preview/codegen/guidance artefakte i ne vraća puni workspace ingestion kontekst
- `reset_flow_state()` i `handle_api_base_url_change()` eksplicitno čiste veliki deo Workspace/Catalog/Debug transient state-a, što potvrđuje da današnji UI nema stabilnu `draft session` jedinicu koja može bezbedno da se vrati posle reload-a ili runtime switch-a
- backend `dataset_id` danas nije dobar restore anchor za resume-by-design, jer `upload_store` ostaje session-scoped in-memory store; to znači da `source_dataset_id` / `target_dataset_id` sami po sebi nisu dovoljni za cross-reload restore

Predloženi prvi minimalni resume slice:

- definisati jednu `draft session` jedinicu koja čuva minimalni restore-worthy Workspace kontekst: source/target schema handle snapshot, `mapping_mode`, `mapping_editor_state`, `mapping_decision_audit`, i osnovni navigation focus (`Workspace` section)
- prvi restore cilj treba da vrati korisnika u `Workspace Review/Decisions` sa istim aktivnim odlukama, ali bez pokušaja da se odmah vrate preview/codegen/refinement/guidance output-i
- governance, benchmark, catalog i admin/debug state ostaviti van prvog slice-a, da se ne pomešaju durable analitički draft i širi produktni navigation cache

Isporučeni continuity pod-slice u ovom wave-u:

- backend sada ima prvi minimalni `draft session` contract: `POST /mapping/draft-sessions`, `GET /mapping/draft-sessions`, `GET /mapping/draft-sessions/{id}`
- persisted payload trenutno pokriva `source_handle`, `target_handle`, `mapping_mode`, `active_workspace_section`, `mapping_runtime`, `mapping_editor_state` i `mapping_decision_audit`
- `Workspace > Decisions` i minimalni `Workspace > Review` restore sada dele isti Streamlit save/load affordance za draft session tok, odvojeno od `mapping set` governance/versioning flow-a
- restore trenutno rekonstruiše minimalni `Workspace Review/Decisions` kontekst iz draft-session detail payload-a i namerno čisti preview/codegen/guidance output-e umesto da ih pokušava vratiti kao stale artefakte
- restore sada čuva i `api_base_url` marker i eksplicitno blokira resume kada se draft ne poklapa sa aktivnim API base URL-om ili sa aktivnim upload schema kontekstom
- restore u `Workspace > Review` vraća samo minimalni stabilni mapping contract (`mapping_runtime`, sintetisani `ranked_mappings`/`mappings`, canonical coverage) bez bounded guidance/output cache-a
- live browser smoke je potvrdio `Decisions -> Mapping Set Versions -> Resume draft session -> Workspace Review` tok tek nakon što je resume prebačen sa direktnog pisanja u widget-bound `active_*` navigation ključeve na `pending_top_level_area` / `pending_workspace_section` pattern
- fokusirani backend smoke sada potvrđuje da se draft session može sačuvati, izlistati i vratiti bez regressije na susednom `mapping set` persistence toku

- [x] Potvrditi šta se danas već čuva kroz `mapping set`, export/import i session state, a šta realno nestaje posle reload-a.
- [x] Definisati `draft session` scope, restore pravila i konflikt semantiku.
- [x] Izabrati prvi minimalni resume slice koji ne meša governance artefakte i ephemeral UI state.
- [x] Isporučiti prvi backend-only slice uz fokusirane testove i jasnu dokumentaciju ponašanja.
- [x] Dodati Streamlit save/load affordance za draft session bez mešanja sa `mapping set` governance tokom.
- [x] Rekonstruisati minimalni `Workspace Decisions` restore iz draft-session detail payload-a.
- [x] Definisati i implementirati konflikt pravila kada se draft restore ne poklapa sa aktivnim runtime/upload kontekstom.
- [x] Proširiti restore sa `Workspace Decisions` na minimalni `Workspace Review` contract bez vraćanja stale guidance/output state-a.

### 3. SAP-first knowledge expansion and canonical coverage wave

Status: accepted planning, parked for current execution wave.

Napomena:

- ovaj pravac ostaje otvoren, ali ga ne diramo dok ga eksplicitno ne izaberemo kao aktivni wave
- prethodni rad na Catalog reuse/discovery ne zatvara SAP ingest i coverage zadatke ispod

- [ ] Napraviti inventory svih postojećih SAP source artefakata i označiti koje izvore tretiramo kao authoritative za field-level knowledge refresh.
- [ ] Definisati staging/provenance format za vendor knowledge ingest (`system`, `module`, `object`, `field`, `description`, `source`, `source_type`, `public_or_internal`, `last_verified_at`).
- [ ] Napraviti SAP-first generated refresh put za knowledge sloj umesto ručnog masovnog editovanja `metadata_dict.csv`.
- [ ] Izvući SAP canonical-gap candidate set i razdvojiti vendor-specific field knowledge od stvarnih cross-system business concepts.
- [ ] Definisati SAP benchmark/eval slice-ove po domenima (`master data`, `FI/AP/AR`, `MM/SD`, `HR`) i KPI-jeve za coverage i mapping quality.
- [ ] Posle SAP pilot rezultata proširiti isti ingest/eval/promocija model na Workday, QAD i QuickBooks.
- [ ] Dokumentovati pravila za javno dostupne web/vendor spec izvore pre širenja na dodatne sisteme.

### 4. Epic 13D: discovery and reuse expansion

Status: completed current wave; carry-forward only if novi catalog discovery pressure opravda novo otvaranje.

Napomena:

- initial 13D slice je već isporučen
- dodat je i field-scoped reuse discovery sa parcijalnim importom i compare/undo UX-om
- sledeći rad širi compare/drilldown i veze prema review/governance toku kroz direktne `Workspace Review` handoff CTA-e iz `Catalog` drilldown površina
- dodat je i sledeći compare/drilldown korak: `Integration Pair Compare` sada otvara i direktan base/peer detail drilldown, ne samo review-focus CTA-e
- učitan `version diff` readout sada takođe ima direktan `Workspace Review` handoff za current/baseline stranu, umesto da ostane pasivan summary-only prikaz
- `version diff` handoff više ne otvara samo opšti review fokus: kada diff nosi više promenjenih source polja, `Workspace Review` sada zadržava privremeni multi-source fokus baš na tim changed rows dok source filter ostaje na `All`
- live browser smoke je potvrdio taj isti `version diff -> Workspace Review` tok nad seeded `browser-diff-focus` verzijama: info handoff poruka nosi `source_scope`, a `Review` panel prikazuje multi-source focus caption dok `Filter by source` ostaje na `All`
- `version diff` readout sada ima i direktne `Governance` CTA-e za current/baseline stranu kada diff already nosi governance follow-up signal; live browser smoke je potvrdio da current governance handoff za draft verziju stvarno prebacuje na top-level `Governance`
- `Governance` handoff više ne završava na generičkom console ulazu: top-level sekcija je sada state-driven, pa `Catalog` može da otvori uži `Canonical` ili `Stewardship` fokus; canonical handoff prefiliuje source-system / business-domain / concept detail, dok unmatched-source slučajevi prioritetno otvaraju `Stewardship` sa fokusom na pogođena source polja
- isti handoff sada i resetuje stare Governance filtere pre preuzimanja novog fokusa, tako da prethodni canonical query ili stewardship owner/status/source filter ne mogu da sakriju ciljanu concept/detail ili gap queue putanju iz `Catalog` CTA-a
- live browser smoke je sada dodatno potvrdio da current diff governance CTA briše namerno postavljen stale `Canonical concept search` filter (`legacy`) i ipak otvara čist `Governance (Canonical)` landing sa handoff scope-om `SAP / Customer`
- diff governance CTA copy više nije generički: current/baseline diff akcije sada u labeli kažu da li vode u `Canonical review` ili `Stewardship`, a prateći caption navodi razlog poput `draft version` ili `unmatched source fields`
- isti CTA clarity pattern sada važi i za glavni `Catalog` drilldown handoff: umesto generičkog `Open canonical governance handoff`, primarni/sekundarni Governance CTA eksplicitno kaže `Open Canonical review` ili `Open Stewardship`
- live browser smoke je potvrđen i za unmatched-source glavnu drilldown putanju: seeded `Stewardship Smoke Sync` mapping set (`#770`) prikazuje `Open Stewardship` u `Catalog` drilldown-u i zaista otvara top-level `Governance` sa aktivnom sekcijom `Stewardship`
- ovaj wave je zatvoren u `completed_slices.md`; naredni aktivni execution fokus prelazi na `Operational hardening nad pilot površinama`

- [x] Potvrditi trenutno stanje discovery/reuse površina posle poslednjih field-reuse slice-ova.
- [x] Definisati sledeći 13D slice bez mešanja sa širim SAP wave-om.
- [x] Isporučiti sledeći compare/drilldown ili review-linked reuse slice sa uskom validacijom.
- [x] Isporučiti dodatni compare -> detail drilldown slice u `Catalog` toku sa fokusiranom validacijom.
- [x] Isporučiti diff-linked review-focus slice u `Catalog` version diff readout-u sa fokusiranom validacijom.
- [x] Suziti diff-linked review handoff tako da `Workspace Review` poštuje changed-source scope iz `Catalog` version diff-a.
- [x] Isporučiti diff-linked governance handoff slice iz `Catalog` version diff readout-a sa fokusiranom validacijom i browser smoke proverom.
- [x] Zabeležiti isporučeni 13D napredak u `completed_slices.md` kada se zatvori sledeći veći wave.

### 5. Operational hardening nad pilot površinama

Status: active execution focus.

Napomena:

- ovo je stalan paralelni tok i ne treba ga mešati sa velikim feature wave-ovima
- ovaj pravac ostaje aktivan i dok kreće `Session continuity` discovery, kao zaštita ključnih pilot workflow-ova od regresija i tihog runtime drifta
- posle zatvaranja `Epic 13D` wave-a, ovo je sada glavni operativni fokus
- `docs/pilot/PILOT_REGRESSION_SUBSET.md` sada eksplicitno pokriva browser smoke za `Catalog -> Workspace Review` diff handoff i `Catalog -> Governance` (`Canonical` / `Stewardship`) handoff tokove
- live prolaz kroz taj novi subset je zabeležen u `docs/pilot/PILOT_EXECUTION_LOG_2026-05-10.md`, uključujući `browser-diff-focus` review/canonical handoff i `Stewardship Smoke Sync` stewardship handoff
- `dbt` Output slice je sada live-proveren na svežem backendu: `Catalog -> Workspace reuse -> Output -> Generate dbt model -> Refine with LLM` prolazi nad seeded approved mapping set-om, dok promena `API Base URL` sada eksplicitno čisti transient backend-bound session state i vraća UI na `Workspace > Setup` umesto da zadrži stare artefakte/dataset handlere preko runtime granice
- `dbt` artifact refinement je dodatno hardenovan za LM Studio near-JSON/prompt-echo odgovore: parser sada ume da spasi rewritten artifact iz `current_code` / `response_format` oblika, uključujući malformed JSON shape koji je prethodno vodio do `HTTP 502: LLM did not return a valid artifact refinement`
- `dbt` Output ostaje namerno starter-only za trenutni wave; carry-forward za narednu iteraciju je generisanje punijeg dbt paketa (`model.sql`, `schema.yml`, i opciono `sources.yml` kada je `source_mode=source`) iz istog centralnog dbt profile-a
- draft-session continuity smoke je sada dodat i u live browser operational-hardening tok: namerno prljav `Workspace > Review` state (`Filter by source = phone` + generisani `Review Queue Plan`) ne preživljava `Resume draft session`, a restored `Review` se vraća na čist `All` slice bez stale guidance output-a
- operativni bootstrap za live smoke više nije ad-hoc ručni korak: `backend/scripts/bootstrap_operational_smoke.py` i PowerShell wrapper seeduju repeatable `browser-diff-focus`, `Stewardship Smoke Sync`, `approved-customer-reuse-smoke`, `customer-draft-session` i `operational-smoke-benchmark` kroz postojeće API-je, uz idempotentno preskakanje već postojećih fixture-a
- isti bootstrap sada garantuje i jedan browser-potvrđen `approved` catalog fixture za `Catalog -> Reuse in Workspace -> Output` tok: `approved-customer-reuse-smoke` se pojavljuje sa `Latest approved version` caption-om, a `Reuse in Workspace` CTA ostaje aktivan bez ručnog governance seedovanja
- benchmark površina više nije samo helper-validirana: seeded `operational-smoke-benchmark` dataset sada je browser-potvrđen kroz `Benchmarks -> Compare scoring profiles -> Benchmark Explanation`, uključujući vidljiv recommendation surface i uspešno generisan bounded fallback explanation (`Key findings`, `Risks`, `Next actions`)
- repeatable single-command operational baseline sada postoji i kao runner: `backend/scripts/run_operational_hardening.py` plus `run_operational_hardening.ps1` orkestriraju bootstrap, fokusirani pytest subset, i live API smoke za `Workspace`, `Catalog` i `Benchmarks`, pa više nije potrebno ručno slagati te korake pre svakog pilot prolaza
- isti trio sada ima i repo-local browser E2E runner: `backend/scripts/run_operational_browser_e2e.py` plus `run_operational_browser_e2e.ps1` automatizuju `customer-draft-session` restore, `browser-diff-focus` review handoff, `stewardship-smoke-sync` governance handoff, `approved-customer-reuse-smoke` reuse apply i `operational-smoke-benchmark` comparison/explanation tok bez ručnog kliktanja
- kada lokalni runtime krene sa praznim catalog skupom, repeatable `Catalog` handoff smoke nije zahtevao novi seed helper: minimalni `browser-diff-focus` diff family uspešno je posejan preko postojećeg `/mapping/sets` API-ja i odmah postao vidljiv kroz `Load all integrations`
- live browser smoke je sada zatvorio i ranije otvorenu loaded-review tvrdnju: sa već učitanim `customer-draft-session` review state-om, `Catalog -> browser-diff-focus -> Load version diff -> Open current diff review focus` zaista vraća UI u `Workspace > Review`, zadržava `Filter by source = All`, i prenosi diff scope kroz `source_scope` info poruku plus review caption umesto kroz tvrdi source filter

Izabrani sledeći aktivni slice:

- loaded-review `Catalog -> Workspace Review` tvrdnja je sada browser-potvrđena; sledeći operational-hardening slice treba birati na drugoj pilot površini, a ne više na ovoj zatvorenoj proveri

- [x] Dopuniti `docs/pilot/PILOT_REGRESSION_SUBSET.md` konkretnim browser smoke koracima za `Catalog -> Workspace Review` i `Catalog -> Governance` handoff tokove.
- [x] Zabeležiti jedan live prolaz kroz novi `Catalog` handoff regression subset u pilot execution log-u.

- [ ] Održavati i širiti uski regression subset za glavne product surface-ove.
- [ ] Dodavati browser-level proveru za najvažnije pilot tokove kada helper testovi više nisu dovoljni.
- [ ] Zatvarati preostale implicitne ili advisory-only governance prolaze kada se pojave u pilot prolazima.
- [ ] Beležiti UX poliranja i stabilizaciona zapažanja iz realnih pilot run-ova.

### 6. Persistence and runtime separation hardening

Status: active carry-forward, ali bez prerane eskalacije scope-a.

Napomena:

- SQLite status backend za mapping jobs je već uveden
- sledeći ozbiljniji rad ovde treba pokrenuti tek kada se pojavi stvarni multi-user ili cross-process pritisak

- [ ] Potvrditi koje trenutne runtime granice stvarno blokiraju sledeći pilot ili load cilj.
- [ ] Definisati minimalni sledeći hardening slice bez uvođenja brokera pre vremena.
- [x] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [x] Uvesti SQLite-backed status/progress backend uz isti `start / poll / cancel` API contract i lokalni thread-backed execution model.
- [x] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [x] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.
- [ ] Uvoditi lease/dequeue ili spoljašnji broker tek kada cross-process execution stvarno postane potreban.
- [x] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.
- [x] Razdvojiti canonical authoring sync od full metadata reseed puta za glossary import i overlay-promotion authoring tokove.
- [x] Uvesti uske repository slojeve za stewardship queue, catalog discovery, mapping-set governance i knowledge runtime snapshot pristup.
- [ ] Širiti normalizaciju dalje samo kada nove discovery/governance površine pokažu da je to stvarno potrebno.

### 7. Epic 14A/14B: performance and signal precomputation

Status: queued after discovery/hardening stabilization.

Napomena:

- vector cache i stable precompute ne treba otvarati kao veliki wave pre nego što reuse discovery i operational hardening pokažu stvarni pressure

- [ ] Potvrditi koje signalne ili runtime putanje danas stvarno prave najveći latency/cost pressure.
- [ ] Definisati prvi uski cache/precompute slice koji ne komplikuje explainability contract.
- [ ] Isporučiti prvi performance slice sa benchmark-validacijom i bez regressions u ranking ponašanju.
