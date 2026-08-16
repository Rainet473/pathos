# Expectation handout: observable answer pathway

## User-visible outcome

While Pathos prepares and delivers a follow-up answer, the right inspector shows
a connected pathway—Understand, Search if needed, Prepare, Answer. The active
node glows, completed nodes remain visibly complete, optional search is visibly
skipped when unused, and future nodes stay muted.

## Inputs, outputs and boundaries

- Inputs: ordered presentation snapshots containing `planningStage` and the
  application-owned presentation phase.
- Outputs/events: a local, derived pathway trail and accessible ordered-list UI.
- External boundaries: frontend reducer, React inspector, responsive CSS.
- Preconditions: the backend already publishes `understanding`, `searching`, and
  `preparing`; answer playout already exposes the `answering` phase.
- Non-goals: exposing model chain-of-thought, adding provider events, displaying
  generated reasoning prose, changing planner policy, or claiming search occurred
  when it was skipped.

## Behavior map

```text
understanding update -> Understand active
searching update     -> Understand done -> Search active
preparing update     -> visited nodes done -> Prepare active
answering update     -> visited nodes done -> Answer active
waiting/completed    -> pathway clears

direct-context path:
Understand done -> Search skipped -> Prepare done -> Answer active
```

## Invariants

- The pathway is derived only from sanitized application stages.
- No hidden reasoning text or chain-of-thought is requested or rendered.
- Search is marked complete only if a `searching` update was actually observed.
- A new `understanding` stage resets history from the previous follow-up.
- A new attempt and non-answer terminal phase clear the pathway.
- Existing phase heading, description, controls, and transport behavior remain.
- The pathway remains readable at desktop and narrow widths.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Direct answer | Understand lights, Search becomes skipped, Prepare then Answer light | Reducer/component test |
| Search-backed answer | nodes light in order and Search remains completed | Reducer/component test |
| New follow-up | prior trail resets at Understand | Reducer test |
| Planning failure | pathway stops and existing failure guidance remains visible | Reducer/UI test |
| Narrow viewport | connected path wraps or scrolls without page overflow | Browser observation |

## Edge and race cases

- Empty/malformed: payload validation still rejects unknown stages.
- Duplicate/repeated: duplicate stage updates do not duplicate nodes.
- Late/out-of-order: older session versions remain rejected by the reducer.
- Cancellation: waiting/failure clears the active pathway and shows existing copy.
- Partial failure: failure guidance remains more prominent than decorative status.
- Recovery: a fresh `understanding` update starts a clean trail.
- Capability mismatch: no search stage means Search is shown as skipped, not done.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Comprehension | current activity is obvious at a glance | heading changes with no visible route | screenshot |
| Truthfulness | optional search differentiates completed and skipped | every answer falsely appears searched | stage sequence + screenshot |
| Privacy | only stage names and short operational copy appear | hidden reasoning prose is exposed | DOM/screenshot |
| Responsive layout | nodes remain connected and legible | inspector overflows or obscures controls | desktop/mobile screenshots |

## Open assumptions

- Four stable product-language nodes communicate progress better than provider-
  specific tool-call detail.
- Keeping a short frontend trail is sufficient; no public schema change is needed.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Frontend tests and production build pass.
- [x] Desktop and narrow observation cases are recorded.
- [x] Deferred visualization refinements are explicit.
