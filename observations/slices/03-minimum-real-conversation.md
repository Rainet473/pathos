# Verified slice: minimum real voice conversation

## Hypothesis

The selected Gemini 2.5 native-audio model can sustain one bounded microphone-in/audio-out conversation with two user interruptions through LiveKit `AgentSession`, while provider-specific SDK types remain outside the domain and presentation controller.

## Observable path

```text
explicit browser Start -> LiveKit room -> provider-neutral session launcher
                       -> LiveKit AgentSession -> selected realtime adapter
                       -> Gemini Live audio response -> browser playout
                       -> two interruptions -> normalized lifecycle evidence
```

## Scope

- New real boundary: LiveKit `AgentSession` and one direct generative speech-to-speech model.
- Still fake/excluded: presentation content selection, narration-beat tools, grounded question routing, slide navigation and the six-slide deck.
- Explicitly excluded: implementing OpenAI and LiveKit Inference in parallel, automatic provider failover, exact scripted narration, custom VAD/DSP and visual polish.

## Entry gate

- [x] Slice 1 transport/recovery and Slice 2 deterministic product gates pass.
- [x] `expectations/minimum-real-conversation.md` defines behavior, provider order and usage bounds.
- [x] The first missing-adapter test is authored and observed failing.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Configuration contract | Construct selected session backend with provider SDKs replaced by recording fakes | Correct model/voice/instructions, no presentation tools, no key leakage |
| Server contract | Request a live session through fake token/session adapters | Quiet preflight, scoped browser token, one launcher call and controlled failure |
| Frontend contract | Exercise attempt reducer and mocked live transport | Quiet initial state, stale-event rejection, duplicate-start protection and cleanup |
| Regression | Run all existing Python/frontend/build gates | Slice 0-2 behavior remains green |
| Live observation | One Gemini session with five turns and two interruptions | Intelligible/relevant responses, both interruptions audible, clean Stop |
| Instrumentation | Retain attempt/turn IDs, provider/model, timestamps, usage and screenshots/recording | Provider behavior and spend are independently inspectable |

## Exit gate

- [x] Offline seam is red first, then green.
- [x] Five-turn Gemini conversation succeeds and spoken interruption works; the
  response-latency gate is split into Slice 3a because the operator observed
  approximately 5-10 seconds after a spoken query.
- [x] Explicit shutdown is visible and controlled.
- [x] Previous tests still pass.
- [ ] Artifacts, usage and limitations are recorded below.

## Fallback or rollback

Keep the passing transport probe and deterministic fake product. Diagnose Gemini only at the new adapter seam for the time box. If the defined Gemini capability gate fails, add an OpenAI adapter for `gpt-realtime-2.1-mini` behind the same session port and run one separately bounded attempt. Do not change domain/controller policy and do not implement both providers pre-emptively.

## Next highest risk

Mapping real provider playout/interruption lifecycle into one application-selected semantic beat without allowing the model to own presentation progress.

## Run evidence

- Date: 16 August 2026.
- Provider decision: Gemini free-tier first; OpenAI `gpt-realtime-2.1-mini` second; LiveKit Inference STT-LLM-TTS third.
- Credential presence was confirmed without printing values: `GOOGLE_API_KEY`, `OPENAI_API_KEY` and existing LiveKit credentials are configured in the ignored `.env`.
- Current official documentation check: LiveKit Agents Google plugin is documented at the 1.5 line; the pinned Gemini 2.5 native-audio preview remains listed by Google and LiveKit. OpenAI officially lists `gpt-realtime-2.1-mini` and automatic best-effort Realtime prompt caching. LiveKit's included Inference credit covers its STT, LLM and TTS catalog rather than direct realtime-provider plugins.
- Red gate: `tests/voice/test_realtime_session_factory.py` initially failed at collection because the Gemini adapter module did not exist. Its five provider-neutral construction and validation cases then passed.
- Dependency compatibility gate: LiveKit Agents `1.5.17` requires `livekit==1.1.8`; after resolving that set, 37 transport/adapter tests passed and the opt-in paid transport test remained skipped.
- Explicit credential/capability smoke requested by the operator: one direct connection to `gemini-2.5-flash-native-audio-preview-12-2025`, one text input (`Say only: okay`), audio output only, no microphone, no LiveKit room and no OpenAI fallback. The response completed, returned 30,720 audio bytes and output transcription `okay`. The provider response did not expose a dollar charge, so no exact cost is claimed.
- Full AgentSession/browser observation: attempt
  `75d5bf0f-8a39-4f1a-870c-b93811c56426` produced intelligible responses,
  accepted spoken interruption and stopped cleanly. Perceived response latency
  was approximately 5-10 seconds, but the run did not retain stage timings, so
  it does not yet distinguish endpointing, provider TTFT or playout. That open
  gate continues in `03a-realtime-responsiveness.md`.
- Full offline regression after the live path was added: dependency check reported no broken requirements; Python `110 passed, 1 skipped` (the opt-in paid LiveKit replay); frontend `30 passed`; production build passed. Vite reported one non-blocking 708 kB single-chunk warning.
- Local readiness: configured backend health returned 200, `/api/live/sessions` appeared in OpenAPI, and the `/live` frontend was served. No room or model request was made by these readiness checks.
