# Semantra Demo Technical Story

Ovaj dokument je propratna tehnicka prica uz live demo runbook i screenshotove. Ideja nije samo da objasni sta korisnik klikce, nego i sta aplikacija radi ispod haube: koji Streamlit view, koja FastAPI ruta, koji servis i koji deo logike ucestvuju u svakom od 8 demo case-ova.

## Zajednicki okvir

- `streamlit_app.py` je glavni ulaz u UI i radi kao thin client iznad FastAPI backend-a.
- `streamlit_ui/api.py` centralizuje pozive prema backend-u kroz `api_request(...)`, dodaje `X-Admin-Token` kada postoji i cita `API Base URL` iz `st.session_state`.
- Workspace stanje se drzi u `st.session_state`, dok se trajni artefakti cuvaju preko backend persistence sloja.
- Backend registruje glavne rute u `backend/app/main.py`: `upload`, `mapping`, `catalog`, `evaluation`, `knowledge` i `observability`.

## 1. Workspace setup sa jednim source/target parom

Screenshot: `01_workspace_setup_profiled.png`

Sta korisnik vidi:

- upload source i target fajla
- interpretaciju da li je fajl row-data, schema spec ili SQL snapshot
- profilisani source i target summary posle `Upload and profile`

Sta se desava u aplikaciji:

- `streamlit_app.py` delegira na `render_workspace_tab(...)` iz `streamlit_ui/workspace_views.py`.
- U okviru `Workspace > Setup`, UI koristi `st.file_uploader(...)` za source i target, a zatim radi pre-inspection korake preko `detect_spec_hint_for_upload(...)` i `sql_tables_for_upload(...)` iz `streamlit_ui/api.py`.
- Kada korisnik klikne `Upload and profile`, `workspace_views.py` poziva `upload_dataset_handle(...)` za svaki fajl i rezultat upisuje u `st.session_state["upload_response"]`.

Koje backend rute ucestvuju:

- `POST /upload/spec/detect` za auto-detekciju schema-spec fajlova
- `POST /upload/sql/tables` za otkrivanje tabela unutar `.sql` snapshot-a
- `POST /upload/handle` za stvarni upload i pretvaranje ulaza u `DatasetHandle`
- `POST /upload/handle/metadata` ako se koristi source companion metadata

Koji servisi odradjuju posao:

- `backend/app/api/routes/upload.py` orkestrira upload tok
- `app.services.tabular_upload_service.parse_tabular_payload(...)` parsira CSV/JSON/XML/XLSX row data
- `app.services.spec_upload_service.parse_spec_payload(...)` pravi schema profile iz field-per-row specifikacije
- `app.services.schema_snapshot_service.build_schema_profile_from_sql_snapshot(...)` pravi profil iz SQL snapshot-a
- `app.services.upload_store.dataset_store` cuva rows i schema profile i vraca `dataset_id` koji ce dalje koristiti mapping tok

Tehnicka poenta za prezentaciju:

- UI ne radi mapping direktno nad raw fajlom. Prvi korak je normalizacija ulaza u backend `DatasetHandle` i `SchemaProfile`, tako da ostatak sistema radi jednako za CSV, JSON, XML, XLSX i SQL snapshot.

## 2. Generate mapping i review trust layer-a

Screenshot: `02_review_trust_layer.png`

Sta korisnik vidi:

- `Generate mapping`
- status blok `Mapping activity`
- `Mapping Trust Layer`, confidence, explanation, `Signal breakdown`, canonical path i LLM decision proposition kada je primenljivo

Sta se desava u aplikaciji:

- `streamlit_ui/workspace_views.py` koristi `poll_mapping_job(...)` da startuje background posao preko `POST /mapping/auto/jobs` i zatim poluje `GET /mapping/jobs/{job_id}`.
- Po zavrsetku, `initialize_mapping_editor_state(...)` iz `streamlit_ui/mapping_state.py` priprema editable stanje za Review i Decisions tok.
- Sam prikaz trust sloja radi `display_trust_layer(...)` iz `streamlit_ui/workspace_review_views.py`, dok `render_mapping_review(...)` prikazuje ranked candidate pregled.

Koje backend rute ucestvuju:

- `POST /mapping/auto/jobs`
- `GET /mapping/jobs/{job_id}`
- alternativno `POST /mapping/canonical/jobs` ako se radi canonical-only varijanta

Koji servisi i funkcije odradjuju posao:

