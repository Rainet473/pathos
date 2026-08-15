# Expectation handout: one real presentation action

## User-visible outcome

The live page is quiet until Start. Start narrates the application-selected
engine-braking beat through the configured LiveKit inference pipeline. If the
listener speaks during narration, audible playout stops, the active beat remains
uncommitted, and the spoken question is answered from the selected slide material.
After a plain question the application waits. An explicit request to continue
authorizes narration to resume from the same uncommitted beat.

## Inputs, outputs and boundaries

- Inputs: Start, browser microphone audio, a spoken question, an optional explicit
  continuation request, and LiveKit speech lifecycle callbacks.
- Outputs/events: presentation snapshot, transcript entries, domain events, and
  provider-neutral narration or answer requests identified by turn ID.
- External boundaries: browser to LiveKit room; Deepgram speech-to-text; Gemma text
  generation; Inworld text-to-speech; LiveKit playout lifecycle.
- Preconditions: the one-slide content fixture validates; the selected LiveKit
  inference pipeline can join the room and carry an interruptible voice turn.
- Non-goals: six-slide breadth, arbitrary slide navigation, temporary question
  slides, provider fallback, deployment, and qualitative claims based only on
  deterministic tests.

## Behavior map

```text
ready --Start--> presenting --audio starts--> presenting
                            |                    |
                            | full playout       | listener speaks
                            v                    v
                        completed           interrupted
                                                 |
                                      validated grounded question
                                                 v
                                             answering
                                              /      \
                                  plain answer        answer + continue
                                       v                    v
                                    waiting             presenting
                                                            |
                                                   same beat selected
```

The application selects content and validates every transition. Provider callbacks
carry facts about speech and intent; they do not mutate presentation state directly.

## Invariants

- Page load never starts narration or a provider connection.
- The semantic presentation cursor remains separate from the visible slide.
- Only completed narration playout commits a beat.
- Interrupted narration preserves the active cursor and does not emit
  `beat_committed`.
- Every playout callback is correlated to the application-issued turn ID; stale,
  duplicate, and out-of-order callbacks cannot advance state.
- A normal question defaults to `ask_before_continuing`; continuation requires an
  explicit user request.
- The application supplies selected slide evidence for the grounded answer.
- Generated prose is never parsed to decide presentation navigation.
- No provider-specific object enters the domain package.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Start and hear the whole beat | The matching narration turn commits once and the one-beat deck completes | Automated |
| Interrupt narration | Audio stops and the cursor remains on beat 1, uncommitted | Automated plus human rubric |
| Ask the fixed engine-braking question | The answer request contains the question and selected deep-dive evidence | Automated |
| Plain question finishes | The phase becomes waiting; narration does not resume | Automated plus human rubric |
| Say "continue after answering" | Answer completion selects the same beat with a new narration turn | Automated plus human rubric |
| Late completion for interrupted narration | A stale-response event is emitted and state is unchanged | Automated |
| Unsupported model intent | The command is rejected without state mutation | Automated |

## Edge and race cases

- Empty/malformed: blank questions, turn IDs, and unsupported intent payloads are
  rejected before controller mutation.
- Duplicate/repeated: duplicate playout completion becomes stale and never commits
  twice; repeated Start is rejected.
- Late/out-of-order: callbacks whose turn ID or purpose does not match the active
  playout are stale.
- Cancellation: stopping a live attempt interrupts or closes the active speech
  handle before releasing the room and provider session.
- Partial failure: provider or playout failure is visible to the client and leaves
  the current beat uncommitted.
- Recovery: this slice starts a fresh attempt; reconnecting an in-flight attempt is
  deferred.
- Capability mismatch: if typed intent delivery or interruptible speech cannot be
  mapped by the selected pipeline, Slice 3 remains the fallback demonstration.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Quiet start | No room/model activity before Start | Connection or speech begins on load | Browser screenshot and backend log |
| Grounding | Answer explains low-gear engine braking using fixture concepts without invented specifics | Unsupported values or unrelated explanation | Transcript and selected evidence ID |
| Interruption | Narration becomes inaudible promptly and no beat commit occurs | Old narration continues or beat advances | Recording and event timestamps |
| Default wait | Silence follows the answer until explicit Continue | Narration resumes automatically | Transcript and event log |
| Authorized resume | "Continue after answering" returns to the same beat coherently | Wrong beat, wrong slide, or no resume | Recording and event log |
| Responsiveness | No accumulating turn queue; stage metrics remain visible | Later responses accumulate multi-second backlog | Provider metrics and attempt ID |

## Open assumptions

- The selected Gemma inference model reliably emits the one typed question intent
  needed by this slice when constrained by the application prompt.
- LiveKit's speech handle lifecycle can be normalized into started, interrupted,
  and completed facts without treating text generation completion as playout
  completion.
- Resume replays the small uncommitted beat rather than attempting word-level audio
  continuation.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [ ] Observation cases were run and evidence was recorded.
- [x] Deferred risks are explicit.
