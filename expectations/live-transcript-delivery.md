# Expectation handout: reliable live transcript delivery

## User-visible outcome

During a live presentation, the transcript panel shows stable user and agent
turns instead of remaining at zero segments. Interim user speech may update in
place; completed user and agent turns remain visible for the attempt.

## Inputs, outputs and boundaries

- Inputs: LiveKit `user_input_transcribed` and `conversation_item_added`
  session events.
- Outputs/events: provider-neutral transcript updates published on a dedicated,
  reliable LiveKit data topic and normalized by the browser transport.
- External boundaries: LiveKit AgentSession events and room data packets.
- Preconditions: the browser and Python worker have joined the same live
  attempt and the worker knows the intended browser identity.
- Non-goals: word-level audio alignment, durable transcript storage,
  retransmission after refresh, or treating transcript text as presentation
  navigation input.

## Behavior map

```text
provider session event
  -> validate role/text/finality
  -> assign attempt-scoped sequence and stable entry identity
  -> reliable worker data packet
  -> browser validates attempt + packet schema
  -> reducer inserts or replaces transcript entry by ID
```

## Invariants

- Transcript packets contain no provider SDK types.
- Every packet is tied to exactly one attempt and has a monotonically increasing
  sequence number.
- Consecutive interim user fragments for one utterance reuse one entry ID; the
  final fragment closes that entry.
- Blank fragments and unsupported conversation roles are ignored.
- Assistant conversation items are final transcript entries.
- A packet from another attempt or a non-worker participant cannot mutate the
  current browser transcript.
- Native LiveKit transcription events may remain as a compatibility fallback,
  but duplicate entry IDs cannot produce duplicate visible rows.
- Transcript content never drives domain transitions or slide navigation.
- A transcript publication failure is logged and does not terminate speech or
  mutate presentation state.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Interim then final user speech | One user row updates in place and becomes final | Automated |
| Assistant item committed | One final agent row appears | Automated |
| Blank or unsupported item | No packet is published | Automated |
| Wrong attempt or sender | Browser ignores the packet | Automated |
| Publish failure | Conversation continues and failure is logged | Automated |
| Live question and answer | Both final turns remain visible in the panel | Human rubric |

## Edge and race cases

- Empty/malformed: blank text and malformed JSON are ignored.
- Duplicate/repeated: identical entry IDs replace rather than append.
- Late/out-of-order: the browser rejects packets whose sequence is not newer
  than the last accepted server transcript sequence.
- Cancellation: an interrupted assistant response may be absent or may contain
  only the provider's committed transcript; it must not be fabricated.
- Partial failure: transcript publication failure does not fail the voice turn.
- Recovery: a new attempt resets transcript entries and accepted sequence.
- Capability mismatch: provider-native room transcription is optional because
  normalized AgentSession events are the authoritative UI feed.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| User turn | Final spoken question appears once | Missing or duplicated question | Attempt ID and screenshot |
| Agent turn | Final answer appears once | Panel remains empty after answer | Attempt ID and screenshot |
| Isolation | New attempt begins with no old transcript | Prior attempt rows remain | Screenshot |
| Voice behavior | Transcript bridge does not delay or stop speech | New audible stall or failed turn | Timing cards and backend log |

## Open assumptions

- LiveKit 1.5.17 emits final assistant text through
  `conversation_item_added` for the configured inference pipeline.
- Interim user events for one utterance arrive serially on the session event
  loop.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [ ] Observation cases were run and evidence was recorded.
- [x] Deferred risks are explicit.
