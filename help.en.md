# Help: Workspace, Benchmarks, and Admin / Debug tabs

This document explains the purpose of the buttons and helper controls in the `Workspace`, `Benchmarks`, and `Admin / Debug` tabs of the Semantra Streamlit app.

Notes:

- Some actions require an admin token.
- If the backend does not have `SEMANTRA_ADMIN_API_TOKEN` configured, the app may currently allow admin/debug and benchmark actions even without a token.
- Most actions display the result immediately in the same tab, below the control that triggered the call.

## Before you start

Recommended order:

1. In the `Workspace` tab, upload the source and target files.
2. Run `Generate mapping`.
3. Only then move to `Benchmarks` or `Admin / Debug`, because some functions are most useful once an active mapping result already exists.

## Global sidebar controls

These controls are not tied to a single tab, but they affect the whole application flow.

### `API Base URL`

The URL field for the backend API.

Use it when:

- the backend is not running on the default URL
- you want to point the UI to another local or remote backend

In most cases this stays on the local default value if the backend runs on the same machine.

### `Admin Token`

The field used to enter the admin token that the backend uses for protected observability, evaluation, and knowledge actions.

Use it when:

- the backend requires a token for benchmark, correction, mapping set, or knowledge actions
- you want to use admin/debug functions without `403` errors

### `Reset flow`

What it does:

- clears the active UI flow state from session state
- resets upload, mapping, preview, code generation, and related working data

When to use it:

- when you want to start over with a new source/target pair
- when the UI state feels inconsistent after several experiments

What to expect after clicking:

- the app returns to a clean initial state
- you need to upload files again if you want to continue the review flow

## Workspace tab

The purpose of this tab is to drive the full main workflow: upload, profiling, mapping generation, manual review, transformations, preview, code generation, decision import/export, mapping sets, and corrections.

For readability, `Workspace` is organized into 4 internal sub-tabs:

- `Setup` for upload, table selection, profiling, and starting the initial auto-mapping run
- `Review` for the trust layer, candidate review, and manual review per column
- `Decisions` for manual overrides, import/export, mapping sets, and corrections
- `Output` for preview and Pandas code generation

## 1. Upload

### `Source file`

The file uploader for the source dataset.

Supported row-based formats include CSV, JSON, XML, and XLSX, as well as SQL schema snapshots when you are using a schema-only flow.

### `Target file`

The file uploader for the target dataset.

It works the same way as `Source file`, but for the destination model or schema you want to map into.

## 2. Select Tables

This section matters only when the uploaded SQL file contains multiple tables.

### `Source table`

Dropdown for choosing the source table from the SQL snapshot.

It appears only when the backend detects multiple tables in the source SQL file.

### `Target table`

Dropdown for choosing the target table from the SQL snapshot.

It appears only when the backend detects multiple tables in the target SQL file.

### `Upload and profile`

What it does:

- sends the source and target files to the backend
- includes the selected source and target tables when needed
- builds schema profiles for both sides
- stores dataset identifiers and preview data in the UI state

When to use it:

- immediately after selecting both the source and target file
- every time you change a file or selected table and want a fresh profile

Prerequisites:

- both files must be selected

What to expect after clicking:

- summary sections for `Source` and `Target` appear
- the app becomes ready for `Generate mapping`

## 3. Review Mapping

### `Generate mapping`

What it does:

- calls the backend auto-mapping flow
- generates ranked candidates and an initial selected target for each source column
- initializes the manual review state in the UI

When to use it:

- after a successful upload and profiling step

What to expect after clicking:

- the trust layer, review tables, manual review, corrections, and preview/code generation actions become available

## Trust Layer and transformations

For each source field you get a block with a target suggestion, a confidence display, and an expander section called `Details and Transformation`.

### `Apply this transformation to data`

Checkbox that activates the suggested transformation code if the system already generated one for that source-target pair.

Use it when:

- you want preview and later code generation to actually use the displayed suggested transformation

### `Generate with LLM`

What it does:

- calls the runtime LLM to suggest a pandas transformation for the currently selected source-target pair

When to use it:

