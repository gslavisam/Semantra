
Imam dovoljno uvida — pregledao sam stvarni kod (backend ~18.8K linija, UI ~17.4K linija), a ne samo dokumentaciju. Evo detaljne revizije i audita projekta Semantra.

## Status update — 2026-06-01

Ovaj dokument je nastao kao originalni audit snapshot. Posle poslednjih execution wave-ova, deo nalaza više nije otvoren u istom obliku. Ispod je kratka status matrica za glavne tačke iz ovog review-a.

### Zatvoreno ili suštinski zatvoreno

- `In-memory vs. durable nekonzistentnost` za upload dataset handle-ove: zatvoreno kroz durable `uploaded_datasets` + repository-backed `dataset_store` façade.
- `SQLite bez WAL/rollback hardening-a`: zatvoreno kroz `WAL`, `busy_timeout`, `foreign_keys=ON` i eksplicitni `rollback()`.
- `llm_timeout_seconds se ignoriše`: zatvoreno kroz eksplicitne bounded timeout settings i centralne helper-e.
- `Duplirana logika praga/težina`: delimično zatvoreno, ali dovoljno da više ne bude razasuta po engine-u; scoring/threshold/SAP calibration politika je izdvojena u `mapping_policy.py`.

### Delimično rešeno

- `Sav backend je sinhron + blokirajući`: nije prebačen na pravi async `httpx` / worker model, ali više nije potpuno nezaštićen. Uveden je mali backpressure boundary (`429 + Retry-After`) za duže sync mapping i bounded LLM putanje.
- `SAP hardkodovan kroz engine`: nije uklonjen iz engine-a, ali je značajno sabijen i centralizovan kroz poseban policy sloj, pa više nije zalepljen kroz više nepovezanih threshold funkcija.
- `Dokumentacija vs. realnost`: značajno popravljeno. Današnji `current_state.md` više eksplicitno opisuje durable upload handle-ove, bounded runtime i state granice nego u trenutku kada je ovaj review prvi put zapisan.

### I dalje otvoreno

- `Open-by-default auth fallback` je i dalje otvoren.
- `CORS` default posture je i dalje preširok za išta osim lokalnog/pilot režima.
- `God-moduli` (`persistence_service.py`, delom `mapping_service.py`) i dalje ostaju realan maintainability nalaz.
- `Embedding durable cache` nije uveden.
- `Pravi async LLM/HTTP put` nije uveden.
- `Repository split` za široki `persistence_service.py` nije urađen.
- `E2E/auth/concurrency` test mreža i dalje ostaje tanja nego što review preporučuje.

### Šta smo konkretno uradili od ovog review-a

- `6A`: durable upload state, SQLite stability, timeout contract cleanup
- `6B`: minimal sync backpressure boundary za duge mapping i bounded LLM rute
- `6C`: mapping policy extraction za SAP calibration i decision thresholds

Zaključak: ovaj review i dalje dobro pogađa glavne arhitektonske teme, ali više nije tačno da su upload state, SQLite connection contract i threshold/timeout contract u starom problematičnom stanju. Danas su najveće preostale otvorene stavke bezbednosni posture (`auth` fallback + CORS) i veći maintainability refactor (`god-moduli`, širi async model, repository split).

# Semantra — Arhitektonski audit i revizija

## 1. Šta je Semantra zapravo (verifikovano iz koda)

FastAPI backend (`backend/app`) + Streamlit UI (`streamlit_ui/`, `streamlit_app.py`). Domen: poluautomatsko semantičko mapiranje source→target / source→canonical šema, sa review/governance/reuse tokovima. Perzistencija je lokalni SQLite (`backend/semantra.sqlite3`). LLM je „bounded" (validacija u zatvorenom skupu kandidata, codegen, narracija), nije autonomni maper — to je dobra i svesna arhitektonska odluka.

Skala koda po modulima govori najviše:

| Modul | Linija | Uloga |
|---|---|---|
| persistence_service.py | 2928 | sve tabele + sva perzistencija u jednoj klasi |
| `metadata_knowledge_service.py` | 2296 | knowledge/SAP signali |
| mapping_service.py | 1494 | scoring + ranking + LLM gate + codegen |
| `models/mapping.py` | 1241 | Pydantic ugovori |
| `routes/mapping.py` | 1068 | jedan ruter sa ~svim mapping endpointima |
| `streamlit_ui/admin_views.py` | 4105 | admin + knowledge + correction + config |
| `streamlit_ui/catalog_views.py` | 2560 | katalog |

To je ~36K linija — projekat je daleko prerastao „pilot" fazu po obimu, ali zadržava pilot-arhitekturu (in-memory store, SQLite, bez async-a).

## 2. Arhitektura — ocena

