# Semantra Demo Screenshots Index

Ovaj dokument mapira screenshotove iz live demo prolaza na osam stavki sa slajda i odgovarajuce korake iz runbook-a.

Screenshot folder:

- `docs/presentation/demo_screenshots/`
- `docs/presentation/demo_screenshots/detail/`

## Optional preflight

Pre ulaska u glavni tok postoji i pomocni screenshot:

- `00_initial_setup_loaded.png`
  - koristi se kao backup kadar za pocetno stanje aplikacije
  - nije direktna stavka sa slajda, nego priprema pre koraka 1

## Slide-to-screenshot mapping

| Slide stavka | Runbook korak | Screenshot | Sta se vidi |
| --- | --- | --- | --- |
| 1. Workspace setup sa jednim source/target parom | 1 | `01_workspace_setup_profiled.png` | Upload source CSV i target JSON fajla, plus profiling summary nakon `Upload and profile` |
| 2. Generate mapping i review trust layer-a | 2 | `02_review_trust_layer.png` | `Mapping Trust Layer`, signal breakdown, confidence i canonical path za review kandidata |
| 3. Decisions sa accepted i manual review primerom | 3 | `03_decisions_active_review.png` | `Active Decisions` sa kombinacijom prihvacenih i review odluka |
| 4. Output preview i accepted-only codegen gate | 4 | `04_output_preview_and_codegen_gate.png` | Preview rezultat i governance gate za code generation dok nisu sve odluke `accepted` |
| 5. Save mapping set i prelazak u approved | 5 | `05_saved_mapping_set_approved.png` | Sacuvana verzija mapping seta i status prebacen na `approved` |
| 6. Catalog detail i `Reuse in Workspace` | 6 | `06_catalog_detail_and_reuse.png` | Catalog detail za sacuvanu integraciju, approved verzija i reuse tok |
| 7. Canonical Console concept detail i overlay activation | 7 | `07_canonical_console_overlay_active.png` | Canonical detail, overlay management i aktivirana overlay verzija |
| 8. Benchmarks run i correction impact | 8 | `08_benchmarks_run_and_correction_impact.png` | `Last Benchmark Result` i `Correction Impact` za sacuvani benchmark dataset |

## Detail split screenshots

Za citljiviju prezentaciju sada postoji i po dva kadra za svaku od 8 glavnih stavki. `top` i `bottom` snimci imaju preklapanje, tako da se nista bitno ne izgubi izmedju njih.

| Slide stavka | Detail top | Detail bottom |
| --- | --- | --- |
| 1 | `detail/01_workspace_setup_profiled_top.png` | `detail/01_workspace_setup_profiled_bottom.png` |
| 2 | `detail/02_review_trust_layer_top.png` | `detail/02_review_trust_layer_bottom.png` |
| 3 | `detail/03_decisions_active_review_top.png` | `detail/03_decisions_active_review_bottom.png` |
| 4 | `detail/04_output_preview_and_codegen_gate_top.png` | `detail/04_output_preview_and_codegen_gate_bottom.png` |
| 5 | `detail/05_saved_mapping_set_approved_top.png` | `detail/05_saved_mapping_set_approved_bottom.png` |
| 6 | `detail/06_catalog_detail_and_reuse_top.png` | `detail/06_catalog_detail_and_reuse_bottom.png` |
| 7 | `detail/07_canonical_console_overlay_active_top.png` | `detail/07_canonical_console_overlay_active_bottom.png` |
| 8 | `detail/08_benchmarks_run_and_correction_impact_top.png` | `detail/08_benchmarks_run_and_correction_impact_bottom.png` |

## Preporuka za upotrebu u prezentaciji

Ako ti treba po jedan kadar po stavci sa slajda, koristi originalne screenshotove redom:

1. `01_workspace_setup_profiled.png`
2. `02_review_trust_layer.png`
3. `03_decisions_active_review.png`
4. `04_output_preview_and_codegen_gate.png`
5. `05_saved_mapping_set_approved.png`
6. `06_catalog_detail_and_reuse.png`
7. `07_canonical_console_overlay_active.png`
8. `08_benchmarks_run_and_correction_impact.png`

Ako hoces citljiviji materijal za prezentaciju ili appendix, koristi `detail/` varijante i prikazuj po dva kadra za svaku stavku.

Ako hoces rezervni uvodni kadar pre glavnog toka, dodaj i `00_initial_setup_loaded.png` kao backup ili appendix screenshot.