- `backend/app/services/mapping_service.py` je glavni engine
- `generate_mapping_candidates(...)` vodi ceo pipeline
- `rank_targets_for_source(...)` racuna kandidate po source polju
- `compute_signals(...)` puni vise signala: `name`, `semantic`, `knowledge`, `canonical`, `pattern`, `statistical`, `overlap`, `embedding`, `correction`, `llm`
- `compute_final_score(...)` pravi finalni score na osnovu aktivnog scoring profila iz konfiguracije
- `apply_llm_validation(...)` ukljucuje LLM samo u ambiguity band-u ili rescue slucajevima, umesto da LLM bude primarni mapper
- `assign_unique_targets(...)` radi globalnu dodelu target polja da vise source kolona ne zavrsi na istom target-u bez kontrole
- `build_llm_decision_proposition(...)` pravi strukturisan LLM review objekat za UI
- `refresh_signal_breakdown(...)` osvezava explainability liniju nakon eventualnog LLM rerank-a

Tehnicka poenta za prezentaciju:

- Trust layer nije dekoracija preko rezultata, nego UI projekcija stvarnih scoring i ranking odluka iz `mapping_service.py`. Korisnik zato ne gleda black-box odgovor, nego auditabilan rangirani predlog.

## 3. Decisions: accepted i manual override

Screenshot: `03_decisions_active_review.png`

Sta korisnik vidi:

- `Manual Review` u `Workspace > Review`
- promena target-a i statusa po source polju
- `Active Decisions` u `Workspace > Decisions`

Sta se desava u aplikaciji:

- `render_mapping_editor(...)` iz `streamlit_ui/workspace_review_views.py` izlistava svako source polje, dozvoljava promenu target-a i postavlja status na `accepted`, `needs_review` ili `rejected`.
- Izabrane vrednosti se drze u `st.session_state["mapping_editor_state"]`.
- `build_mapping_decisions(...)` iz `streamlit_ui/mapping_state.py` prevodi editor stanje u kanonski spisak aktivnih odluka koje koristi preview, codegen, benchmark i persistence tok.
- `render_mapping_decision_summary(...)` iz `streamlit_ui/workspace_decision_views.py` prikazuje taj spisak kao `Active Decisions`.

Koji servisi i helper-i odradjuju posao:

- `default_editor_entry(...)` i `initialize_mapping_editor_state(...)` pune pocetno stanje iz auto-mapper izlaza
- `effective_transformation_code(...)` i `resolve_suggested_transformation_code(...)` iz `streamlit_ui/mapping_helpers.py` odlucuju da li se koristi direct, suggested ili custom transformacija
- `upsert_manual_mapping(...)` i `remove_manual_mapping(...)` podrzavaju dodatne rucne intervencije iz Decisions taba

Tehnicka poenta za prezentaciju:

- Auto-mapper daje predlog, ali finalna operativna istina u aplikaciji postaje ono sto udje u `mapping_decisions`. To je governance tacka gde covek ima poslednju rec.

## 4. Output: advisory preview i accepted-only codegen gate

Screenshot: `04_output_preview_and_codegen_gate.png`

Sta korisnik vidi:

- `Generate preview`
- preview rezultat i transformation validation detalje
- `Generate Pandas code`, koji ostaje blokiran dok sve aktivne odluke nisu `accepted`

Sta se desava u aplikaciji:

- `streamlit_ui/workspace_views.py` gradi `mapping_decisions` iz session state-a.
- `Generate preview` salje `POST /mapping/preview` i vraca sample izlaz za prvih nekoliko redova.
- `Generate Pandas code` salje `POST /mapping/codegen`, ali samo ako `_workspace_codegen_block_reason(...)` ne vrati blokadu.
- Preview advisory poruka dolazi iz `_workspace_preview_advisory_message(...)` i namerno dozvoljava korisniku da vidi rezultat i pre potpune governance potvrde.

Koje backend rute i servisi ucestvuju:

- `POST /mapping/preview` u `backend/app/api/routes/mapping.py`
- `POST /mapping/codegen` u istoj ruti
- `backend/app/services/preview_service.build_preview(...)` pravi preview i `transformation_previews`
- `backend/app/services/transformation_service.build_transformed_target_frame(...)` izvrsava transformacionu logiku nad uzorkom podataka
- `backend/app/services/codegen_service.generate_pandas_code(...)` emituje pandas kod za finalne odluke
- `backend/app/api/routes/mapping.py::_require_accepted_output_decisions(...)` i `streamlit_ui/governance.py::mapping_output_block_reason(...)` zajedno sprovode isto governance pravilo i u backend-u i u UI-ju

