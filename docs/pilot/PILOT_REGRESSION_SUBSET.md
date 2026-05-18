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
- Canonical Console stewardship tok

## Stabilna pilot preporuka

Za osnovni pilot tok koristi `Use LLM validation = off` kao podrazumevanu postavku, osim kada je cilj sesije eksplicitno LLM ambiguity review ili transformation generation.

Razlog:

- deterministic-first tok je brži i stabilniji za demo/pilot prolaze
- LLM-enabled mapping ostaje koristan, ali nije najbolji default za najkraći regression/prove-it loop

## Pre-flight

1. Pokreni lokalni stack.
	Sačekaj da `start_semantra.ps1` prijavi `Backend is ready` i `Streamlit is ready` pre otvaranja UI-ja.
2. Potvrdi da `Workspace`, `Catalog` i `Canonical Console` otvaraju bez runtime grešaka.
3. Za showcase quick demo koristi `ui_fixtures/showcase_customer_mapping/showcase_customer_source.csv` i `ui_fixtures/showcase_customer_mapping/showcase_customer_target.json`.

## Regression komande

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

### Benchmarks

- benchmark explanation unlock/helper tok
- benchmark governance gate za `Save current mapping as benchmark`
- saved dataset / profile-comparison helper tok

### Canonical Console

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
2. Učitaj jedan `approved` integration detail, pa potvrdi da `Mapping Set Drilldown` prikazuje compare baseline i handoff CTA ka `Workspace` ili `Canonical Console`.
3. Otvori `Workspace Reuse Fit`, generiši bounded reuse procenu i potvrdi da surface prikazuje workspace context, fit/risk summary i sledeće akcije bez automatskog apply ponašanja.
4. Klikni `Reuse in Workspace` samo za `approved` version i potvrdi da se pojavi success status poruka za apply/reuse tok.
5. Klikni `Open workspace review handoff` i potvrdi da top-level navigacija zaista pređe u `Workspace` umesto da ostane u `Catalog` ili padne na Streamlit grešku.
6. Ako `Catalog` pokuša da otvori integration detail koji više ne postoji u backend-u, potvrdi da se stale state očisti i da status traka traži refresh query rezultata.

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