- when you know the mapping is correct but it needs a transformation
- when you want a faster first draft of the transformation code

Prerequisites:

- an active target must exist for that source
- the LLM runtime must be configured and available

What to expect after clicking:

- the generated transformation code is inserted into the manual code field
- reasoning and warning messages may appear along with the suggestion

### `Reusable template for <source>`

Dropdown for selecting a ready-made transformation template.

Use it when:

- you want a standard text or formatting transformation without using the LLM

### `Apply template`

What it does:

- takes the selected reusable template and materializes it for the concrete source-target pair

When to use it:

- when you know you need a standard transformation and do not want to generate new code

What to expect after clicking:

- the template code is inserted into the manual/custom transformation field

### `Define pandas/Python transformation for <source> (optional)`

Text area for manually writing custom transformation code.

Use it when:

- you want full control over the transformation
- the LLM suggestion is not good enough
- the template is not sufficient

### `Apply generated/custom transformation`

Checkbox that activates the manually entered or LLM/template-generated code.

Use it when:

- you want preview and code generation to use this exact custom/generated code

Important:

- entering code alone is not enough; the checkbox decides whether the transformation will actually be applied

## Review tables and filters

### `Filter by status`

Dropdown for filtering the `Selected Mapping` view by status.

### `Filter by confidence label`

Dropdown for filtering by confidence label.

### `Filter by source`

Dropdown for focusing on a single source column.

These controls do not change backend state. They are only for inspection and focus during review.

## Manual Review section

For each source row, you can manually change the target and status.

### `Target for <source>`

Dropdown for manually selecting the target candidate for a given source.

Use it when:

- you want to replace the initially selected target with another proposal from the candidate list

### `Status for <source>`

Dropdown with the statuses `accepted`, `needs_review`, and `rejected`.

Use it when:

- you want to confirm the mapping
- you want to leave the mapping for later review
- you want to reject the mapping

## Add Manual Mapping section

This section is used to add or override a source-target pair that the auto-mapper did not propose or did not handle well.

### `Manual source column`

Dropdown for choosing the source column you want to add manually or override.

### `Manual target column`

Dropdown for manually selecting the target column.

### `Manual status`

Dropdown for the status of the manually added decision.

### `Add mapping`

What it does:

- writes the manual source-target pair into the active review state

When to use it:

- when the auto-mapper did not propose the needed connection
- when you want to extend the mapping with business knowledge

What to expect after clicking:

- the manual pair appears in the `Manual additions and overrides` table

### `Remove manual mapping`

Dropdown for choosing a manually added or overridden mapping that you want to remove.

### `Remove`

What it does:

- removes the selected manual mapping from the active review state

When to use it:

- when you added the wrong manual pair
- when you want to fall back to the system suggestion for that source

## Active Decisions

This table has no buttons, but it is important because it shows the currently active mapping decisions that will be used in preview, code generation, export, and save operations.

If you do not see what you expect here, first fix the `Manual Review` or `Add Manual Mapping` section.

## Export / Import Decisions

### `Download mapping JSON`

What it does:

- exports the currently active mapping decisions as a JSON file

When to use it:

- for review-state backups
- for moving mapping decisions across sessions
- for manual editing outside the UI

### `Import mapping JSON`

File uploader for a JSON file with a `mapping_decisions` payload.

### `Apply imported mapping`

What it does:

- loads mapping decisions from the uploaded JSON into the current review state

When to use it:

- when you want to restore a previously exported mapping
- when you receive mapping decisions from another workflow

What to expect after clicking:

- the editor state is updated to match the imported payload

## Mapping Set Versioning

This section lets you save the current review state as a versioned mapping set on the backend and compare versions of the same mapping set through a lightweight governance flow.

### `Mapping set name`

The name of the mapping set you are saving.

### `Mapping set created by`

Optional identifier for the person or team saving the mapping set.

### `Mapping set owner`

Optional owner for the mapping set at the whole-version level.

Use it when:

- you want to mark the team or person who formally owns that mapping set
- you want clearer governance context during later review

### `Mapping set assignee`

Optional current assignee or reviewer for that version.

Use it when:

