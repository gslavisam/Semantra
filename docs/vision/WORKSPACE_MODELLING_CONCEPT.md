# Workspace Modelling Concept

## Purpose

This document proposes a new `Modelling Overview` subtab inside `Workspace` as a bounded conceptual-design layer that helps Semantra produce better review decisions, clearer mapping governance, stronger output contracts, and a reusable `BA Mapping Report` style summary of the full workspace result.

The goal is not to turn Semantra into a generic diagramming tool, UML suite, or enterprise architecture platform. The goal is narrower:

- present the single connected result that Workspace has already implied through Setup, Review, Decisions, and Output
- define what target business object is being built
- define the intended target grain and key business rules
- classify target attributes before or alongside field-level mapping decisions
- expose graphical `source -> concept -> target` structure as a final review aid, not as the primary artifact
- feed the existing `Review`, `Decisions`, and `Output` workflow with a better upstream contract

Most importantly, `Modelling Overview` should not be a decorative side panel. It should produce a concrete model contract and a compact overall-result summary that other `Workspace` sections can use.

Just as important, the tab should move toward a report-first mental model:

- the tab should read top-down like a structured `BA Mapping Report`
- the same report structure should later be exportable as a document
- the UI should synthesize signals and selected evidence from `Setup`, `Review`, `Decisions`, and `Output`, rather than copying each tab into a fifth place

The report is therefore the target artifact. The interactive tab is the presentation surface for that artifact.

## Why This Makes Sense Now

Semantra already has a partial form of target-shaping design inside `Workspace > Output` through the current `Transformation Design` slice:

- `target grain`
- `defaults / fallback behavior`
- `global rules`
- `field rules`
- bounded `structured spec proposal`

That means the product already accepts the idea that field-to-field mappings are not sufficient by themselves. A higher-level contract is already emerging.

`Modelling` would extend that idea one level up:

- from field rules to conceptual attributes
- from transformation notes to business object design
- from isolated mapping rows to an explicit target model

This is why the proposal is evolutionary rather than disruptive.

## Core Product Positioning

`Modelling` should be positioned as:

`business-target modelling that directly drives mapping and output behavior`

It should not be positioned as:

- a freeform ER tool
- a BPMN or process modeller
- a generic graph program
- a replacement for downstream implementation modeling

That boundary is critical. If the feature tries to support every modeling use case, it will become too broad and drift away from Semantra's core strength.

## First Principle: Derived First, Not Blank Canvas

The first version of `Modelling` should not begin as a blank authoring screen.

It should begin as a derived conceptual view of what the current `Workspace` state already implies.

That means the initial model should be generated from existing product evidence such as:

- active mapping decisions
- target fields already present in the current mapping state
- `resolution_type` and `resolution_payload`
- `Transformation Design` inputs already captured in `Output`
- accepted, pending, and excluded mapping outcomes

The user should then be able to refine, correct, and extend that derived model in a controlled way.

This matters for three reasons:

- it avoids the blank-page problem
- it keeps the model grounded in real workflow evidence
- it reduces the risk that `Modelling` becomes a disconnected parallel artifact

The right V1 mental model is therefore:

`derived model view first, light authoring and correction second`

Not:

`full manual modeling studio first`

## Recommended Placement in Workspace

For the current V1 posture, `Modelling` should sit at the end of the `Workspace` flow:

1. `Setup`
2. `Review`
3. `Decisions`
4. `Output`
5. `Modelling`

Why this order for now:

- `Setup`, `Review`, `Decisions`, and `Output` still carry the real operational workflow.
- the current V1 `Modelling` slice behaves more like a conceptual overview and correction surface than a mandatory upstream authoring step.
- placing it after `Output` makes that lower current operational weight explicit.

This also matches the present product truth: the first slice is more useful as a read-mostly conceptual summary of what the workspace already resolved.

The best longer-term framing for that summary is not `mini modelling studio`, but `BA Mapping Report generated from current workspace evidence`.

Longer term, if `Modelling` starts to materially steer review and output closure earlier in the analyst flow, it can be moved upstream.

For an incremental rollout, `Modelling` should initially coexist with the current `Output > Transformation Design` surface and later absorb or feed it.

## What Scope Makes Sense

The useful scope for Semantra is conceptual target modeling, not full logical or physical modeling.

### In scope

- target business object definition
- target grain
- key attributes and attribute groups
- required vs optional attributes
- target attribute intent and business meaning
- coarse relationships between entities or sub-objects
- business rules that affect mapping or output
- attribute classification hints such as:
  - sourced from source data
  - fixed value
  - derived value
  - target managed
  - out of scope
- coverage view across modeled vs mapped vs unresolved target attributes

### Out of scope for the first wave

- full ERD modeling with physical types, indexes, and DDL
- BPMN or workflow process modeling
- open-ended canvas editing with arbitrary nodes and shapes
- code generation directly from diagrams without review and decision checkpoints
- generic architecture repository behavior

## V1 Product Proposal

The first useful version should be intentionally narrow.

Just as important, the first useful version should be derived-first.

