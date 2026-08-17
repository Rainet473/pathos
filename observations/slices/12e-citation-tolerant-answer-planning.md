# Verified slice: citation-tolerant answer planning

## Hypothesis

The application can preserve a model's grounded answer decision whenever a
valid turn, evidence item, or slide citation survives, deriving bounded packaged
evidence from a verified slide when necessary. Extended knowledge is used only
when no support can be recovered.

## New boundary

One deterministic normalization step between the model's terminal answer-plan
proposal and the existing strict validation boundary.

## Entry gate

- [x] Current search results are transaction-scoped and application validated.
- [x] Active follow-up turns are excluded from eligible supporting history.
- [x] Runtime evidence identifies the same `ineligible_turn` metadata error in
  both ABS and engine-braking questions.
- [x] Both rejected proposals retained valid current deck evidence and originally
  selected `grounded + presentation`.
- [x] The expectation handout exists before source changes.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Planner transaction | offline application tests | active/unknown IDs are filtered when valid support remains |
| Slide derivation | offline application tests | invalid slide is recovered from evidence ID and yields packaged summary support |
| Truthful grounding | negative application tests | only no remaining turn/evidence/slide support rejects |
| Provider trace | fake streamed tool call | accepted result logs all filtering without exposing it to speech |
| Voice bridge | fake accepted normalized plan | grounded mode reaches answer generation; recovery is not invoked |
| Regression | full offline backend/frontend gates | all earlier behavior remains green |

## Exit evidence

- Red gate: the focused planner tests initially failed four new cases against
  strict `ineligible_turn` / `unknown_slide` rejection.
- Proposal-boundary red gate: slide-only support, a mismatched focus ID, and a
  combined plan with one surviving support kind initially failed before
  application normalization.
- Focused green gate: 65 citation-contract, planning, provider-trace, and answer
  directive checks passed.
- Full backend gate: `343 passed, 3 skipped`; skipped tests are the three
  credential-gated LiveKit live suites.
- Frontend gate: 9 Vitest files / 43 tests passed.
- Production build gate: TypeScript no-emit check and Vite build passed.
- The answer-directive integration test confirms that `braking-abs` slide-only
  support becomes `motorcycle-controls.braking-abs.summary.0`, reaches the
  generation instructions, and stays `grounded + presentation`.
- The replay test confirms raw unknown/current-turn citation errors remain in
  the function call and private filter report while the normalized application
  decision remains valid in the next reasoning snapshot.

## Live gate

Ask the deck-supported ABS and engine-braking questions again. Both should show
`grounded · presentation`; `.runtime/livekit-silent-planning.jsonl` should record
the filtered active turn if the model repeats that metadata error.