- you want to track who is currently expected to review or finish the version

### `Version note`

Optional note attached to that mapping set version.

### `Review note`

Optional governance/review note for that version.

Use it when:

- you want to record why the version is moving into review, what is still pending, or what condition must be met next

### `Save mapping set version`

What it does:

- saves the active mapping decisions as a new mapping set version
- also saves `owner`, `assignee`, `version note`, and `review note` metadata with that version

When to use it:

- when you want a review snapshot that can be reloaded later
- when you are creating versioned iterations of mapping work

What to expect after clicking:

- a success message with the name and version
- the mapping set list may be refreshed immediately

### `Load saved mapping sets`

What it does:

- loads all previously saved mapping set versions from the backend

When to use it:

- when you want to inspect and use older saved versions

### `Select saved mapping set`

Dropdown for selecting a concrete saved mapping set version.

### `Apply saved mapping set`

What it does:

- loads the selected mapping set into the current review state
- writes an `apply` audit event on the backend

When to use it:

- when you want to continue earlier review work or test an older decision set

### `Saved mapping set status`

Dropdown for choosing the new status of the selected mapping set version.

### `Update saved mapping set status`

What it does:

- changes the status of the selected mapping set version on the backend
- can also refresh `owner`, `assignee`, and `review note`

When to use it:

- when a mapping set moves from draft into review or approved status

### `Load selected mapping set audit`

What it does:

- loads the audit history for the selected mapping set

When to use it:

- when you want to inspect the lifecycle changes of that version

### `Compare against version`

Dropdown for selecting an older version of the same mapping set to compare against.

It appears when at least two versions exist for the same `mapping set name`.

### `Load mapping set diff`

What it does:

- loads the diff between the currently selected version and the chosen older version
- shows an `Added`, `Removed`, and `Changed` summary
- shows a table of changes per source column

What counts as a change:

- target column changed
- decision status changed
- transformation code changed

When to use it:

- when you want to see exactly what changed between two review iterations
- when you want to check whether a newer version only adds fields or also changes already reviewed decisions

## Save Corrections section

This section is used to save the differences between the system suggestion and your final review decision, and to work with reusable rule candidates.

### `Correction note`

Optional note saved with each persisted correction.

### `Load reusable rule candidates`

What it does:

- loads reusable correction rule candidates based on previous correction history

When to use it:

- when you want to see which user corrections repeat often enough to become rules

### `Load promoted reusable rules`

What it does:

- loads already promoted reusable rules

When to use it:

- when you want to inspect which rules are already actively influencing ranking

### `Save reviewed corrections`

What it does:

- persists the current review differences as corrections in the observability layer

When to use it:

- when you have finished manual review and want the system to remember those decisions

What to expect after clicking:

- a success message with the number of saved corrections
- the `Last saved corrections` section gets new data

### `Promote reusable rule candidate`

Dropdown for selecting the candidate you want to turn into a reusable rule.

### `Promote selected reusable rule`

What it does:

- promotes the selected correction candidate into a persistent reusable rule

When to use it:

- when you know a correction pattern repeats and should influence future ranking more strongly

## Final actions in the Workspace tab

### `Generate preview`

What it does:

- executes a preview of the active mapping decisions on source data
- includes transformation preview when transformations are activated

When to use it:

- when you want to see what the result would look like before code generation or persistence

Prerequisites:

- at least one active mapping decision must exist

What to expect after clicking:

- the `Preview` section appears
- unresolved targets and transformation validation details may appear

### `Generate Pandas code`

What it does:

- generates Pandas code based on the active mapping decisions and activated transformations

When to use it:

- when you want a starter artifact for implementing the mapping

Prerequisites:

- at least one active mapping decision must exist

What to expect after clicking:

- the `Generated Pandas Code` section appears
- warnings may appear if there are issues or fallback situations

## Benchmarks tab

The purpose of this tab is to save a realistic mapping scenario as a benchmark, run it again later, and measure the impact of correction learning.

### Helper fields and controls

#### `Benchmark dataset name`

This is the name under which the current mapping scenario will be saved as a benchmark dataset.

Use it when:

