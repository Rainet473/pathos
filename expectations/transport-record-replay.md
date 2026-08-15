# Expectation handout: controlled audio record/replay

## User-visible outcome

A user explicitly starts a transport probe, records a short microphone clip, and hears that clip played back exactly once after recording ends. The screen reports enough timing and audio metadata to distinguish a working browser–Python media path from a silent or malformed one.

## Inputs, outputs and boundaries

- Inputs: user gesture, microphone permission, audio frames, stop action and LiveKit room credentials minted by the backend.
- Outputs/events: capture started, capture stopped, frames received, replay started, replay completed, failure and reconnect state.
- External boundaries: browser media APIs, LiveKit Cloud WebRTC and a Python LiveKit participant.
- Preconditions: headphones, network access, valid LiveKit configuration and an explicit user gesture.
- Non-goals: acoustic quality scoring, model interaction, VAD tuning, presentation state and simultaneous live self-echo.

## Behavior map

```text
idle
  └─ user starts → capturing → user stops → transferring → replaying → complete
                         └─ disconnect/error ───────────────→ failed
failed ── new explicit attempt → capturing
```

## Invariants

- The probe captures or plays nothing before an explicit user action.
- Returned audio is played once and only after capture stops.
- Provider and LiveKit secrets never enter browser-visible configuration.
- Each attempt has an identifier; late frames from an older attempt cannot complete a newer one.
- Failure is visible and leaves the user able to make a fresh attempt without restarting the Python process.
- Metrics describe observed frames and timestamps; they do not claim byte parity across a lossy WebRTC codec boundary.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Three-second spoken clip | One intelligible replay with nonzero frame count and plausible duration | Human rubric plus metrics |
| Empty capture | Controlled validation failure; no replay | Automated |
| Malformed sample metadata | Rejected before publication | Automated |
| Duplicate stop event | One finalized attempt and one replay at most | Automated |
| Disconnect during capture | Visible failure followed by a successful new attempt | Automated plus observation |

## Edge and race cases

- Empty/malformed: zero frames, invalid sample rate, unsupported channel count and missing attempt ID.
- Duplicate/repeated: repeated Start or Stop, duplicate final frame and replay-complete callback.
- Late/out-of-order: frames or completion from a superseded attempt.
- Cancellation: before the first frame, mid-capture and after transfer but before replay.
- Partial failure: browser publishes while Python cannot return audio, or returned track exists but cannot autoplay.
- Recovery: reconnect creates a new attempt ID and clears stale transport state.
- Capability mismatch: codec resampling changes bytes or sample rate while preserving intelligible duration.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Intelligibility | Recorded phrase is understandable | Silence, severe clipping or unrelated audio | Short recording and attempt ID |
| Feedback | No simultaneous speaker-to-mic loop | Howl, repeated echo or continuous loop | Recording and headphone note |
| Repeatability | Five consecutive attempts complete without server restart | Intermittent hangs or manual restart | Timestamped attempt table |
| Visibility | Active phase and failures are obvious | UI appears frozen or falsely complete | Screenshot and event log |

## Open assumptions

- LiveKit Cloud credentials and a supported browser will be available for Slice 1.
- Browser autoplay may require an additional user gesture; that state must be explicit rather than bypassed.

## Exit criteria

- [ ] Tests were written before transport implementation.
- [ ] New tests were observed failing for the intended reason.
- [ ] Deterministic transport-boundary tests pass offline.
- [ ] Five live observation attempts were run and evidence was recorded.
- [ ] Deferred codec and network risks are explicit.
