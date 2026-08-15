# Verified slice: one real presentation action

## Hypothesis

The selected LiveKit inference pipeline can be connected to the existing
application-owned presentation controller so that one real narrated beat and one
grounded interruption obey the same commitment and continuation rules as the fake
runtime.

## Observable path

```text
listener -> browser microphone -> LiveKit pipeline -> typed application intent
         -> presentation controller -> selected fixture evidence -> LiveKit speech
         -> browser audio plus presentation snapshot and domain events
```

## Scope

- New real boundary: LiveKit speech and intent lifecycle mapped into provider-neutral
  application commands and domain events.
- Still fake: none in the live voice path; the content deck remains a fixed local
  fixture and observation remains human-evaluated.
- Explicitly excluded: six-slide breadth, dynamic retrieval, model-directed slide
  navigation, automatic provider fallback, deployment, and in-flight reconnect.

## Entry gate

- [x] Relevant prior slice passes: attempt
  `a9f44bc7-0b78-48b2-a333-93ab1e92415b` completed with two successful
  interruptions and no accumulating latency.
- [x] Expectation handout exists at
  `expectations/real-presentation-action.md`.
- [x] First failing test is defined in
  `tests/application/test_live_presentation_session.py`.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Automated | Offline orchestration and adapter tests with recorded provider-neutral callbacks | Both continuation variants pass; interruption and stale callbacks never commit a beat |
| Observation | Two live runs using headphones: plain question and answer-and-continue | Prompt audible interruption, grounded concise answer, correct wait or same-beat resume |
| Instrumentation | Attempt ID, turn IDs, domain-event timestamps, and provider stage metrics | Every callback is attributable; no silent transition or accumulating response queue |

## Exit gate

- [ ] Observable path succeeds repeatedly.
- [ ] Failure path is visible and controlled.
- [x] Previous tests still pass: 138 Python tests passed with the opt-in paid
  LiveKit test skipped; 33 frontend tests and the production build passed.
- [ ] Artifacts and limitations are recorded.

## Automated evidence

- The application tests were first observed failing because the real presentation
  module did not exist; the adapter tests were first observed failing because the
  presentation transport contract did not exist.
- `conda run --no-capture-output -n synthio pytest -q`:
  138 passed, 1 paid live test skipped.
- `conda run --no-capture-output -n synthio npm test -- --run`:
  33 passed.
- `conda run --no-capture-output -n synthio npm run build`:
  TypeScript and Vite production build passed; Vite reported only the existing
  large-chunk advisory.

## Live observation pending

Run two fresh `/live` attempts with headphones. In the first, interrupt the opening
beat with “Why does engine braking feel stronger in a low gear?” and verify that the
answer finishes in `waiting`. Use the Continue button and verify the same beat is
selected again. In the second, interrupt with the same question followed by
“Continue after answering” and verify direct same-beat resumption. Retain attempt IDs,
screenshots, transcript, event log, timing cards, and a short recording.

## Fallback or rollback

Keep Slice 3's verified minimum conversation and Slice 2's deterministic presentation
available as separate routes. Provider selection remains explicit; no hidden fallback
changes runtime semantics.

## Next highest risk

Six-slide content breadth, deterministic question-scope routing, and temporary visual
context changes without coupling visible slides to the semantic presentation cursor.