- you want to distinguish multiple benchmark scenarios
- you want versioning of benchmark sets by business domain or test iteration

Examples:

- `customer-master-clean-v1`
- `erp-noisy-aliases-v1`
- `pilot-scenario-2`

#### The JSON view below the title `Save Current Mapping As Benchmark`

This is not a button, but it is an important indicator. It shows exactly which benchmark case will be saved if you click `Save current mapping as benchmark`.

If you do not see anything useful there yet, do not save the benchmark. Go back to the `Workspace` tab and make sure you have active mapping decisions.

#### `Saved dataset`

Dropdown list of previously saved benchmark datasets.

Use it to choose which benchmark you want to run or which one you want to use for measuring correction impact.

#### `Run selected benchmark with configured LLM`

Checkbox that decides whether the benchmark should run heuristically only or with the active runtime LLM as well.

Use it when:

- you want to compare behavior without the LLM and with the LLM
- you want to test whether the LLM truly improves the result or only introduces variation

Do not enable this checkbox if:

- the LLM runtime is not configured
- you want a purely deterministic comparison across iterations

### Buttons in the Benchmarks tab

#### `Save current mapping as benchmark`

What it does:

- takes the current mapping scenario from the active review state
- saves it as a benchmark dataset in the backend persistence layer

When to use it:

- when you create a scenario that you want to measure again later
- when you want to save a real-life pilot example as a reference test

Prerequisites:

- at least one active mapping decision must exist
- `Benchmark dataset name` must not be empty

What to expect after clicking:

- a success message with `dataset_id`, name, and version
- the benchmark later appears in the list of saved datasets

Best practice:

- save small, representative benchmark scenarios instead of a single huge benchmark

#### `Load saved benchmark datasets`

What it does:

- loads all previously saved benchmark datasets from the backend

When to use it:

- when you enter the `Benchmarks` tab for the first time
- when you have just saved a new benchmark and want to refresh the list

What to expect after clicking:

- a table with benchmark datasets appears below
- the `Saved dataset` dropdown gets new options

#### `Load benchmark runs`

What it does:

- loads the history of earlier benchmark executions

When to use it:

- when you want to inspect previous results and compare iterations
- when you want to check whether a refactor or overlay changed quality

What to expect after clicking:

- the `Benchmark Run History` table appears below

#### `Run selected benchmark`

What it does:

- runs the selected benchmark dataset through the evaluation backend
- uses heuristic only or heuristic + LLM, depending on the checkbox

When to use it:

- when you want to see the current system quality on a saved benchmark
- when you are checking whether a new system change improves or degrades mapping quality

What to expect after clicking:

- `Last Benchmark Result` appears below
- the result is shown as a JSON payload with metrics

How to interpret it:

- focus on accuracy, top-1 accuracy, and the total number of correct matches

#### `Measure correction impact`

What it does:

- measures the difference between the baseline result and the correction-aware result
- shows whether correction history and reusable rules are actually improving mapping quality

When to use it:

- when you already have saved corrections and want to see their effect
- when you are evaluating whether the learning loop is worth developing further

What to expect after clicking:

- the `Correction Impact` table appears
- it shows baseline accuracy, correction-aware accuracy, and the difference between them

How to interpret it:

- a positive `accuracy_delta` means correction history helps
- a small or zero delta means there is still not enough high-quality feedback history or the rules are not targeted well enough

## Admin / Debug tab

The purpose of this tab is to load backend runtime state, the knowledge layer, audit trails, glossary state, and supporting diagnostic data.

If you see a message saying that an admin token is required, first enter it in the sidebar field `Admin Token`.

### Top button group

#### `Load runtime config`

What it does:

- loads the backend runtime configuration through the observability endpoint

When to use it:

- when you want to check which LLM provider is active
- when you want to check whether the admin token is configured
- when you want to inspect gating thresholds and other active runtime settings

What to expect after clicking:

- the `Runtime Config` section appears below in JSON format

#### `Load decision logs`

What it does:

- loads decision log records that the backend stores during mapping decisions

When to use it:

- when you want to inspect how the system made decisions
- when you are investigating an unexpected mapping

