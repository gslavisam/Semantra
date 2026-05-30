# Pilot Regression Subset

Ovaj dokument definiše uski regression subset za demo/pilot isporuke.

Nije zamena za širi test suite. Služi kao praktični minimum koji treba pustiti pre svake pilot ili showcase sesije.

## Cilj

Potvrditi da glavni Semantra pilot tok ostaje stabilan na ključnim površinama:

- Workspace upload/setup i output gating
- Workspace review, bounded guidance i attention surfacing
- Workspace output refinement i accepted-only artifact flow
- Catalog reuse/discovery tok
- Benchmarks explanation tok
- Governance > Canonical Console stewardship tok

## UI orijentacija za ovaj subset

Aktuelna UI organizacija za ovaj dokument je:

- top-level area: `Workspace`, `Catalog`, `Benchmarks`, `System`, `Governance`
- `Workspace` pod-tabovi: `Setup`, `Review`, `Decisions`, `Output`
- `Canonical Console` i `Stewardship` su sekcije unutar `Governance`

## Stabilna pilot preporuka

Za osnovni pilot tok koristi `Use LLM validation = off` kao podrazumevanu postavku, osim kada je cilj sesije eksplicitno LLM ambiguity review ili transformation generation.

Razlog:

- deterministic-first tok je brži i stabilniji za demo/pilot prolaze
- LLM-enabled mapping ostaje koristan, ali nije najbolji default za najkraći regression/prove-it loop

## Pre-flight

1. Pokreni lokalni stack.
	Sačekaj da `start_semantra.ps1` prijavi `Backend is ready` i `Streamlit is ready` pre otvaranja UI-ja.
2. Potvrdi da `Workspace`, `Catalog` i `Governance` otvaraju bez runtime grešaka, i da se `Canonical Console` sekcija unutar `Governance` normalno renderuje.
3. Ako lokalni runtime nema potrebne smoke fixture podatke, pokreni `backend/scripts/bootstrap_operational_smoke.ps1` ili `backend/scripts/bootstrap_operational_smoke.py` da repeatable seeduje `browser-diff-focus`, `Stewardship Smoke Sync`, `approved-customer-reuse-smoke`, `customer-draft-session` i `operational-smoke-benchmark` kroz postojeće API-je.
4. Za showcase quick demo koristi `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv` i `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`.

## Regression komande

Za jedan repeatable operational-hardening prolaz preko `Workspace`, `Catalog` i `Benchmarks`, koristi:

```powershell
python backend/scripts/run_operational_hardening.py --base-url http://127.0.0.1:8000 --admin-token <token>
```

ili na Windows-u:

```powershell
.\backend\scripts\run_operational_hardening.ps1 -AdminToken <token>
```

Ovaj runner radi tri stvari redom:

- pokreće bootstrap fixture-a za repeatable smoke preuslove
- izvršava fokusirani Streamlit regression subset
- proverava live API smoke baseline za `Workspace`, `Catalog` i `Benchmarks`

Za browser-level potvrdu istog pilot trija koristi fokusirani Playwright smoke runner:

```powershell
python -m playwright install chromium
python backend/scripts/run_operational_browser_e2e.py --streamlit-url http://127.0.0.1:8501 --base-url http://127.0.0.1:8000 --admin-token <token>
```

ili na Windows-u:

```powershell
.\backend\scripts\run_operational_browser_e2e.ps1 -AdminToken <token>
```

Ovaj runner automatizuje glavni browser smoke put preko `Workspace`, `Catalog`, `Governance` i `Benchmarks`; detalji su u [docs/pilot/OPERATIONAL_BROWSER_E2E.md](D:/py_radno/Semantra/docs/pilot/OPERATIONAL_BROWSER_E2E.md).

Ako želiš isti tok da vodiš ručno pred publikom, koristi [docs/pilot/MANUAL_LIVE_DEMO_SCRIPT.md](D:/py_radno/Semantra/docs/pilot/MANUAL_LIVE_DEMO_SCRIPT.md).

Pusti ovaj uski subset iz repo root-a:

```powershell
python -m pytest tests/test_streamlit_workspace_views.py tests/test_streamlit_workspace_review_views.py tests/test_streamlit_catalog_views.py tests/test_streamlit_benchmark_views.py tests/test_streamlit_admin_views.py -q
```

Ako želiš i backend mapping minimum:

```powershell
python -m pytest backend/tests/test_mapping_service.py backend/tests/test_spec_upload_service.py -q
```

