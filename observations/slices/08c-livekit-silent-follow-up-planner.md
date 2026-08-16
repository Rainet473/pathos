# Verified slice: silent LiveKit follow-up planner

## Hypothesis

The selected LiveKit Inference Gemma route can emit the native bounded search and
terminal-plan protocol reliably enough for application validation, without an
AgentSession or any speech side effect.

## Observable path

```text
recorded active follow-up context
  -> real LiveKit Inference text LLM
  -> native search/submit calls
  -> deterministic Slice 2 execution and validation
  -> sanitized live planning record
```

## Scope

- New real boundary: LiveKit Inference text completion with
  `google/gemma-4-31b-it`, native tools, provider usage, and normalized roles.
- Still deterministic: deck search, provenance, validation, application state,
  and the two recorded follow-up inputs.
- Explicitly excluded: STT, TTS, LiveKit rooms, browser UI, answer generation,
  focus navigation, narration resumption, and production-path activation.

## Entry gate

- [x] Context/provenance and deterministic planning/search slices are committed.
- [x] Expectation handout exists before source changes.
- [x] Pinned LiveKit SDK behavior and configured credential names were inspected.
- [x] First failing adapter tests are defined and observed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Schema/format | Offline tests over real LiveKit chat/tool types | Two tools only; aliases/bounds and turn-reference adjacency survive normalization |
| Protocol | Scripted LLM chunks through the real adapter loop | Conversation and search paths accept; invalid/multiple/text-only paths stop |
| Authority | Invalid proposal and controller non-mutation checks | Only application-validated plan data exits |
| Live provider | One opt-in two-case Gemma probe | Native arguments validate and one terminal decision occurs per case |
| Instrumentation | Sanitized request evidence | Request IDs, roles, latency, usage, and cache tokens are present or explicitly unavailable |
| Regression | Repository check script | All previous offline Python/frontend/build gates remain green |

## Planned live usage ceiling

- Two fixed text-only cases.
- Expected passing path: three requests without correction, or four when one
  conversation-plan schema correction is needed.
- Hard rerun ceiling: five requests. The second case starts only if the
  conversation case succeeds within its two-request correction allowance; the
  material case may then consume its three-request application ceiling.
- No retries, rooms, participants, STT, TTS, audio, or browser session.
- At most 512 completion tokens per request. Actual provider-reported token usage
  will be recorded before claiming the gate passed.

## Exit gate

- [x] Both native-tool paths succeed in the opt-in live probe.
- [x] Terminal plan occurs once per case and all citations validate.
- [x] No speech-capable dependency or presentation mutation is used.
- [x] Provider normalization and usage evidence are retained.
- [x] Previous tests still pass.
- [x] Artifacts, limitations, and next risk are recorded.

## Recorded evidence

### Red baseline and deterministic gates

- Before implementation, the adapter and live-probe modules both failed
  collection because `voice_presentation.adapters.livekit.silent_planner` did
  not exist.
- Requirement-audit tests then independently exposed incorrect turn-reference
  adjacency, missing post-search direction, non-explicit provider defaults, and
  the absent one-correction path before each fix.
- Final adapter/probe gate: 12 deterministic tests passed and the opt-in live
  probe skipped by default.
- Final repository gate: 242 Python tests passed and two live tests skipped by
  default. Dependency checking reported no broken requirements.
- Frontend gate: 7 files and 34 tests passed; type-check and production build
  succeeded. Vite retained the pre-existing approximately 708 kB chunk warning.
- `git diff --check` passed.

### Provider findings and corrections

The first reachable provider run exposed three repeated searches for the direct
conversation reference. The trace showed that the application snapshot had been
inserted between the active `Turn reference` and its user message. Restoring
immediate annotation adjacency changed Gemma to a direct terminal call.

The next calls exposed two cross-field schema variants that JSON Schema had not
made sufficiently clear: a focus slide missing from supporting slides, and
combined grounding without deck evidence. The provider-facing schema now makes
all defaulted fields explicit, the stable protocol states the focus/support
rule, and one parseable Pydantic failure may receive one sanitized correction.
Application-invalid IDs and a second invalid schema remain terminal.