What to expect after clicking:

- the `Decision Logs` table appears

#### `Load saved corrections`

What it does:

- loads all saved user corrections from the system

When to use it:

- when you want to check whether correction history was actually stored
- when you want to assess the quality of the learning data

What to expect after clicking:

- the `Saved Corrections` table appears

#### `Load benchmark runs`

What it does:

- loads the history of evaluation runs from the backend

When to use it:

- when you want to view benchmark history from a debug perspective without leaving the `Benchmarks` tab

What to expect after clicking:

- the `Evaluation Runs` table appears

### Knowledge Overlays section

This section is used for inspecting and managing knowledge overlay versions.

#### `Load knowledge overlays`

What it does:

- loads the list of all saved overlay versions

When to use it:

- when you want to see which overlay versions exist
- when you plan to activate, deactivate, or inspect details

What to expect after clicking:

- a table of overlay versions appears below
- the `Overlay version` dropdown gets options

#### `Reload knowledge`

What it does:

- forces the backend to reload the knowledge runtime layer

When to use it:

- after activating or importing knowledge/glossary data
- when you suspect the backend runtime was not refreshed

What to expect after clicking:

- a summary of `Knowledge mode`, the active overlay, and the number of active entities appears or refreshes

#### `Load active knowledge status`

What it does:

- effectively loads the current active runtime state of the knowledge layer

When to use it:

- when you only care about runtime status, not the broader reload workflow with other actions

Note:

- it currently uses the same backend call as `Reload knowledge`, so the effect is similar

#### `Load knowledge audit log`

What it does:

- loads the audit log for knowledge lifecycle actions

When to use it:

- when you want to see who performed create, activate, deactivate, archive, or import operations, and when

What to expect after clicking:

- the `Knowledge Audit Log` table appears

### Controls for uploading a knowledge overlay file

#### `Knowledge overlay CSV`

File uploader for a CSV containing overlay entries.

Use it when you want to import:

- abbreviations
- synonyms
- field aliases
- concept aliases

#### `Overlay version name`

The name of the new overlay version.

Recommendation:

- use a name that clearly describes the domain and version, for example `sales-domain-overlay-v1`

#### `Created by`

Optional field for recording who created the overlay.

This is useful for auditability and team collaboration.

#### `Validate knowledge CSV`

What it does:

- checks the CSV without saving it as a new overlay version

When to use it:

- always before `Save overlay version`, especially for larger CSV files

What to expect after clicking:

- a validation summary appears
- a table of preview rows appears with status, normalization, and possible issues

How to interpret it:

- `valid` means the row is ready to save
- `invalid` means there is an error that must be fixed in the CSV
- conflicts and duplicates should be reviewed before saving

#### `Save overlay version`

What it does:

- saves the uploaded knowledge CSV as a new overlay version

When to use it:

- when validation passed or when you intentionally want to save the content together with its validation result

What to expect after clicking:

- a success message with the version name and number of saved entries
- the overlay version list is refreshed automatically
- the validation result remains available for inspection

### Canonical Glossary section

This section is used to import and export the canonical glossary CSV file.

#### `Canonical glossary CSV`

File uploader for canonical glossary import.

Use it when you want to load a new glossary version from CSV.

#### `Load canonical glossary export`

What it does:

- loads the current glossary CSV from the backend into UI memory

When to use it:

- when you want to download the current glossary for review, backup, or editing

What to expect after clicking:

- the `Download canonical glossary CSV` button appears

#### `Import canonical glossary`

What it does:

- imports the uploaded canonical glossary CSV into the backend
- then refreshes the knowledge runtime

When to use it:

- when you want to replace or refresh the canonical glossary

What to expect after clicking:

- a success message appears
- a summary with the number of imported rows and canonical concepts appears
- the knowledge runtime status is refreshed

Important:

- this changes the file-backed canonical glossary, so use it carefully and preferably with a controlled CSV version

#### `Download canonical glossary CSV`

What it does:

- downloads the glossary that was previously loaded by clicking `Load canonical glossary export`

When to use it:

- for local backup
- for manual glossary edits before a new import

### Overlay versions and lifecycle actions

