# Verified slice: release finish

## Hypothesis

The validated live presentation can become the sole production surface while
retaining fake/probe regression evidence and making provider/LiveKit adapter
boundaries understandable to a new contributor.

## Observable path

```text
repository checkout -> documented install -> root live UI -> live API bootstrap
  -> application-controlled presentation -> documented evidence and limitations
```

## Scope

- New real boundary: production-versus-harness application composition.
- Existing boundary reorganized: provider factories and the LiveKit conversation
  launcher are split behind their existing public contracts.
- Still internal: deterministic fake and record/replay probe harnesses.
- Explicitly excluded: generic deck import, deployment automation, external
  retrieval, answer-playout navigation, and semantic follow-up improvements.

## Entry gate

- [x] Full deck and live three-model pipeline completed in an observed attempt.
- [x] Manual deck browsing and context capture were observed.
- [x] Expectation handout exists.
- [x] Focused release-surface failures are recorded.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Production API | OpenAPI and route tests | live/health/render present; fake/probe absent |
| Adapter contract | provider factory tests | shared contract and distinct provider options pass |
| Regression harness | existing fake/probe suites | deterministic behavior remains green |
| Frontend | test and production build | root imports live app; build succeeds |
| Onboarding | public-doc inspection and commands | no private handoff required |
| Observation | attempt `35a5be63-…` audit | cursor separation, completion and context limitations recorded honestly |

## Exit gate

- [x] Production surface is minimal and observable.
- [x] Failure paths remain controlled and credential-safe.
- [x] Previous test gates pass.
- [x] Documentation and limitations are recorded.

## Red evidence

The release contract was run before implementation and produced three intended
failures:

1. the configured application still exposed fake/probe routes;
2. unused Google/OpenAI provider plugins were default dependencies; and
3. provider factories had not yet moved behind importable dedicated modules.

The earlier fake, probe, and provider contract suites remained the preservation
gate during the change.

## Implementation result

- `create_configured_app()` now composes only the live service. Generic
  `create_app()` injection still mounts fake/probe routes for explicit harnesses.
- `/` mounts only the quiet live experience and no longer links internal slices.
- provider factories live under `adapters/livekit/agents/`; their base owns only
  shared validation, identity, and credential-safe representation.
- LiveKit session launching and thin agent construction moved out of the room
  bridge without changing their established import surface.
- Google and OpenAI realtime plugins became opt-in extras; the verified LiveKit
  inference pipeline remains the default installation.
- public README, architecture, contribution, environment, and release-check
  guidance no longer depend on private planning material.

## Automated exit evidence: 16 August 2026

`scripts/check.sh` passed with the configured Python 3.12 conda environment:

- Python compile gate: passed.
- Python tests: 210 passed; one quota-spending LiveKit test skipped by its
  explicit opt-in guard.
- Installed Python dependency check: no broken requirements.
- Frontend tests: 11 files and 54 tests passed.
- TypeScript and production Vite build: passed.
- The generated JavaScript bundle is approximately 708 kB; Vite's existing
  500 kB chunk advisory remains a non-blocking performance refinement.

The first tool-shell invocation stopped before testing because it did not inherit
the active conda environment's npm path. Supplying the configured environment
path ran the unchanged script successfully; the script intentionally keeps its
active-environment guard.

## Context and manual observation evidence

Attempt `35a5be63-5af1-447d-871d-e76ce8cdc3b8` completed with browsing,
interruption, questions, and direct continuation. The sanitized audit records
stable provider-stage latency, retained interrupted history, and correct
visible-slide/cursor separation. It also records KI-006: short referential
follow-ups can be falsely classified as out of scope.

## Remaining release decision

The engineering exit gate is complete. A public redistribution release is not:
the repository owner must explicitly choose a software license before reuse
terms can be claimed.

## Fallback or rollback

Keep the current monolithic adapters and dynamic app composition if module
splitting changes runtime behavior. Production endpoint gating and public
documentation can ship independently.

## Next highest risk

Conversational-reference grounding and manual navigation during answer playout,
not authoring-format import.
