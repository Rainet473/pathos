# Verified slice: live-only runtime pruning

## Hypothesis

The fake and record/replay products can be removed without losing meaningful
coverage because the live application contract now has deterministic tests and
LiveKit transport can be diagnosed with one direct opt-in SDK smoke.

## Observable path

```text
checkout -> install -> one live frontend/API -> deterministic live-contract tests
                                      -> optional direct LiveKit audio smoke
```

## Scope

- New real boundary: none; this slice retires historical boundaries.
- Still fake: lightweight test collaborators around LiveKit AgentSession and
  conversation callbacks.
- Explicitly excluded: live presentation behavior changes, a model call, deck
  import, retrieval improvements, and deployment.

## Entry gate

- [x] Release-finish suite passes.
- [x] Expectation handout exists.
- [x] First failing source-surface test is recorded.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Source surface | module and server-signature contract tests | no historical product modules or injection ports |
| Behavior preservation | live application/domain/bridge suites | every relevant fake scenario remains covered |
| Frontend | source contract, tests, build | no probe/fake product; live UI unchanged |
| Transport diagnostic | opt-in direct SDK test | publisher audio frame reaches subscriber |
| Full regression | release check | all offline gates pass; paid test skips by default |

## Exit gate

- [x] Live-only source surface passes.
- [x] Failure paths remain visible and controlled.
- [x] Previous live tests still pass.
- [x] Removed files and retained limitations are recorded.

## Exit evidence

- Red source gate: 11 expected failures and 11 passes. The failures named the
  historical modules, missing neutral contracts, and obsolete server injection
  ports; the newly migrated live-application cases already passed.
- Backend migration gate: 82 application, domain, server, and deck-contract
  tests passed after the production routes and runtimes were removed.
- Frontend gate: 34 tests passed and the Vite production bundle built after the
  historical UIs were deleted and shared live types/visuals were relocated.
- Full offline release gate: 173 Python tests passed, the opt-in LiveKit test
  skipped by default, all 34 frontend tests passed, dependency checks passed,
  and the production bundle built.
- Direct boundary gate: `RUN_LIVEKIT_TESTS=1` completed the two-participant
  synthetic-audio smoke in 3.16 seconds with no inference model involved.

No manual browser/voice observation was repeated because this slice changes no
runtime presentation behavior. Previously accepted live attempts remain the
qualitative baseline.

## Fallback or rollback

If a fake scenario exposes a missing live-application contract, migrate that
behavior first and postpone deletion of only the necessary helper. The probe UI
and custom replay protocol remain removable independently.

## Next highest risk

The direct audio smoke proves LiveKit SDK transport only; it does not prove
browser permissions, audible output, or provider inference. The already-recorded
conversational-reference limitation remains separate product work.
