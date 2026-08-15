# Expectation handout: <behavior>

## User-visible outcome

<What a user or downstream system can observe.>

## Inputs, outputs and boundaries

- Inputs:
- Outputs/events:
- External boundaries:
- Preconditions:
- Non-goals:

## Behavior map

```text
<small state, sequence, or data-flow map>
```

## Invariants

- <fact that must always remain true>

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Happy path |  | Automated |
| Boundary |  | Automated |
| Failure |  | Automated |
| Real-world sanity case |  | Human rubric |

## Edge and race cases

- Empty/malformed:
- Duplicate/repeated:
- Late/out-of-order:
- Cancellation:
- Partial failure:
- Recovery:
- Capability mismatch:

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
|  |  |  |  |

## Open assumptions

- <assumption that is not yet an established requirement>

## Exit criteria

- [ ] Tests were written before implementation.
- [ ] New tests were observed failing for the intended reason.
- [ ] Deterministic suite passes offline.
- [ ] Observation cases were run and evidence was recorded.
- [ ] Deferred risks are explicit.
