# Expectation handout: live-only release runtime

## User-visible outcome

The repository contains one application experience: the live interruptible
presentation. Historical fake and record/replay products do not appear in the
runtime package, frontend, routes, or default test surface. Deterministic tests
still exercise the live application contract without provider spend, and one
small opt-in SDK smoke test can isolate LiveKit audio transport.

## Inputs, outputs and boundaries

- Inputs: live bootstrap requests, packaged deck content, browser microphone and
  navigation commands, and normalized provider callbacks.
- Outputs/events: live session credentials, presentation state, transcript,
  lifecycle, timing, and verified narration commitment.
- External boundaries: LiveKit Cloud and the selected voice-provider factory.
- Preconditions: the release-finish gate passes and fake/probe endpoints are
  already absent from configured production composition.
- Non-goals: changing presentation semantics, provider models, the deck format,
  answer retrieval, UI appearance, or acoustic behavior.

## Behavior map

```text
offline tests -> ApplicationPresentationSession -> domain controller

browser -> live bootstrap -> LiveKit conversation bridge -> provider pipeline

opt-in diagnostic -> two direct LiveKit SDK participants -> audio frame observed
```

## Invariants

- Quiet start, interruption, continuation, navigation, stale-callback, and
  exactly-once commitment tests target the live application contract.
- `JoinTokenIssuer` is a live authentication port, not housed in a probe module.
- shared slide view models are independent of fake application code.
- compact deterministic deck material lives under `tests/fixtures`, not the
  release content surface.
- configured and generic server composition cannot mount fake/probe routes.
- provider and LiveKit SDKs remain outside the domain and application core.
- the optional audio diagnostic uses no custom replay protocol or second UI.
- paid/network tests remain explicitly opt-in and skipped by default.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Live application test | deterministic directive is started and settled | Automated |
| Clarification with continue wording | answer still ends waiting | Automated |
| Server composition | only health, render, and optional live route exist | Automated |
| Historical module import | fake/probe product modules do not exist | Automated |
| LiveKit transport diagnostic | published synthetic audio reaches the subscriber once | Opt-in integration |

## Edge and race cases

- Empty/malformed: existing bootstrap and presentation validation remains.
- Duplicate/repeated: stale playout and duplicate commitment tests remain.
- Late/out-of-order: live application and bridge tests remain authoritative.
- Cancellation: conversation launcher and lifecycle tests remain.
- Partial failure: provider launch remains a redacted 503.
- Recovery: a fresh live attempt remains possible after stop/failure.
- Capability mismatch: provider-specific factories remain explicit.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Product surface | one quiet live UI | hidden fake/probe routes or links | route/source tests |
| Determinism | live application tested without network | tests require provider spend | offline suite |
| Diagnostic | small direct media smoke | second capture/replay product | opt-in test source |
| Live behavior | unchanged from accepted attempt | altered interruption or cursor semantics | prior attempt evidence |

## Open assumptions

- The direct SDK audio smoke is sufficient for isolating LiveKit transport; it
  does not prove browser permissions, provider inference, or audible quality.
- Removing historical observation tools is acceptable because their boundary
  has already been retired and retained evidence remains in `observations/`.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Opt-in diagnostic remains skipped by default and has no probe imports.
- [x] Public documentation describes one live product.
- [x] Observation cases were not rerun because user-visible behavior is unchanged.
- [x] Deferred risks are explicit.