## Površine koje ovaj subset pokriva

### Workspace

- upload/setup helpers
- companion metadata poruke
- preview advisory i codegen governance gate
- output refinement helper-i i runtime gating
- repeated review attention summary
- bounded review guidance unlock/helper tokovi

### Catalog

- concept-centric reuse view
- discovery overview matrix
- reuse hint-ovi, stale-state recovery i mapping-set reuse guard
- version diff -> `Workspace > Review` handoff sa changed-source scope signalom
- `Governance > Canonical Console` / `Governance > Stewardship` handoff sa section-aware landing-om

### Benchmarks

- benchmark explanation unlock/helper tok
- benchmark governance gate za `Save current mapping as benchmark`
- saved dataset / profile-comparison helper tok

### Governance > Canonical Console

- stewardship queue helper-i
- repeated canonical gap surfacing
- approval/rejection governance helper-i

## Bounded guidance discoverability smoke

Koristi isti showcase iz `Pre-flight` dela:

1. U `Workspace` učitaj `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv` i `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`, pa generiši mapping bez uključivanja `Use LLM validation`.
2. U `Review` potvrdi da su `Mapping Analysis Overview` i `Review Queue Plan` vidljivi bez dodatnog debug znanja i da oba imaju jasan generate/unlock state.
3. U `Canonical Gap Suggestions` potvrdi da je `Gap Queue Summary` vidljiv i kada još nema kandidata, sa eksplicitnom unlock porukom.
4. U `Catalog` učitaj bar jedan saved integration detail i potvrdi da je `Workspace Reuse Fit` vidljiv pre samog generate koraka, zajedno sa workspace context readout-om i governance blokadom kada version nije `approved`.
5. U `Benchmarks` potvrdi da je `Benchmark Explanation` vidljiv i kada nema učitanog benchmark evidence skupa, sa jasnom porukom šta ga otključava.

Ovaj smoke ne proverava kvalitet svih LLM tekstova; proverava discoverability, bounded positioning i jasan sledeći korak za guidance surface-e.

## Output refinement smoke

Koristi isti showcase iz `Pre-flight` dela:

1. U `Workspace` učitaj `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv` i `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`, pa generiši mapping bez uključivanja `Use LLM validation`.
2. U `Output` potvrdi da je preview i dalje dostupan kao advisory surface, ali da je `Generate Pandas code` i dalje governance-blokiran dok postoje `needs_review` odluke.
3. Kada je codegen artefakt već učitan iz ranije prihvaćenog state-a ili fixture-a, potvrdi da `Refine with LLM` ostaje odvojena refinement površina sa jasnim pending/accept/discard tokom, a ne da prepisuje originalni artefakt bez eksplicitne potvrde.
4. Ako refinement nije dostupan zbog runtime ili zato što nema učitanog artefakta, potvrdi da je razlog jasan i da UI ne ostaje u praznom stanju bez sledećeg koraka.

Ovaj smoke proverava da output artefakti ostanu governance-sensitive i da refinement ostane eksplicitno dvokoračni tok.

## Catalog reuse end-to-end smoke

Koristi aktivni workspace showcase snapshot i bar jedan `approved` saved mapping set:

1. U `Catalog` osveži rezultate sa `Load all integrations` i potvrdi da discovery overview prikazuje broj approved integracija za trenutni skup.
2. Učitaj jedan `approved` integration detail, pa potvrdi da `Mapping Set Drilldown` prikazuje compare baseline i handoff CTA ka `Workspace` ili `Governance > Canonical Console`.
3. Otvori `Workspace Reuse Fit`, generiši bounded reuse procenu i potvrdi da surface prikazuje workspace context, fit/risk summary i sledeće akcije bez automatskog apply ponašanja.
4. Klikni `Reuse in Workspace` samo za `approved` version i potvrdi da se pojavi success status poruka za apply/reuse tok.
5. Klikni `Open workspace review handoff` i potvrdi da top-level navigacija zaista pređe u `Workspace` umesto da ostane u `Catalog` ili padne na Streamlit grešku.
6. Ako `Catalog` pokuša da otvori integration detail koji više ne postoji u backend-u, potvrdi da se stale state očisti i da status traka traži refresh query rezultata.

## Catalog handoff regression smoke

Koristi seeded `browser-diff-focus` integration family za diff handoff putanje i jedan seeded unmatched-source draft mapping set (na primer `Stewardship Smoke Sync`) za `Stewardship` granu:

