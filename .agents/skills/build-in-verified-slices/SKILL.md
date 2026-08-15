---
name: build-in-verified-slices
description: Plan and deliver new systems, integrations, pipelines, and substantial features as the smallest observable vertical slices with explicit entry and exit gates. Use when work spans multiple boundaries, depends on an external service, is vulnerable to hidden failures between phases, or should advance from transport and fakes to a real provider without broad scaffolding.
---

# Build In Verified Slices

Reduce uncertainty one boundary at a time. Every slice must produce an observable result, add only one meaningful risk when practical, retain the previous evidence, and leave the system in a runnable state.

## Start with the risk ladder

1. Map the boundaries and rank the unknowns by how likely they are to invalidate the design.
2. Invoke `$spec-first-testing` to define the first slice's behavior before implementation.
3. Choose the thinnest path through the real system that tests the highest-risk boundary.
4. Fill out `assets/slice-ledger.md` with the hypothesis, evidence, exit gate, and rollback.

Do not equate a horizontal layer with a vertical slice. A slice should cross enough of the system to produce an end-user or operator-visible result.

## Default progression

Adapt this progression to the project; skip a stage when it does not retire a real risk.

1. **Contract and harness** — schemas, state transitions, fake ports, and failing acceptance tests.
2. **Transport probe** — move the smallest real payload through the client/server or process boundary and observe it at both ends.
3. **Fake end to end** — exercise the user flow through a deterministic adapter with no paid or variable dependency.
4. **Real provider minimum** — prove the narrowest provider interaction without tools or product breadth.
5. **One domain action** — connect one validated tool, content item, or state-changing action through the real adapter.
6. **Adversarial behavior** — interruption, cancellation, races, retries, disconnects, and unsupported capabilities.
7. **Breadth and finish** — expand content, polish UI, deploy, and document only after core risks are closed.

## Gate every slice

Before coding, record:

- the single hypothesis this slice tests;
- the new boundary or dependency introduced;
- the automated tests and real-world observation;
- what remains fake;
- a measurable exit condition;
- the fallback if the hypothesis fails.

Do not start the next slice until the exit condition is met or the plan is explicitly revised.

## Keep boundaries replaceable

- Define provider-independent inputs, outputs, events, errors, and capabilities.
- Make fakes obey the same contract as real adapters.
- Keep provider callbacks out of domain policy.
- Preserve prior test suites as regression gates.
- Instrument crossings with identifiers and timestamps when ordering or latency matters.
- Prefer controlled record/replay over live acoustic echo when echo can create feedback or make evidence ambiguous.

## Diagnose failures at the newest seam

When a slice fails:

1. Reproduce using the smallest probe from the previous passing slice.
2. Compare expected and observed events at the newly introduced seam.
3. Avoid compensating in downstream layers until the source boundary is understood.
4. Add a regression test or observation case that would have exposed the issue.
5. Revise the adapter or the documented contract, then rerun all earlier gates.

## Completion evidence

For each completed slice, report:

- the observable outcome;
- commands and tests run;
- retained artifacts such as logs, traces, transcripts, recordings, or screenshots;
- remaining fakes and limitations;
- the next risk, not merely the next layer.
