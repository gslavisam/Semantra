# Operational Browser E2E

Ovaj dokument opisuje fokusirani browser-level E2E smoke za glavni pilot trio: `Workspace`, `Catalog` i `Benchmarks`.

Nije zamena za širi test suite niti za postojeći `run_operational_hardening.py` baseline. Njegova uloga je da automatizuje najvažniji UI prolaz koji je do sada bio proveravan ručnim browser smoke koracima.

Za ručnu, uživo prezentaciju istog toka koristi [docs/pilot/MANUAL_LIVE_DEMO_SCRIPT.md](D:/py_radno/Semantra/docs/pilot/MANUAL_LIVE_DEMO_SCRIPT.md).

## Šta runner proverava

Runner iz [backend/scripts/run_operational_browser_e2e.py](D:/py_radno/Semantra/backend/scripts/run_operational_browser_e2e.py) radi sledeće:

1. bootstrapuje repeatable smoke fixture-e preko postojećeg `bootstrap_operational_smoke.py` helper-a
2. u `Workspace` učitava saved draft session `customer-draft-session` i potvrđuje `Review` contract
3. u `Catalog` prolazi `browser-diff-focus -> Load version diff -> Open current diff review focus`
4. u `Catalog` prolazi `stewardship-smoke-sync -> Open Stewardship`
5. u `Catalog` prolazi `approved-customer-reuse-smoke -> Reuse in Workspace`
6. u `Benchmarks` prolazi `operational-smoke-benchmark -> Compare scoring profiles -> Benchmark Explanation`

## Preduslovi

Instaliraj Python dependency i Chromium browser binarije za Playwright:

```powershell
python -m pip install -r backend/requirements.txt
python -m playwright install chromium
```

Zatim pokreni lokalni backend i Streamlit UI.

## Komande

Python entry point:

```powershell
python backend/scripts/run_operational_browser_e2e.py --streamlit-url http://127.0.0.1:8501 --base-url http://127.0.0.1:8000 --admin-token <token>
```

Windows wrapper:

```powershell
.\backend\scripts\run_operational_browser_e2e.ps1 -AdminToken <token>
```

Za lokalni debugging možeš koristiti i headed mode:

```powershell
.\backend\scripts\run_operational_browser_e2e.ps1 -AdminToken <token> -Headed -SlowMoMs 250
```

## Kada ga koristiti

Koristi ovaj runner:

1. kada želiš browser potvrdu glavnog pilot toka, ne samo helper/API signal
2. posle izmena koje dodiruju `Workspace` handoff, `Catalog` drilldown/reuse ili `Benchmarks` explanation
3. kao dopunu postojećem `run_operational_hardening.py` baseline-u, ne kao njegovu zamenu

## Očekivani rezultat

Uspešan run ispisuje jedan JSON summary sa bootstrap rezultatom i browser smoke statusom za `workspace`, `catalog` i `benchmarks` grane.