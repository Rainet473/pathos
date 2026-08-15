# Expectation handout: LiveKit Inference pipeline comparison

## User-visible outcome

The operator can explicitly select `livekit_inference_pipeline` and run the
same short conversation through a conventional STT -> LLM -> TTS pipeline.
The page identifies the pipeline and its three exact models. It never silently
falls back to Gemini or OpenAI Realtime.

## Current documented starter configuration

LiveKit's Voice AI quickstart, checked on 2026-08-16, recommends:

- STT: `deepgram/nova-3`, language `multi`;
- LLM: `google/gemma-4-31b-it`;
- TTS: `inworld/inworld-tts-2`, voice `Ashley`.

These are accessed through LiveKit Inference and therefore receive the
configured `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` rather than
`GOOGLE_API_KEY` or `OPENAI_API_KEY`.

The current pinned Python SDK (`livekit-agents==1.5.17`) does not expose the
quickstart's newer `inference.TurnDetector` symbol. This slice uses its supported
STT endpointing mode instead of adding an undocumented compatibility shim. The
model trio remains exactly the documented starter trio.

## Construction contract

- All three model clients are built behind `VoiceSessionFactory`.
- Because the application launches `AgentSession` from FastAPI rather than the
  Agent Worker API, the conversation runner owns a LiveKit HTTP context from
  before provider construction until after `AgentSession.aclose()`. A context
  already supplied by a worker remains a nested no-op.
- `AgentSession` receives explicit STT, LLM and TTS instances and STT turn
  detection.
- The headphone-only observation disables the framework's three-second AEC
  interruption warmup so a first-response barge-in is observable.
- No provider key, transcript text or generated prose enters browser identity
  or diagnostic records.
- Diagnostics keep endpointing, LLM first-token, TTS first-byte and interruption
  detection timings distinct rather than collapsing them into one latency.

## Deterministic cases

| Case | Oracle |
|---|---|
| Recording constructors | Exact model IDs, language, voice and STT endpointing |
| FastAPI runner lifecycle | HTTP context enters before model construction and exits after agent close |
| Start/provider failure | Agent, room and HTTP context are each released once |
| Explicit provider selection | Pipeline registers without Google/OpenAI keys |
| Missing LiveKit credentials | Existing controlled startup failure remains |
| Gemini/OpenAI selected | Pipeline constructors are never used as fallback |
| Regression | All existing offline tests and frontend build remain green |

## Bounded live observation

Run at most three short turns and one interruption, stopping within two minutes.
Record perceived end-of-speech to audible response, provider stage metrics when
available, first-response interruption behavior, and whether latency accumulates.

Pass requires an audible response within three seconds on at least two of three
turns, one interruption stopping active audio within 500 ms, no accumulating
10-20 second gap, and a clean explicit Stop.
