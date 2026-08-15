# Slice 3a observation: realtime responsiveness

## Hypothesis

The existing Gemini Live path can expose enough normalized lifecycle and
provider timing data to locate the reported 5-10 second response delay without
changing the working interruption behavior or adding another paid provider.

## Entry evidence

- Manual attempt: `75d5bf0f-8a39-4f1a-870c-b93811c56426`.
- Provider/model: `gemini_live` /
  `gemini-2.5-flash-native-audio-preview-12-2025`.
- Local attempt duration: 136.544 seconds; four LiveKit participant-minutes as a
  conservative upper bound.
- Passed: intelligible responses, spoken interruption and explicit Stop.
- Failed: perceived post-query latency, approximately 5-10 seconds.
- Missing evidence: end-of-turn, model TTFT and first-playout timestamps.

## Planned observable path

```text
user/agent lifecycle events -> normalized attempt timeline -> local JSONL
provider metrics            -> TTFT and usage fields        -> same timeline
browser state changes       -> client-observed latency      -> visible summary
```

## Exit evidence

- Attempt `4a188bb9-a400-45d1-9b6d-fcf6e83c6047` ran for 152.175 seconds and
  completed six Gemini generations.
- Model TTFT values: 3.443, 3.744, 4.772, 2.907, 2.500 and 1.927 seconds.
- Input token counts grew from 469 to 2,316 without monotonically increasing
  TTFT, ruling out context growth as the cause of the accumulating delay.
- Gaps between generation completion and the next generation creation were
  approximately 9.2, 14.9, 11.2, 19.4 and 22.7 seconds.
- The UI's 24.60-second `server turn to speech` value was a telemetry defect:
  Gemini/LiveKit user-state events bracket a generation rather than raw user
  speech. The value paired different turns and is withdrawn.
- Result: responsiveness gate failed. Proceed to the bounded OpenAI Realtime
  mini comparison; if the shared symptom remains, instrument raw microphone
  frame activity next.
- Follow-up attempt `091b2a5c-fda2-4d3a-9747-ff4e903eb6eb` ran for 38.975
  seconds. The first generation began at 4.519 seconds, first audio arrived
  6.050 seconds later, and generation completed at 16.584 seconds. The operator
  attempted to interrupt that first response, but no provider interruption or
  cancellation appeared and the generation completed normally. The second
  response began at 19.739 seconds with 1.571-second TTFT.
- The exact Gemini model reports caching as unsupported in Google's current
  model documentation. Context-window compression addresses long-session
  lifetime and compounding context cost; this short attempt grew only from 539
  to 837 input tokens, so caching/compression is not a plausible remedy for the
  missing interruption event.
- A shared implementation constraint also affected the first-response test:
  LiveKit Agents 1.5.17 defaults to a three-second AEC warmup during which user
  interruption audio is ignored. The UI requires headphones, so all comparison
  factories now explicitly disable this warmup. This explains why an early
  first-response barge-in may be ignored, but it does not explain the later
  10-22 second inter-generation gaps.
- The invalid lifecycle-derived `serverTurnLatencyMs` and
  `bargeInStopLatencyMs` fields were removed. Realtime response gaps now come
  only from consecutive provider metrics; the pipeline additionally reports
  endpointing, LLM first token, TTS first audio and interruption detection as
  separate stages.
- Deterministic exit gates after adding the OpenAI mini and LiveKit Inference
  comparison factories: 126 Python tests passed with one opt-in live test
  skipped, 31 frontend tests passed, production build passed, and `pip check`
  found no broken requirements.

## LiveKit Inference first-run incident

- The first pipeline attempt returned HTTP 201 but never answered. Both the STT
  stream and TTS connection-pool prewarm then failed with `Attempted to use an
  http session outside of a job context` and `AgentSession` closed.
- Cause: the application deliberately uses its own FastAPI launcher rather than
  LiveKit's Agent Worker API, but the pipeline's inference clients require an
  explicitly owned `livekit.agents.utils.http_context` in that execution mode.
- Required correction: enter the HTTP context before provider construction,
  keep it alive for the full `AgentSession`, and exit only after agent cleanup.
