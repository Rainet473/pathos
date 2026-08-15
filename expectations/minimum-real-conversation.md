# Expectation handout: minimum real voice conversation

## User-visible outcome

A user explicitly starts one live voice session, speaks naturally to one
generative voice model, hears concise spoken responses, and can interrupt the
agent while it is talking. The page identifies the active provider/model and
shows connection, listening, speaking, interrupted, completed and failed states
without exposing credentials.

## Inputs, outputs and boundaries

- Inputs: explicit user start/stop actions, browser microphone audio, stable system instructions and an operator-selected runtime configuration.
- Outputs/events: normalized session state, stable transcripts when available, turn/interruption timestamps, provider/model identity and usage metadata exposed by the runtime.
- External boundaries: browser media, LiveKit Cloud WebRTC, LiveKit Python `AgentSession`, and one selected model backend.
- Preconditions: working Slice 1 transport, valid LiveKit credentials, headphones and exactly one configured provider credential for a direct realtime model.
- Non-goals: slide content, presentation tools, narration cursors, grounded motorcycle answers, exact scripted speech, automatic cross-provider failover, visual polish and six-slide breadth.

## Provider order and universal seam

The application selects one backend before a session begins:

1. `gemini_live`: direct Gemini Live speech-to-speech through the LiveKit Google plugin, using `gemini-2.5-flash-native-audio-preview-12-2025`.
2. `openai_realtime`: direct OpenAI Realtime speech-to-speech through the LiveKit OpenAI plugin, using `gpt-realtime-2.1-mini` only after the Gemini capability gate fails.
3. `livekit_inference_pipeline`: LiveKit Inference STT -> LLM -> TTS only after both direct realtime candidates fail or a later requirement proves that scripted output/transcript timing needs the cascade.

All three configurations are constructed behind one provider-neutral session
port. A provider failure is reported; it never silently spends quota on the
next backend. Provider SDK objects remain inside adapters.

## Behavior map

```text
quiet
  -> explicit Start -> connecting -> listening <-> speaking
                                      -> user speech while speaking -> interrupted -> listening
  -> explicit Stop / bounded timeout -> disconnected
  -> provider or transport error -> failed -> fresh explicit attempt
```

## Invariants

- Page load creates no LiveKit room and invokes no model.
- One explicit start selects one provider for the entire attempt.
- The browser receives only a room URL and scoped participant token; provider and LiveKit secrets remain server-side.
- No presentation/domain tool is registered in Slice 3.
- Provider callbacks are normalized before application/UI code observes them.
- Each attempt and turn has an identity; late events from an older attempt do not mutate the current session.
- Interruption does not fabricate a transcript, answer or completed turn.
- Stop, disconnect, timeout and failure release microphone, room and model resources.
- OpenAI prompt caching is treated as automatic best-effort optimization, not a correctness dependency; instructions remain stable during a session and cache metrics are recorded when available.
- Fallback activation is an operator decision after evidence, never an automatic retry.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Page load | Quiet/disconnected; no worker or model request | Automated plus browser observation |
| Five short turns | Five intelligible, relevant spoken responses in one bounded session | Human rubric plus timestamps |
| Interrupt twice | Current speech stops and the session accepts the new utterance twice | Human rubric plus normalized events |
| Provider config | One selected backend maps to one AgentSession configuration with no presentation tools | Automated |
| Missing selected key | Controlled preflight failure before room/model startup | Automated |
| Provider error | Visible failure; no implicit request to a fallback provider | Automated |
| Stale callback | Older attempt cannot change current UI/session state | Automated |
| Explicit stop | Microphone, room and provider session close once | Automated plus observation |

## Edge and race cases

- Empty/malformed: blank provider/model/voice/instructions and unsupported provider identifiers fail before connection.
- Duplicate/repeated: repeated Start while connecting/active is ignored; Stop is idempotent.
- Late/out-of-order: callbacks carry attempt identity and stale callbacks are discarded.
- Cancellation: before model connection, during agent speech and after an interruption all release resources.
- Partial failure: room succeeds but model connection fails, or model responds while browser audio playback is blocked.
- Recovery: a failed attempt can be followed by one fresh attempt with the same explicitly selected provider.
- Capability mismatch: direct realtime models may delay transcripts and cannot guarantee exact scripted speech; those are not disguised as test failures in Slice 3.
- Security/privacy: unpaid Gemini content is non-sensitive test material because its free-tier terms permit product-improvement use.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Conversation | Five relevant, concise, intelligible turns | Silence, unrelated responses or repeated hangs | Attempt ID, stable transcript and recording |
| Interruption | Agent audibly stops twice and accepts the new utterance | Agent talks over the user or loses the new turn | Event timestamps and recording |
| Quiet start | No room/model activity before Start | Autoconnect or unsolicited speech | Initial screenshot and server log |
| Visibility | Connection/speaking/listening/failure are distinguishable | Frozen or falsely completed UI | Screenshots and event log |
| Resource control | Explicit Stop or timeout closes the attempt | Microphone/session remains active | Shutdown event and usage row |

## Usage and fallback bounds

- No live request runs until the implementation passes all offline gates and the operator-visible hypothesis/bound is announced again.
- Gemini gate: one session, at most five user turns and two interruptions, at most three wall-clock minutes, using only non-sensitive motorcycle-demo phrases.
- OpenAI fallback gate: only if Gemini fails its defined capability gate; one session, at most five turns and three wall-clock minutes, with a conservative stop target of USD 0.25 from the user's existing API credit.
- LiveKit Inference fallback: only if both direct realtime candidates fail or a cascade-specific requirement is established; announce a separate model selection and credit bound first.

## Open assumptions

- The pinned Gemini preview remains accessible to the configured Google project and compatible with the installed LiveKit Google plugin.
- `AgentSession` exposes enough normalized lifecycle/metrics events for this slice without presentation tools.
- Provider usage details may require adapter-specific instrumentation even though session lifecycle uses one normalized port.

## Exit criteria

- [x] Behavior and provider order were written before implementation.
- [x] New offline tests fail for the intended missing-adapter reason.
- [x] Deterministic Python/frontend suites pass offline.
- [ ] One bounded real-provider observation passes five turns and two interruptions.
- [ ] Provider/model versions, usage, artifacts and limitations are recorded.
- [x] Earlier fake and transport gates remain green.
