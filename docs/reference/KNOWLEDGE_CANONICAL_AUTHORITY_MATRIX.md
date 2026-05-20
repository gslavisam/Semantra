# Knowledge/Canonical Authority Matrix

Ovaj dokument je kratka operativna referenca: sta je source-of-truth u fajlovima, sta je runtime snapshot u SQLite bazi i kako ide sinhronizacija.

## Brzi odgovor

- Fajlovi su authoring/source-of-truth sloj (verzionisan, reviewable, reproducibilan).
- SQLite je runtime/cache sloj (brz start, upiti, operativna stanja).
- Sistem radi DB-first kada je seed hash validan; inace radi reseed iz fajlova i upisuje novu runtime sliku u bazu.

## Authority Matrix

| Sloj | Primarni izvor istine | Runtime kopija u bazi | Tabele/fajlovi | Kako se osvezava |
|---|---|---|---|---|
| Canonical koncepti | `metadata_dict/canonical_glossary_erp.csv` | Da | `canonical_concepts` | `refresh()` ili canonical authoring sync |
| Canonical field context | `metadata_dict/canonical_field_context_enrichment.csv` | Da | `canonical_field_contexts` | `refresh()` ili canonical authoring sync |
| Knowledge koncepti (base) | `metadata_dict/metadata_dict.csv` + `metadata_dict/metadata_dictionary.xlsx` | Da | `knowledge_concepts`, `knowledge_field_contexts` | `refresh()`/reseed iz source fajlova |
| Vendor knowledge overlay seed (HRDH/WD) | `metadata_dict/hrdh_knowledge_overlay.csv`, `metadata_dict/wd_hr_knowledge_overlay.csv` | Indirektno (ulazi u seeded knowledge runtime) | ulazi u `knowledge_concepts`/`knowledge_field_contexts` tokom seeda | ucitava se pri source-file load i ulazi u DB snapshot |
| QB knowledge overlay seed | `metadata_dict/qb_knowledge_overlay.csv` | Indirektno (ulazi u seeded knowledge runtime) | ulazi u `knowledge_concepts` tokom seeda QB wave | auto-ucitava se pri `refresh()` ako source hash validna |
| Aktivni overlay (stewardship) | DB overlay zapisi | Da (native) | `knowledge_overlay_versions`, `knowledge_overlay_entries` | aktivacija/deaktivacija overlay verzije |
| Stewardship/audit state | DB | Da (native) | `knowledge_stewardship_items`, `knowledge_audit_logs` | kroz API/stewardship tokove |
| Seed metadata i validnost cache-a | DB + source-file hash iz fajlova | Da | `knowledge_seed_meta` | pri svakom seed/sync ciklusu |

## Gde se vidi DB-first logika

- `metadata_knowledge_service.refresh()`:
  - racuna source hash iz skupa source fajlova
  - ako `knowledge_seed_meta.source_hash` odgovara, runtime ucitava iz SQLite (`sqlite_cache`)
  - ako ne odgovara, ucitava iz source fajlova i radi `replace_runtime_snapshot()`

- Relevantni kod:
  - `backend/app/services/metadata_knowledge_service.py`
  - `backend/app/services/knowledge_runtime_repository.py`
  - `backend/app/services/persistence_service.py`

## Zasto nije sve samo u bazi

1. Reproducibilnost i disaster recovery:
   - baza moze da se rebuild-uje iz verzionisanih seed fajlova.

2. Governance i audit kroz Git:
   - canonical/knowledge promene u CSV/XLSX source fajlovima imaju diff, review i istoriju promena.

3. Performanse u runtime-u:
   - DB snapshot daje brze upite i startup bez ponovnog parsiranja velikih workbook fajlova.

4. Operativno razdvajanje odgovornosti:
   - authoring sloj (fajlovi) i runtime sloj (DB) imaju razlicite zahteve i ciklus promene.

## Prakticna preporuka

- Za trajnu semantiku i canonical governance: menjati source-of-truth fajlove i/ili stewardship tok koji ih sinhronizuje.
- Za brzo izvrsavanje i produkcioni runtime: oslanjati se na SQLite runtime snapshot.
- Kada postoji dilema sta je trenutno aktivno: proveriti `runtime_source` i `knowledge_seed_meta` stanje.

## Workday HRDH datahub overlay authority entry

- `metadata_dict/hrdh_knowledge_overlay.csv`, `metadata_dict/wd_hr_knowledge_overlay.csv`:
  - `generated_overlay_source`: `yes`
  - `knowledge_sources/generated/overlays`:
    - `Generated Workday datahub concept-alias pairs from promotion wave-1/wave-2; auto-loaded by metadata_knowledge_service.refresh() for runtime field discovery`