Ako lokalni runtime krene bez catalog podataka, prvo seeduj minimalni `browser-diff-focus` v1/v2 par preko postojećeg `POST /mapping/sets` API-ja; za ovaj smoke nije potreban poseban seed helper u kodu.

1. U `Catalog` učitaj `browser-diff-focus` detail i otvori najnoviji draft version sa dostupnim baseline diff-om.
2. Klikni `Open current diff review focus` i potvrdi da UI prelazi u `Workspace > Review`, a status poruka jasno signalizuje multi-source diff scope (`source_scope=... diff fields`).
3. Ako aktivni Workspace već ima učitan review set, potvrdi i da `Filter by source` ostaje na `All` dok review caption nosi multi-source diff fokus umesto tvrdog source filtera.
4. Vrati se u isti `Catalog` diff readout, klikni `Open current diff Canonical review` i potvrdi da UI prelazi u `Governance` sa aktivnom sekcijom `Canonical Console`, uz očišćen stale `Canonical concept search` ili drugi prethodni governance filter.
5. Učitaj unmatched-source draft mapping set (na primer `Stewardship Smoke Sync`), otvori `Mapping Set Drilldown` i potvrdi da glavni Governance CTA eksplicitno glasi `Open Stewardship`.
6. Klikni `Open Stewardship` i potvrdi da UI prelazi u `Governance` sa aktivnom sekcijom `Stewardship`, umesto da ostane na generičkom governance landing-u.

Ovaj smoke proverava da noviji `Catalog` handoff CTA-e nisu samo helper-level signal, već da stvarno prebacuju korisnika na tačan top-level area, odgovarajuću sekciju i očekivani filter/focus scope.

## Draft-session review restore smoke

Koristi jedan postojeći `Review` draft session ili ga prvo sačuvaj iz `Workspace > Decisions`:

1. U `Workspace > Review` učitaj review-ready mapping state i namerno postavi ne-default review slice, na primer `Filter by source = phone`.
2. Generiši `Review Queue Plan` za taj filtrirani slice i potvrdi da surface jasno govori da plan važi za trenutno filtrirani review set.
3. Pređi u `Workspace > Decisions -> Mapping Set Versions`, učitaj saved draft sessions i resumuj jedan `Review` draft session.
4. Potvrdi da UI zaista vraća korisnika u `Workspace > Review` bez Streamlit runtime greške pri navigaciji.
5. Potvrdi da se review filteri vraćaju na podrazumevani `All` slice i da prethodno generisani `Review Queue Plan` ne ostaje zalepljen kao stale guidance output.
6. Potvrdi da se minimalni restored review contract ipak normalno renderuje: `Mapping Trust Layer`, `Review Queue Plan` expander u praznom/generate stanju, `Selected Mapping`, i `Scoring runtime` caption.

Ovaj smoke proverava da draft-session resume ne vraća samo navigaciju, već i čist review context bez slučajno prenetih filtera ili bounded guidance output-a iz prethodnog session state-a.

## Benchmark explanation end-to-end smoke

Koristi bilo koji postojeći saved benchmark dataset ili prethodno pripremljen minimalni fixture dataset:

1. U `Benchmarks` potvrdi da `Save current mapping as benchmark` ostaje blokiran kada aktivni workspace još ima `needs_review` odluke.
2. Učitaj `Saved Benchmark Datasets`, izaberi jedan dataset i pokreni bar jedan evidence path, po mogućstvu `Compare scoring profiles` jer je najbrži regression prolaz.
3. Potvrdi da `Scoring Profile Comparison` ili drugi benchmark evidence surface prikaže rezultat i preporuku bez runtime greške.
4. Otvori `Benchmark Explanation`, generiši explanation i potvrdi da surface prikazuje summary, findings, risks i next actions, uz jasan `Fallback` ili `LLM` metadata signal.

Ovaj smoke proverava unlock -> evidence -> explanation tok, ne kvalitet svih narativnih formulacija.

Koristi ovaj subset:

1. pre demo/pilot sesije
2. odmah posle manjih UI governance ili discovery izmena
3. kao prvi check pre šireg suite-a kada vreme nije dovoljno za puni prolaz

## Van ovog subset-a

Ovaj paket namerno ne garantuje:

- pun LLM runtime health
- dugačke benchmark tokove
- sve transformation execution edge-case-ove
- multi-user ili dugotrajni job behavior