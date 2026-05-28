# Full Menu Presentation Asset Map

Ovaj dokument mapira postojeci demo asset set na slajdove iz [docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md](D:/py_radno/Semantra/docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md).

Fokus je na vec generisanim fajlovima iz:

- `docs/pilot/demo_assets/workspace_recordings_20260527`
- `docs/pilot/demo_assets/manual_live_demo_20260527`
- `docs/pilot/demo_assets/full_menu_supporting_assets_20260527`

Gde ne postoji dedicated asset za odredjeni slajd, to je eksplicitno oznaceno da znas gde treba live prikaz ili dodatni screenshot.

## Slide Map

| Slide | Tema | Primary asset | Kako da ga koristis | Status |
| --- | --- | --- | --- | --- |
| 1 | Naslov i problem | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Pauziraj na uvodnom kadru sa top-level navigacijom ili koristi live pocetni ekran | Reuse existing video |
| 2 | Navigaciona mapa | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Koristi opening frame ili kratko live preletanje preko navigacije | Reuse existing video |
| 3 | Workspace -> Setup | `docs/pilot/demo_assets/workspace_recordings_20260527/01_standard_two_file_mapping/01_standard_two_file_mapping.webm` | Glavni video za upload i profile tok | Dedicated asset |
| 3 | Workspace -> Setup | `docs/pilot/demo_assets/workspace_recordings_20260527/01_standard_two_file_mapping/screenshots/01_standard_two_file_mapping_01.png` | Static fallback kadar za slajd | Dedicated asset |
| 4 | Workspace -> Review | `docs/pilot/demo_assets/workspace_recordings_20260527/03_llm_decision_flow/screenshots/03_llm_decision_flow_01.png` | Pokazi review/LLM proposal surface kao static trust-layer kadar | Dedicated asset |
| 4 | Workspace -> Review | `docs/pilot/demo_assets/workspace_recordings_20260527/03_llm_decision_flow/03_llm_decision_flow.webm` | Koristi ako hoces kratki video umesto statike | Dedicated asset |
| 5 | Workspace -> Decisions | `docs/pilot/demo_assets/workspace_recordings_20260527/03_llm_decision_flow/03_llm_decision_flow.webm` | Pokriva prelaz iz review-a u bounded decision workflow | Dedicated asset |
| 6 | Workspace -> Output | `docs/pilot/demo_assets/workspace_recordings_20260527/04_workspace_output_generation/04_workspace_output_generation.webm` | Glavni video za Pandas/dbt/refinement demonstraciju | Dedicated asset |
| 6 | Workspace -> Output | `docs/pilot/demo_assets/workspace_recordings_20260527/04_workspace_output_generation/screenshots/04_workspace_output_generation_01.png` | Static kadar za Pandas/output state | Dedicated asset |
| 6 | Workspace -> Output | `docs/pilot/demo_assets/workspace_recordings_20260527/04_workspace_output_generation/screenshots/04_workspace_output_generation_02.png` | Static kadar za dbt/refinement state | Dedicated asset |
| 7 | Catalog -> Search and Discovery | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Koristi deo snimka gde se ulazi u `Catalog` i pokrece query | Reuse existing video |
| 8 | Catalog -> Detail, Diff, Reuse i Handoff | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/01_catalog_reuse_01.png` | Primarni static kadar za approved reuse pricu | Dedicated asset |
| 8 | Catalog -> Detail, Diff, Reuse i Handoff | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/03_catalog_diff_handoff_01.png` | Dodaj kao drugi kadar za diff review handoff | Dedicated asset |
| 8 | Catalog -> Detail, Diff, Reuse i Handoff | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/04_catalog_stewardship_handoff_01.png` | Dodaj kao governance handoff kadar | Dedicated asset |
| 8 | Catalog -> Detail, Diff, Reuse i Handoff | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Koristi ako hoces jedan objedinjeni video umesto tri statike | Dedicated asset |
| 9 | Benchmarks -> Dataset and Run Management | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Koristi benchmark segment snimka kao uvod u dataset/run management | Reuse existing video |
| 10 | Benchmarks -> Profile Comparison and Explanation | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/05_benchmarks_explanation_01.png` | Primarni static kadar za comparison i explanation | Dedicated asset |
| 10 | Benchmarks -> Profile Comparison and Explanation | `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm` | Video fallback za celu benchmark sekvencu | Dedicated asset |
| 11 | System -> Admin | `docs/pilot/demo_assets/full_menu_supporting_assets_20260527/11_system_admin_01.png` | Primarni static kadar za runtime config, scoring runtime i admin operacije | Dedicated asset |
| 12 | System -> Debug | `docs/pilot/demo_assets/full_menu_supporting_assets_20260527/12_system_debug_01.png` | Primarni static kadar za decision logs, knowledge runtime i audit observability | Dedicated asset |
| 13 | Governance overview | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/04_catalog_stewardship_handoff_01.png` | Koristi kao ulazni governance kadar pre razdvajanja po sekcijama | Reuse existing screenshot |
| 14 | Governance -> Canonical | `docs/pilot/demo_assets/full_menu_supporting_assets_20260527/14_governance_canonical_01.png` | Primarni static kadar za canonical glossary i concept stewardship povrsinu | Dedicated asset |
| 15 | Governance -> Knowledge | `docs/pilot/demo_assets/full_menu_supporting_assets_20260527/15_governance_knowledge_01.png` | Primarni static kadar za knowledge registry i linked canonical kontekst | Dedicated asset |
| 16 | Governance -> Overlays & Runtime | `docs/pilot/demo_assets/full_menu_supporting_assets_20260527/16_governance_overlays_runtime_01.png` | Primarni static kadar za overlay summary i runtime management | Dedicated asset |
| 17 | Governance -> Stewardship | `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/04_catalog_stewardship_handoff_01.png` | Primarni stewardship kadar iz handoff toka | Dedicated asset |

## Najjaci postojeći asseti

Ako hoces najbrzi deck bez dodatnog snimanja, oslanjaj se prvenstveno na ove fajlove:

1. `docs/pilot/demo_assets/workspace_recordings_20260527/01_standard_two_file_mapping/01_standard_two_file_mapping.webm`
2. `docs/pilot/demo_assets/workspace_recordings_20260527/03_llm_decision_flow/03_llm_decision_flow.webm`
3. `docs/pilot/demo_assets/workspace_recordings_20260527/04_workspace_output_generation/04_workspace_output_generation.webm`
4. `docs/pilot/demo_assets/manual_live_demo_20260527/manual_live_demo_recording.webm`
5. `docs/pilot/demo_assets/manual_live_demo_20260527/screenshots/05_benchmarks_explanation_01.png`

## Preporuka za deck bez dodatnog snimanja

Ako hoces da odmah sastavis prezentaciju bez novih capture-a:

1. koristi video assete za `Workspace` i `Catalog/Benchmarks`
2. koristi static screenshot-ove kao naslovne kadrove za sekcije gde je video predug za slajd
3. koristi `full_menu_supporting_assets_20260527` za `System` i tri nedostajuce `Governance` sekcije

## Preostali opcioni capture gapovi

Full-menu deck sada ima dedicated asset za svaku veliku sekciju. Ako budes radio naredni asset pass, ovo su opcioni dodatni kadrovi koji mogu jos da ga ulepsaju:

1. poseban `Governance overview` screenshot umesto reuse stewardship handoff kadra
2. dedicated `Governance -> Stewardship` screenshot nezavisan od catalog handoff sekvence
3. dodatni drugi kadar za `System -> Debug` sa otvorenim `Canonical Coverage` ili `Decision Logs`

To vise nije blokirajuci gap, vec samo polish layer za bogatiji deck.