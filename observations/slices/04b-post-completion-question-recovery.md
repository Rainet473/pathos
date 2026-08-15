# Verified slice: post-completion question recovery

## Hypothesis

Separating narration completion from conversational availability lets the
application answer a boundary question without reopening the deck, while tuned
endpointing and transcript grouping preserve one coherent user turn.

## Observable path

```text
final narration playout -> completed application state
  -> spoken question -> application answer directive
  -> model text -> TTS playout -> completed application state

STT fragments -> endpoint window -> normalized transcript group -> one UI row
```

## Scope

- New behavior: questions are legal after narration completion and return to the
  completed state after verified answer playout.
- Boundary tuning: short STT pauses remain one provider user turn.
- Presentation only: normalized transcript fragments may share one visible ID.
- Explicitly excluded: paraphrase-classifier improvements and multi-slide breadth.

## Entry evidence: failed live attempt, 16 August 2026

- Attempt: `e67f2864-9e36-464e-a0ee-b283bccd212f`.
- The final narration committed the one-beat deck before the user-turn callback
  reached application policy.
- `prepare_question` called `begin_answer` while phase was `completed`; the
  controller rejected the transition because it only allowed `interrupted` and
  `waiting`.
- LiveKit logged the unhandled `TransitionRejected`, so the provider never
  received answer instructions and no voice response could be generated.
- The transcript channel delivered the speech, but three closely spaced final STT
  fragments appeared as separate user rows.
- Diagnostic timing places the first question speech roughly 286 ms after the
  narration speaking lifecycle ended. The observed issue is therefore a boundary
  question race, even though it was perceived as an interruption.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Domain transition | Complete deck, answer, finish answer | Returns to completed; no beat replay or duplicate completion event |
| Application action | Ask after one-beat completion | Answer directive exists; no resume narration exists |
| Adapter bridge | Complete narration, invoke user-turn hook | Instructions return and answer playout settles without error |
| Endpoint configuration | Factory constructor recording | 1.2 s minimum and 3.0 s maximum are passed with STT turn detection |
| Transcript grouping | Timed fake transcript events | Brief fragments replace one entry; assistant/timeout opens a new entry |
| Regression | Full Python, frontend and build gates | All earlier tests pass |
| Observation | One bounded local live attempt | Audible answer and one coherent user row |

## Exit gate

- [ ] Observable path succeeds repeatedly.
- [x] Failure path is visible and explained.
- [x] Previous deterministic tests still pass.
- [ ] Live evidence is recorded.

## Offline evidence: 16 August 2026

- The focused red gate produced seven failures at the intended boundaries:
  completed-state answer rejection, missing transcript grouping controls, and the
  unchanged STT endpoint configuration.
- The controller now records the phase an answer must return to. Completed-deck
  questions enter `answering`, and verified answer playout returns to `completed`
  without a narration directive or duplicate completion event.
- That return phase survives interruption of the answer, so a follow-up answer
  cannot accidentally reopen a finished presentation.
- The inference pipeline now asks LiveKit for a 1.2-second minimum and 3.0-second
  maximum STT endpoint window. The installed LiveKit 1.5.17
  `TurnHandlingOptions` accepted the exact configuration locally.
- Final user fragments within 1.5 seconds reuse one transcript ID and accumulate
  their text. An assistant item, blank final boundary, or elapsed window closes
  the group.
- Focused result: 38 tests passed.
- Full Python result: 154 passed; the opt-in paid LiveKit test skipped.
- Full frontend result: 8 files and 42 tests passed.
- TypeScript production build passed. Vite retains the known non-blocking warning
  for the approximately 717 kB application bundle.

## Fallback or rollback

Retain post-completion answer support independently. If the endpoint window harms
responsiveness, revert only the endpoint tuning and keep transcript grouping as a
display safeguard.
