# Verified slice: validated answer-focus navigation

## Hypothesis

An application-validated focus proposal can show answer support on another slide
without moving the semantic narration cursor, and can restore that cursor's slide
before exactly-once resumption.

## Observable path

```text
spoken follow-up -> validated plan with focus slide -> question slide visible
  -> streamed answer -> wait on support OR restore -> resume preserved beat
```

## Scope

- New real boundary: the accepted planner `focus_slide_id` now reaches the
  application-owned visible-slide transition already transported to the browser.
- Still fake: deterministic tests own provider plans and playout callbacks.
- Explicitly excluded: ASR acronym repair, malformed-plan/citation fallback,
  manual browsing during answer audio, embeddings, and prose-derived navigation.

## Entry gate

- [x] Context, planning, streaming answer, and recovery offline gates pass.
- [x] Live attempt `3536b0b3-9285-4934-9290-9c60342a7c30` exercised the
  30-second deadline, completed cleanly, and proved accepted ABS
  answer-and-continue behavior after a correct transcription.
- [x] The first live ABS miss is isolated to `ABS` -> `APS` transcription plus a
  malformed terminal plan and is explicitly deferred to robustness work.
- [x] Expectation handout exists before source changes.
- [x] First failing focus tests are defined and observed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Application focus | Accepted cross-slide plan test | Visible slide changes with reason `question`; cursor is unchanged |
| Waiting | Answer settlement test | Support slide remains visible and no beat commits |
| Direct continuation | Ordered event test | `restore` occurs before resume and preserved beat selection exactly once |
| Manual distinction | Existing navigation regression | User browse continues to emit reason `user` |
| Transport/browser | Presentation-state tests | Structured reason and visible slide survive serialization/rendering |
| Live observation | Cross-slide spoken question | Browser visibly focuses support and restores before resumed narration |

## Exit gate

- [x] Observable path succeeds repeatedly offline.
- [x] Failure path is visible and controlled.
- [x] Previous tests still pass.
- [x] Artifacts and limitations are recorded.

## Recorded evidence

- Red baseline: two focused application cases failed because the accepted plan's
  validated focus slide was discarded and `control-loop` remained visible. The
  neighboring controller restoration-order case passed, isolating the missing
  boundary to application plan acceptance.
- Implementation: accepted plan focus now enters the existing controller
  `begin_answer` transition. No provider, domain-state, transport, or frontend
  navigation authority was added.
- Focused gate: 35 application/domain tests and 30 planner/LiveKit/transport tests
  passed. The focused cases prove question-reason focus, waiting on support,
  restore-before-resume ordering, exactly-once beat selection, and no narration
  beat commitment by an answer.
- Retained gate: 262 backend tests passed and two opt-in live tests were skipped.
  All 36 frontend tests passed, the TypeScript/Vite production build completed
  with its existing chunk-size warning, and `pip check` found no broken
  requirements.
- Live post-change observation: repository-owner browser test on attempt
  `6729e607-f271-487c-9859-bfdf61c5d44b` used "Explain ABS and then continue
  your presentation." The supporting `braking-abs` slide appeared for the
  answer, then the original `control-loop` narration slide was restored and the
  preserved presentation continued as expected.
- Runtime corroboration: the planner accepted `braking-abs` as both supporting
  and focus slide after one search in 2.003 seconds; the answer transcript was
  grounded in the two cited ABS passages; narration resumed on the preserved
  control-loop beat; and the 48.635-second attempt ended with outcome
  `completed`. The runtime JSONL does not persist the browser's domain-event
  list, so the visual focus/restore judgment is the human observation while
  event ordering remains covered deterministically.

## Fallback or rollback

Keep `focus_slide_id` validated but unapplied, preserving the currently proven
answer, waiting, and continuation behavior.

## Next highest risk

Robustness and release evidence: acronym transcription, graceful fallback after
malformed/citation failures, mode variation, cancellation, and caching.
