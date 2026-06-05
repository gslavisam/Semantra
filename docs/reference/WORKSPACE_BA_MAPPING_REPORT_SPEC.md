# Workspace BA Mapping Report Spec

## Goal

Define the target structure for `Workspace > Modelling Overview` as a report-first artifact.

The desired end state is not a loose dashboard and not a second copy of the earlier tabs. The desired end state is a top-down `BA Mapping Report` that presents the result of the full workspace activity in a form that can later be exported as a document.

## Core Principle

`Modelling Overview` should synthesize the result of the workflow, not replay the full workflow.

That means the report should:

- summarize what the analyst started from
- summarize what evidence the product processed
- summarize what decisions and modeling conclusions were reached
- show the resulting target contract
- show remaining gaps, risks, and exclusions
- show the synthesized `source -> concept -> target` graph as the visual capstone

That also means the report should not:

- duplicate all controls from `Setup`, `Review`, `Decisions`, and `Output`
- dump every mapping row without hierarchy
- behave like a freeform modelling canvas
- replace the operational workflow tabs as the place where decisions are actually made

## Report Consumers

Primary readers:

- business analyst
- solution analyst
- delivery lead
- governance reviewer
- implementation team member who needs a compact handoff summary

Secondary use:

- exportable document for project working sessions, approvals, or delivery handoff

## Report Rendering Model

The same logical artifact should support two surfaces:

1. rendered inside `Workspace > Modelling Overview`
2. exported later as a Markdown-based document

For that reason, the tab should increasingly be built from report sections that can be assembled into one canonical Markdown payload.

## Proposed Top-Down Report Structure

### 1. Executive Summary

Purpose:

- give a one-screen summary of the workspace outcome

Content:

- target object name
- target context summary
- active decision count
- accepted vs open decision count
- mapped vs unresolved vs excluded coverage
- output-contract readiness
- short overall conclusion

Source signals:

- `Setup`
- `Decisions`
- `Output`
- derived concept model

### 2. Starting Point and Scope

Purpose:

- explain what the analysis started from and in what boundary it was performed

Content:

- workspace scope: source system, business domain, integration name
- source artifact summary
- target context summary
- mapping mode
- projection mode
- important assumptions captured during setup or target selection

Source signals:

- `Setup`
- mapping runtime context

### 3. Source and Target Landscape

Purpose:

- explain the input and intended target in business terms

Content:

- source tables or source structure in compact form
- target object
- target grain
- target profile or dataset context
- important source companion or target companion enrichment signals when present

Source signals:

- `Setup`
- `Review`
- `Output`

### 4. Mapping Outcome Summary

Purpose:

- summarize what the mapping exercise produced before going into detailed decisions

Content:

- active mapping count
- accepted, needs-review, rejected counts
- resolution-type distribution
- matched, unresolved, excluded, target-managed, modeled-only counts
- notable drift or mismatch signals

Source signals:

- `Review`
- `Decisions`
- derived concept model

### 5. Key Decisions and Rationale

Purpose:

- make the decision outcome legible without showing the full decision editor

Content:

- grouped summary of important accepted decisions
- grouped summary of open decisions
- fixed-value, derived-value, N/A, and target-managed highlights
- short rationale lines pulled from mapping explanations, resolution payloads, or review notes when available

Selection rule:

- include only the most decision-significant items, not every row

Source signals:

- `Review`
- `Decisions`

### 6. Concept Model Result

Purpose:

- describe the business object and concept contract produced by the work

Content:

- business object name
- description
- business purpose
- target grain
- concept groups
- modeled attributes overview
- required attributes
- business rules

Source signals:

- derived concept model
- user corrections in `Modelling Overview`
- `Output > Transformation Design`

### 7. Source -> Concept -> Target Graph

Purpose:

- provide the most compact visual synthesis of how source evidence becomes target intent

Content:

- source nodes
- concept nodes
- target nodes
- labeled edges for direct, fixed, derived, target-managed, and excluded semantics when useful

Rules:

- graph is explanatory, not editable in V1
- graph should stay bounded and readable
- graph should reflect the report narrative, not replace it

Source signals:

- `Decisions`
- derived concept model

### 8. Output Contract Summary

Purpose:

- explain whether the workspace result is ready to become governed output

Content:

- transformation-spec state
- target-field coverage summary
- defaults and global rules presence
- excluded output summary
- preview and codegen readiness signals
- explicit blockers if the output path is not ready

Source signals:

- `Output`
- transformation status helpers
- preview and code generation gating signals

### 9. Risks, Gaps, and Open Questions

Purpose:

- make unresolved work visible at the end of the report

Content:

- required unresolved attributes
- modeled-but-unmapped attributes
- mapped-but-unmodeled targets
- rejected decisions
- open governance or readiness concerns

Source signals:

- drift summary
- decision status summary
- output gating summary

### 10. Recommended Next Steps

Purpose:

- convert the report into a practical handoff artifact

Content:

- what must be done next to close the result
- which surface the user should return to if action is needed
- whether the workspace is ready for preview, codegen, export, or approval

## Section-to-Workspace Mapping

| Report section | Main sources |
| --- | --- |
| Executive Summary | Setup, Decisions, Output, concept model |
| Starting Point and Scope | Setup, runtime context |
| Source and Target Landscape | Setup, Review, Output |
| Mapping Outcome Summary | Review, Decisions, concept model |
| Key Decisions and Rationale | Review, Decisions |
| Concept Model Result | Modelling Overview, Output |
| Source -> Concept -> Target Graph | Decisions, concept model |
| Output Contract Summary | Output |
| Risks, Gaps, and Open Questions | Decisions, drift summary, Output |
| Recommended Next Steps | synthesized from all sections |

## UI Implications for the Tab

The tab should be visually organized like a report:

- actions row at the top
- report sections rendered top-down below it
- concise metrics only where they help the report narrative
- expandable detail blocks where raw evidence is useful
- concept-editing controls kept bounded so they support the report rather than dominate it

## Export Direction

Later export should not invent a new document shape.

Instead:

- the tab should assemble a canonical Markdown report payload
- the UI should render that payload section-by-section
- export should reuse the same payload with only light presentation changes

That is the cleanest way to keep `Modelling Overview` and future document export aligned.