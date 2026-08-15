# Expectation handout: OpenAI Realtime latency comparison

## User-visible outcome

The operator can explicitly select `openai_realtime`, run the same short live
voice conversation through the existing provider-neutral session port, and
compare responsiveness with the failed Gemini observation. Selection never
falls through automatically and the page displays the exact provider/model.

## Evidence motivating the fallback

Gemini attempt `4a188bb9-a400-45d1-9b6d-fcf6e83c6047` completed six
generations. Provider TTFT ranged from 1.927 to 4.772 seconds and did not grow
with context, but successive gaps between generation completion and the next
generation creation were approximately 9.2, 14.9, 11.2, 19.4 and 22.7 seconds.
The operator repeatedly attempted to interrupt during those gaps. This fails
the Slice 3a responsiveness gate and activates the already-defined OpenAI
fallback.

The previous `serverTurnLatencyMs` display is invalid for the Gemini adapter:
its LiveKit plugin emits input-speech lifecycle events at generation boundaries,
not raw microphone speech boundaries. That value must be removed rather than
reinterpreted.

## Configuration contract

- Provider: `openai_realtime`.
- Exact model: `gpt-realtime-2.1-mini`.
- Backend kind: `realtime`.
- Credential: `OPENAI_API_KEY`, read server-side only.
- No tools, presentation actions or automatic cross-provider fallback.
- Stable concise instructions and one provider connection per attempt.
- Disable the three-second AEC interruption warmup for this headphone-only test.
- Realtime session construction remains behind `VoiceSessionFactory`.

## Diagnostic contract

- Realtime metrics normalize TTFT, response duration, token counts, cached input
  tokens, cancellation and connection reuse for either provider.
- The diagnostic ledger derives `providerResponseStartGapMs` from consecutive
  response metrics. It is explicitly a gap containing user speech and provider
  activity detection; it is not mislabeled as model TTFT.
- A new attempt resets all gap state. Missing metrics remain absent.
- No transcript text or credential is written to diagnostics.

## Test and observation matrix

| Case | Oracle |
|---|---|
| OpenAI factory with recording constructors | Exact mini model, voice and instructions; one tool-free `AgentSession` |
| Missing selected OpenAI key | Controlled 503; configured Google key is not used |
| Unsupported provider | Controlled 503 with no provider construction |
| Consecutive metrics | Correct response-start gap; no stale lifecycle pairing |
| Offline regression | All prior Python/frontend/build gates remain green |
| Live comparison | At most three short turns and one interruption in two minutes |

## Usage bound and exit gate

Official OpenAI documentation currently lists `gpt-realtime-2.1-mini` at USD
10/M audio input tokens and USD 20/M audio output tokens, with lower cached
audio input pricing. The live comparison stops after at most two minutes or
three short turns, with a conservative USD 0.25 test ceiling. Exact account
billing remains authoritative in the OpenAI dashboard.

Pass requires:

- audible first response within 3 seconds of the operator finishing a short
  question on at least two of three turns;
- one audible interruption stopping the active response within 500 ms;
- no accumulating 10-20 second inter-generation gap;
- clean explicit Stop and retained attempt diagnostics.

If the OpenAI comparison also fails, do not add another model immediately.
Instrument raw microphone activity and audio-frame arrival across the
browser/LiveKit boundary because the shared transport then becomes the leading
suspect.
