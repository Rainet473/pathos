# Expectation handout: controlled audio record/replay

## User-visible outcome

A user explicitly starts a transport probe, records a short microphone clip, and hears that clip played back exactly once after recording ends. The screen reports enough timing and audio metadata to distinguish a working browser–Python media path from a silent or malformed one.

## Inputs, outputs and boundaries

- Inputs: user gesture, microphone permission, audio frames, stop action and LiveKit room credentials minted by the backend.
- Outputs/events: capture started, capture stopped, frames received, replay started, replay completed, failure and reconnect state.
- External boundaries: browser media APIs, LiveKit Cloud WebRTC and a Python LiveKit participant.
- Preconditions: headphones, network access, valid LiveKit configuration and an explicit user gesture.
- Non-goals: acoustic quality scoring, model interaction, VAD tuning, presentation state and simultaneous live self-echo.

### Attempt-scoped wire contract

- The browser chooses a unique `attemptId` for each explicit probe and requests a short-lived room token from `POST /api/probe/sessions`.
- Bootstrap accepts only a `probe-...` room name, a `browser-...` participant identity and a UUID attempt identifier. It returns the LiveKit server URL and participant token, never API credentials.
- Browser control signals and Python status signals are reliable LiveKit data packets on the `voice-probe.control.v1` topic.
- Every signal carries `version: 1`, `type`, `attemptId` and a monotonic client-relative timestamp. Status signals may add frame count, sample count and audio duration.
- Microphone and replay tracks use 48 kHz mono PCM at the Python boundary. Individual accepted frames must be non-empty and no longer than 100 ms.
- Audio itself travels as a LiveKit media track. Data packets coordinate start/stop/status only; they are not an alternate audio upload path.

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
| Late status from an old attempt | Current UI state and metrics do not change | Automated |
| Token bootstrap | Invalid room/identity is rejected and the response contains no API secret | Automated |

## Edge and race cases

- Empty/malformed: zero frames, invalid sample rate, unsupported channel count and missing attempt ID.
- Duplicate/repeated: repeated Start or Stop, duplicate final frame and replay-complete callback.
- Late/out-of-order: frames or completion from a superseded attempt.
- Cancellation: before the first frame, mid-capture and after transfer but before replay.
- Partial failure: browser publishes while Python cannot return audio, or returned track exists but cannot autoplay.
- Recovery: reconnect creates a new attempt ID and clears stale transport state.
- Capability mismatch: codec resampling changes bytes or sample rate while preserving intelligible duration.
- Security: browser grants are room-scoped, time-limited, and limited to microphone/data publish plus subscription.

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