The original observation harness also allowed both cases to consume their
per-case maximum, so its stated three-request ceiling was not a real worst-case
cap. That first external attempt used six requests. The corrected harness stops
before case two unless case one passes within two requests and now has a true
five-request maximum. This budget correction was made before the final live
gate.

### Successful live observations

Two complete two-case observations reached accepted application plans with the
final prompt/schema behavior:

- Conversation reference: one native `submit_answer_plan`; accepted
  `answer-plan-0003`; cited `narration-0002` (and, in observed runs, optionally
  the preceding `narration-0001`); no deck evidence or search.
- Material question: one native `search_material` followed by one native
  `submit_answer_plan`; accepted `answer-plan-0007`; cited
  `motorcycle-controls.clutch-and-gears.narration.1`.
- Each run produced exactly one accepted application decision per case. No
  AgentSession, room, STT, TTS, speech handle, controller mutation, navigation,
  or continuation action existed in the path.

The final run used three requests, 4,518 total tokens, zero provider-reported
cached prompt tokens, and approximately 4.88 seconds of aggregate provider
request duration. The prior complete successful run used 4,908 total tokens and
also reported zero cached tokens. Native role evidence retained system,
developer, assistant, and user messages; after search, the next request ended in
an assistant tool call followed by a tool result.

Across all diagnosis and success attempts, the local ledger contains 16 actual
provider requests, 23,597 total tokens, and 3,584 provider-reported cached prompt
tokens. Two initial sandbox-blocked records contain zero external requests. This
larger diagnostic total includes the six-request harness-budget mistake and
three one-request schema diagnostics; it is not the expected cost of the final
three-request passing path.

Sanitized evidence is retained locally in
`.runtime/livekit-silent-planning.jsonl`, which is ignored and not committed. It
contains request IDs, role sequences, tool names, timing, usage, cache counts,
validated traces, and fixed validation messages, but no raw model prose or
hidden reasoning.

## Oracle changes made from real evidence

- The application snapshot moved before the active turn annotation so `Turn
  reference` remains immediately adjacent to its plain message.
- Provider schemas require every field explicitly while preserving nullability;
  the application models remain the final validator.
- Search output now reports remaining allowance and forbids repeating the same
  query; after two searches the provider sees only the terminal tool.
- One parseable schema/coherence failure may self-correct once through a native
  error result. Malformed JSON and application rejections do not retry.
- The live harness budget was changed from an assumed three-request maximum to
  an expected three/four and hard five-request ceiling.

## Files in this slice

- `backend/src/voice_presentation/adapters/livekit/silent_planner.py`
- `backend/src/voice_presentation/adapters/livekit/context_format.py`
- `tests/adapters/test_livekit_silent_planner.py`
- `tests/live/test_livekit_gemma_planner.py`
- `expectations/livekit-silent-follow-up-planner.md`
- `observations/slices/08c-livekit-silent-follow-up-planner.md`

The current live lexical question path and all speech, controller, transport,
and browser behavior remain unchanged.

## Remaining risks

- The self-correction branch is deterministic-test verified but was not needed
  on the final passing live run; model variance remains measurable rather than
  eliminated.
- Cached input was nonzero on some diagnostic repetitions but zero on both
  complete successful runs, so no prompt-cache performance claim is justified.
- Larger histories, other presentations, cancellation during a real provider
  stream, reconnects, and concurrent follow-ups remain unobserved.
- Tool-disabled streamed answer generation, TTS timing, browser status,
  interruption settlement, focus navigation, and continuation remain future
  gated slices.

## Fallback or rollback

The committed deterministic Slice 2 harness remains runnable and the current
live lexical answer path remains unchanged. If the provider cannot follow the
tool contract, the adapter can be removed without changing domain state,
transport, speech, navigation, or browser behavior.

## Next highest risk

Whether an accepted plan can drive tool-disabled streamed answer generation
through TTS while preserving interruption, verified playout settlement, default
waiting, and explicit answer-and-continue permission.
