# Expectation handout: realtime responsiveness diagnostics

## User-visible outcome

The existing Gemini Live conversation remains interruptible and exposes enough
attempt-scoped timing evidence to explain a slow response. A human observer can
distinguish end-of-turn delay, model time to first audio and browser playout
instead of reporting one undifferentiated latency estimate.

## Current observation and scope

- Attempt `75d5bf0f-8a39-4f1a-870c-b93811c56426` produced intelligible responses,
  accepted spoken interruptions and shut down cleanly.
- Perceived response latency was approximately 5-10 seconds after a spoken
  query. No stage timestamps were retained, so provider versus implementation
  attribution is not yet supported.
- This sub-slice adds measurements and a bounded tuning seam. It does not add a
  second provider, change presentation behavior or weaken interruption.

## Timings and meanings

| Measurement | Start | End | What it can diagnose |
|---|---|---|---|
| Model TTFT | Provider generation request | Provider first output audio | Gemini/provider generation delay |
| Provider response-start gap | Previous generation completes | Next generation is created | User speech plus provider activity detection between responses; not model TTFT |
| Client-observed turn latency | Browser no longer reports the local participant as active | Browser observes agent state `speaking` | Approximate acoustic-to-playout experience; explicitly less authoritative than server metrics |

The Gemini LiveKit adapter's user lifecycle events occur at generation
boundaries and cannot identify raw microphone start/stop. The earlier
`serverTurnLatencyMs` interpretation is therefore withdrawn. Browser-observed
latency additionally includes WebRTC and playout.

For the headphone-only comparison, construct `AgentSession` with
`aec_warmup_duration=None`. LiveKit Agents otherwise ignores user interruption
audio for the first three seconds of the first speaking turn, which makes the
required first-response barge-in observation impossible by construction.

## Invariants

- Measurements carry the current attempt ID, an increasing sequence number and
  monotonic elapsed milliseconds.
- No credential or transcript text is written to the diagnostic ledger.
- Unknown or unavailable provider fields remain absent; they are never reported
  as zero.
- Realtime model metrics retain TTFT, cancellation, connection reuse and token
  counts when LiveKit exposes them.
- The measured first-response interruption failure justifies disabling the AEC
  warmup for the explicitly headphone-only comparison.
- Gemini endpointing explicitly uses a 500 ms end-of-speech silence window for
  the rerun. This is a reversible latency setting; the diagnostic evidence must
  still show whether endpointing, model TTFT or later transport dominates.
- Page load remains quiet, and diagnostics create no provider calls.

## Observation gate

- Use headphones for one new Gemini attempt of at most three user turns, two
  minutes and one interruption.
- Keep the local diagnostic JSONL row(s), attempt ID and one screenshot.
- Working target: audible response within 3,000 ms of the operator finishing a
  short turn and barge-in stop within 500 ms. These are product targets, not
  claims about provider guarantees.
- If server turn latency is high and model TTFT is low, investigate
  endpointing/framework/playout before changing model.
- If model TTFT accounts for most of the delay, run a separately bounded model
  comparison behind the existing provider-neutral port.

## Exit criteria

- [ ] Offline contracts cover normalized lifecycle and provider metrics.
- [ ] One live attempt records stage timings without transcript content.
- [ ] The 5-10 second delay is attributed to a measured stage.
- [ ] Interruption still passes after instrumentation.
- [ ] Earlier deterministic and transport gates remain green.