That means:

- Semantra first generates an inferred conceptual model from current `Workspace` state
- the user reviews that inferred model as a conceptual presentation of current mapping reality
- the user can then correct, enrich, group, and extend the model
- those corrections do not silently overwrite mapping decisions; they become explicit hints or controlled apply actions

## Overview Direction: BA Mapping Report

The strongest product direction for `Modelling Overview` is to structure it as a business-analyst report of the completed workspace activity.

That report should answer, in order:

1. what problem space and target context did we start from
2. what source and target evidence did we analyze
3. what mapping and modeling decisions did we make
4. what target object and concept contract did that work produce
5. what is still open, risky, or excluded
6. how does the `source -> concept -> target` picture look as a synthesized result

This direction is stronger than a generic metrics panel because it gives the user a narrative artifact that can be reviewed, discussed, approved, and later exported.

In practical product terms, that means:

- the top of the tab should read like report sections, not a random dashboard
- controls stay available, but the main visual hierarchy should belong to the report body
- the graph is a supporting section inside the report, not the whole point of the tab
- section content should reuse existing workspace signals and selected explanatory text from the workflow, not duplicate raw UI controls from the earlier tabs

The detailed proposed report structure lives in `docs/reference/WORKSPACE_BA_MAPPING_REPORT_SPEC.md`.

### 1. Target object

Define:

- object name
- object description
- business purpose

Examples:

- `Customer master`
- `Vendor master`
- `Invoice header`
- `Employee profile`

In V1 this object should be prefilled whenever Semantra can infer a likely target object from current target context, naming, or transformation design inputs.

### 2. Grain and keys

Define:

- target grain
- primary business key
- optional natural keys or reference keys

Examples:

- one row per customer
- one row per invoice header
- one row per employee assignment

In V1, `target grain` should be derived from existing `Transformation Design` state when present, and otherwise left editable but empty.

### 3. Concept groups

Allow the user to define groups such as:

- identity
- classification
- status
- dates
- contact
- financials
- references

These are not physical tables. They are conceptual buckets that make review easier.

In V1, Semantra may propose default groups from target names or existing canonical cues, but the user should be able to reorganize them.

### 4. Attributes

The center of the V1 should be an editable modeled-attributes table with columns such as:

- attribute name
- group
- business meaning
- required or optional
- expected resolution type
- notes

`Expected resolution type` is particularly valuable because it creates an upstream modeling hint for the exact decision model already present in Semantra.

In V1, the first attribute set should come from the current target fields already visible in mapping decisions and transformation rules. The user can then:

- add missing modeled attributes that do not yet exist in current mappings
- mark attributes as required or optional
- correct the expected resolution type
- add business meaning and notes

Examples:

- `customer_id` -> expected `direct_mapping` or `target_managed`
- `record_source` -> expected `fixed_value`
- `full_name` -> expected `derived_value`
- `legacy_internal_flag` -> expected `out_of_scope`

### 5. Relationships and business rules

Allow a lightweight relationship section for things like:

- parent-child references
- lookup dependencies
- one-to-many conceptual notes
- survivorship or deduplication notes
- defaulting rules

This should stay textual or semi-structured in V1, not become a full graph semantics engine.

In V1, these rules should also accept imported or derived hints from the current `Output > Transformation Design` state.

### 6. Graphical preview

V1 should include a graphical model preview, but not necessarily a full graphical editor.

The practical choice is:

- user first reviews an inferred model generated from existing workspace evidence
- user edits forms and structured tables to correct or extend it
- Semantra renders a diagram-like preview of:
  - the target object
  - concept groups
  - modeled attributes
  - key relationships

This provides the graphical value without forcing a high-cost interactive canvas in the first slice.

## Why This Is Valuable

`Modelling` creates value only if it changes downstream quality.

### Impact on Review

`Review` could use the model to:

- show which candidate target belongs to which concept group
- flag when a row is mapping into an attribute marked `target managed`
- flag when a mapped target attribute is not in the conceptual model
- prioritize review for required modeled attributes that still have weak or missing mappings

### Impact on Decisions

`Decisions` could use the model to:

- pre-suggest likely `resolution_type`
- expose unresolved required modeled attributes
- separate genuine data gaps from intentionally excluded attributes
- explain why some target fields are `fixed_value`, `derived_value`, `target_managed`, or `N/A`
- highlight drift between the current conceptual model and the current active decisions

### Impact on Output

`Output` could use the model to:

- seed `Transformation Design`
- validate target grain against modeled intent
- summarize coverage of required modeled attributes
- keep generated artifacts aligned with intended target object structure
- show when the current output contract has drifted away from the corrected conceptual model

## Technical Feasibility

This is feasible, but the feasibility depends heavily on scope discipline.

### Feasible now

The following are realistic without a major architecture rewrite:

- a new `Workspace` subtab
- a derived conceptual model generated from current workspace state
- session-state-backed conceptual model forms
- a structured model payload in `st.session_state`
- draft persistence of that model with existing workspace session patterns
- model-aware summary and coverage helpers
- a rendered graph preview from structured data
- downstream use of the model in `Review`, `Decisions`, and `Output`

