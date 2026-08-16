# Expectation handout: silent LiveKit follow-up planner

## User-visible outcome

An operator can run two opt-in text-only probes against the selected LiveKit
Inference Gemma model and inspect a bounded, validated plan for a conversation
reference and a deck-search question. The probe cannot produce audio, move a
slide, resume narration, or bypass application validation.

## Inputs, outputs and boundaries

- Inputs: one provenance-aware context ending at the active user follow-up, the
  active planning snapshot, the packaged deck, and the two Slice 2 tool schemas.
- Outputs/events: native LiveKit function calls, application-produced function
  results, one accepted or rejected application decision, per-request timing and
  token usage, cached-input tokens when reported, and provider-normalized role
  sequences without hidden reasoning text.
- External boundary: `livekit.agents.inference.LLM` using
  `google/gemma-4-31b-it` and the configured LiveKit credentials.
- Preconditions: Slices 1 and 2 are green; the live probe is explicitly enabled
  and credentials are present.
- Non-goals: AgentSession, STT, TTS, rooms, browser state, final-answer
  generation, slide navigation, continuation, prompt-cache optimization, or
  changes to the current live question path.

## Behavior map

```text
plain native context ending at active follow-up
  -> silent LiveKit Inference chat with search_material + submit_answer_plan
  -> exactly one native tool call in each provider response
  -> application executes search or validates terminal proposal
  -> native call/output appended for another bounded request when needed
  -> accepted plan or controlled failure; never speech or state mutation
```

## Invariants

- Only the two planning tools are registered, with schemas derived from the
  provider-neutral Slice 2 models.
- Provider-facing raw schemas make every defaulted field explicit while keeping
  nullable fields nullable. Cross-field rules that JSON Schema cannot express,
  such as `focusSlideId` also appearing in `supportingSlideIds`, are stated in
  the stable protocol and still revalidated by the application.
- The first provider request uses required tool choice and disables parallel tool
  calls. At most three provider requests and two searches are possible.
- The supplied reasoning snapshot ends at the active follow-up; later turns are
  rejected before any provider request.
- Plain user and assistant content stays in native message roles. Compact
  developer turn references remain immediately before their annotated message.
- The application snapshot is inserted immediately before the active turn's
  developer annotation. The `Turn reference` therefore remains immediately
  before the plain user follow-up, which remains the final message.
- Every provider response must contain exactly one native function call. Text
  emitted beside a call is discarded and counted; text without a call is a
  controlled failure.
- One parseable JSON call that fails the provider-neutral Pydantic contract may
  receive one sanitized validation-error result and one correction attempt.
  Malformed JSON, a second schema failure, or an application-invalid proposal
  remains terminal.
- Search output comes only from the deterministic deck-local Slice 2 search.
  Provider-supplied arguments never become trusted evidence.
- A successful search output states the remaining search allowance and directs
  the model not to repeat the same query; after the allowance is exhausted, only
  the terminal submission tool is exposed.
- A terminal proposal is accepted only through `FollowUpPlanningSession`.
  Invalid schema, IDs, scope/source combinations, focus, session identity, or
  stale/cancelled state cannot produce a plan.
- The adapter directly uses the text LLM client. It has no speech, room,
  controller, navigation, or presentation-session dependency.
- Provider retries are disabled for the live probe. A single run is capped at
  the planning deadline and a per-request completion-token ceiling.
- Timing, prompt/completion/total tokens, and provider-reported cached prompt
  tokens are recorded per request. Zero cached tokens is reported as evidence,
  not interpreted as a caching guarantee.
- Raw model prose or hidden reasoning is not retained in the observation log.
  Invalid arguments retain only JSON/validation error locations and types, never
  raw untrusted values.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Conversation reference | One `submit_answer_plan` call cites the interrupted narration turn and is accepted without search | Offline adapter test + opt-in live probe |
| Deck question | One `search_material` call is followed by one terminal plan citing returned evidence | Offline adapter test + opt-in live probe |
| Provider preamble | Text accompanying one valid tool call is discarded and counted, never exposed as speech | Automated |
| Text-only response | Run terminates with `missing_tool_call`; no answer or plan is fabricated | Automated |
| Multiple/unknown tool calls | Run terminates with an explicit provider-protocol failure | Automated |
| Schema correction | One parseable incoherent call receives a sanitized tool error and may correct once | Automated + live |
| Invalid terminal proposal | Application rejection is retained and no accepted plan exists | Automated |
| Live sanity case | Both cases expose native tool chronology, roles, latency, and token usage | Operator rubric |

## Edge and race cases

- Empty/malformed: malformed JSON stops the run. One parseable schema-invalid
  call may self-correct once; a repeated failure stops the run.
- Duplicate/repeated: more than one call in a provider response and attempts past
  the Slice 2 tool limits cannot be accepted.
- Late/out-of-order: active session/follow-up identity is checked by the
  application on every tool action.
- Cancellation: total planning timeout cancels the application transaction and
  closes the active stream.
- Partial failure: provider/API failures retain sanitized type information and
  do not fall through to free-form answers.
- Recovery: a fresh planner instance can retry a case; a rejected transaction is
  never reused.
- Capability mismatch: if Gemma or LiveKit normalizes roles/tools incompatibly,
  the live gate remains failed and Slice 2 stays the fallback.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Native tools | One call per response; search result is fed back before submit | Prose-only answer, parallel calls, or parsed navigation prose | Sanitized JSONL trace |
| Validation | Accepted IDs resolve through Slice 1/2 state | Provider output trusted directly | Application decision and cited IDs |
| Silence | No AgentSession, TTS, room, or speech handle exists | Any audio or `generate_reply` path | Dependency/test assertions |
| Normalization | System/developer/user roles and assistant/tool continuation are observable | Turn annotations merge into spoken user/assistant text | Provider-role sequences |
| Usage | Request count, timing, tokens, and cache fields are explicit | Unbounded retries or assumed caching | Per-request telemetry |

## Open assumptions

- The live observations establish that LiveKit Inference accepts the normalized
  Pydantic-derived schemas and honors native required/named tool choice for the
  selected Gemma route.
- Prompt-cache behavior is variable: diagnostic repetitions reported cached
  input, while both complete successful observations reported zero cached input.
- Larger histories, other decks, disconnect races, and production concurrency
  remain unmeasured.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic adapter and protocol tests pass offline.
- [x] Both bounded live cases produce valid native tool arguments and exactly one
  terminal application decision.
- [x] No speech or presentation state mutation occurs.
- [x] Provider role/schema normalization, timing, tokens, and cached input are
  recorded.
- [x] All retained repository gates pass.
- [x] Deferred answer streaming, UI, navigation, and caching risks are explicit.
