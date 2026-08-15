# Expectation handout: provider usage accounting

## User-visible outcome

Every live transport attempt leaves a local, inspectable usage record so the operator can bound the new LiveKit WebRTC participant-minute consumption caused by this repository without exposing credentials or claiming knowledge of earlier account usage.

## Inputs, outputs and boundaries

- Inputs: attempt identifier, UTC start time, elapsed worker-session time, bounded browser-session policy and terminal outcome.
- Outputs/events: one append-only JSONL row per launched worker and an aggregate local-usage summary.
- External boundaries: LiveKit Cloud billing rounds each participant connection to whole minutes; the Cloud dashboard remains authoritative for account-wide usage.
- Preconditions: the runtime can append to the configured local ledger path.
- Non-goals: accounting for downstream transfer GB or inference, querying invoices, predicting compressed WebRTC byte counts exactly, recording audio, or inferring consumption from API secrets.

## Behavior map

```text
launch worker -> start monotonic timer -> completed / failed / cancelled
              -> append redacted usage row -> summarize local upper bound
```

## Invariants

- The ledger never stores the LiveKit URL, API key, API secret, participant token or audio.
- Exactly one terminal record is written for each worker task, including cancellation and failure.
- Duration is measured monotonically and cannot be negative.
- Worker and browser participant connections are rounded independently. The browser term is one minute because the application enforces a sub-minute connection cap.
- Remaining allowance is labelled as an estimate from a caller-supplied baseline, never as the provider's authoritative balance.
- Ledger failure must be visible in application logs but must not keep a finished room connected.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| 12-second successful attempt with two possible participants | Local upper bound is 2 participant-minutes | Automated |
| 61-second worker attempt plus a sub-minute browser cap | Local upper bound is 3 participant-minutes | Automated |
| Worker fails before browser joins | A failed row is still written, conservatively bounded | Automated |
| Application shutdown cancels a worker | A cancelled row is written once | Automated |
| Ledger inspected after live gate | Attempts and cumulative upper bound can be reconciled with the test table | Human observation |

## Edge and race cases

- Empty/malformed: malformed historical rows are rejected by the summarizer rather than silently counted.
- Duplicate/repeated: a worker task has one `finally` path and writes one row.
- Late/out-of-order: JSONL ordering is informative only; attempt IDs are the identity.
- Cancellation: cancellation is recorded and then re-raised so cleanup semantics remain intact.
- Partial failure: an append failure is logged without swallowing the worker's original terminal state.
- Recovery: a later attempt appends independently after a failed attempt.
- Capability mismatch: provider dashboard figures can differ because this is a conservative local upper bound.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Privacy | Only allowlisted non-secret fields appear | Credential, token, URL or audio appears | Redacted schema inspection |
| Accounting | One row per attempted worker and conservative total | Missing attempts or fractional minute undercount | JSONL ledger and summary output |
| Clarity | Local estimate and provider balance are distinguished | Estimate presented as exact remaining credits | Run ledger note |

## Open assumptions

- Slice 1 has at most two billable WebRTC participants per attempt: one browser connection capped below 60 seconds and one Python worker measured monotonically.
- The current free allowance must be supplied from current official documentation or the user's dashboard when summarizing.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended missing-module reason.
- [x] Deterministic accounting and launcher tests pass offline.
- [x] A live attempt produces one redacted ledger row.
- [x] The live observation ledger reports the incremental upper bound and the account-baseline limitation.
