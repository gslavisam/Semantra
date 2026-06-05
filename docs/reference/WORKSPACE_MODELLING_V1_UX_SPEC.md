# Workspace Modelling V1 UX Spec

## Goal

Define the first concrete UX slice for `Workspace > Modelling Overview` in a way that stays aligned with Semantra's current `Setup -> Review -> Decisions -> Output` workflow and current overview-first product value.

In V1, this tab is not a copy of the other tabs. It is a single connected overview of the workspace result, showing only the signals that tie those tabs together: target context, decision closure, concept coverage, output-contract readiness, and the derived concept model. A `source -> concept -> target` graph is a supporting visualization layered on top of that overview.

The strongest product direction is to structure that overview as a rendered `BA Mapping Report` in Markdown form, so the same logical artifact can later be exported as a document.

The goal of V1 is not open-ended model authoring. The goal is:

- present a conceptual model inferred from the current workspace state
- let the user correct and enrich that model
- expose the impact of those corrections on review, decisions, and output
- avoid introducing a second silent source of truth

## Core Design Principle

V1 is `derived-first`.

That means the first user experience is:

1. Semantra derives a conceptual model from the current workspace state.
2. The user reviews that inferred model.
3. The user edits or extends the model where Semantra is incomplete or wrong.
4. The user explicitly applies model hints back into workflow surfaces where appropriate.

It is intentionally not:

1. open an empty canvas
2. manually design everything from scratch
3. hope it stays aligned with mapping decisions later

## UI Placement

Top-level placement inside `Workspace` for the current V1 slice:

1. `Setup`
2. `Review`
3. `Decisions`
4. `Output`
5. `Modelling`

Why here for now:

- the current V1 slice behaves more like a post-run conceptual overview and correction surface than a primary operational step
- users should first complete the high-value operational path, then inspect the conceptual model derived from that state
- if later slices make `Modelling` materially steer decision closure earlier, the tab can move upstream

## Primary Inputs

The inferred model should be generated from current workspace evidence such as:

- active mapping decisions
- target fields already visible in mapping decisions
- `resolution_type` and `resolution_payload`
- current `Transformation Design` fields such as `target grain`, defaults, global rules, and field rules
- accepted vs open review outcomes
- target context already established in the workspace

## Primary UI Sections

The V1 tab should have a report-first structure.

### 1. Top actions row

Buttons:

- `Generate model from current workspace`
- `Refresh from workspace`
- `Apply model hints to decisions`
- `Show drift`

Behavior:

- `Generate model from current workspace` creates the first inferred conceptual model if none exists.
- `Refresh from workspace` rebuilds inferred fields from the latest workspace state while preserving user-entered corrections where possible.
- `Apply model hints to decisions` performs explicit, bounded sync actions only.
- `Show drift` highlights where the model and current operational state disagree.

### 2. Report body

This should be the dominant visual structure of the tab.

Recommended order:

- executive summary
- starting point and scope
- source and target landscape
- mapping outcome summary
- key decisions and rationale
- concept model result
- `source -> concept -> target` graph
- output contract summary
- risks, gaps, and next steps

The detailed section contract lives in `docs/reference/WORKSPACE_BA_MAPPING_REPORT_SPEC.md`.

### 3. Bounded editing and drill-down support

The tab can still expose editing or drill-down controls, but those should support the report rather than replace it.

Examples:

- target object corrections
- business purpose corrections
- required attribute corrections
- business-rule corrections
- drift details

## Detailed Section Behavior

### Executive summary

This should answer, in one pass:

- what object are we building
- how closed is the decision set
- how complete is the concept coverage
- is the output contract ready
- what is the overall current conclusion

### Starting point and scope

This should summarize the boundary of the exercise rather than repeat the full setup form.

### Mapping outcome summary

This should synthesize key review and decision signals rather than dump all mapping rows.

### Key decisions and rationale

This should surface only the most decision-significant rows, especially:

- fixed values
- derived values
- `N/A`
- target-managed outcomes
- unresolved required items

### Concept model result

This is the main editable panel.

Subsections:

- target object
- grain and keys
- concept groups
- modeled attributes
- relationship notes
- business rules

Each subsection should visually distinguish:

- inferred values
- user-corrected values
- user-added values that did not come from workspace inference

### Impact and coverage panel

This is the read-only analytical side.

It should show:

- modeled attribute counts
- required vs optional counts
- mapped vs unresolved counts
- distribution of expected resolution types
- modeled-but-unmapped attributes
- mapped targets not represented in the current model
- drift warnings
- pending model corrections not yet applied to workflow hints

### Target object

Fields:

- object name
- description
- business purpose

Behavior:

- prefill from target naming and workspace context when possible
- allow free edit
- show whether the current value is inferred or user-corrected

### Grain and keys

Fields:

