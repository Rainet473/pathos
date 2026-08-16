# Expectation handout: question-reasoning context and turn provenance

## User-visible outcome

An operator can inspect a deterministic inference-context record and identify
which logical presentation turns, provider items, retained text, native tool
events, and application decisions contributed to it. Natural user and assistant
messages remain plain text, and this slice does not change live question-answer
selection or speech behavior.

## Inputs, outputs and boundaries

- Inputs: application turn IDs, session versions, plain user/assistant text,
  optional slide/beat metadata, provider item IDs, delivery outcomes, native tool
  calls/results, and application validation decisions.
- Outputs/events: validated provenance-ledger entries, compact `Turn reference:`
  annotations, ordered provider-neutral context items, deterministic JSON, and a
  LiveKit/OpenAI-compatible formatted projection used only by offline tests.
- External boundaries: the installed LiveKit chat-context formatter; no network
  or model provider call.
- Preconditions: the current live-only release and its offline regression gates
  remain available.
- Non-goals: material search, answer-plan execution, live model tools, answer
  generation changes, slide navigation, continuation changes, provider-wire
  capture, or cache-hit claims.

## Behavior map

```text
plain logical turn + application metadata + provider fragments
  -> provenance ledger validates and resolves the logical turn
  -> compact developer annotation immediately precedes its plain message
  -> native function call/result and decision records retain chronology
  -> deterministic trace JSON and provider-format projection
```

## Invariants

- User and assistant content is stored and formatted as native plain messages,
  never XML or metadata-wrapped prose.
- A `Turn reference:` developer item annotates only the immediately following
  user or assistant item.
- Plans and trace records cite application-owned logical turn IDs, never provider
  item IDs as authority.
- Provider item IDs map to a logical turn without replacing its logical identity.
- Interrupted assistant history contains only actual retained text supplied by
  the runtime; planned or unheard endings are never reconstructed.
- Function calls and function results remain typed context items rather than
  prose embedded in assistant messages.
- Application decisions are trace records, not model messages or state-changing
  tool side effects.
- Serialization is deterministic apart from explicitly recorded capture time.
- The application-visible trace does not claim to be the provider's private wire
  representation.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Ten-turn chronology | Conversation-cited and material-search follow-ups round-trip with stable logical IDs and native tool records | Automated snapshot |
| Plain-message boundary | Annotation and message are adjacent, while message content contains no provenance markup | Automated |
| Interrupted narration | Ledger and context contain only the truncated actual text and an interrupted delivery outcome | Automated |
| Unknown citation | Resolving an unregistered logical turn fails without changing the ledger | Automated |
| Provider formatting | Installed LiveKit formatter preserves developer annotations, plain roles, tool calls, and tool outputs in order | Automated offline adapter test |
| Operator sanity check | Serialized chronology is readable and distinguishes model context from application decisions | Human rubric |

## Edge and race cases

- Empty/malformed: reject blank IDs/text, invalid role-purpose combinations,
  malformed tool arguments/results, and incomplete turn metadata.
- Duplicate/repeated: provider fragments de-duplicate per logical turn; repeated
  identical updates are idempotent; conflicting logical-turn definitions fail.
- Late/out-of-order: provider fragments may attach after turn creation, but an
  unknown or stale session version cannot silently create a cited turn.
- Cancellation: an interrupted turn retains its actual text and never becomes
  completed because a later callback arrives without an explicit valid update.
- Partial failure: rejected application decisions remain observable with a
  bounded reason code and are never represented as accepted model context.
- Recovery: trace JSON round-trips without relying on in-memory object identity.
- Capability mismatch: provider-format tests expose role/tool normalization
  differences; this slice does not compensate by rewriting plain messages.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Chronology | Every annotation, message, tool item, and decision is attributable in order | Tool records pasted into prose or ambiguous adjacency | Serialized turn-10 fixture output |
| Fidelity | Interrupted text is visibly partial and marked interrupted | Invented completion of unheard text | Focused test assertion and sample JSON |
| Boundary clarity | Trace fidelity and application decisions are labeled separately | Claim of exact provider-internal context | Slice ledger note |

## Open assumptions

- The pinned LiveKit 1.5.17 OpenAI-compatible formatter currently preserves
  interleaved `developer` roles and native tool records; the minimum live-planner
  slice must separately verify the closest observable provider-normalized form.
- Provider-fragment grouping beyond explicit IDs remains a later transcript
  concern and must not invent missing words.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Ten-turn fixture round-trips deterministically.
- [x] Every cited turn resolves through the application ledger.
- [x] Interrupted actual-text behavior is covered.
- [x] Native function call/result and application-decision traces are covered.
- [x] Installed provider-format adapter test passes offline.
- [x] All retained offline backend and frontend gates pass.
- [x] Operator sanity case is run and evidence is recorded.
- [x] Deferred risks are explicit.