**Šta je dobro:**
- Čista slojevitost `routes → services → models`. Servisi su odvojeni od ruta, Pydantic ugovori su jasni.
- Signal-bazirani scoring sa 5 profila i runtime override-ima (mapping_service.py) je elegantan i podesiv.
- Config je deterministički: dataclass + `SEMANTRA_*` env/.env, sa `backend_code_fingerprint()` za detekciju drift-a runtime-a — odlična ideja za reproduktivnost.
- LLM je apstrahovan kroz `LLMProvider` Protocol sa Static/OpenAI/LMStudio implementacijama i JSON-salvage parsiranjem — robusno na „prljave" odgovore modela.

**Glavni arhitektonski problemi:**

1. **God-moduli.** persistence_service.py (2928 linija, jedna klasa, 20+ tabela) i mapping_service.py (scoring + ranking + LLM gate + transformacije pomešani). Ovo je #1 dug za održavanje.

2. **In-memory vs. durable nekonzistentnost.** `upload_store.py` je in-memory; `source_dataset_id`/`target_dataset_id` ne preživljavaju reload backend-a. Vaše sopstvene repo-memory beleške to potvrđuju kao ponavljajući izvor bagova (preview hardening, draft-session restore). To je suštinska arhitektonska pukotina: deo stanja je trajan (SQLite), a sidrišni handle-ovi nisu.

Status 2026-06-01: zatvoreno za prvi minimalni scope. `upload_store` više nije single-source in-memory registry; dataset handle-ovi su durabilni kroz SQLite-backed `uploaded_datasets`, a ordinary backend reload više ne ruši minimalni `dataset_id` lookup contract za upload -> mapping -> preview tokove.

3. **Sav backend je sinhron + blokirajući.** LLM pozivi koriste `urllib.request` (blocking) unutar FastAPI; nema `async`/connection pool-a. Za jedan workspace radi, ali svaki LLM poziv blokira worker.

Status 2026-06-01: delimično rešeno. Nije uveden pravi async HTTP/worker model, ali sync mapping i bounded LLM putanje sada imaju eksplicitni backpressure boundary (`429 + Retry-After`) umesto neograničenog request piling-a.

4. **SQLite bez WAL/pool-a.** `connection()` (persistence_service.py) otvara novu konekciju po operaciji, bez `check_same_thread`, bez WAL moda, bez eksplicitnog `rollback()`. Konkurentni upisi → „database is locked". OK za demo, rizik za pilot sa više korisnika.

Status 2026-06-01: delimično do suštinski rešeno za trenutni pilot scope. WAL, `busy_timeout`, `foreign_keys=ON` i eksplicitni `rollback()` su uvedeni. Širi pool/worker model i dalje nije uveden.

## 3. Bezbednost — nalazi (po prioritetu)

🔴 **Otvoreno po defaultu.** U deps.py, kada `admin_api_token` nije postavljen I nema principal header-a, vraća se `development-admin` sa **SVIM rolama**. Default deployment = pun admin pristup bez autentikacije. Mora postojati eksplicitan „secure by default" prekidač.

Status 2026-06-01: i dalje otvoreno.

🟡 **CORS `allow_origins=["*"]` + `allow_credentials=True`** (main.py). Ova kombinacija je nevalidna/rizična po CORS spec — browser je odbija sa kredencijalima, ali signalizira preširoku politiku. Treba lista dozvoljenih origin-a iz config-a.

Status 2026-06-01: delimično otvoreno. CORS više ide kroz `settings.cors_origins`, ali default posture je i dalje praktično širok za lokalni režim i nije produkciono sužen.

🟢 **Pozitivno:** SQL je parametrizovan (`?` placeholderi, uključujući dinamičke `IN (...)` liste); tajne su izbačene iz izvornog koda i idu iz `.env` (potvrđeno i u repo-memory belešci o GitHub push protection).

**Preporuka:** dodati `SEMANTRA_REQUIRE_AUTH` koji u produkciji obara default „development-admin" fallback; suziti CORS; maskirati ključeve u observability snapshot-u (već se radi za `*_configured` boolean — dobro).

## 4. Mapping engine — kvalitet

