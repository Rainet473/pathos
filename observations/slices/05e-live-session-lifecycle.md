# Slice 5e - Live-session lifecycle

## Entry gate

- Full six-slide deterministic progression: passed.
- Live interruption and answer-and-continue paths: user-observed pass.
- Full-deck live progression: user-observed functional, with an unexpected
  three-minute disconnect captured during `power-to-wheel`.

## Fixed contract

Follow `expectations/live-session-lifecycle.md` without changing the timeout
values or reclassifying an unexpected provider failure as a graceful end.

## Boundary sequence

1. Publish the backend-owned idle and absolute limits through session bootstrap.
2. Prove backend inactivity, absolute-age, and post-completion activity behavior.
3. Mirror those reasons in browser cleanup and presentation state.
4. Remove deprecated/speculative AgentSession integration warnings.
5. Run the earlier deterministic and frontend regression gates.

## Automated evidence

- Initial red failures: 8 backend and 5 frontend failures, all at the intended
  missing lifecycle-policy, terminal-reason, supported-metrics, and
  preemptive-generation boundaries.
- Focused backend lifecycle tests: 30 passed.
- Focused browser lifecycle tests: 17 passed.
- Full backend regression: 181 passed; 1 paid LiveKit test skipped by its
  explicit quota guard.
- Full frontend regression: 49 passed.
- TypeScript check: passed.
- Production build: passed; existing large-chunk advisory remains.
- Python lint/format command was unavailable because Ruff is not installed in
  the configured environment; the complete Python test gate passed.

## LiveKit option-shape hotfix

- User-observed failure: the installed SDK rejected boolean
  `preemptive_generation=False` because `TurnHandlingOptions` requires an options
  mapping.
- Initial regression: the focused factory test failed on the boolean/mapping
  mismatch.
- Fix: pass `{"enabled": false}` and construct the installed `AgentSession` in a
  deterministic adapter-conformance test.
- Focused result: 13 passed.
- Full backend result after hotfix: 182 passed; 1 paid LiveKit test skipped.
- Browser observation: not run because the explicitly requested in-app Browser
  surface was unavailable; no alternate browser was substituted.

## Human observation

- Attempt ID: `35a5be63-5af1-447d-871d-e76ce8cdc3b8`.
- Final completed state remained visible and browsable: passed.
- The session completed without the earlier unexpected mid-deck disconnect:
  passed.
- Inactivity message, if explicitly observed: pending.
- Backend warnings absent: not independently captured in the retained evidence.

## Exit evidence

Automated gates and one user-observed full-deck lifecycle passed. The explicit
inactivity-timeout observation remains pending; the 15-minute absolute ceiling
was not waited out during this release run.
