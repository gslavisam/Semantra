Pre nego što dam zaključke, kratko skeniram realne signale van dokumentacije: veličinu/strukturu ključnih backend service-a, koliko testova zapravo postoji, i da li current_state.md ima delove o boundaries koje još nisam video. Tako audit neće biti samo prepričavanje dokumenata.    


# Audit i preporuka — Semantra

## Trenutno stanje

Semantra je pilot-ready semantic integration workbench: FastAPI backend, Streamlit UI, SQLite persistence, deterministic-first sa bounded AI slojem. End-to-end tok od upload-a do mapping review-a, transformation authoring-a, governance-a, canonical stewardship-a, benchmark-a i catalog reuse-a stvarno radi i pokriven je governance enforcement-om.

**Veličina koda i test pokrivenost (mereno):**
- backend services: top 5 — persistence_service.py 2216, metadata_knowledge_service.py 1335, mapping_service.py 1036, llm_service.py 705, mapping_analysis_service.py 639
- routes: knowledge.py 675, mapping.py 584
- Streamlit: admin_views.py 2599, workspace_review_views.py 1576, catalog_views.py 1461
- testovi: 216 backend + 125 UI test funkcija

## Šta je jako

1. Deterministic-first dizajn sa bounded AI — auto-apply/auto-approve se nigde ne dešava; sve LLM površine imaju fallback.
2. Governance discipline je realna i enforcement je u backend-u, ne samo u UI-u (approved-only reuse, accepted-only codegen, gated benchmark save, gated overlay activate/archive, ready-for-approval canonical gap).
3. Pilot-complete Canonical Console workflow sa overlay-first → promotion modelom i auditom.
4. Pristojno široka regression mreža (216 + 125 testova) sa fokusiranim helper testovima, ne samo smoke nivoom.
5. Phase 4 separation je započet kako treba: canonical authoring više ne povlači full reseed, `/knowledge/reload` i `/observability/mapping-jobs/runtime` surfacuju runtime/cache/durability signale.
6. Repo dokumentacija ima jasne uloge: current_state.md, completed_slices.md, plan.md, epics.md, implementation_checklists.md — i upravo je očišćeno tako da se ne preklapaju.

## Realni rizici i tehnički dug

1. **God-object servisi**. persistence_service.py (2.2k linija) i metadata_knowledge_service.py (1.3k linija) nose previše odgovornosti. To je nominovano i u planu (`Knowledge and canonical runtime separation`, `Mapping engine decomposition`), ali još uvek je risk magnet — svaka veća promena tu ima nesrazmeran blast radius.
2. **UI monoliti**. admin_views.py je 2.6k linija; workspace_review_views.py i catalog_views.py zajedno ~3k. UI logika ovog obima u Streamlit fajlovima je krhka za refactor.
3. **Background jobs nisu durable**. In-memory/thread model je u redu za pilot, ali sada već ima eksplicitne durable-backend trigger-e — to je signal da je ovo prvi pravi „kandidat za bol” kada se pređe iz pilot u multi-user.
4. **Knowledge layer je dual-source**. Canonical glossary i metadata su i dalje fajl-backed sa SQLite cache-om. Sloj koji opslužuje runtime je DB-first, ali source-of-truth nije DB. Migracija ka DB-only authoring modelu je formalno otvorena (`Epic 1` next step).
5. **LLM signal fusion je još na nivou closed-set validatora**. `Epic 14C` ostaje proposed; trenutno LLM doprinosi review-u, ali ne ulazi u ranking fuziju.
6. **Operacionalizacija je ograničena**. Postoje preview, codegen, test sets, ali ne i release artifacts, scheduler ili durable execution (`Epic 10`). To je svesno granično, ali znači da Semantra nije ETL runtime.
7. **Performance sloj nije productized**. Per-run target embedding cache postoji, ali širi precompute/cache layer (`Epic 14A/14B`) nije zatvoren.

## Šta još stoji otvoreno (sažeto iz epics.md)

- `Epic 7`: konzistentniji naming/journey, jasnije razdvajanje explanation/triage/refinement.
- `Epic 13D`: bogatiji compare/drilldown, jače vezivanje Catalog signala sa review/governance.
- `Epic 14A/14B/14C`: target vector cache productization, stable signal precomputation, LLM signal fusion.
- `Epic 12B`: system-specific virtual targets (samo kad canonical baza to opravda).
- `Epic 1` follow-through: DB-only canonical source-of-truth.
- `Epic 14F` follow-up: stabilizacija konzole, bulk-safe UX, non-happy-path productization.
- `Epic 8`: dublja analytics/KPI nadgradnja iznad benchmark MVP-a.
- `Epic 4`: dublji execution safety za transformacije.
- `Epic 3`: dalji quality tuning za corrections/reusable rules.
- `Epic 10`: release artifacts, batch runtime, scheduler, persistent background execution.
- `Epic 9`: data quality intelligence kao novi review signal.
- `Epic 15`: derived graph projection/lineage.