### Feasible later, but more expensive

- interactive drag-and-drop canvas editing
- layout persistence for nodes and edges
- custom graph manipulation behaviors
- richer edge semantics and nesting behavior

Those would likely require a custom Streamlit component or a dedicated frontend surface rather than plain Streamlit widgets.

## Recommended Technical Shape

The first technical slice should introduce a new bounded state object, for example:

```python
workspace_concept_model = {
    "source_mode": "derived_from_workspace",
    "source_snapshot": {
        "mapping_decision_count": 12,
        "transformation_spec_present": True,
    },
    "object_name": "Customer master",
    "description": "Customer profile used by downstream CRM sync",
    "target_grain": "One row per customer",
    "concept_groups": [
        {"id": "identity", "label": "Identity"},
        {"id": "status", "label": "Status"},
        {"id": "contact", "label": "Contact"},
    ],
    "attributes": [
        {
            "name": "customer_id",
            "group": "identity",
            "required": True,
            "expected_resolution_type": "direct_mapping",
            "notes": "Primary business identifier",
        },
        {
            "name": "record_source",
            "group": "status",
            "required": True,
            "expected_resolution_type": "fixed_value",
            "notes": "Set to the source-system name",
        },
    ],
    "relationships": [
        {
            "from": "Customer master",
            "to": "Customer address",
            "kind": "has_many",
            "notes": "Only primary address enters the current target",
        }
    ],
    "business_rules": [
        "Keep only active customers.",
        "Deduplicate by customer_id and keep the newest record.",
    ],
    "drift_summary": {
        "unmodeled_targets": ["credit_limit"],
        "modeled_but_unmapped": ["customer_segment"],
    },
}
```

This is sufficiently expressive for V1 and still aligned with Semantra's current workflow style.

The most important source-of-truth rule for V1 is:

- active mapping decisions remain the operational truth for preview and code generation
- the conceptual model is a derived and editable contract layer
- model corrections affect workflow only through explicit apply or refresh actions
- Semantra should show drift rather than silently reconciling conflicts

## UI Proposal

The `Modelling` tab should use a derived-first layout:

### Top actions row

- `Generate model from current workspace`
- `Refresh from workspace`
- `Apply model hints to decisions`
- `Show drift`

This makes the relationship to the existing workflow explicit.

### Left side: inferred model and editable corrections

- object metadata
- grain and keys
- concept groups
- modeled attributes table
- relationship notes
- business rules

The left side should clearly distinguish:

- inferred values from current workspace state
- user-corrected values
- added model elements that do not yet exist in active mappings

### Right side: model preview and coverage

- graphical model preview
- modeled attribute counts
- required vs optional counts
- mapped vs unresolved counts
- distribution of expected resolution types
- warnings such as:
  - required modeled attribute has no accepted mapping
  - mapping exists for target not present in model
  - target is marked both required and `out_of_scope`
    - model corrections are not yet applied to current decisions

This keeps the feature analytical rather than diagram-first.

## Phase Plan

### Phase 1. Derived model presentation with controlled edits

Deliver:

- new `Modelling` tab
- derived concept model state object
- generation of initial inferred model from current workspace state
- forms for object, grain, groups, attributes, and rules
- basic model summary and coverage panel
- explicit refresh and drift behavior
- draft persistence in workspace continuity flows

This phase already provides value even without a graphical editor.

### Phase 2. Downstream awareness and model-guided workflow

Deliver:

- decisions hints using expected resolution type
- review coverage against modeled attributes
- output summary aligned to required modeled attributes
- explicit apply actions from model corrections into workflow hints

This is likely the highest-value release point.

### Phase 3. Graph preview and richer interaction

Deliver only if earlier phases prove real adoption value:

- rendered conceptual diagram preview
- draggable nodes
- editable edges
- saved layout
- richer visual interactions

This phase should be justified by user behavior, not by novelty alone.

## Major Risks

### 1. Scope inflation

If `Modelling` tries to become a general modeling suite, it will dilute Semantra's core value.

### 2. Decorative diagrams

If the graphical output looks good but does not affect `Review`, `Decisions`, or `Output`, the feature will not justify its complexity.

### 3. Cognitive overload

Business analysts should not have to learn a full modeling methodology before they can get mapping value.

### 4. Competing sources of truth

The concept model, manual mapping decisions, and transformation design must not diverge silently.

## Recommendation

Semantra should support `Workspace > Modelling`, but only as a bounded conceptual target-model layer tightly integrated with the existing workflow.

The right first goal is not:

- `build a revolutionary modeling canvas`

The right first goal is:

- `build a derived and editable target model contract that improves mapping review, decision closure, and governed output generation`

That direction is both feasible and strategically differentiated.

## Recommended First Implementation Question

Before coding begins, the most important design question is:

`What is the minimum model contract that materially improves Review, Decisions, and Output?`

If that question is answered well, `Modelling` can become one of the strongest product differentiators in Semantra without turning the product into a generic modeling platform.