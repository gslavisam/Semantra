# Semantra Presentation Scenario

## Presentation Goal

This presentation introduces Semantra as a pilot-ready semantic mapping and governance workbench, explains what the product already supports today, clarifies the concrete outputs it produces, highlights the emerging BA Mapping Report capability, and positions it as a reusable delivery capability rather than a one-off demo tool.

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

## Slide 2. The problem

**Title:**
The Problem

**Slide bullets:**

- schema mapping is still slow, fragmented, and hard to reuse
- teams start from specs, SQL snapshots, and partial metadata, not only clean sample data
- one-off AI suggestions are hard to trust in delivery work
- mapping knowledge often disappears after a project ends

**Key message:**
Integration delivery needs a more structured and governable way to move from raw structures to reviewed decisions.

---

## Slide 3. What Semantra provides

**Title:**
What Semantra Provides

**Slide bullets:**

- a pilot-ready semantic mapping and governance workbench
- explainable mapping suggestions with review checkpoints
- governed artifacts, reusable catalog knowledge, and benchmark history
- transformation starter code and output preview
- a BA Mapping Report that turns the workspace outcome into a business-facing summary

**Key message:**
Semantra does not stop at suggestions; it helps teams produce a reviewable and reusable delivery outcome.

---

## Slide 4. Main product surface

**Title:**
Main Product Surface

**Slide bullets:**

- `Workspace`
- `Governance`
- `Catalog`
- `Benchmarks`
- `System`
- `Modelling / BA Report` (emerging)

**Key message:**
The product now has clear operator-facing areas rather than one generic review screen.

**Talk track:**
`Workspace` covers ingest, mapping, review, decisions, preview, code generation, and bounded `Workspace Copilot` guidance. `Governance` contains `Canonical Console` and stewardship workflows. `Catalog` supports search and reuse. `Benchmarks` measures quality. `System` supports runtime inspection and operational controls. A new `Modelling / BA Report` view helps turn workspace evidence into a structured, analyst-ready summary.

**Sidebar note:**
The UI also includes a multi-view sidebar for `System`, `WS Copilot`, `WS Brief`, `Help`, and `Reference`.

---

## Slide 5. Why this matters

**Title:**
Why This Matters

**Slide bullets:**

- less rework across mapping and delivery cycles
- clearer review and approval decisions
- better traceability from source structure to target outcome
- reusable semantic knowledge for future projects
- a stronger handoff from analysis to implementation

**Key message:**
The real value is not only better mapping suggestions; it is less friction, more trust, and a stronger delivery package.

**Talk track:**
For a business analyst, delivery lead, or reviewer, the important outcome is not just a suggested mapping. It is a structured and explainable result that can be reviewed, approved, reused, and handed off with less rework and better traceability.

---

## Slide 6. Core value proposition

**Title:**
Core Value Proposition

**Slide bullets:**

- map faster with a more structured starting point
- understand why a mapping was suggested
- produce delivery-ready mapping summaries
- review before generating durable artifacts
- improve quality through governed feedback and reusable report artifacts

**Key message:**
Semantra turns mapping from a one-time analyst task into a repeatable and improvable operating capability, and the BA Mapping Report makes the outcome visible to business and delivery stakeholders.

---

## Slide 7. How mapping decisions are produced

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

## Slide 8. Canonical layer and stewardship

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

## Slide 9. Governance model

**Title:**
Governance Model Today

**Slide bullets:**

- versioned mapping sets with status, audit, and diff
- approved-only reuse back into Workspace
- advisory preview before final approval
- governance-gated code generation and transformation test execution
- closed-review-only durable corrections
- first pilot RBAC slice with role-based access for mapping and draft session surfaces

**Key message:**
Trust comes from explicit control points, not from pretending that all automation is safe by default.

---

## Slide 10. Catalog and reuse

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

## Slide 11. Benchmarks and learning

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

## Slide 12. Typical workflow story

**Title:**
Typical Workflow Story

**Slide bullets:**

1. upload source and target structures or schema specs
2. generate ranked mapping suggestions
3. inspect trust layer and canonical paths
4. review or override mappings
5. review the derived BA Mapping Report and target contract
6. preview transformations and generate code when accepted
7. save governed mapping sets
8. search and reuse existing work later through Catalog

**Key message:**
Semantra supports an end-to-end analyst loop, not only one ranking step.

---

## Slide 13. Architecture overview

**Title:**
Architecture Overview

**Slide bullets:**

- FastAPI API layer for application orchestration
- service layer for mapping, preview, catalog, evaluation, and knowledge logic
- modular Streamlit UI for product flows
- SQLite persistence for governed artifacts and semantic memory
- file-backed canonical seed inputs with DB-first runtime loading
- complementary `semantra_agent` SDK layer for LangChain/LangGraph and scripted integration use cases

**Key message:**
The architecture is already structured for pilot-grade product growth, not just for a single script demo.

---

## Slide 14. PMO service framing

**Title:**
Semantra as a Delivery Capability

**Slide bullets:**

- usable in integration design, migration analysis, canonical alignment work, and analyst handoff
- outputs reviewed mappings, canonical findings, transformation starters, benchmarks, reusable governed artifacts, and BA Mapping Reports
- reduces repeated mapping effort across delivery streams
- improves traceability, semantic reuse, and delivery readiness

**Key message:**
Semantra can be framed not only as a tool, but as a reusable internal delivery capability.

---

## Slide 15. Current boundaries

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

## Slide 16. Next step

**Title:**
Where the Product Goes Next

**Slide bullets:**

- documentation aligned with the real current product
- manual pilot proof and value validation
- repeatable live demo and presentation discipline
- mature the BA Mapping Report into an exportable approval and handoff artifact
- enterprise-wide hardening only after proven value
- evolve the complementary `semantra_agent` SDK as part of the broader agentic integration surface

**Key message:**
The next step is to prove and package the value of the current product clearly before expanding it into a broader enterprise program.

---

## Slide 17. Closing

**Title:**
Closing

**Slide bullets:**

- Semantra makes mapping explainable
- Semantra makes mapping reviewable
- Semantra makes mapping reusable
- Semantra turns semantic integration work into a governed delivery capability, including BA-ready reporting

**Key message:**
Semantra is the foundation for reusable semantic integration knowledge under analyst and stewardship control.

---

## Executive Summary

**Bottom line:**
Semantra helps integration teams move from fragmented mapping work to a governed, explainable, and reusable delivery process.

**Three takeaways:**

- it reduces the cost and rework of manual mapping by giving analysts a structured starting point
- it makes decisions reviewable and traceable instead of opaque or one-off
- it produces reusable artifacts, including a BA Mapping Report, that support delivery handoff and future projects

---

## Optional Demo Flow

If a live demo is included, use this sequence:

1. `Catalog` to show approved reuse
2. `Modelling / BA Report` to show the synthesized business-facing summary
3. `Workspace` to show draft-session continuity and active review context
4. `Catalog` diff or stewardship handoff to show governed follow-up
5. `Benchmarks` to show profile comparison and explanation
6. `WS Copilot` to show bounded closure/readiness guidance in the live workflow
7. use the broader `Workspace > Setup -> Review -> Decisions -> Output` walkthrough only as an extended technical appendix when the audience wants implementation depth
