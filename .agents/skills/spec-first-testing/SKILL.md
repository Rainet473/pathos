---
name: spec-first-testing
description: Define observable behavior before implementation and derive tests from requirements rather than generated code. Use when adding or changing a feature, pipeline, API, state machine, adapter, bug fix, or integration; when edge cases or race conditions matter; or when a qualitative system needs a repeatable human-observation rubric alongside automated tests.
---

# Spec First Testing

Turn the intended behavior into an independent oracle before reading or writing the implementation that will satisfy it. Keep deterministic assertions separate from qualitative evaluation, and require evidence from both when both matter.

## Workflow

1. Read the user-visible requirements, existing contracts, and relevant external specifications.
2. Create an expectation handout from `assets/expectation-handout.md` before editing source code.
3. Draw the smallest state or data-flow mind map needed to expose boundaries and ordering.
4. Record invariants, non-goals, examples, failure behavior, and unresolved assumptions.
5. Design the test matrix before implementation.
6. Write the smallest tests that express the contract and run them to observe a meaningful failure.
7. Implement only enough behavior to pass the next failing test.
8. Run automated tests and the observation cases. Preserve transcripts, screenshots, logs, or recordings when they are the evidence.
9. Update the handout when the intended behavior changes; do not silently weaken an expectation because the implementation differs.

## Choose the right oracle

Use deterministic assertions for:

- schemas, serialization, values, and event shapes;
- state transitions and ordering;
- idempotency, versioning, cancellation, and stale-result rejection;
- errors, timeouts, retries, cleanup, and resource ownership;
- adapter conformance with fakes or recorded fixtures.

Use observation cases with an explicit rubric for behavior that is real but not safely reducible to equality checks, such as:

- whether a spoken response is concise, intelligible, or well-grounded;
- whether interruption feels prompt in realistic audio;
- whether an explanation resumes coherently;
- whether a UI state is understandable to a first-time evaluator.

Never label a qualitative judgement as a passing parity test. Record the input, artifact, rubric, evaluator, and result so another person can repeat the check.

## Edge-case pass

Reason through at least these families before implementation:

- empty, malformed, boundary-size, and unsupported inputs;
- repeated commands and duplicate events;
- cancellation before, during, and after an external operation;
- late or out-of-order callbacks;
- partial success and dependency failure;
- reconnect, restart, and recovery;
- concurrent actors or overlapping turns;
- security, privacy, and unsafe requests where relevant;
- capability differences between real and fake adapters.

Add only relevant cases, but document why an applicable-looking family is excluded.

## Guardrails

- Do not derive the expected behavior from the code under test.
- Do not inspect a new implementation first when a requirement can serve as the oracle.
- Do not mock away the boundary being evaluated.
- Keep network/provider tests opt-in and separately marked; the default suite must be deterministic and offline.
- Prefer one precise failing test over broad scaffolding.
- If a requirement is ambiguous enough to change behavior materially, make that ambiguity visible instead of encoding a guess as fact.

## Completion evidence

Report:

- the expectation handout used;
- which tests failed before implementation and pass after it;
- which behavior was manually observed;
- uncovered risks and deferred cases;
- any expectation changed during implementation and the reason.
