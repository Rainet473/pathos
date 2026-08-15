# Verified slice: one-slide deterministic fake product

## Hypothesis

The complete quiet-start, interruption, answer and wait/resume semantics work repeatedly without a model, media transport, network access or provider credentials.

## Observable path

```text
browser action -> local FastAPI fake-session boundary -> application controller
               -> deterministic fake voice lifecycle -> versioned snapshot
               -> React phase, slide, cursor, turn and transcript display
```

## Scope

- New real boundary: local React-to-FastAPI product actions and versioned state snapshots.
- Still fake: voice generation, speech recognition, turn detection and all provider/media behavior.
- Explicitly excluded: LiveKit `AgentSession`, Gemini/Google, paid/live probes, six-slide breadth, model tools, acoustic claims, visual polish and public documentation.

## Entry gate

- [x] Slice 0's 27 requirement-derived tests fail only at the absent domain implementation seam.
- [x] Slice 1 retains 48 Python passes, one skipped opt-in live test, 16 frontend passes and a successful build.
- [x] At Slice 2 entry, Slice 1's five spoken clips, intelligibility, screenshot/recording and disconnect/recovery remained explicitly open; prior evidence permitted this independent offline slice to advance.
- [x] `expectations/deterministic-fake-product.md` defines the observable behavior and rubric.
- [x] The first missing source seams are the validated domain contracts, controller, fake runtime and fake-session UI path.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Domain oracle | Run existing contract, narration, interruption and scope tests | All 27 pass without changing the requirement-derived assertions |
| Fake adapter | Exercise normalized start, complete, interrupt, duplicate and capability behavior | Adapter is deterministic, explicit and provider-neutral |
| Product scenario/API | Drive both plain-question and answer-and-continue paths through the local session boundary | Waiting and direct-resume snapshots preserve the same uncommitted beat and reject illegal actions visibly |
| Frontend state | Test quiet initial state and version-based stale snapshot rejection | Older responses cannot overwrite newer UI state |
| Browser observation | Run both scripted paths from fresh sessions | Phase, slide, cursor and turn identity remain legible and match the event log |
| Regression | Run all Python and frontend tests plus the production build | Slice 1 gates remain green; live test stays opt-in |

## Exit gate

- [x] Both offline acceptance paths succeed repeatedly from a fresh session.
- [x] Illegal and stale actions are visible and controlled.
- [x] The previous Python/frontend gates still pass.
- [x] Browser screenshots and exact commands/results are recorded below.
- [x] Remaining fakes, the then-open Slice 1 observations and later live risks stay explicit.

## Fallback or rollback

If the browser-to-FastAPI seam fails, retain the passing domain/controller and fake-runtime scenario as an offline command-line proof, keep the UI gate open, and diagnose only the newest HTTP or rendering boundary.

## Next highest risk

Whether the selected realtime model can hold a stable microphone-in/audio-out conversation with prompt interruption while preserving these normalized controller semantics.

## Run evidence

- Date: 16 August 2026.
- Runtime: `synthio` conda environment with Python 3.12.13, pytest 9.1.1, Node 24.19.0 and npm 11.17.0.
- Pre-implementation domain command: `conda run -n synthio python -m pytest -q tests/contract tests/domain`.
- Pre-implementation domain result: 27 failures in 0.12 seconds, all caused by `ModuleNotFoundError: No module named 'voice_presentation.domain'`.
- Retained Slice 1 Python command: `conda run -n synthio python -m pytest -q tests/transport tests/server tests/adapters tests/scripts tests/live`.
- Retained Slice 1 Python result: 48 passed and one opt-in live test skipped in 2.96 seconds.
- Retained frontend command: `conda run -n synthio npm test`.
- Retained frontend result: 3 files and 16 tests passed in 0.16 seconds.
- Retained build command: `conda run -n synthio npm run build`.
- Retained build result: successful; the accepted Slice 1 large-chunk warning remains.
- New Python red gate: collection stopped at the absent domain, application and `create_offline_app` seams; no provider or environment failure masked it.
- New frontend red gate: `src/presentation/state.test.ts` failed because the independently specified state module did not exist.
- Boundary gates during implementation: 10 content/contract tests, then 29 content/domain tests, then 8 fake-runtime/scenario tests and 13 combined fake/probe server tests passed before advancing.
- Scope regression red gate: an ambiguous question with a continuation suffix was initially classified out of scope; the added regression then passed after phrase handling and clarification-wait policy were corrected.
- Final Python command: `conda run -n synthio python -m pytest -q`.
- Final Python result: 89 passed and one opt-in LiveKit Cloud test skipped in 2.87 seconds.
- Final frontend command: `conda run -n synthio npm test`.
- Final frontend result: 4 files and 20 tests passed in 0.18 seconds.
- Final build command: `conda run -n synthio npm run build`.
- Final build result: successful; 25 modules transformed and the 698.14 kB pre-gzip JavaScript chunk retains the accepted optimization warning.
- Static checks: Python compilation, `git diff --check` and a provider-name scan of `voice_presentation.domain` all passed.
- Local server observation: credential-free FastAPI bound at `127.0.0.1:8000`, Vite bound at `127.0.0.1:5173`, `/api/health` returned `{"status":"ok"}`, and both `/` and `/probe` served the application shell with the updated product title.
- Plain-question HTTP observation (`2f244d46-4c00-48d4-9dc2-5ac4cfe57053`): ready was quiet; Start produced `narration-1`; interruption produced grounded `answer-2`; answer completion entered `waiting` with `engine-braking/0` preserved; explicit Continue created active narration turn `narration-3` at the same cursor.
- Direct-resume HTTP observation (`dc8e5f46-1fc6-4950-97f1-e7ca21ad7119`): Start reached version 2; interruption reached answering at version 5; answer completion restored active `narration-3` at the same `engine-braking/0` cursor at version 7; one matching completion reached `completed` at version 8 with exactly one committed cursor.
- Repeatability evidence: `test_fresh_sessions_produce_the_same_script_and_transition_shape` runs the complete plain-question shape twice from fresh sessions and compares transcript and state outputs.
- Browser observation: the evaluator supplied sequential browser screenshots from the local application. They show ready/version 0 with no turn, transcript or events; presenting/version 2 with `narration-1`; answering/version 5 with grounded `answer-2` and the same cursor; waiting/version 6 with no active turn and an explicit Continue control; and direct-resume events from `answer-4` to `narration-5`. The evaluator separately confirmed that completing the resumed narration displayed `Presentation complete`. The screenshots remain attached to the evaluation conversation and were not copied into the repository.
- Provider usage: zero LiveKit, Google, OpenAI or other external calls were made in Slice 2.

## Advancement decision

The Slice 2 implementation, deterministic offline behavior and visual observation gate are complete. The evaluator-observed UI states agree with the automated and served-HTTP evidence. Slice 1's five spoken clips, intelligibility and disconnect/recovery observations were still open at this decision and were not replaced by fake evidence; they were subsequently completed and recorded in `observations/slices/01-transport-record-replay.md`.