## Preporuka za dalji razvoj

Predlažem da naredni 3–4 talasa idu ovim redom, jer to istovremeno smanjuje rizik i ne razvlači proizvod u previše paralelnih pravaca.

**Wave A — runtime/persistence hardening (arhitekturni dug)**
- razbiti persistence_service.py na uske module po domenu (mapping sets, knowledge, overlays, audit, jobs, benchmarks). Bez funkcionalne promene, samo seam.
- nastaviti odvajanje metadata_knowledge_service.py u: canonical authoring/read, overlay lifecycle, runtime matching, reseed/refresh.
- prvi korak ka DB-only canonical authoring: pisati overlay/promotion isključivo kroz DB, a glossary CSV tretirati kao izlazni snapshot, ne kao izvor.
- razlog: trenutni Phase 4 slice je već postavio seam i status signale; nastavak je sada najjeftiniji.

**Wave B — durable background jobs (operativni preduslov za multi-user)**
- prvi korak nije broker, nego durable job/status u SQLite-u (job zapis, status tranzicije, retry_count, cancel_requested/canceled_at, append-only event log).
- API površina ostaje ista (`start`, `get status`, `cancel`).
- razlog: već imamo eksplicitne durable-backend trigger-e u `/observability/mapping-jobs/runtime`; ovo otključava ozbiljniji pilot bez preranog brokera.

**Wave C — Epic 13D dublji discovery (jedini realan novi product wave)**
- bogatiji concept-centric compare kroz više integracija.
- visual/relational discovery sloj nad postojećim catalog/canonical podacima.
- jače vezivanje reuse signala sa Workspace review handoff-om (osnova postoji).
- razlog: ovo je jedini otvoreni pravac koji daje vidljivu novu vrednost korisniku, a stoji na već postavljenoj infrastrukturi.

**Wave D — performance i signal fusion**
- productize `Epic 14A` target vector cache i `14B` precompute samo posle benchmark dokaza dobitka.
- razmotriti `14C` LLM signal fusion tek ako benchmark pokaže da kontrolisan LLM input u ranking ne lomi explainability.
- razlog: bez wave A/B, optimizacija ranking puta nosi manju vrednost jer su drugi delovi krhkiji.

**Šta NE bih sada otvarao**
- `Epic 10` puni execution platform sloj — proizvod za to još nema ni durable jobs ni release pipeline.
- `Epic 15` graph layer — nema stabilnu izvor-podlogu dok canonical/catalog read modeli ne sazru.
- `Epic 12B` system-specific virtual targets — gura kompleksnost pre nego što canonical baza zatraži.
- `Epic 9` data quality intelligence — vrednost je realna, ali nije sledeća racionalna investicija pre A/B/C.

**Operativna pravila koja bih zadržao**
- jedan glavni product fokus po wave-u.
- svaki wave završiti uskim, ciljanim testovima (postojeća 216 + 125 mreža je dobra polazna).
- ne kombinovati veliki refactor i novi feature u istom talasu.
- posle svakog wave-a osvežiti current_state.md, completed_slices.md i plan.md.

## TL;DR

Semantra je solidna pilot-ready aplikacija sa stvarnim governance enforcement-om i pristojnom test mrežom, ali je nakupila tehnički dug u par velikih servisa i UI fajlova, i još uvek ima fajl-backed canonical source-of-truth i in-memory job runtime. Najvrednije sledeće investicije su, redom: razbijanje god-object servisa i DB-only canonical authoring, pa durable job/status backend, pa novi `Epic 13D` discovery wave, a tek onda performance/precompute i LLM fusion.




# 2026-06-06 Review
Reviewing the app structure and key UX flows in `Workspace`, `Catalog`, `Benchmark`, and `Governance` to form a business/user-centric audit.

## Business / User Flow Review

I reviewed the current Semantra UI flow across Workspace, Catalog, Benchmark, and Governance by examining:

- workspace_views.py
- catalog_views.py
- benchmark_views.py
- governance.py
- shared_views.py

---

## 1. Workspace Flow

### Strengths
- Clear section breakdown: `Setup → Review → Decisions → Output → Modelling Overview`
- `render_workspace_tab()` is the single entrypoint, so the workflow is centralized and consistent.
- Setup has strong upload + schema detection + companion metadata support.
- Workspace Copilot provides section-aware guidance and handoffs.
- The report builder already captures:
  - executive summary
  - scope/context
  - business intent
  - decision closure
  - field-level signals
  - graph evidence
  - transformation rationale
  - governance readiness

