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

Ovaj dokument sada služi kao operativni tracker za aktuelne otvorene pravce.

Trenutno izabrani naredni portfolio fokus:

- `Operational hardening nad ključnim pilot tokovima` kao stalni paralelni execution tok
- `Transformation Design` kao sledeći planirani `Workspace` capability wave

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
- persisted payload trenutno pokriva `source_handle`, `target_handle`, `mapping_mode`, `active_workspace_section`, `mapping_runtime`, `mapping_editor_state`, `mapping_decision_audit`, `transformation_spec` i bounded `output_state`
- `Workspace > Decisions` i minimalni `Workspace > Review`/`Output` restore sada dele isti Streamlit save/load affordance za draft session tok, odvojeno od `mapping set` governance/versioning flow-a
- restore trenutno rekonstruiše minimalni `Workspace Review/Decisions` kontekst iz draft-session detail payload-a, vraća `Transformation Design`, i po potrebi vraća bounded output snapshot (`preview`, generated/refined artifact, mapping-analysis summary/script) umesto slepog re-run-a
- restore sada čuva i `api_base_url` marker i eksplicitno blokira resume kada se draft ne poklapa sa aktivnim API base URL-om ili sa aktivnim upload schema kontekstom
- restore u `Workspace > Review` i `Workspace > Output` vraća minimalni stabilni mapping contract (`mapping_runtime`, sintetisani `ranked_mappings`/`mappings`, canonical coverage) plus samo eksplicitno sačuvane bounded output snapshot-e
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
- zatvoren je i mali ingest hardening dodatak za parser boundary: malformed ili shape-invalid `JSON` / `XML` payload-i sada imaju fokusiranu API coverage mrežu i na realnom upload putu i na advisory `POST /upload/spec/detect` putu; detekcija za njih vraća `hint=None`, dok stvarni upload/recovery i dalje ostaju strict `400` reject bez bounded fallback-a

Izabrani sledeći aktivni slice:

- sledeći glavni operational-hardening fokus je `Workspace` kao primarni radni tok; ostale površine se proveravaju prvenstveno kroz njihove handoff-e u isti tok ili iz njega

### 5A. Workspace-first operational focus

Status: active and now treated as the primary pilot hardening surface.

Operativna odluka:

- `Workspace` nosi glavni analyst workflow i predstavlja glavni end-user proizvodni sloj; treba da dobije oko 80% praktične validacije pažnje
- `Governance` ostaje važan, ali primarno kao organizacioni link ka `EA`, `MDM`, integration dev i srodnim upravljačkim funkcijama koje prate ili usmeravaju Workspace rezultate
- `Catalog`, `Benchmarks`, `Governance` i `System` proveravati pre svega kao ulaze, izlaze ili nadzor nad Workspace životnim ciklusom

Već browser-potvrđeni Workspace slučajevi:

- [x] `Workspace > Setup` standard two-file row-data upload/profile tok radi na malom smoke paru (`smoke_source.csv` -> `smoke_target.csv`).
- [x] `Workspace > Setup -> Generate mapping` daje stabilan heuristic mapping rezultat bez obaveznog LLM validaion sloja.
- [x] `Workspace > Review` prikazuje trust layer, canonical coverage, ranked candidates, review queue i manual review površinu nad istim mapping rezultatom.
- [x] `Workspace > Decisions` više ne puca na draft-state panelima; `Draft Decision State` i `Draft Review State` renderuju se u live browser prolazu.
- [x] Upload-based `Workspace` tok sada može da sačuva draft session, zatim posebno `decision-state` i `review-state` nad istim aktivnim draft anchor-om.
- [x] `Workspace > Output` je browser-potvrđen za advisory preview i Pandas starter generation nad istim upload-based mapping stanjem.
- [x] `Workspace > Output` accepted-only/advisory gate matrix je browser-potvrđen: preview ostaje dozvoljen uz advisory poruku na `needs_review`, dok Pandas, PySpark i dbt generation ostaju striktno blokirani do punog `accepted` stanja.
- [x] `Catalog -> Reuse in Workspace` handoff vraća odobreni mapping set nazad u Workspace review/decisions tok.
- [x] `Resume draft session` više vraća čist review state bez stale guidance/output tragova.

Workspace slučajevi koji sada nose glavni sledeći fokus:

