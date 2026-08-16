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

## Human observation

- Attempt ID: pending.
- Final completed state remains available for follow-up questions: pending.
- Inactivity message, if explicitly observed: pending.
- Backend warnings absent: pending.

## Exit evidence

Automated exit gates passed. One user-observed full-deck run remains before this
slice is considered acoustically closed.