### Observations
- Workspace is quite rich and detailed, which is good for analysts but may overwhelm business users.
- The `Selected Mapping and Transformation Summary` section is useful, but it can still feel dense if the table is large.
- The report currently generates many sections; for business audiences, the top-level summary and “must know” bullets should be the most prominent.
- `Review Evidence Highlights` and `Field-level Signals` are valuable, but they rely on `mapping_response` + session state, so users may still find the “selected mapping” section incomplete if the active mapping state is not fully initialized.

### Potential UX improvements
- Add a compact “current state” banner in Workspace showing:
  - upload status
  - review completeness
  - open decisions count
  - output block reason
  - governance readiness
- Make the report generation behavior more explicit when no mapping rows exist, to avoid a blank or “no rows” feeling.
- For business users, consider collapsing the detailed markdown table behind a “Show mapping table” toggle.

---

## 2. Catalog Flow

### Strengths
- Good reuse guidance and workspace handoff messaging.
- `_catalog_next_action_plan()` clearly maps catalog status to next actions in Workspace / Governance.
- Field reuse shortlist and reuse-fit context are good for selective reuse decisions.
- Catalog handoff logic is explicitly designed to keep the workspace context visible and prevent blind reuse.

### Observations
- The Catalog flow is business-oriented: it surfaces “open workspace handoff”, “review handoff”, and “governance handoff”.
- It seems well-aligned to a process where catalog discovery feeds back into workspace decisions.
- The current design may require better state visibility around “current loaded workspace snapshot vs catalog candidate” to avoid confusion.

### Potential UX improvements
- Add an explicit “Current Workspace Snapshot” card when comparing catalog candidates.
- Show a small summary of:
  - overlapping fields
  - unmatched sources
  - approval status
  - governance risk
- Emphasize that Catalog is a reuse/comparison surface, not the authoring surface.

---

## 3. Benchmark Flow

### Strengths
- The Benchmark page is clearly telemetry-focused.
- It separates:
  - saving current mapping as benchmark
  - loading saved datasets
  - running benchmark
  - correction impact
  - profile comparison
  - explanation generation
- It uses the governance helper to block benchmark saves until decisions are accepted, which is a strong business rule.

### Observations
- This is a good “quality evidence” flow for governance or audit use cases.
- The current wording already positions benchmarks as evaluation/read-only rather than a place to edit mappings.

### Potential UX improvements
- Strengthen the label: “Benchmark quality review / audit evidence” to avoid confusion.
- If possible, add a short “When to use Benchmarks” checklist:
  - mapping decisions are accepted
  - baseline is stable
  - quality evidence is needed for governance
- Consider a “ready to promote” indicator for benchmark datasets that have strong accuracy and correction-impact results.

---

## 4. Governance Flow

### Strengths
- Governance is implemented as guardrails and block reasons, not as the main mapping authoring flow.
- `mapping_set_workspace_block_reason()` and `mapping_output_block_reason()` communicate why actions are blocked.
- Catalog reuses governance handoff logic for status-based decisions.

### Observations
- Governance currently appears more like a safety layer than a full workflow surface.
- That is okay, but business users may want a clearer governance readiness status in Workspace itself.
- The Workspace report already includes a governance readiness section, which is good.

### Potential UX improvements
- Surface governance readiness prominently in:
  - Workspace Output
  - Modelling Overview report
  - Catalog handoff panel
- Add a straightforward card like:
  - “Governance ready”
  - “Needs approval”
  - “Review canonical coverage first”
- This would help business users know whether the current workspace state is ready for approval handoff.

---

## Overall Recommendations

1. Keep the Workspace report strong, but make the top-level narrative even more business-first:
   - “What changed”
   - “What is still unresolved”
   - “What should be approved next”

2. In Workspace, make the navigation more explicit around “move to next stage”:
   - review complete → decisions
   - decisions accepted → output
   - output contract ready → governance / catalog reuse

3. In Catalog, ensure the reuse candidate and workspace comparison state are clearly labeled:
   - “This catalog version is approved / draft”
   - “This workspace snapshot includes X active decisions”
   - “Reuse will import Y selected decisions”

4. For Benchmarks, label it clearly as audit/quality evidence and keep users from trying to “edit mapping here.”

5. For Governance, add a visible readiness indicator in Workspace and Catalog, rather than only using block messages.

---

## Conclusion

The current app structure is quite solid. The strongest areas are:
- Workflow segmentation in Workspace
- Catalog reuse planning
- Benchmark evidence separation
- Governance block rules

The main business/UX risk is complexity and information density. Simplifying the user-facing summaries and making the next action clearer will make the app more approachable for non-technical business users while preserving the strong technical capability underneath.