- [x] Canonical-mode `Workspace > Setup -> Review -> Decisions -> Output` je browser-potvrđen end-to-end na `smoke_source.csv` uz `Canonical target intent = SAP`; `Target context: SAP | Projection: target-aware canonical | Profile: sap_customer_master` ostaje stabilan kroz Review, Decisions i Output, preview ostaje nedostupan, a Pandas code generation prolazi nad source-to-canonical odlukama.
- [x] Add manual same-concept canonical target selection in `Workspace > Review`: surface candidate targets sharing source canonical concept, allow reviewer selection in the decision editor, and persist it as the chosen mapping target.
- [x] `Workspace > Decisions -> Save mapping set version -> approve -> Catalog -> Reuse in Workspace` je browser-potvrđen kao puni governance/reuse povratni krug iz jednog glavnog workspace rada; live prolaz je sačuvao `workspace-reuse-1780002617742`, prebacio ga u `approved`, našao ga u `Catalog` i vratio isti approved artefakt nazad u Workspace review state.
- [x] `Workspace` ponašanje posle `Reset flow` i posle promene `API Base URL` je browser-potvrđeno; `Reset flow` vraća čist `Workspace > Setup`, a promena `API Base URL` sada eksplicitno čisti transient backend-bound state i vraća UI na `Workspace > Setup` čak i kada je korisnik prethodno bio u `Catalog`.
- [ ] Browser-potvrditi da draft resume iz upload-based toka vraća ispravan `Review` ili `Decisions` section i odgovarajući `workspace_target_context` bez mešanja starog local state-a.
- [x] Prošao je jači manual-review/override scenario: `phone` je ručno prebačen sa `phone_number` na `customer_id`, prvo ostavljen u `needs_review` pa zatvoren kao `accepted`; browser-potvrđeno je da `Output` tada prvo ostaje advisory/codegen-blocked, zatim posle zatvaranja odluke otključava codegen, dok `Save Corrections` prvo blokira otvoreni override a zatim uspešno persisituje 1 correction entry kada override dobije zatvoren status.
- [ ] Proveriti output refinement putanje (`Pandas`/`dbt` refine with LLM`) kao deo istog Workspace toka, ne samo kao odvojeni output smoke.

Workspace UX/stability zapažanja koja su već zatvorena:

- [x] Review/Decisions draft-state panel adapter mismatch (`unexpected keyword argument 'api_request'`) je popravljen i browser-potvrđen.
- [x] Saved draft-session picker više ne ostaje zalepljen za stariji entry sa istim imenom; selector sada prati aktivni `draft_session_id`.

### 6. Workspace Modelling derived-first V1

Status: active execution focus.

Napomena:

- `Modelling` kreće kao `derived-first` površina, ne kao blank-canvas authoring studio
- prvi implementacioni cilj je da `Workspace` prikaže konceptualni model koji već proizlazi iz aktivnih odluka i `Transformation Design` state-a
- korekcije modela moraju ostati bounded i ne smeju tiho da prepišu runtime mapping odluke

- [ ] Dodati `Workspace > Modelling` section shell u postojeći Workspace tok.
- [ ] Izvesti početni koncept model iz aktivnog `mapping_decisions` i `Transformation Design` state-a.
- [ ] Dodati osnovni `derived-first` editing sloj za object/grain/dodatne atribute i required flagove.
- [ ] Prikazati drift između koncept modela i aktivnog Workspace mapping state-a.
- [ ] Prikazati bounded modelling hints bez tihog menjanja `Decisions` ili `Output` stanja.
- [ ] Pokriti modelling helper logiku fokusiranim `Workspace` testovima.
- [ ] Validirati prvi slice fokusiranim pytest prolazom.
- [x] `API Base URL` switch više ne ostavlja UI zalepljen na starom top-level tabu; reset sada ide i kroz `pending_top_level_area` / `pending_workspace_section` handoff pa se live UI vraća na `Workspace > Setup` umesto da zadrži stari `Catalog` radio izbor.

Workspace Copilot bounded closure/output mini-slice je zatvoren:

- [x] Dodati `Review -> Decisions` risk/closure summary u `Workspace Copilot` kao bounded, current-state readout.
- [x] Dodati `Decisions -> Output` readiness assessment koji razlikuje governance blocker, proposal drift i spremno stanje.
- [x] Dodati `Output` explanation shell za gating i warning prioritization nad postojećim artifact/refinement state-om.
- [x] Dopuniti quick-ask discoverability i fokusiranu `Streamlit` test mrežu za nove Copilot capability-je.
- [x] Izložiti iste capability-je i kroz glavni `Workspace Copilot` panel u aktivnom `Workspace` section-u, ne samo kroz sidebar quick-ask.
- [x] Zatvoriti live rerun/hot-reload pad nad stale `DeletedFile` upload state-om koji je browser smoke otkrio tokom ovog slice-a.
- [x] Proći uski live browser smoke za `Review`, `Decisions` i `Output` panel pitanja nad glavnim `Workspace Copilot` shell-om.
- [x] Zatvoriti glavni `Workspace Copilot` section-handoff pad gde je `Open Decisions` pokušavao da menja widget-bound `active_*` navigation ključeve usred render-a.
- [x] Potvrditi live browser putem da `Review -> Open Decisions -> Am I ready for Output?` i `Output` gating objašnjenje rade nad realnim mapping state-om bez navigacionog pada.

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

### 6A. Durable upload state, SQLite stability, and timeout contract cleanup

Status: completed current execution wave.

Zašto je ovaj wave izabran sada:

- `upload_store` i dalje drži aktivne dataset handle-ove samo u memoriji, pa ordinary backend reload i dalje može da slomi `dataset_id` anchor i restore/preview/codegen tokove
- SQLite je već legitiman pilot backend za Semantru, ali connection contract još nije dovoljno operativno ojačan za mirniji lokalni multi-request rad
- `llm_timeout_seconds` trenutno nije jedinstveno poštovan kroz sve bounded LLM putanje, pa runtime config nije potpuno istinit operativni ugovor

Šta ovaj wave jeste:

- uzak backend/runtime hardening slice nad postojećim API contract-om
- fokus na trajnosti dataset anchor-a, stabilnijem SQLite connection ponašanju i usaglašenom timeout contract-u

Šta ovaj wave nije:

- nije puni `workspace` DB-native redesign
- nije prelazak na broker/worker queue ili širi async backend refactor
- nije mapping-engine decomposition wave
- nije SAP knowledge/model refactor wave

Operativna odluka za scope:

- `async` backend ostaje follow-up tema posle ovog wave-a, osim ako tokom ove implementacije uski testovi pokažu da je blocking LLM boundary sada glavni realni pilot problem
- embedding durable cache ostaje van scope-a ovog wave-a jer je trenutni embedding provider i dalje `none` ili deterministic `hash`, pa nema dokazano skupog eksternog embedding poziva koji sada traži persistence sloj
- SAP hardcoding i šira signal/weight konsolidacija ostaju carry-forward refactor teme, ne blokiraju ovaj hardening slice

Precizni ciljevi prvog execution slice-a:

- uvesti durable backend identitet za uploaded dataset handle i schema-profile lineage bez razbijanja postojećeg `/upload` -> `/mapping` contract-a
- ojačati SQLite connection/runtime ponašanje tako da lokalni pilot režim bude otporniji na `database is locked` i sličan connection drift
- poravnati LLM timeout ponašanje tako da `settings.llm_timeout_seconds` ili jasno izvedeni bounded timeout setting zaista bude authoritative runtime contract

Checklist za implementaciju:

- [x] Potvrditi tačne read/write tačke koje danas zavise od `upload_store` in-memory dataset state-a (`upload`, companion enrichment, preview, mapping, draft restore) i zapisati minimalni durable contract koji te putanje zaista traže.
Potvrđeni inventory za prvi slice:

- write ulazi su koncentrisani u `backend/app/api/routes/upload.py`: `/upload/spec` i `parse_and_store_upload()` upisuju dataset handle kroz `save_schema_profile()` ili `save_rows()`, dok `/upload/handle/metadata` radi in-place enrichment kroz `merge_companion_metadata()`
- live read površine su koncentrisane u `backend/app/api/routes/mapping.py`: `/mapping/auto`, `/mapping/auto/jobs`, `/mapping/canonical`, `/mapping/canonical/jobs`, `/mapping/refine`, `_resolve_refinement_target_schema()` i `/mapping/transformation/generate` traže lookup po `source_dataset_id` / `target_dataset_id`, ali koriste samo `handle.schema_profile`
- `/mapping/preview` je jedina aktivna backend putanja koja danas poseže za `source.rows`; pritom `preview_service.build_preview()` i `transformation_service.build_transformed_target_frame()` koriste samo prvih 10 redova, a endpoint već ima fallback `source_preview_rows` contract za slučaj da lookup po `dataset_id` padne
- `draft session` restore nije primarno vezan za live `dataset_store` lookup: `DraftSessionCreateRequest` i `DraftSessionDetail` već persisitiraju `source_handle` / `target_handle` snapshot payload, pa minimalni restore-worthy review/decisions/output tok već radi nad snapshot contract-om, ne nad obaveznim ponovnim čitanjem iz `upload_store`

Minimalni durable contract potvrđen ovim prolazom:

- obavezno: `dataset_id`, `dataset_name`, `schema_profile`
- potrebno za postojeći preview i upload response surface: bounded `preview_rows`
- potrebno za metadata lineage i kasniji restore/debug: lightweight ingest metadata (`storage_mode`, `source_format`, opcioni `selected_table` / spec lineage marker)
- nije dokazano potrebno za prvi hardening slice: neograničeni full row payload; trenutni backend behavior pokazuje da je bounded preview payload dovoljan za postojeći preview contract, dok mapping/refine/codegen lookup-i rade nad schema handle-om
- [x] Definisati uski persisted dataset model: `dataset_id`, `dataset_name`, `schema_profile`, bounded `preview_rows`, dovoljno lineage metadata i samo onaj raw/derived payload koji je potreban za postojeće restore i preview tokove.
Prva-wave odluka za model:

- authoritative persistent ključ ostaje postojeći `dataset_id: str`, bez uvođenja novog numeričkog upload identiteta u ovom slice-u
- durable payload čuva `dataset_id`, `dataset_name`, `schema_profile`, bounded `preview_rows` i mali ingest metadata envelope (`storage_mode`, `source_format`, `selected_table`, `created_at`, opciono `updated_at`)
- `schema_profile.row_count` ostaje deo authoritative profila; ne uvodi se odvojeni duplicate row-count field osim ako migracioni/write path to kasnije zatraži radi query optimizacije
- full raw rows ne ulaze u prvi persistent contract; za postojeći backend preview behavior authoritative ostaje bounded `preview_rows`, jer current preview ionako koristi samo prvih 10 redova
- companion metadata merge i SQL/schema-spec lineage ažuriraju isti persistent dataset payload, ne otvaraju poseban secondary resource tip

- [x] Izabrati gde taj model živi: uski repository/service sloj iznad SQLite-a, bez uvlačenja celog upload lifecycle-a direktno u široki `persistence_service` surface više nego što je neophodno.
Prva-wave odluka za smeštaj:

- dodaje se novi uzak repository sloj tipa `uploaded_dataset_repository.py`, po istom obrascu kao postojeći `draft_session_repository.py`, `mapping_governance_repository.py` i srodni repozitorijumi
- SQLite tabela i niski CRUD helper-i i dalje žive u `persistence_service.py`, jer je to i dalje centralni schema/migration owner, ali rute i `upload_store` ne treba direktno da zavise od širokog persistence surface-a
- `dataset_store` ostaje glavni façade za upload runtime: prvo upisuje/čita kroz repository-backed durable store, a lokalni in-memory cache ostaje samo opportunistic hot cache umesto jedinog source-a za dataset lookup
- API contract (`/upload`, `/upload/handle`, `/upload/handle/metadata`, `/mapping/*`) ostaje nepromenjen; promena je unutrašnja backend persistence zamena, ne novi route surface
- [x] Implementirati durable dataset save/load contract tako da postojeći `dataset_store` može da ostane façade nad novim backend modelom umesto da API i UI odmah menjaju ceo tok.
Isporučeno u ovom wave-u:

- `backend/app/services/upload_store.py` više nije single-source in-memory registry; ostaje isti façade, ali čita/piše kroz novi `uploaded_dataset_repository.py` i koristi memoriju samo kao hot cache
- novi SQLite-backed `uploaded_datasets` contract čuva `dataset_id`, `dataset_name`, `schema_profile`, bounded `preview_rows` i lineage metadata bez promene postojećeg `/upload` i `/mapping` API surface-a
- `/upload/spec`, row-data upload i SQL snapshot upload sada svi pune isti durable dataset contract sa odgovarajućim `source_format` / `storage_mode` markerima
- [x] Obezbediti da ordinary backend reload više ne invalidira aktivne `source_dataset_id` / `target_dataset_id` handlere za minimalni restore-worthy scope.
Potvrđeni ishod:

- `dataset_store.get_dataset()` sada fallback-uje na durable repository kada lokalni cache nema traženi handle
- fokusirani smoke testovi potvrđuju da `mapping/auto` i `mapping/preview` nastavljaju da rade i posle `dataset_store.clear_memory_cache()` simulacije ordinary backend reload-a
- [x] Definisati jasnu granicu šta ostaje transient UI/session state, a šta postaje durable upload/runtime entitet, da se ne otvori prerani "persist everything" scope.
Granica posle ovog wave-a:

- durable backend entitet je uploaded dataset handle sa bounded preview payload-om i ingest lineage metadata
- `upload_response` wrapper, aktivni Workspace section, review filteri, generated guidance/output panel state i ostala Streamlit orkestracija i dalje ostaju transient/session-local sloj
- draft-session snapshot i dalje ostaje zaseban continuity contract; ovaj wave ga nije pretvarao u `persist everything` redesign
- [x] Ojačati SQLite connection contract: WAL režim, razuman `busy_timeout`, eksplicitni rollback na exception putanji i jedan dosledan connection bootstrap za runtime operacije.
Isporučeno u `persistence_service.connection()`:

- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`
- `PRAGMA foreign_keys=ON`
- eksplicitni `rollback()` na exception putanji pre zatvaranja konekcije
- [x] Proveriti da li postoje uski write-hotspot-ovi ili cleanup tokovi kojima treba dodatni serialization/locking guard u lokalnom pilot režimu, bez uvođenja brokera ili lease worker modela.
Zaključak ovog wave-a:

- dodatni app-level serialization guard nije uveden, jer novi upload-dataset write path radi kroz kratke single-row upsert operacije, a runtime hot cache je već zatvoren postojećim `Lock`-om u `upload_store`
- za prvi pilot hardening slice `WAL` + `busy_timeout` + rollback contract pokrivaju realni operativni lock rizik bez uvođenja šireg worker/lease modela
- eventualni budući hotspot ostaje tema samo ako live pilot ili širi test subset pokažu stvarni contention izvan ovog upload slice-a
- [x] Inventarisati sve LLM putanje koje danas clamp-uju ili zaobilaze `settings.llm_timeout_seconds` i svesti ih na jedan jasan runtime contract.
Potvrđeni inventory i poravnanje:

- bounded JSON helper i runtime probe helper više ne nose skriveni literalni clamp u telu funkcije
- transformation-generation bounded path sada koristi isti centralni helper umesto lokalnog `min(..., 5.0)` obrasca u `mapping_service.py`
- [x] Odlučiti da li bounded LLM operacije ostaju na posebnom kratkom timeout-u; ako ostaju, izvući to u eksplicitno imenovan setting umesto skrivenog `min(..., 5.0)` obrasca u više fajlova.
Prva-wave odluka:

- bounded LLM operacije ostaju namerno kraće od opšteg `llm_timeout_seconds`
- to je sada eksplicitno modelovano kroz `llm_bounded_timeout_seconds` i `llm_probe_timeout_seconds`, uz centralne helper-e umesto razasutih literalnih clamp-ova
- [x] Dodati fokusirane backend testove za: durable dataset round-trip, reload-safe dataset lookup, SQLite hardening regression, i timeout contract ponašanje.
Potvrđena validacija:

- `tests/test_api_smoke.py -k "survives_dataset_store_memory_reset or survives_dataset_store_memory_reset_with_persisted_preview_rows"` prolazi
- `tests/test_provider_and_persistence.py -k "sqlite_connection_applies_busy_timeout_and_rollback"` prolazi
- `tests/test_llm_and_evaluation.py -k "bounded_llm_timeout"` prolazi
- [x] Posle implementacije ažurirati `current_state.md`, `completed_slices.md` i ovaj dokument u istom wave-u.

Definition of done za ovaj wave:

- uploaded dataset handle više nije samo in-memory anchor za glavni upload -> mapping -> preview tok
- ordinary backend reload ne ruši minimalni dataset lookup contract za postojeće radne tokove koje eksplicitno podržimo u ovom slice-u
- SQLite runtime bootstrap koristi jedno dosledno hardening ponašanje za connection/timeout/rollback putanje
- `llm_timeout_seconds` više nije implicitno ignorisan ili prikriveno clamp-ovan bez jasnog config contract-a
- fokusirani testovi potvrđuju novi behavior bez regressije na postojećem `/upload`, `/mapping`, `draft session` i output helper scope-u

### 6B. Minimal sync backpressure boundary for long mapping and bounded LLM routes

Status: completed current execution wave.

Zašto je ovaj wave izabran sada:

- `mapping/auto` i `mapping/canonical` već imaju async job varijante, ali sync route-ovi i dalje nisu imali nikakav mali runtime backpressure boundary za lokalni pilot režim
- bounded guidance i output LLM putanje (`analysis`, `review-plan`, `workspace-guidance`, `artifact refinement`, `transformation generation`) i dalje su išle direktno na request thread bez capacity guard-a
- cilj je bio da se uvede najmanji održiv operativni boundary pre većeg async/job-generalization refactora

Šta ovaj wave jeste:

- uzak runtime hardening slice za lokalni backend overload scenario
- eksplicitni `429 + Retry-After` contract kada su duže sync mapping ili bounded LLM lane-ovi puni
- zadržavanje postojećeg API surface-a uz jasniji fallback na već postojeće async job putanje tamo gde one već postoje

Šta ovaj wave nije:

- nije generički job framework za sve LLM response tipove
- nije prelazak na broker/worker execution model
- nije Streamlit polling/UI wave za nove async guidance tokove

Isporučeno u ovom wave-u:

- [x] Identifikovati koje duže request putanje već imaju async fallback, a koje i dalje ostaju potpuno sync i neograničene.
Potvrđeni scope:

- `mapping/auto` i `mapping/canonical` već imaju `/jobs` fallback i zato su najbolji kandidati za sync backpressure boundary umesto za novi job model
- preostale bounded LLM putanje ostaju sync, ali sada imaju mali concurrency guard umesto potpunog neograničenog request piling-a
- [x] Uvesti minimalni runtime capacity service umesto širenja postojećeg `mapping_job_store` modela na nove response tipove.
Isporučeno:

- dodat je `backend/app/services/runtime_capacity_service.py`
- uvedeni su odvojeni lane-ovi za `sync mapping` i `bounded LLM` pozive
- uvedeni su eksplicitni settings: `sync_mapping_max_concurrent_requests`, `bounded_llm_max_concurrent_requests`, `runtime_capacity_retry_after_seconds`
- [x] Ojačati sync mapping route-ove koji već imaju async fallback tako da vrate jasan backpressure signal umesto da tiho zagušuju lokalni runtime.
Isporučeno:

- `/mapping/auto` sada vraća `429` sa `Retry-After` i hint-om ka `/mapping/auto/jobs` kada je sync mapping lane pun
- `/mapping/canonical` sada vraća isti obrazac sa hint-om ka `/mapping/canonical/jobs`
- [x] Ojačati bounded LLM route-ove malim concurrency guard-om bez menjanja njihovog response shape-a.
Isporučeno:

- bounded LLM guard sada pokriva `/mapping/refine` kada `use_llm=True`, `/mapping/analysis/summary`, `/mapping/analysis/narration`, `/mapping/review-plan`, `/mapping/workspace-guidance`, `/mapping/codegen/refine`, `/mapping/transformation/generate` i `/mapping/transformation/spec/propose`
- guard ne menja success payload shape; menja samo overload ponašanje u jasan `429` contract
- [x] Zadržati granicu tako da fallback/deterministic ponašanje i dalje radi kada LLM provider nije aktivan.
Potvrđeno ponašanje:

- bounded guidance route-ovi aktiviraju guard samo kada stvarno postoji LLM provider putanja; fallback-only tokovi ne dobijaju lažni overload blok
- [x] Dodati fokusirane backend testove za backpressure signal i non-regression na susednim success putanjama.
Potvrđena validacija:

- `tests/test_api_smoke.py -k "test_sync_auto_map_returns_429_when_runtime_capacity_is_full"` prolazi
- `tests/test_api_smoke.py -k "test_workspace_guidance_returns_429_when_bounded_llm_capacity_is_full"` prolazi
- `tests/test_api_smoke.py -k "test_auto_map_survives_dataset_store_memory_reset or test_review_plan_returns_structured_clusters_when_llm_is_available or test_workspace_problem_guidance_uses_llm_when_provider_returns_valid_json or test_transformation_spec_proposal_endpoint_returns_structured_spec"` prolazi
- `tests/test_api_smoke.py -k "test_mapping_analysis_summary_uses_llm_when_provider_returns_valid_json or test_mapping_analysis_narration_returns_fallback_when_provider_missing"` prolazi
- `tests/test_api_smoke.py -k "test_transformation_generation_endpoint_returns_llm_generated_code"` prolazi

Definition of done za ovaj wave:

- lokalni backend više nema potpuno neograničen sync request piling na najskupljim mapping i bounded LLM putanjama koje su trenutno ostale sync
- caller dobija jasan `429 + Retry-After` signal umesto tihog request zadržavanja kada je lane pun
- postojeći success tokovi za mapping analysis, review plan, workspace guidance, transformation generation i transformation spec proposal ostaju netaknuti

### 6C. Mapping policy extraction for SAP calibration and decision thresholds

Status: completed current execution wave.

Zašto je ovaj wave izabran sada:

- `mapping_service.py` je nosio i generički scoring engine i SAP-specifične calibration pragove u istom modulu
- odluke za confidence label, auto-accept status, SAP boost i closed-set fallback bile su razasute kroz više funkcija i literalnih pragova
- cilj je bio da se smanji hardcoding i dupliranje bez otvaranja velikog engine decomposition wave-a

Šta ovaj wave jeste:

- uzak internal cleanup slice nad scoring/threshold politikom
- centralizacija scoring profila i signal pragova bez promene spoljnog API contract-a

Šta ovaj wave nije:

- nije zamena SAP heuristika novim knowledge-model slojem
- nije novi scoring profile system ili retuning signal weights
- nije puna podela `mapping_service` na više execution komponenti

Isporučeno u ovom wave-u:

- [x] Izdvojiti scoring profile i threshold politiku iz glavnog mapping engine modula u poseban policy sloj.
Isporučeno:

- dodat je `backend/app/services/mapping_policy.py`
- scoring profile definicije i weight resolution više nisu lokalno ugnježdene u `mapping_service.py`
- [x] Centralizovati odluke za confidence label i auto-accept pragove, uključujući SAP PIR override putanju.
Isporučeno:

- `score_to_label()` i `label_to_status()` sada koriste isti centralni `DecisionThresholdPolicy` resolver umesto odvojene lokalne threshold grananja
- [x] Centralizovati SAP calibration pragove i signal-evidence pragove koji su prethodno bili razasuti kroz više funkcija.
Isporučeno:

- `is_strong_canonical_concept_match()`, `compute_sap_confidence_boost()`, `is_sap_anchor_preserved()`, `sap_business_anchor_floor()`, `has_strong_identifier_consensus()`, `canonical_core_identifier_floor()`, `should_fallback_to_closed_set_no_match()` i explanation threshold odluke sada čitaju pragove iz centralnih policy objekata umesto iz razasutih literalnih vrednosti
- [x] Zadržati ponašanje engine-a stabilnim i eksplicitno razdvojiti test koji proverava name-deemphasis od testova koji proveravaju SAP boost behavior.
Potvrđeno:

- SAP name-deemphasis unit test sada eksplicitno zamrzava `source_sap_profile` kada želi da proveri samo deemphasis logiku, dok zasebni SAP anchor/boost testovi i dalje proveravaju pravi runtime behavior
- [x] Dodati fokusiranu validaciju za scoring profile, SAP calibration i threshold routing posle extraction-a.
Potvrđena validacija:

- `tests/test_mapping_service.py -k "sap or label_to_status_auto_accepts_scores_above_auto_accept_threshold or scoring_weight_overrides_replace_profile_weights or compute_final_score_normalizes_over_active_weights or mapping_returns_no_match_when_closed_set_is_only_weak_candidates"` prolazi
- statička provera nad `mapping_policy.py`, `mapping_service.py` i `test_mapping_service.py` je čista

Definition of done za ovaj wave:

- SAP calibration i decision-threshold politika više nisu razasute kroz engine kao niz nepovezanih literalnih pragova
- scoring profile i threshold odluke imaju jedan centralni policy sloj koji se može dalje refaktorisati bez ponovnog kopanja po celom `mapping_service.py`
- behavior-scoped mapping testovi potvrđuju da cleanup nije promenio postojeći scoring contract

### 7. Minimal identity + durable jobs

Status: closed as the first backend identity + durable-jobs wave.

Napomena:

- cilj ovog wave-a nije puni enterprise auth/RBAC/SSO program, nego minimalni identity i ownership model koji omogućava durable jobs i kasniji workspace ownership
- posao ovde nije više `da li imamo bazu`, nego da svaki job i svaki radni kontekst dobije stabilan actor/workspace anchor
- durable job runtime treba rešavati prvo za `mapping` i `benchmark` execution, uz zadržavanje postojećeg `start / poll / cancel` API surface-a koliko god je moguće

Minimalni ciljni scope za ovaj wave:

- uvesti backend `user_id`, `workspace_id` i po potrebi tanki `org_id` model dovoljan za ownership, audit i job attribution
- ne uvoditi širok permissions matrix u prvom slice-u; dovoljno je da backend zna ko je pokrenuo job, kome pripada workspace i ko sme da nastavi/otkaže execution
- prebaciti job execution sa local thread-centric implicitnog ownership-a na durable DB-backed lifecycle sa worker claim / heartbeat / recovery semantikom

Operativni redosled za prvi slice:

- prvi isporučeni pod-slice ovog wave-a je namerno uzak: uvedeni su `created_by` i `workspace_id` anchor-i za async `mapping` job status, `draft session` persistence, benchmark dataset persistence i evaluation run history, bez otvaranja punog auth/RBAC ili punog `workspace` entiteta
- postojeći fokusirani smoke testovi sada potvrđuju da se ti anchor-i zaista čuvaju i vraćaju kroz `mapping/auto/jobs`, `mapping/draft-sessions`, `evaluation/datasets` i `evaluation/runs`
- zatvarajući pod-slice ovog wave-a dopunio je `mapping_jobs` runtime metapodacima za `worker_id`, `claimed_at`, `heartbeat_at`, `lease_expires_at` i `recovery_signal`, plus named migration hook za taj runtime sloj; restart sada ostavlja durable failed/recovery trag umesto implicitnog gubitka aktivnog execution konteksta

- [x] Potvrditi minimalni identity model potreban za `mapping job`, `benchmark run`, `draft session` i budući `workspace` ownership bez otvaranja punog auth/RBAC wave-a.
- [x] Definisati backend entitete i ključeve za prvi identity slice (`user`, `workspace`, job `created_by`, job `workspace_id`, draft `workspace_id`).
Prva-wave odluka: nema posebnog `user` ni `workspace` DB modela; authoritative identity ključevi su za sada tanki string anchor-i `created_by` i `workspace_id`, a durable backend ključevi ostaju `mapping_jobs.job_id`, `draft_sessions.id`, `benchmark_datasets.id` i `evaluation_runs.id`.
- [x] Odlučiti da li prvi korak koristi lokalni/dev identity bootstrap ili jednostavan token-to-actor mapping bez uvođenja spoljnog identity provajdera.
Prva-wave odluka: koristi se lokalni/dev bootstrap kroz eksplicitno prosleđene `created_by` i `workspace_id` vrednosti uz postojeći admin-guard; spoljašnji identity provider i puni token-to-user mapping nisu otvoreni u ovom wave-u.
- [x] Uvesti migracioni sloj za nove identity i job-runtime tabele umesto daljeg ručnog SQLite schema drift-a.
- [x] Proširiti `mapping_jobs` model tako da čuva actor/workspace ownership, worker lease/claim stanje, heartbeat, retry, cancel metadata i recovery signal.
- [x] Dodati append-only event/progress log dovoljan da UI i dalje može da radi `poll status`, ali sada nad durable execution zapisom.
- [x] Isporučiti prvi identity-anchor pod-slice za `mapping` async job status kroz `created_by` i `workspace_id` metadata round-trip.
- [x] Isporučiti isti identity-anchor obrazac za `draft session` persistence i restore payload.
- [x] Isporučiti isti identity-anchor obrazac za benchmark dataset persistence i evaluation run history.
- [x] Razdvojiti API contract od execution implementacije tako da `mapping` i `benchmark` route-ovi ne zavise od in-process memorijskog owner-a.
Prva-wave odluka: `mapping` `start / poll / cancel` API ostaje stabilan, ali lifecycle ide preko `MappingJobStateStore` + SQLite runtime store-a; `benchmark` ostaje sync request/response tok i nema poseban in-process owner-dependent async runtime.
- [x] Isporučiti prvi durable execution slice za `mapping` jobove uz restart/recovery scenarije i fokusirane backend testove.
- [x] Zatvoriti benchmark execution granicu u prvom wave-u bez razbijanja postojećeg UX flow-a.
Prva-wave odluka: benchmark execution ne dobija poseban async durable worker runtime; durable backend sloj u ovom wave-u pokriva benchmark dataset identity i evaluation run history, dok benchmark run ostaje sinhroni tok.
- [x] Dokumentovati granicu prvog wave-a: minimal identity i durable jobs jesu uvedeni, ali puni user management i collaboration UX još nisu otvoreni.
Granica zatvorenog wave-a: uvedeni su minimalni actor/workspace anchor-i, durable mapping job status + recovery metadata i ownership-aware cancel/readout guard-ovi; nisu otvoreni puni user management, org model, async benchmark workers, niti collaboration UX preko više korisnika.

### 8. Workspace ownership + conflict semantics

Status: closed as the first backend workspace-ownership + conflict-contract wave.

Napomena:

- ovaj wave ne treba otvarati pre nego što postoji bar minimalni actor/workspace anchor iz prethodnog pravca
- cilj nije da svaki `st.session_state` ključ postane DB red, nego da svaki business-grade workspace entitet dobije ownership, version i konflikt semantiku
- najvažniji rezultat ovog pravca je da Semantra prestane da tretira aktivni workspace kao implicitni browser-local kontekst bez jasnog vlasnika i pravila prepisivanja

Minimalni ciljni scope za ovaj wave:

- `workspace` postaje backend entitet sa owner-om, statusom i stabilnim restore anchor-om
- `draft session`, `review state`, `decision workspace` i relevantni output draft-ovi dobijaju jasnu vezu ka workspace-u
- uvode se pravila za parallel open, stale restore, overwrite, optimistic version check i explicit handoff/resume ponašanje

Operativni redosled za prvi slice:

- prvi isporučeni pod-slice ovog wave-a je backend-only i namerno uzak: `workspace_id` sada prolazi kroz `mapping set` create/list/detail payload i kroz `apply` audit zapis, tako da reuse tok više nije potpuno odsečen od workspace konteksta
- sledeći isporučeni pod-slice proširio je isti anchor u `catalog` projekciju i `Catalog integration detail` odgovor, tako da `mapping set -> catalog handoff` više ne odbacuje `workspace_id` na read-model granici
- naredni isporučeni pod-slice uvodi isti anchor u `decision log` observability artifact: sync `auto/canonical` mapping putanje sada prosleđuju `created_by` i `workspace_id` u persisted decision logs, pa backend review/decision readout više nije potpuno anoniman i van workspace konteksta
- sledeći isporučeni pod-slice uvodi actor/workspace anchor i u prvi pravi `save decisions` artifact: persisted `draft session` sada backfill-uje `created_by` i `workspace_id` u svaki `mapping_decision_audit` entry, pa restore payload više ne čuva decision audit potpuno bez per-entry konteksta
- sledeći isporučeni pod-slice uvodi i prvi backend ownership reject na reuse putanji: `mapping set apply` sada odbija cross-workspace apply kada request workspace ne odgovara persisted `mapping_set.workspace_id`, a `apply` audit nasleđuje stored workspace anchor i kada ga request ne pošalje
- sledeći isporučeni pod-slice prenosi isti ownership guard i na job-control mutaciju: `mapping job cancel` sada opciono prima caller `created_by/workspace_id` context i odbija cross-workspace ili cross-actor cancel kada se ne poklapa sa persisted job metadata
- sledeći isporučeni pod-slice prenosi isti ownership guard i u prvi konkretan `resume draft` backend readout: `draft session detail` sada opciono proverava caller `created_by/workspace_id` context i odbija cross-workspace ili cross-actor resume kada se ne poklapa sa persisted draft metadata
- zatvarajući pod-slice ovog wave-a zaključuje backend granicu: current persisted reuse/review/restore artifacts sada imaju workspace anchor, prvi ownership reject radi na `apply reuse`, `cancel job` i `resume draft`, a konflikt contract je eksplicitno definisan pre budućih write-slice-ova sa `expected_version`

- [x] Potvrditi koji današnji Workspace entiteti moraju postati durable backend modeli (`workspace`, upload lineage, review queue state, decision state, transformation draft, selected mapping context).
Prva-wave odluka: durable backend modeli u sadašnjem scope-u su `mapping_jobs`, `draft_sessions`, `mapping_sets` + `catalog` projekcije, `benchmark_datasets` i `evaluation_runs`; budući standalone `workspace` entitet ostaje sledeći wave, ali današnji business-grade restore/reuse/audit artefakti više nisu samo browser-local.
- [x] Definisati šta je authoritative `workspace` snapshot, a šta ostaje legitimno session-local UI state.
Prva-wave odluka: authoritative backend snapshot za restore/review je `draft session detail` sa `source_handle`, `target_handle`, `mapping_runtime`, `mapping_editor_state` i `mapping_decision_audit`; session-local UI state ostaju navigacioni fokus, privremeni filteri, otvoreni paneli i drugi transient affordance-i koji ne nose ownership/audit semantiku.
- [x] Uvesti `workspace_id` kroz postojeće `draft session`, `mapping set reuse`, `catalog handoff` i `review/decisions` putanje.
- [x] Isporučiti prvi workspace-anchor pod-slice kroz `mapping set` create/list/detail persistence i `apply` audit trail.
- [x] Isporučiti sledeći workspace-anchor pod-slice kroz `mapping set -> catalog` projekciju i `Catalog integration detail` read model.
- [x] Isporučiti prvi workspace-anchor pod-slice u `review/decision` readout putanji kroz persisted `decision log` metadata (`created_by`, `workspace_id`).
- [x] Isporučiti prvi workspace-anchor pod-slice u `save decisions` snapshot putanji kroz `draft session mapping_decision_audit` metadata (`created_by`, `workspace_id`).
- [x] Isporučiti prvi backend ownership check na `apply reuse` putanji kroz reject za cross-workspace `mapping set apply` zahteve.
- [x] Isporučiti sledeći backend ownership check na `cancel job` putanji kroz reject za cross-workspace ili cross-actor cancel zahteve kada caller context postoji.
- [x] Isporučiti sledeći backend ownership check na `resume draft` putanji kroz reject za cross-workspace ili cross-actor draft-session resume zahteve kada caller context postoji.
- [x] Definisati optimistic concurrency contract (`version`, `updated_at`, `last_writer`, `stale_write` odgovor) za workspace-level izmene.
Prvi isporučeni `expected_version` implementation slice:
- `draft session update` sada koristi `version`, `last_writer` i `expected_version` contract; successful write podiže verziju, no-op write ne pravi lažni drift, a stale update vraća `409` sa `detail_code = stale_write` i current backend metadata
Radni contract za naredne implementation slice-ove:
- svaki durable workspace-like write model (`workspace`, `draft session`, `review state`, `decision state`, job control mutacije koje menjaju shared state) dobija monotono `version` polje, `updated_at` UTC timestamp i `last_writer` actor identifikator
- svaki mutating request koji menja postojeći shared workspace state treba da nosi `expected_version`; read-only i create tokovi ga ne zahtevaju, a legacy mutacije bez te vrednosti mogu ostati privremeno dozvoljene samo dok nisu prebačene na novi contract
- uspešan write inkrementira `version` za `+1` samo kada se payload zaista promeni; `updated_at` i `last_writer` prate poslednju stvarnu izmenu, dok idempotentni/no-op save ne treba da pravi lažni konflikt drift
- conflict odgovor je `409` sa stabilnim `detail_code = stale_write` i payload-om koji nosi bar `workspace_id`, `current_version`, `expected_version`, `updated_at`, `last_writer` i kratku poruku da je potreban reload pre overwrite-a
- [x] Definisati konflikt pravila za paralelni rad: isti owner u dve sesije, drugi korisnik nad istim workspace-om, restore starog draft-a preko novijeg workspace stanja, i cancel/close tokom aktivnog job-a.
Radna konflikt pravila za naredne ownership/concurrency slice-ove:
- isti owner u dve sesije nad istim workspace-om je dozvoljen, ali drugi write sa starim `expected_version` dobija `409 stale_write`; read-only resume/status tokovi ostaju dozvoljeni
- drugi korisnik nad istim workspace-om može da čita samo ako ownership policy to eksplicitno dozvoli, ali shared mutacije (`save decisions`, `apply reuse`, `cancel job`, budući `workspace save`) moraju biti odbijene čim caller `created_by` ili `workspace_id` ne odgovara authoritative backend zapisu
- restore starog draft-a preko novijeg workspace stanja ne sme tiho da overwrite-uje backend stanje: dozvoljen je read-only resume payload, ali prvi naredni write mora da prođe kroz `expected_version` proveru ili da vrati `stale_write` sa current metadata za reload/rebase
- cancel ili close tokom aktivnog job-a ne sme da menja ownership anchor: `cancel job` je dozvoljen samo matching owner/workspace caller-u, a kasniji restore/close tokovi moraju da vide final job status umesto da implicitno resetuju workspace state
- [x] Zatvoriti ownership scope za današnje shared backend mutacije i readout putanje.
Prva-wave odluka: current shared backend putanje koje postoje danas (`draft session` save/resume snapshot, `mapping set apply`, `mapping job cancel`, persisted `decision log` readout i `mapping_decision_audit` snapshot) imaju anchor ili ownership guard; buduće dedicated `save decisions` mutation rute moraju naslediti isti contract kada budu uvedene.
- [x] Zatvoriti backend handoff scope za `Catalog`, `Governance` i `Benchmarks` workspace context.
Prva-wave odluka: persisted backend artefakti za `Catalog`/`Governance`/`Benchmarks` sada nose `workspace_id` gde imaju business-grade reuse/audit smisao; browser-local navigation handoff ostaje eksplicitno UI-local i nije deo ovog backend wave-a.
- [x] Isporučiti prvi backend restore/conflict slice sa fokusiranim backend testovima.
Prva-wave odluka: backend restore/conflict foundation zatvara se kroz ownership-aware `resume draft`, `apply reuse`, `cancel job` guard-ove i eksplicitni `stale_write` contract; browser smoke za budući UI stale-rebase tok prelazi u sledeći UI hardening wave.
- [x] Dokumentovati koja ponašanja postaju eksplicitna: ko je owner, kada je stanje stale, kada je potreban reload, i kada sistem odbija overwrite.
Eksplicitna ponašanja posle zatvaranja wave-a:
- owner je onaj actor/workspace anchor koji je persisted uz job, draft ili mapping-set artifact; backend više ne pretpostavlja implicitni lokalni owner za shared read/write tokove
- stanje je stale kada caller radi write sa starim `expected_version` ili pokušava resume/apply/cancel iz nepoklopljenog owner/workspace konteksta
- reload je potreban kada backend vrati `409 stale_write` ili ownership mismatch detalj koji pokazuje da je authoritative stanje promenjeno ili pripada drugom anchor-u
- overwrite se odbija kada shared mutacija nema matching ownership context ili kada sledeći concurrency slice aktivira `expected_version` proveru nad novijim authoritative snapshot-om

Napomena o granici zatvorenog scope-a:

- poglavlja `7` i `8` su završena u okviru svog backend wave scope-a i ne nose više otvorene obavezne stavke za početak poglavlja `9`
- sve dalje aktivnosti na istoj temi vode se kao zaseban nastavak ispod i predstavljaju sledeći collaboration/write-hardening wave, ne dokaz da `7` ili `8` nisu bili kompletirani

### 8A. Follow-on wave: shared workspace writes and collaboration readiness

Status: completed for the first draft-session anchored shared-write wave.

Svrha:

- odvojiti budući rad na multi-user write contract-ima, stale/rebase UX-u i eventualnom pravom `workspace` agregatu od već zatvorenih backend foundation wave-ova u `7` i `8`
- omogućiti da `9` krene nezavisno, dok se ovaj wave otvara samo kada želimo dalje da širimo collaboration i shared-write semantiku

Šta je već rešeno pre ovog wave-a:

- minimalni actor/workspace anchor postoji kroz `created_by` i `workspace_id`
- durable `mapping job` runtime i recovery metadata postoje
- prvi ownership guard-ovi postoje za `apply reuse`, `cancel job` i `resume draft`
- prvi `expected_version` write path postoji kroz `draft session update`

Šta je isporučeno u ovom wave-u:

- ownership + stale guard logika više ne ostaje ručno kopirana samo po starim putanjama, već koristi prvi zajednički helper/policy obrazac kroz `job cancel`, `draft resume/update` i `mapping set apply`
- `draft session` je potvrđen kao prvi authoritative shared-write anchor za Workspace continuity i collaboration-readiness, bez otvaranja novog `workspace` agregata prerano
- uveden je prvi pravi `save decisions` API surface kroz dedicated `draft session decision-state` write putanju sa `expected_version`, `last_writer`, `updated_at` i `stale_write` contract-om
- uveden je i odvojeni `review state` write surface nad istim `draft session` anchor-om, tako da filteri/section context mogu da se čuvaju bez punog snapshot overwrite-a
- Streamlit UI sada prati aktivni draft session i na `stale_write` reaguje konzistentno: reload-uje latest backend draft state umesto da tiho nastavi sa zastarelim lokalnim anchor-om
- `mapping set status/apply` u ovom wave-u ostaju ownership-only mutacije; puni optimistic concurrency nije nametnut governance verzijama koje već imaju sopstvenu version-lineage semantiku

Operativni pregled aktivnosti:

- [x] Uvesti prvi ponovljiv helper obrazac za ownership + stale guard-ove na postojećim shared write/read putanjama (`job cancel`, `draft resume/update`, `mapping set apply`) pre nego što krene novi write surface.
- [x] Proširiti `expected_version`, `version`, `updated_at` i `last_writer` contract na prve naredne shared write putanje posle `draft session update`, kroz dedicated `decision-state` i `review-state` write surface-e.
- [x] Definisati da `draft session decision-state/review-state` dobijaju isti optimistic concurrency contract, dok `mapping set status/apply` u ovom wave-u ostaju ownership-only mutacije.
- [x] Potvrditi da `draft session` ostaje dovoljan authoritative restore/write anchor za prvi collaboration-readiness wave; poseban `workspace` agregat se odlaže dok shared write surface ne preraste ovaj scope.
- [x] Proširiti uvedeni helper/policy layer za ownership + stale checks na prve nove shared route-ove, umesto da se guard logika dalje širi ručno po svakom route-u.
- [x] Isporučiti prvi pravi `save decisions` API surface koji ne zavisi od implicitnog browser-local stanja i koji direktno piše durable backend decision state.
- [x] Dodati backend read/write model za `review state` i `decision state` kroz draft-session partial update contract, bez preuranjenog uvodjenja novog agregata.
- [x] Definisati i isporučiti prvi UI odgovor na `stale_write`: reload current backend state za aktivni draft session.
- [x] Potvrditi da `Catalog`, `Governance`, `Benchmarks` i `target intent` tokovi i dalje smeju da koriste UI-local navigacioni handoff kada nema durable write semantike, dok shared writes koriste backend anchor.
- [x] Odvojiti sledeći auth/collaboration wave od ovog scope-a: puni user management, org model, assignee inbox, live collaboration i lock indicators nisu deo zatvorenog 8A wave-a.

Kriterijum za zatvaranje ovog follow-on wave-a:

- najmanje dva do tri glavna shared write path-a koriste isti optimistic concurrency contract
- stale/reload ponašanje je konzistentno između backend odgovora i UI reakcije
- ownership i concurrency guard-ovi više ne nastaju ad hoc po ruti, nego kroz jasan ponovljiv obrazac
- i dalje ostaje legitimno da se posle toga otvori zaseban auth/collaboration epic, umesto da se ova tema beskonačno produžava

Operativni pregled zatvorenog scope-a:

- [x] Tri glavna shared write path-a sada koriste isti draft-session optimistic concurrency contract: `draft session update`, `decision-state save`, `review-state save`.
- [x] UI stale/reload ponašanje je usklađeno sa backend `stale_write` odgovorom kroz reload latest draft-state tok.
- [x] Ownership i concurrency guard-ovi više ne nastaju ad hoc po prvim ključnim mapping rutama.
- [x] Dalji multi-user collaboration i auth scope ostaju legitimno izdvojeni u sledeći epic.

### 8B. Follow-on wave: broader collaboration UX and shared artifact concurrency

Status: future follow-on after closed `8A`.

Šta sledeće ostaje izvan zatvorenog 8A scope-a:

- browser smoke pokrivenost za stale resume/rebase tokove kada UI dobije pun compare/rebase affordance
- odluka da li dodatni shared artifact write-ovi van draft-session anchor-a treba da dobiju isti optimistic concurrency contract ili posebnu semantiku
- eventualni standalone `workspace` agregat ako shared write surface preraste draft-session anchor
- auth/org/live-collaboration sloj: user management, lock indicators, assignee inbox i slični multi-user workflow elementi

### 9. Target platform intent and system-specific target profiles

Status: completed for the first canonical-first target-intent wave.

Napomena:

- ovaj pravac ne menja canonical-first osnovu proizvoda
- cilj nije da korisnik bira vendor umesto canonical sloja, nego da eksplicitno kaže ka kom velikom target sistemu želi da ide
- taj izbor radi kao `target intent` signal koji pojačava canonical target projection i explainability, bez preskakanja canonical sloja
- zatvoreni scope ovog wave-a ostaje `Source -> Canonical -> Target-aware canonical projection`, ne puni vendor-specific output generation matrix

Minimalni produktni cilj:

- u `Workspace` setup toku korisnik može da odabere `integration target family`
- `Canonical only` ostaje validna i prva opcija
- izbor konkretnog target sistema ne preskače canonical mapiranje, nego aktivira system-aware target profile i relevantnije output/reuse tokove

Šta je isporučeno u ovom wave-u:

- podržani `target intent` izbori su formalizovani kroz backend contract za `canonical` i `sap`
- uveden je `/mapping/target-intents` endpoint kao izvor podržanih opcija za workspace/setup i canonical mapping tokove
- `build_virtual_target_schema()` više nije canonical-only: sada gradi canonical projection sa target-aware alias hintovima za `sap`
- `GET /mapping/target-fields` koristi isti target-intent contract i radi za podržane target profile opcije, ne samo za `canonical`
- canonical mapping response sada eksplicitno vraća `mapping_runtime.target_system`, `mapping_runtime.target_profile` i `mapping_runtime.target_projection_mode`
- prvi realni vendor vertical slice pokriven je kroz `sap_customer_master` target profile, sa fokusiranom runtime validacijom bez regressije canonical-only contract-a

Produktna pravila koja treba očuvati:

- canonical ostaje stabilan semantički sloj i glavni reuse anchor
- vendor-specific target profile služi kao accelerator i implementacioni izlazni sloj, ne kao nova source-of-truth semantika
- system-specific knowledge ne sme automatski da postane global canonical registry bez stewardship/promocije

Operativni pregled zatvorenog scope-a:

- [x] Potvrđen je backend tok `source upload + target intent + canonical/system-aware canonical izlaz` bez narušavanja postojećeg `canonical-only` toka.
- [x] Definisan je prvi isporučeni skup `integration target family` opcija za `Canonical only` i `SAP`, uz canonical-first pravilo.
- [x] `target intent` je postao deo mapping request konteksta i response explainability contract-a, a ne samo prolazni UI filter.
- [x] `target intent` utiče na virtual target izbor i candidate narrowing kroz target-aware canonical alias projection.
- [x] Uveden je prvi uski `system-specific target profile` slice za SAP, bez otvaranja preširokog vendor matrix-a.
- [x] Za ovaj wave storage/reuse contract ostaje na postojećem `target_system` + `artifact_type` modelu, bez otvaranja novog persistence sloja samo zbog target intent-a.
- [x] Explainability ostaje jasna kroz runtime metadata contract koji razlikuje `canonical_only` i `target_aware_canonical` projekciju.
- [x] Isporučen je prvi uski vertical slice sa fokusiranom runtime validacijom nad realnim SAP use case-om i bez regressije canonical-only putanje.
- [x] Dokumentovana je granica proizvoda: target platform dropdown ostaje intent/projection layer, ne zamena za canonical model.

Napomena o granici zatvorenog scope-a:

- ovaj wave ne uvodi puni vendor-specific output generation niti širi target matrix preko prva dva podržana izbora
- ovaj wave ne uvodi poseban persisted `target_profile` read/write model u `mapping set`, `catalog` ili budući `workspace` agregat
- buduće širenje ove teme treba voditi kao zaseban nastavak ispod, ne kao dokaz da `9` nije kompletirana

### 9A. Follow-on wave: broader target profile matrix and workspace continuity persistence

Status: started with first continuity slice; broader matrix/reuse persistence still follow-on.

Šta ovaj nastavak otvara tek kada zatreba:

- širenje target-intent opcija na dodatne sisteme kao što su `Salesforce`, `Workday`, `Coupa` ili drugi sistemi sa dovoljno jakim knowledge signalom
- proširenje postojećeg `draft session` / `workspace reuse` continuity contract-a tako da `target_system` i eventualni `target_profile` postanu deo stabilnog workspace identiteta, a ne samo runtime metadata jednog mapping request-a
- odvajanje explicitnog `target_profile` persistence contract-a u `mapping set`, `catalog`, `workspace reuse` i eventualni budući `workspace` agregat tek kada to stvarno postane potrebno za reuse i ownership semantiku
- target-aware output artifact generation posle canonical mapiranja, umesto današnjeg canonical/system-aware canonical projection scope-a
- dodatnu explainability i catalog/reuse logiku koja razlikuje canonical projection, target-specific output i eventualne profile-specific transform templates

Prvi isporučeni continuity slice u ovom nastavku:

- `draft session` payload sada čuva opšti `workspace_target_context` snapshot (`target_system`, `target_profile`, `target_projection_mode`, `artifact_type`), umesto da target intent ostane samo uski canonical-specific izuzetak
- restore/conflict logika koristi taj novi workspace target context uz backward-compatible fallback na stariji `canonical_target_system` payload
- fokusirana backend smoke validacija potvrđuje da canonical draft session može da sačuva, izlista i vrati isti target-intent/projection režim

Strateška napomena:

- ovo nije zaseban persistence sloj samo za `target intent`, već nastavak globalne strategije da isti workspace može bezbedno da se vrati, nastavi i reuse-uje sa istim operativnim kontekstom
- prvi cilj tog nastavka nije novi vendor matrix, nego da restore/runtime kontinuitet dosledno pamti u kom intent/projection režimu je workspace radio

### 10. Epic 14A/14B: performance and signal precomputation

Status: queued after discovery/hardening stabilization.

Napomena:

- vector cache i stable precompute ne treba otvarati kao veliki wave pre nego što reuse discovery i operational hardening pokažu stvarni pressure

- [ ] Potvrditi koje signalne ili runtime putanje danas stvarno prave najveći latency/cost pressure.
- [ ] Definisati prvi uski cache/precompute slice koji ne komplikuje explainability contract.
- [ ] Isporučiti prvi performance slice sa benchmark-validacijom i bez regressions u ranking ponašanju.

### 11. Transformation Design / structured transformation spec

Status: first implementation slice delivered; docs and broader persistence follow-on remain open.

Napomena:

- današnji `Workspace > Output` već pokriva transformation generation, manual transformation editing, preview, starter codegen i refinement, ali nema jednu centralnu, business-readable transformation specifikaciju
- ovaj pravac ne treba otvoriti kao slobodan `opiši transformaciju pa generiši kod` prompt box, nego kao kontrolisani `Transformation Design` sloj koji korisnik može da pregleda, menja, potvrdi i kasnije sačuva
- prvi slice treba da ostane unutar `Workspace > Output` kako bismo izbegli prerani veliki workflow refactor; poseban `Transform` korak ima smisla tek ako prvi slice dokaže jasnu korisničku vrednost

Predloženi prvi slice:

- `Transformation Design` sekcija u `Workspace > Output`
- strukturisani `TransformationSpec` model sa `target_grain`, `target_fields`, `field_rules`, `global_rules`, `defaults`, `validation_rules` i primerima kada postoje
- bounded pomoćni tok koji pretvara prirodni jezik u predlog strukturisanog spec-a, bez direktnog prompt-to-code auto-apply ponašanja
- `preview` i `codegen` koriste potvrđeni spec kada postoji; u suprotnom ostaju na današnjem output contract-u

Operativne odluke za prvi talas:

- authoritative put ostaje ručno potvrđen i vidljivo editovan transformation spec
- `LLM` predlog je advisory, mora da vrati strukturisani odgovor i ne sme direktno da zameni aktivni generated artifact
- prvi slice ne otvara multi-step orchestration, scheduler, batch runtime niti proizvoljni DAG model
- prvi slice je sada stvarno isporučen kroz `Workspace > Output`, backend `TransformationSpec` contract, bounded proposal helper, spec-aware preview/codegen i draft-session restore/save tok
- sidebar `Workspace Copilot` output readiness/explanation sada koristi `Transformation Design` summary i pending spec proposal stanje za warning prioritization
- operativni browser E2E runner za `customer-draft-session` prosiren je da proverava i restored `Transformation Design` seed u `Workspace > Output`, ali live potvrda ostaje otvorena dok se ne zatvori trenutni `Resume draft session` browser timing issue

- [x] Potvrditi tačnu granicu između današnjeg transformation authoring/output surface-a i novog `Transformation Design` sloja.
- [x] Definisati minimalni `TransformationSpec` contract za prvi slice (`target_grain`, `target_fields`, `field_rules`, `global_rules`, `defaults`, `validation_rules`, `examples`).
- [x] Odlučiti i dokumentovati da prvi slice živi u `Workspace > Output`, a ne kao novi top-level workflow korak.
- [x] Dizajnirati `Transformation Design` UI shell za target structure, per-field rules i global rules bez velikog layout refaktora.
- [x] Uvesti session-state model za transformation spec tako da može da živi uz postojeći output workflow bez konflikta sa današnjim transformation editor-om.
- [x] Dodati bounded `natural language -> structured spec proposal` helper koji vraća striktno validiran predlog umesto generated code-a.
- [x] Uvesti jasnu validaciju i state model za `invalid`, `incomplete` i `ready for preview/codegen` transformation spec stanja.
- [x] Povezati potvrđeni transformation spec sa postojećim `preview` i `Pandas` / `PySpark` / `dbt` generation putanjama bez rušenja postojećeg fallback contract-a.
- [x] Definisati kako prvi slice persistira ili namerno još ne persistira transformation spec kroz `draft session` i kasnije `mapping set` / output draft tok.
- [x] Dodati fokusirane testove za spec state, proposal normalizaciju, validation gate i output integration.
- [ ] Ažurirati `current_state.md`, `help`, `README` i relevantne reference kada prvi slice bude stvarno isporučen.
