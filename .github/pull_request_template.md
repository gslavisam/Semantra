## Summary

Kratko opisi:
- sta se menja
- zasto je promena potrebna
- koji efekat ocekujes

## Change Type

Mark one or more:
- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Docs
- [ ] Tests
- [ ] Config or deployment
- [ ] Performance
- [ ] Prompt or LLM behavior

If this PR changes bounded prompts or LLM contracts, also use `.github/PULL_REQUEST_TEMPLATE/prompt-change.md` as the review checklist.

## Scope

- Affected areas:
- Key files or modules:
- Out of scope:

## Behavior Change

### Before

- 

### After

- 

## Validation

### Tests Run

- `pytest ...`
- `pytest ...`

### Manual Checks

- 

### Not Validated

- 

## Risks

- Primary regression risk:
- User-facing impact if wrong:
- Is failure obvious or silent:

## Compatibility Impact

Mark all that apply:
- [ ] No compatibility impact
- [ ] API response changed
- [ ] Schema or payload changed
- [ ] Config or env changed
- [ ] Migration or rollout note needed

Details:
- 

## Docs Updated

- [ ] No docs update needed
- [ ] README
- [ ] PROJECT_OVERVIEW
- [ ] Reference docs
- [ ] Operational or setup docs

## Rollback

- Revert commit or PR
- Revert config or schema changes if any
- Note any cleanup needed after rollback

## Reviewer Focus

Reviewers should verify:
- the change matches the stated scope
- validation is adequate for the touched behavior
- compatibility impact is explicit
- docs are updated when behavior or workflow changed