Tehnicka poenta za prezentaciju:

- Preview je namerno savetodavan, a codegen je namerno restriktivan. To razdvaja analiticko gledanje od produkcionog artefakta.

## 5. Save mapping set i prelazak u approved

Screenshot: `05_saved_mapping_set_approved.png`

Sta korisnik vidi:

- formu za `Mapping set name`, owner, assignee, note i review note
- `Save mapping set version`
- listu sacuvanih mapping set-ova
- promenu statusa u `approved`

Sta se desava u aplikaciji:

- `render_mapping_io_panel(...)` iz `streamlit_ui/workspace_decision_views.py` skuplja aktivne odluke i metadata polja.
- `build_mapping_set_payload(...)` iz `streamlit_ui/mapping_state.py` formira payload koji, osim mapping odluka, nosi i canonical coverage kontekst, unmatched source polja i governance metadata.
- Posle save-a, isti panel omogucava `Load saved mapping sets`, `Update saved mapping set status` i `Load selected mapping set audit`.

Koje backend rute i servisi ucestvuju:

- `POST /mapping/sets` za kreiranje verzionisanog mapping seta
- `GET /mapping/sets` za listu verzija
- `POST /mapping/sets/{mapping_set_id}/status` za status tranziciju
- `GET /mapping/sets/{mapping_set_id}/audit` za audit trag
- `backend/app/services/persistence_service.save_mapping_set(...)` cuva durable artefakt
- `append_mapping_set_audit(...)` u `backend/app/api/routes/mapping.py` dopisuje audit zapis pri `create`, `status_change` i `apply`

Tehnicka poenta za prezentaciju:

- Ovde mapping prestaje da bude samo session state. Postaje verzionisani, auditabilni artefakt sa statusnim lifecycle-om, vlasnistvom i review napomenama.

## 6. Catalog: detail, latest approved version i Reuse in Workspace

Screenshot: `06_catalog_detail_and_reuse.png`

Sta korisnik vidi:

- `Catalog` tab sa search/filter slojem
- integration detail sa latest i latest approved verzijom
- version drilldown i `Reuse in Workspace`

Sta se desava u aplikaciji:

- `render_catalog_tab(...)` iz `streamlit_ui/catalog_views.py` poziva catalog endpoint-e i drzi nekoliko detail view state-ova u session-u.
- Kada korisnik klikne `Reuse in Workspace`, helper `_reuse_catalog_mapping_set_in_workspace(...)` radi backend apply poziv i zatim kroz `_apply_mapping_set_detail_to_workspace(...)` vraca taj artefakt nazad u aktivni workspace state.

Koje backend rute i servisi ucestvuju:

- `GET /catalog/integrations` i `GET /catalog/search` za pronalazenje reusable integracija
- `GET /catalog/integrations/{integration_name}` za integration detail
- `POST /mapping/sets/{mapping_set_id}/apply` za vracanje approved verzije u workspace tok
- `backend/app/api/routes/mapping.py::apply_mapping_set(...)` eksplicitno blokira reuse ako status nije `approved`
- `backend/app/services/persistence_service` odrzava i mapping set-ove i catalog projekcije nad njima, ukljucujuci canonical concepts i unmatched source informacije

Tehnicka poenta za prezentaciju:

- Catalog nije samo pregled starih rezultata. To je reuse sloj nad odobrenim mapping artefaktima, sa jasnim pravilom da samo approved verzija sme nazad u Workspace.

## 7. Canonical Console: concept detail i overlay activation

Screenshot: `07_canonical_console_overlay_active.png`

Sta korisnik vidi:

- canonical concept search i detail
- usage, field contexts, active overlay aliases i catalog usage
- upload knowledge overlay CSV-a, validation, save i activation

Sta se desava u aplikaciji:

- `render_canonical_console_panel(...)` iz `streamlit_ui/admin_views.py` je governance povrsina za canonical runtime.
- Registry deo koristi `GET /knowledge/canonical-concepts`, a detail deo `GET /knowledge/canonical-concepts/{concept_id}`.
- Overlay deo koristi `Validate knowledge CSV`, `Save overlay version`, `Load details` i `Activate selected overlay`, a UI odmah osvezava runtime summary posle tih akcija.

