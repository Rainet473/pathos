# Verified slice: validated streaming follow-up answer

## Hypothesis

One accepted, still-current follow-up plan can drive the existing tool-disabled
LiveKit LLM-to-TTS stream without weakening interruption, playout settlement,
default waiting, or explicit continuation semantics.

## Observable path

```text
listener follow-up -> silent planner -> application validation
  -> tool-disabled generate_reply -> streamed TTS playout
  -> answer settlement -> wait or authorized narration resume
```

## Scope

- New real boundary: the accepted silent-planner result enters the active live
  voice session and produces one streamed answer turn.
- Still deterministic: plan validation, evidence resolution, state transitions,
  cursor ownership, continuation permission, and offline collaborators.
- Explicitly excluded: answer-focus navigation, embeddings/network retrieval,
  prompt-cache tuning, provider replacement, and prose-derived actions.

## Entry gate

- [x] Context/provenance, deterministic planning/search, and silent Gemma planner
  slices pass.
- [x] Expectation handout exists before source changes.
- [x] First failing application/adapter tests are defined and observed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Application contract | Offline accepted/stale/rejected plan tests | Only an accepted current plan creates one answer directive |
| Provider boundary | Offline LiveKit bridge collaborator | `generate_reply` receives tools disabled and no completed answer string |
| State authority | Waiting, continuation, interruption, duplicate callback tests | Cursor and beat commits remain correct and exactly-once |
| Prompt behavior | Directive assertions | Cited evidence, disclosure, and no redundant permission request |
| UI status | Frontend/state tests plus browser observation | Preparation status is visible without reasoning prose |
| Live voice | One bounded browser session | Grounded answer streams, normal case waits, authorized case resumes after playout |
| Regression | Repository check script | Previous backend/frontend/build gates remain green |

## Planned live usage ceiling

- One browser room/session using the selected Deepgram + Gemma + Inworld
  pipeline.
- Two listener follow-ups: one normal conversation/deck-grounded answer and one
  explicit answer-and-continue case.
- At most two silent-planner searches per follow-up and one accepted terminal
  plan; no automatic rerun after a failed observation.
- Stop after the two answer outcomes or after one provider/session failure.
- Record actual room duration, planner requests/tokens, answer timing, and TTS
  evidence before making a completion claim.

## Exit gate

- [ ] Observable path succeeds for waiting and explicit continuation.
- [x] Failure and answer-interruption paths are visible and controlled offline.
- [x] No narration beat is committed by answer playout in application/bridge tests.
- [x] Tool-disabled streaming is evidenced at the LiveKit adapter boundary.
- [x] Previous deterministic tests still pass.
- [x] Artifacts, limitations, and next risk are recorded.

## Recorded evidence

- Meaningful red baseline: the configured Python 3.12 environment reported an
  import error for the then-missing `PlanningStage`; later adapter tests failed
  on the missing planner bridge and callback contract. The planning-diagnostic
  test failed on the missing separate telemetry method, and the UI test failed
  on the missing status module.
- Provider-neutral and LiveKit slice tests: 41 passed before the additional
  failure/interruption hardening; the expanded LiveKit launcher/bridge and
  diagnostic selection then passed 27 tests.
- Final deterministic Python gate: 256 passed, with the two explicitly paid live
  tests skipped. `pip check` reported no broken requirements.
- Frontend: 36 tests passed and the Vite production build completed. The bundle
  retained the pre-existing large-chunk warning.
- Browser quiet-start precondition passed at `http://127.0.0.1:5173/`: the page
  showed `Quiet and disconnected`, with Start enabled and Stop disabled.
- Bounded live attempt `2c6b289e-ddfb-4122-a311-7da6f3c1f278` ran for 128.814
  seconds and then stopped explicitly. The local usage ledger records one
  completed room and a four-participant-minute conservative upper bound.
- The live pipeline streamed 12 narration turns. All 12 recorded distinct LLM
  TTFT and TTS-first-audio values; observed TTFT ranged from 329 to 1,096 ms and
  TTS first audio from 614 to 1,215 ms. The browser showed the current slide,
  turn, cursor, and timing while narration progressed.
- The browser and diagnostics recorded zero listener transcript segments and
  zero `user_state_changed -> speaking` events. A direct request for user speech
  and one synthetic system-speaker prompt were not captured by Chrome's selected
  microphone path. Consequently there were zero planning events, zero planner
  ledger rows, and zero answer context rows for this attempt.
- The live answer, default-wait, explicit-continuation, and acoustic answer-
  interruption gates remain **not observed**. The attempt was not retried because
  the declared ceiling allowed one room and no automatic retry after a failed
  observation.

## Files changed

- Provider-neutral planning status, accepted-plan answer directives, and
  controlled failure transition in `backend/src/voice_presentation/`.
- LiveKit callback, planner, launcher, context-trace, and diagnostic integration.
- Browser planning status, scope/source display, failure guidance, and planning
  duration display in `frontend/src/live/`.
- Application, adapter, transport, server, and frontend tests plus `.env.example`.

## Fallback or rollback

The committed silent planner and the current lexical live answer path remain the
rollback until this slice passes. A failure does not justify moving plan
validation or state ownership into the provider callback.

## Next highest risk

First, complete the blocked spoken Slice 4 answer gate with a microphone path
that produces a listener transcript. Only then proceed to model-proposed focus
slides; navigation must not hide an unobserved answer-streaming regression.