These controls become useful once the overlay version list has already been loaded.

#### `Overlay version`

Dropdown for choosing the concrete overlay version you want to act on next.

#### `Load details`

What it does:

- loads details of the selected overlay version, including its entries

When to use it:

- when you want to inspect the exact contents of a specific overlay version

What to expect after clicking:

- an `Overlay detail` summary appears
- a table with entries from that version appears

#### `Activate selected overlay`

What it does:

- activates the selected overlay version as the runtime overlay

When to use it:

- when you want the mapping engine and trust layer to use that exact overlay version

What to expect after clicking:

- the runtime status shows the new active overlay
- the overlay version list is refreshed
- details of the selected version are reloaded

#### `Deactivate selected overlay`

What it does:

- deactivates the selected overlay version

When to use it:

- when you want to move back from an active overlay variant to a validated but inactive state

What to expect after clicking:

- runtime status is refreshed
- the overlay is no longer active in the knowledge runtime

#### `Archive selected overlay`

What it does:

- archives the selected overlay version

When to use it:

- when you no longer want to use an overlay operationally but still want it to remain in history

What to expect after clicking:

- the version status moves into an archived state
- the list and details are refreshed

Note:

- archiving is not the same as deleting. It is a lifecycle status change.

#### `Rollback active overlay`

What it does:

- moves the runtime knowledge layer back to the previously active overlay version
- if there is no previous one, it may return the system to base-only mode

When to use it:

- when a newly activated overlay version makes mapping quality worse
- when you want a fast rollback to an earlier stable state

What to expect after clicking:

- runtime status changes
- the overlay version list is refreshed
- details of the active version are reloaded

### Diagnostic sections below the buttons

These sections are not buttons, but they are important for interpreting results:

#### `Knowledge mode ...`

Shows:

- whether the backend is running in `base_only` or `overlay_active` mode
- which overlay is currently active
- the number of active entries and the knowledge concept count

#### `Validation summary`

Shows:

- the total number of rows from the uploaded CSV
- how many are valid, invalid, duplicates, and conflicts

#### `Canonical Coverage`

This appears only if a `mapping_response` from the `Workspace` tab already exists.

Use it to inspect:

- source-side coverage
- target-side coverage
- project-level canonical coverage for the active mapping context

#### `Knowledge and Canonical Match Insights`

Helps you inspect:

- the knowledge signal
- the canonical signal
- confidence
- explanation details for each source-target pair

## Recommended practical flows

### Flow 1: Benchmark quality check

1. In the `Workspace` tab, upload source and target.
2. Click `Generate mapping`.
3. Go to `Benchmarks`.
4. Enter a name in `Benchmark dataset name`.
5. Click `Save current mapping as benchmark`.
6. Click `Load saved benchmark datasets`.
7. Select a dataset from `Saved dataset`.
8. Click `Run selected benchmark`.
9. If needed, click `Measure correction impact`.

### Flow 2: Import and activate a knowledge overlay

1. Go to `Admin / Debug`.
2. Upload a file using `Knowledge overlay CSV`.
3. Click `Validate knowledge CSV`.
4. Review `Validation summary` and the preview rows.
5. Click `Save overlay version`.
6. Click `Load knowledge overlays`.
7. Select a version in `Overlay version`.
8. Click `Activate selected overlay`.
9. Click `Reload knowledge` or inspect runtime status.

### Flow 3: Export and import the canonical glossary

1. Click `Load canonical glossary export`.
2. Click `Download canonical glossary CSV` to save the current state.
3. Prepare the new CSV version.
4. Upload it using `Canonical glossary CSV`.
5. Click `Import canonical glossary`.
6. Check the import summary and the knowledge runtime status.

## Quick tips

- Before doing benchmark work, always check that the expected overlay is active.
- Before importing the canonical glossary, create an export as a backup.
- Treat `Validate knowledge CSV` as a required step, not an optional one.
- `Measure correction impact` only makes sense once the system already has saved corrections.
- If results look strange, start with `Load runtime config`, `Load knowledge overlays`, and `Load active knowledge status` before doing deeper debugging.
