## Summary

Kratko opisi:
- koji prompt surface se menja
- koji problem se resava
- koji efekat ocekujes

## Surface Affected

- Surface:
- Static template:
- Dynamic builder:
- Runtime caller:

## Static Prompt Change

- Added:
- Removed:
- Reworded:
- Guardrails strengthened:
- Output-format instructions changed:

## Payload Change

- Added fields:
- Removed fields:
- Renamed fields:
- Payload label changed:
- Baseline or fallback behavior changed:

## Contract Change

Mark one:
- [ ] No contract change
- [ ] Contract changed

If changed:
- Added fields:
- Removed fields:
- Behavior or parser impact:

## Validation

### Tests Run

- `pytest ...`
- `pytest ...`

### What These Checks Prove

- prompt shape still matches the current caller
- runtime path still works for the edited surface
- output contract remains compatible

### Not Validated

- 

## Risks

- Primary regression risk:
- User-facing impact if wrong:
- Is failure obvious or silent:

## Docs Updated

- [ ] Updated `docs/reference/LLM_PROMPT_MATRIX.md`
- [ ] Updated `docs/reference/LLM_PROMPT_EVALUATION_CHECKLIST.md` if acceptance criteria changed
- [ ] Updated architecture docs if wording or behavior changed

## Rollback

- Revert static template change
- Revert builder or payload change
- Revert tests and docs if needed

## Reviewer Focus

Reviewers should verify:
- static prompt text and dynamic payload still agree
- any contract change is explicit and tested
- the prompt remains grounded in the provided payload
- fallback or baseline behavior has not become over-anchoring
