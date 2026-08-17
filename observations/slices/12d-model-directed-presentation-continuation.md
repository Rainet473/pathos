# Verified slice: model-directed presentation continuation

## Hypothesis

A natural standalone continuation request can be represented as a typed planner
action and safely executed by application code, while canonical wording stays on
the zero-latency matcher path and ordinary questions keep the answer-plan path.

## Observable path

```text
final transcript
  -> bounded matcher (canonical request) -> application resume
  -> otherwise silent planner
       -> answer plan -> answer flow
       -> continue action -> application validation -> narration flow
```

## Scope

- New boundary: a terminal provider-neutral continuation action in silent
  planning.
- Strengthened boundary: bounded standalone-command grammar.
- Explicitly excluded: navigation actions, completed-deck replay, semantic/web
  search changes, and general answer-and-continue redesign.

## Entry gate

- [x] The interruption cursor and verified playout behavior already pass.
- [x] The canonical matcher and Continue button already resume safely.
- [x] Runtime evidence shows natural “carry on/continue on with the
  presentation” wording was incorrectly turned into an answer plan.
- [x] The expectation handout exists before source changes.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Matcher grammar | offline parameterized tests | observed variants match; compound/negated phrases do not |
| Planning transaction | offline application tests | action is terminal, current, and exclusive with answer plan |
| Provider adapter | fake streamed tool call | action schema is exposed and accepted without search |
| Voice bridge | fake planner and speech handles | no answer is generated; resumed beat and following beat narrate |
| Regression | full offline/backend/frontend gates | earlier tests and production build pass |

## Exit evidence

- Red gate: the focused suite initially failed during collection because the
  typed presentation-action contract did not exist.
- Focused application/planner/bridge gate: `107 passed`.
- Full backend gate: `336 passed, 3 skipped`; the skips are the explicitly
  quota-gated LiveKit transport and inference tests.
- Frontend gate: `43 passed`.
- TypeScript and Vite production build: passed.
- Runtime/provider spend: none.
- The bridge regression proves that the model-proposed action creates no answer
  turn, restores the interrupted cursor, waits for verified beat playout, commits
  that beat once, and automatically selects the following beat.

## Live gate

Repeat after deterministic gates:

1. Interrupt narration.
2. Say “Okay, carry on with the presentation then.”
3. Confirm no acknowledgement answer is spoken.
4. Let the resumed beat finish and confirm narration proceeds to the next beat
   without asking to continue again.