Jezgro je solidno: 10 signala (`name, semantic, knowledge, canonical, pattern, statistical, overlap, embedding, correction, llm`), zatvoreni LLM gate u traci ambiguiteta, i `no_match` kada su svi kandidati slabi (potvrđeno u testovima — dobra dizajnerska odluka protiv „least-bad" auto-selekcije).

**Slabosti:**
- **SAP hardkodovan kroz engine.** ~10 `sap_*` parametara u config.py i boost logika rasuta po `mapping_service` + `metadata_knowledge_service`. Ovo curi domensku specifiku u generički engine i otežava dodavanje novih ERP-ova bez diranja jezgra. Trebalo bi izvući u pluggable „domain knowledge pack".
- **Embedding se ne kešira durabilno** — recomputed po job-u.
- **Duplirana logika praga/težina** na više mesta (mapping vs evaluation servis).
- **`llm_timeout_seconds` se ignoriše** na nekim putanjama (hardkodovan cap) — treba poštovati config.

Status 2026-06-01:

- SAP hardcoding: delimično rešeno. Politika je izdvojena u `mapping_policy.py`, ali engine još nije ERP-agnostičan plug-in sloj.
- Embedding durable cache: i dalje otvoreno.
- Duplirana logika praga/težina: značajno smanjena kroz policy extraction.
- `llm_timeout_seconds`: zatvoreno kroz eksplicitne bounded timeout settings i centralne helper-e.

## 5. Dokumentacija vs. realnost

README je iznenađujuće tačan i detaljan u opisu feature-a, ali:
- README opisuje `workspace_views.py` kao centar — kod je realno raspodeljen na `workspace_views/review_views/decision_views` (refaktoring se desio, README delom zaostaje).
- README tvrdi „durable persistence" — ali upload store je in-memory; trajnost važi za mapping-set/knowledge, ne za sidrišne dataset handle-ove. Ovo je najveća dokument-vs-kod divergencija.
- `tts_provider` default je `lmstudio_orpheus`, što vezuje audio za lokalni LM Studio — README to ne ističe kao runtime preduslov.

Status 2026-06-01:

- tvrdnja o upload trajnosti više nije netačna u istom obliku, jer su uploaded dataset handle-ovi sada durabilni
- dokumentacioni drift nije potpuno nestao, ali je manji nego u trenutku ovog prvog review-a

## 6. Testiranje

13 backend test fajlova pokrivaju mapping/knowledge/persistence/spec dobro (po memory belešci ~37+ testova prolazi). **Praznine:** nema E2E (upload→map→review→save), nema testova autentikacije/CORS-a, nema UI testova, nema konkurentnosti, LLM se testira samo mock-om.

---

## Preporuke — kako dalje (prioritizovano)

**P0 — Bezbednost i ispravnost (brzo, visok uticaj):**
1. Ukloniti „open-by-default" — uvesti `SEMANTRA_REQUIRE_AUTH`; suziti CORS na konfigurisanu listu.
Status 2026-06-01: i dalje otvoreno.
2. Uključiti SQLite **WAL mod** + `check_same_thread=False` sa pool/lock-om, eksplicitan `rollback()`.
Status 2026-06-01: delimično zatvoreno. WAL + `rollback()` + `busy_timeout` su uvedeni; pool / širi threading model nije.
3. Persistirati upload store (ili snimati schema-handle snapshot) da reload backend-a ne invalidira `dataset_id` — rešava celu klasu bagova iz vaših beleški.
Status 2026-06-01: zatvoreno za prvi minimalni scope.

**P1 — Refaktoring god-modula (srednji uticaj, izolovani rizik):**
4. Razbiti persistence_service.py na repozitorijume po domenu (`MappingSetRepository`, `CorrectionRepository`, `KnowledgeRepository`, `DraftSessionRepository`) sa zajedničkim `connection()` slojem. Radi se inkrementalno — fasada zadržava postojeći API.
Status 2026-06-01: i dalje otvoreno kao veći maintainability wave.
5. Izdvojiti iz mapping_service.py: `ScoringEngine` (signali+težine), `RankingEngine`, `LLMValidationGate`, `TransformationCodegen`. Centralizovati pragove/težine na jedno mesto.
Status 2026-06-01: delimično rešeno. Centralizacija scoring/threshold politike je urađena kroz `mapping_policy.py`, ali puni decomposition `mapping_service.py` nije.
6. Izvući SAP/ERP specifiku iz jezgra u **domain knowledge pack** (data-driven, ne hardkod) — čini engine ERP-agnostičnim.
Status 2026-06-01: i dalje otvoreno, iako je prag/policy deo sada centralizovan.

**P2 — Kvalitet i skaliranje:**
7. Async LLM/HTTP putanja (`httpx.AsyncClient`) ili thread offload, da LLM ne blokira workere.
Status 2026-06-01: delimično rešeno samo kroz backpressure boundary; pravi async path i dalje nije uveden.
8. Durabilni embedding keš.
Status 2026-06-01: i dalje otvoreno.
9. E2E + auth + konkurentnost testovi; CI gate na `pytest`.
Status 2026-06-01: i dalje otvoreno kao širi kvalitet wave.
10. Sinhronizovati README/`project_docs` sa realnim modulima i jasno označiti runtime preduslove (LM Studio, in-memory upload).
Status 2026-06-01: delimično rešeno. `project_docs/current_state.md` i delivery ledger su osveženi; `review.md` sada takođe nosi status anotaciju.

Ako želiš, mogu da krenem sa konkretnim refaktoringom — predlažem da prvi korak bude P0-3 (perzistencija upload handle-ova) jer rešava najviše stvarnih bagova, ili P1-4 (repository split) ako je prioritet dugoročna održivost. Reci koji pravac i radim izmene.
