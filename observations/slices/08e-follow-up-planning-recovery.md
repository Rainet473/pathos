# Verified slice: follow-up planning recovery

## Hypothesis

The validated streaming-answer path can recover from deadline-edge terminal
responses, historical-evidence proposals, stale failure display, and adjacent STT
fragments without weakening planning bounds or application-owned continuation.

## Observable path

```text
spoken follow-up -> bounded turn stabilization -> silent planner
  -> current evidence validation -> streamed answer
  -> verified playout -> wait or authorized narration resume
```

## Scope

- New real boundary: no new provider or transport dependency; this hardens the
  existing LiveKit STT/planner/application seams exposed by one live attempt.
- Still fake: provider streams and timing are deterministic in the default test
  suite.
- Explicitly excluded: answer-focus navigation, external search, transcript word
  reconstruction, and unbounded provider retries.

## Entry gate

- [x] The prior context, planner, and streaming-answer deterministic gates pass.
- [x] A completed live attempt captured the four failure/recovery symptoms.
- [x] Expectation handout exists before source changes.
- [x] First failing regression tests are defined and observed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Planner contract | Recorded provider/tool tests | Historical evidence is rejected visibly and can be corrected within bounds |
| Deadline settlement | Controlled async stream test | A response received before the deadline completes local validation |
| Deadline configuration | Application default test | One follow-up receives a shared 30-second planning deadline |
| Application recovery | State-transition tests | Starting recovery clears stale failure without altering the cursor |
| Turn stabilization | Adjacent-fragment adapter test | One complete follow-up and continuation preference reach planning |
| Regression | Backend, frontend, and build gates | All retained offline suites remain green |
| Live observation | ABS and AWS utterances | One answer each; automatic resume only after answer playout |

## Exit gate

- [x] Observable path succeeds repeatedly offline.
- [x] Failure path remains visible and controlled.
- [x] Previous tests still pass.
- [x] Artifacts and remaining live limitations are recorded.

## Recorded evidence

- Entry attempt: `a4df4e08-84c9-452c-8ae8-55e60c7c6e4e` completed the deck but
  exposed one planner timeout, one historical-evidence rejection, one stale
  failure display during resumed narration, and one split AWS/continuation turn.
- Red baseline: the focused Python run produced five expected failures while 26
  neighboring tests passed. The failures reproduced terminal cancellation at the
  deadline edge, terminal rejection of historical evidence without a correction
  path, stale failure state after Continue, missing `then narration` continuation
  recognition, and the absent fragment-coalescing hook.
- Frontend red baseline: the focused status test failed because every non-timeout
  reason still used the same generic message.
- Timeout-tuning red baseline: the application-default assertion observed the
  previous `10.0`-second value. The first retained backend run then exposed one
  timeout-control fixture that implicitly depended on that old default; its
  scenario now requests 10 seconds explicitly.
- Targeted implementation gate: 31 planner, application, and LiveKit bridge tests
  passed, including deadline-edge local settlement, historical-evidence
  correction, stale-error clearing, incomplete-fragment coalescing, and explicit
  continuation recognition.
- Retained backend gate: 260 passed and the two opt-in paid/live tests remained
  skipped. `pip check` reported no broken requirements.
- Retained frontend gate: 36 tests passed. TypeScript checking and the Vite
  production build completed; the pre-existing large-chunk warning remains.
- Thirty-second deadline gate: the application and domain contract checks pass;
  the retained backend suite reports 261 passed and two opt-in live tests skipped.
  The frontend still reports 36 tests passed, the production build completes,
  and `pip check` reports no broken requirements.
- No post-fix provider or acoustic run was spent automatically. The live ABS and
  AWS answer-and-continue cases remain the exit evidence needed before starting
  answer-focus navigation.

## Fallback or rollback

Retain the current controlled waiting failure and explicit retry path. Do not
allow an unvalidated answer or model-owned continuation to mask a failed fix.

## Next highest risk

After this recovery gate, rerun the bounded live ABS/AWS cases. Only then advance
to validated answer-focus navigation.