Koje backend rute i servisi ucestvuju:

- `GET /knowledge/canonical-concepts` za registry
- `GET /knowledge/canonical-concepts/{concept_id}` za detalj koncepta
- `POST /knowledge/overlays/validate` za validaciju overlay CSV-a
- `POST /knowledge/overlays` za cuvanje overlay verzije
- `GET /knowledge/overlays` i `GET /knowledge/overlays/{overlay_id}` za listu i detalje
- `POST /knowledge/overlays/{overlay_id}/activate` za aktivaciju overlay verzije

Koji servisi odradjuju posao:

- `backend/app/api/routes/knowledge.py::_canonical_concept_registry(...)` spaja bazni glossary, field contexts, catalog usage i aktivne overlay alias-e u jedinstven registry pogled
- `backend/app/services/knowledge_overlay_service.knowledge_overlay_validation_service` validira CSV redove, konflikte i duplicate unose
- `backend/app/services/persistence_service` cuva verzije i overlay entry-je
- `backend/app/services.metadata_knowledge_service.refresh()` osvezava runtime canonical/knowledge sloj odmah nakon aktivacije
- `metadata_knowledge_service` potom koristi overlay alias-e u sledecim mapping rundama kao deo knowledge i canonical alignment logike

Tehnicka poenta za prezentaciju:

- Ovo nije debug-only ekran. To je governance mehanizam za knowledge runtime: validacija, verzionisanje, aktivacija i momentalno osvezavanje canonical interpretacije za naredne mapping tokove.

## 8. Benchmarks: run i correction impact

Screenshot: `08_benchmarks_run_and_correction_impact.png`

Sta korisnik vidi:

- cuvanje trenutnog mappinga kao benchmark dataset
- izbor sacuvanog benchmark dataset-a
- `Run selected benchmark`
- `Measure correction impact`
- rezultat, correction impact i opcionalno profile comparison / run history

Sta se desava u aplikaciji:

- `render_benchmark_tab(...)` iz `streamlit_ui/benchmark_views.py` gradi benchmark case iz aktivnog workspace stanja preko `build_current_benchmark_case(...)`.
- `Save current mapping as benchmark` salje taj case na backend kao trajni benchmark dataset.
- `Run selected benchmark` izvrsava evaluaciju nad sacuvanim dataset-om i smesta rezultat u `st.session_state["last_benchmark_result"]`.
- `Measure correction impact` radi drugi evaluacioni prolaz i prikazuje razliku izmedju baseline i correction-aware rezima.

Koje backend rute i servisi ucestvuju:

- `POST /evaluation/datasets` za cuvanje benchmark dataset-a
- `GET /evaluation/datasets` za listu benchmark dataset-ova
- `POST /evaluation/datasets/{dataset_id}/run` za benchmark rezultat
- `POST /evaluation/datasets/{dataset_id}/correction-impact` za correction impact
- `POST /evaluation/datasets/{dataset_id}/compare-profiles` za scoring profile comparison
- `GET /evaluation/runs` za istoriju benchmark run-ova

Koji servisi odradjuju posao:

- `backend/app/services/evaluation_service.evaluate_cases(...)` rekreira source i target `SchemaProfile` objekte po benchmark case-u i ponovo poziva `generate_mapping_candidates(...)`
- `evaluate_correction_impact(...)` poredi baseline i correction-aware rezultat
- `build_scoring_profile_comparison_response(...)` poredi profile kao sto su `balanced`, `schema_only`, `data_rich` i `canonical_first`
- posto benchmarking koristi isti `mapping_service.py`, ovo nije odvojeni demo engine nego merenje nad istom realnom ranking logikom koja se koristi i u Workspace toku

Tehnicka poenta za prezentaciju:

- Benchmarks sluze da se heuristika i governovano ucenje mere kao proizvodni signal kvaliteta, a ne samo da se vizuelno pregledaju jedan po jedan predlog.

## Kratka poruka za zatvaranje price

Ako treba jedna zajednicka tehnicka recenica za svih 8 case-ova, najkrace je:

- Semantra koristi Streamlit kao review i governance klijent, FastAPI kao orchestration sloj, `mapping_service.py` kao deterministicki scoring engine sa ciljano ukljucenim LLM-om, i persistence/catalog/knowledge/evaluation slojeve da isti mapping od pregleda preraste u odobren, reusable i merljiv artefakt.