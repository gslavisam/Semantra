# Semantra Presentation Scenario

## Presentation Goal

This presentation introduces Semantra as a pilot-ready semantic mapping and governance workbench, explains what the product already supports today, and positions it as a reusable delivery capability rather than a one-off demo tool.

Recommended duration:

- 15 to 20 minutes for overview only
- 25 to 30 minutes if you also include a short live demo

Recommended audience:

- PMO
- enterprise architecture
- delivery leads
- business analysts
- integration leads
- data and platform stakeholders

---

## Slide 1. Title

**Title:**
Semantra
Explainable Semantic Mapping for Integration Delivery

**Key message:**
Semantra helps teams move from raw schemas to reviewed mapping decisions, canonical concepts, and reusable governed artifacts.

**Talk track:**
Semantra is built to make mapping explainable, reviewable, and reusable. It is not a black-box AI mapper. It is a deterministic-first workbench with bounded AI assistance where analysts and stewards stay in control.

---

## Slide 2. Why this exists

**Title:**
Why Semantra Exists

**Slide bullets:**

- schema mapping is slow and hard to reuse
- projects often start from specs, SQL snapshots, or partial metadata, not only from clean row data
- black-box LLM mapping is hard to trust in delivery work
- organizations need reviewed mapping memory, not just one-off outputs

**Key message:**
Semantra exists because integration teams need a structured alternative to spreadsheet-only mapping and uncontrolled AI mapping.

---

## Slide 3. What Semantra is today

**Title:**
What Semantra Is Today

**Slide bullets:**

- pilot-ready semantic mapping and governance workbench
- FastAPI backend plus Streamlit product UI
- deterministic-first mapping engine with bounded AI assistance
- SQLite-backed artifact, catalog, and governance memory

**Key message:**
Semantra is already useful in controlled analyst and pilot workflows today, even though it is not yet a production orchestration platform.

---

## Slide 4. Main product surface

**Title:**
Main Product Surface

**Slide bullets:**

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

**Key message:**
The product now has clear operator-facing areas rather than one generic review screen.

**Talk track:**
`Workspace` covers ingest, mapping, review, decisions, preview, and code generation. `Canonical Console` handles semantic stewardship. `Catalog` supports search and reuse. `Benchmarks` measures quality. `Admin / Debug` supports runtime inspection.

---

## Slide 5. Core value proposition

**Title:**
Core Value Proposition

**Slide bullets:**

- map faster
- understand why a mapping was suggested
- review before generating durable artifacts
- improve quality through governed feedback
- reuse semantic knowledge across projects

**Key message:**
Semantra turns mapping from a one-time analyst task into a repeatable and improvable operating capability.

---

## Slide 6. How mapping decisions are produced

**Title:**
How Mapping Decisions Are Produced

**Slide bullets:**

- lexical similarity
- semantic similarity
- metadata knowledge and aliases
- canonical glossary signal
- pattern and statistical hints
- correction history and reusable rules
- optional bounded LLM validation for ambiguity cases

**Key message:**
Semantra does not rely on one signal and does not let AI own the full mapping process.

---

## Slide 7. Canonical layer and stewardship

**Title:**
Canonical Layer and Stewardship

**Slide bullets:**

- source-to-canonical mapping without a real target
- canonical concept registry and detail views
- canonical-gap review and suggestion flow
- overlay lifecycle and promote-to-glossary workflow

**Key message:**
The canonical layer is already an active governance surface, not only a future idea.

---

## Slide 8. Governance model

**Title:**
Governance Model Today

**Slide bullets:**

- versioned mapping sets with status, audit, and diff
- approved-only reuse back into Workspace
- advisory preview before final approval
- governance-gated code generation and transformation test execution
- closed-review-only durable corrections

**Key message:**
Trust comes from explicit control points, not from pretending that all automation is safe by default.

---

## Slide 9. Catalog and reuse

**Title:**
Catalog as Reusable Memory

**Slide bullets:**

- integration listing and search
- concept-centric detail
- similar integration discovery
- approved artifact reuse into Workspace
- support for both standard and canonical-only saved artifacts

**Key message:**
The catalog already exists as the first reusable memory layer of the product.

**Talk track:**
This is an important change in the story. The catalog is no longer only a future roadmap item. The current slice already supports search, detail, and reuse. The next step is to deepen discovery, not to invent the catalog from scratch.

---

## Slide 10. Benchmarks and learning

**Title:**
Quality Measurement and Learning

**Slide bullets:**

- saved benchmark datasets and runs
- correction-impact measurement
- governed correction persistence
- reusable learning through promoted rules

**Key message:**
Semantra measures and improves mapping quality instead of staying a stateless suggestion engine.

---

## Slide 11. Typical workflow story

**Title:**
Typical Workflow Story

**Slide bullets:**

1. upload source and target structures or schema specs
2. generate ranked mapping suggestions
3. inspect trust layer and canonical paths
4. review or override mappings
5. preview transformations and generate code when accepted
6. save governed mapping sets
7. search and reuse existing work later through Catalog

**Key message:**
Semantra supports an end-to-end analyst loop, not only one ranking step.

---

## Slide 12. Architecture overview

**Title:**
Architecture Overview

**Slide bullets:**

- FastAPI API layer for application orchestration
- service layer for mapping, preview, catalog, evaluation, and knowledge logic
- modular Streamlit UI for product flows
- SQLite persistence for governed artifacts and semantic memory
- file-backed canonical seed inputs with DB-first runtime loading

**Key message:**
The architecture is already structured for pilot-grade product growth, not just for a single script demo.

---

## Slide 13. PMO service framing

**Title:**
Semantra as a Delivery Capability

**Slide bullets:**

- usable in integration design, migration analysis, and canonical alignment work
- outputs reviewed mappings, canonical findings, transformation starters, benchmarks, and reusable governed artifacts
- reduces repeated mapping effort across delivery streams
- improves traceability and semantic reuse

**Key message:**
Semantra can be framed not only as a tool, but as a reusable internal delivery capability.

---

## Slide 14. Current boundaries

**Title:**
What Semantra Is Not Yet

**Slide bullets:**

- not a production ETL runtime
- not a connector-heavy integration platform
- not a multi-step enterprise workflow engine
- not a graph-native metadata platform

**Key message:**
The current scope is intentionally focused. The product is strongest when positioned as a semantic mapping and governance workbench.

---

## Slide 15. Next step

**Title:**
Where the Product Goes Next

**Slide bullets:**

- documentation aligned with the real current product
- manual pilot proof and value validation
- repeatable live demo and presentation discipline
- enterprise-wide hardening only after proven value

**Key message:**
The next step is to prove and package the value of the current product clearly before expanding it into a broader enterprise program.

---

## Slide 16. Closing

**Title:**
Closing

**Slide bullets:**

- Semantra makes mapping explainable
- Semantra makes mapping reviewable
- Semantra makes mapping reusable
- Semantra turns semantic integration work into a governed delivery capability

**Key message:**
Semantra is the foundation for reusable semantic integration knowledge under analyst and stewardship control.

---

## Optional Demo Flow

If a live demo is included, use this sequence:

1. `Catalog` to show approved reuse
2. `Workspace` to show draft-session continuity and active review context
3. `Catalog` diff or stewardship handoff to show governed follow-up
4. `Benchmarks` to show profile comparison and explanation
5. use the broader `Workspace > Setup -> Review -> Decisions -> Output` walkthrough only as an extended technical appendix when the audience wants implementation depth
