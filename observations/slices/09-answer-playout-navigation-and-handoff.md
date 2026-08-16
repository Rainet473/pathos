# Verified slice: answer-playout navigation and assignment handoff

## Hypothesis

Manual browsing can abandon an active answer and preserve the presentation
cursor without creating a second resumable-audio state machine, and the final
repository can explain and demonstrate that behavior concisely.

## Observable path

```text
listener browses during answer -> validate target -> interrupt answer once
  -> application waiting/completed state -> visible authored slide
  -> optional Continue restores preserved narration beat
```

## Scope

- New real boundary: browser navigation controls are enabled during answer
  playout and explicitly abandon that answer.
- Still fake: deterministic speech handles prove ordering before any acoustic
  observation.
- Included finish work: public demo script, approved known-issue reconciliation,
  accurate architecture text, bounded UI polish, and evidence-based legacy audit.
- Explicitly excluded: `additional-context.json`, generic PPTX import, vector
  search, deployment, answer-audio resumption, and model-owned navigation.

## Entry gate

- [x] Question-reasoning PR #1 is merged into `main` at `52f9d65`.
- [x] Slice 8g full gate passed: 291 Python tests, 3 paid opt-in skips,
  37 frontend tests, and production build.
- [x] Expectation handout exists before source changes.
- [x] First failing state/bridge/frontend tests were defined and observed. The
  initial red gate exposed retained answer-continuation metadata, an incorrect
  post-completion return phase, and command-side interruption before target
  validation; frontend policy helpers were absent.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| State | Domain/application tests | answer metadata clears, cursor is preserved, waiting/completed return is correct |
| Adapter | Fake LiveKit speech handle | target validates first, answer interrupts once, late callback is inert |
| Frontend | Component-policy/reducer tests | answering permits navigation; planning still blocks it; consequence is disclosed |
| Browser | Local production UI observation | controls and answer-interruption copy are understandable at desktop and narrow width |
| Cleanup | Import/reference and release-surface audit | only demonstrably unused production code is removed; provider/test contracts stay intact |
| Regression | `scripts/check.sh` | all retained tests, dependency checks, and production build pass |

## Exit gate

- [x] Answer-playout browse/abandon/continue succeeds repeatedly offline.
- [x] Invalid, duplicate, late, post-completion, and answer-and-continue cases pass.
- [x] Public demo and limitations match implemented behavior.
- [x] Quiet-start UI was observed at the default desktop viewport and 390 px
  width. Live answer-planning and acoustic interruption remain a user-run gate
  because Start requests microphone access.
- [x] Cleanup audit removed the obsolete `conversation.py` launcher/private-agent
  re-export path. Optional realtime adapters, boundary fakes in tests, and old
  slice records remain because each has an explicit supported or evidentiary role.
- [x] Previous tests remain green: final release gate passed with 295 Python
  tests, 3 paid opt-in skips, 39 frontend tests, dependency checks, and a
  production build.

## Fallback or rollback

Restore the current answering-phase control disablement. The existing answer,
interruption, focus, waiting, and continuation behavior remains independently
valid.

## Evidence captured so far

- Focused KI-004 gate: 4 backend scenarios and 4 frontend policy tests passed.
- Adjacent presentation regression: 74 backend tests passed.
- Complete frontend unit gate: 39 tests passed.
- Cleanup import boundary: 42 launcher, provider, server, and release tests passed.
- Visual observation: quiet-start consent copy and layout remained readable at
  desktop and 390 px width without activating a microphone.
- UI delivery: LiveKit was moved behind a Start-time dynamic import. Production
  output changed from one 710.72 kB application chunk to a 214.49 kB initial
  chunk plus a 496.93 kB on-demand transport chunk, without a Vite size warning.

## Next highest risk

The remaining KI-004 risk is acoustic provider behavior: a human should verify
that selecting another slide stops a speaking answer promptly. Beyond that,
generic content ingestion (KI-005) is a larger product slice and is intentionally
outside this assignment handoff.
