# Mapping Analysis Overview Spec

## Goal

Introduce a user-facing mapping analysis overview in the Semantra Review flow. The feature summarizes the current mapping state for a technical implementor or data engineer and highlights mapping quality, review queue, canonical findings, transformation hotspots, and next engineering actions.

Audio narration is a secondary layer built on top of the generated overview. It does not read the raw mapping payload directly.

## Scope

Included in the first slice:

- Backend summary service for generating a structured overview from `AutoMappingResponse`
- `POST /mapping/analysis/summary`
- Streamlit Analysis panel inside the existing Review tab
- Deterministic fallback when no LLM provider is available
- Prompt contract for optional LLM-backed summary generation

Included in the second slice:

- `POST /mapping/analysis/narration`
- `POST /mapping/analysis/audio`
- LM Studio Orpheus WAV generation in backend Python
- Streamlit audio player and download action inside the Analysis panel

Excluded from the first slice:

- Changes to mapping ranking or assignment logic
- Automatic audio generation after each mapping run
- Persisting overview results in storage
- Media management workflow for generated audio

## Architecture

The feature belongs to the Review layer, not the mapping engine.

Correct pipeline:

`mapping_response -> summary overview -> spoken script -> audio`

Key rule:

- `mapping_service.py` remains responsible for scoring and assignment only.
- Overview generation is read-only and happens after mapping is already available.

## Backend Placement

- `backend/app/services/mapping_analysis_service.py`
- `backend/app/api/routes/mapping.py`
- `backend/app/models/mapping.py`

## UI Placement

- `streamlit_ui/api.py`
- `streamlit_ui/workspace_review_views.py`
- `streamlit_ui/workspace_views.py`
- `streamlit_app.py`

## API Contract

### Endpoint

`POST /mapping/analysis/summary`

### Request

- `mapping_response`: existing `AutoMappingResponse`
- `workspace`:
- `mapping_mode`: `standard` or `canonical`
- `source_dataset_name`
- `target_dataset_name`
- optional `source_system`
- optional `target_system`
- optional `business_domain`
- optional `integration_name`
- `options`:
- `audience`: currently `technical_implementor`
- `include_narration_seed`: boolean

### Response

Stable top-level fields:

- `title`
- `audience`
- `mapping_mode`
- `overall_mapping_health`
- `confidence_distribution`
- `strongest_matches`
- `needs_review_items`
- `unmatched_sources`
- `canonical_coverage_summary`
- `transformation_hotspots`
- `implementation_risks`
- `recommended_next_actions`
- `narration_script_seed`
- `generation_metadata`

## Fallback Rules

If the configured LLM is unavailable or returns invalid JSON, the service must still return the same response shape.

Fallback output is derived only from:

- mapping status counts
- confidence buckets
- unmatched rows
- low-confidence or conflicting rows
- canonical coverage metrics
- transformation presence
- explanation and signal evidence already present in the payload

The fallback path must not invent missing business context.

## Summary Prompt Rules

System role:

`You are a senior data integration analyst preparing a technical mapping handoff for a data engineer. You must summarize only the evidence present in the provided payload. Do not invent business rules, source semantics, target semantics, or transformations that are not supported by the payload.`

Task guidance:

- produce one technical mapping overview
- prioritize ambiguity, risk, canonical grounding, and implementation effort
- do not restate every row

Hard constraints:

- JSON only
- no markdown
- no prose outside JSON
- use only provided payload evidence
- return empty structures instead of invented content

## Audio Prompt Rules

Audio is not implemented in this slice, but the prompt contract is fixed.

System role:

`You are a technical presenter explaining mapping analysis to a data engineer. Your script must sound natural when read aloud and must stay faithful to the supplied overview.`

Hard constraints:

- exactly one final spoken script
- no markdown
- no headings
- no bullets
- no speaker labels
- no stage directions
- no multiple alternatives
- wrap output only inside `<final_script>` and `</final_script>`

## UI Behavior

The Analysis panel lives in the Review tab and appears when `mapping_response` exists.

Panel states:

- empty: no overview generated yet
- loading: overview request in progress
- ready: summary sections visible
- error: inline retry state

Displayed sections:

- top actions row
- accepted / review / unmatched / risk metrics
- strongest matches
- needs review
- canonical coverage and findings
- transformation hotspots
- implementation risks
- recommended next actions
- narration preview

Current first-slice behavior:

- Generate analysis is functional

Current audio behavior:

- Generate audio first requests spoken narration from the current summary
- Then it requests WAV audio from the LM Studio Orpheus backend route
- The Review panel renders inline playback and download inside the same Analysis expander

## Session-State Rules

- Cache summary in Streamlit session state
- Invalidate cached summary whenever a new mapping response is generated
- Invalidate cached summary when upload context changes enough to invalidate mapping output
- Do not regenerate summary implicitly when audio is requested

## Validation Status

The initial implementation slice has focused automated coverage for:

- backend deterministic summary route
- backend LLM-backed merge path
- Streamlit API helper payload shaping
- workspace view orchestration compatibility

## Next Slice

Recommended next step:

1. Add spoken-script generation and TTS delivery on top of `narration_script_seed`
2. Decide whether audio is returned as base64 or file/blob path
3. Add UI playback and download behavior only after the summary contract is stable