- target grain
- primary business key
- optional natural keys

Behavior:

- prefill from existing `Transformation Design` state when available
- otherwise remain editable and blank
- show warning when grain conflicts with existing transformation design or output intent

### Concept groups

Fields:

- group name
- optional description

Behavior:

- Semantra may propose starter groups from target names or concept patterns
- user can add, rename, merge, and reassign groups
- no freeform nested hierarchy in V1

### Modeled attributes

This should be the central `st.data_editor` table.

Columns:

- attribute name
- group
- business meaning
- required
- expected resolution type
- current mapped target
- current mapping status
- notes
- origin

`origin` values:

- `inferred`
- `corrected`
- `user_added`

Behavior:

- prepopulate from current mapped target fields
- allow adding attributes that are not yet present in active mapping decisions
- allow marking attributes as `required`
- allow setting expected resolution types such as `direct_mapping`, `fixed_value`, `derived_value`, `target_managed`, and `out_of_scope`
- show current mapped target and status as read-only workspace evidence columns

### Relationship notes

V1 should support only lightweight structure:

- related object
- relationship kind
- notes

No arbitrary graph editing is required in V1.

### Business rules

V1 should support:

- ordered textual rules
- defaults and edge cases
- deduplication or survivorship notes

These should seed or mirror `Transformation Design` later but must not overwrite it silently.

## Sync Rules

This is the most important part of the V1 UX.

### Source of truth

- active mapping decisions remain the operational truth for preview and code generation
- the model is a derived and editable contract layer

### Allowed automatic behavior

- generate inferred model from current workspace state
- refresh inferred evidence columns
- preserve user corrections where the system can do so safely

### Not allowed as silent behavior

- silently changing active mapping decisions because the model was edited
- silently deleting user-added modeled attributes because the latest workspace state does not contain them
- silently rewriting `Transformation Design` based on model edits

### Explicit apply behavior

`Apply model hints to decisions` may do bounded actions such as:

- suggest `resolution_type` for rows that do not have a strong explicit decision yet
- flag required modeled attributes with no active mapping
- flag targets that appear in decisions but not in the current model
- seed `Transformation Design` recommendations

It should not auto-approve or auto-save governance outcomes.

## Drift Model

`Show drift` should summarize at least these categories:

- modeled but unmapped
- mapped but unmodeled
- modeled as required but currently excluded
- modeled expected resolution type differs from current decision type
- output grain differs from modeled grain

This is essential to keep `Modelling` from becoming stale or misleading.

## Right-Panel Warnings

The impact panel should show warnings such as:

- `Required modeled attribute has no accepted mapping.`
- `Current decision marks this target as target managed, but the model expects direct mapping.`
- `The current output contract includes targets that are not present in the conceptual model.`
- `Model corrections exist but have not been applied back as workflow hints.`

## V1 Graphical Behavior

V1 does not need a full editor canvas.

It should support:

- diagram-like preview of the target object
- grouped attribute rendering
- simple relationship lines or grouped association display

It should not require:

- draggable nodes
- manual edge drawing
- saved canvas layout

## Session State Shape

Representative state objects:

```python
workspace_concept_model
workspace_concept_model_generated
workspace_concept_model_last_refresh
workspace_concept_model_drift_summary
workspace_concept_model_pending_hints
```

The model object itself should store both inferred and corrected metadata rather than only the final edited values.

## UI Actions and Expected Outcomes

### Generate model from current workspace

Outcome:

- create an inferred concept model from current workspace state
- populate the tab
- store drift baseline against current state snapshot

### Refresh from workspace

Outcome:

- update inferred evidence from the latest state
- preserve user corrections when they do not directly conflict
- update drift summary

### Apply model hints to decisions

Outcome:

- create bounded hints and warnings
- optionally seed decision-side helper state
- do not silently commit operational changes

### Show drift

Outcome:

- show disagreement between the model and current workspace operational state
- allow the user to decide whether to refresh, keep overrides, or apply hints

## Acceptance Criteria for V1

- The tab can generate a conceptual model from current workspace state.
- The user can edit and extend the model without losing derived evidence.
- The UI clearly distinguishes inferred vs corrected vs user-added content.
- The UI exposes drift between the concept model and current decisions or output design.
- No model edit silently overwrites mapping decisions or output contracts.
- The user can trigger explicit apply actions for bounded model hints.

## Non-Goals

- open-ended diagramming canvas
- full ER or UML authoring
- automatic bidirectional sync without review
- replacement of the existing decision governance flow

## Suggested Implementation Order

1. Add tab shell and state object.
2. Implement `Generate model from current workspace`.
3. Add editable modeled-attributes table with origin markers.
4. Add drift summary and right-panel warnings.
5. Add bounded `Apply model hints to decisions` behavior.
6. Add graphical preview last.