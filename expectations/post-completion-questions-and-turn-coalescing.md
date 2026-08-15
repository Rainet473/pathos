# Expectation handout: post-completion questions and coherent user turns

## User-visible outcome

The listener can ask a question immediately after the final narration finishes and
still receive one spoken answer. The presentation remains complete after that
answer. Natural pauses inside one spoken question do not create several visible
user rows.

## Inputs, outputs and boundaries

- Inputs: a final narration playout completion, subsequent microphone speech,
  LiveKit STT endpoint decisions, and normalized user transcript events.
- Outputs/events: one application-authorized answer turn, a completed presentation
  snapshot after answer playout, and one progressively updated visible user entry.
- External boundaries: LiveKit turn detection, AgentSession user-turn callbacks,
  STT transcript callbacks, provider generation and TTS playout.
- Preconditions: the application-controlled one-beat presentation and normalized
  transcript channel already pass their offline gates.
- Non-goals: semantic merging of unrelated questions, durable transcript repair,
  or changing the question-scope classifier.

## Behavior map

```text
presenting --final narration playout--> completed
                                           |
                                      user question
                                           v
                                       answering
                                           |
                                  verified answer playout
                                           v
                                       completed

closely spaced STT fragments --before assistant reply--> one visible user entry
```

## Invariants

- `completed` remains terminal for narration but not for conversation.
- A post-completion question issues an answer turn without selecting or replaying
  another narration beat.
- Completing that answer returns to `completed`, including when the user says
  "continue" after the deck has no remaining narration.
- The final beat remains committed exactly once and no second
  `presentation_completed` event is fabricated for the answer.
- An interrupted post-completion answer may be replaced by a follow-up answer, but
  its eventual return phase remains `completed`.
- STT fragments separated by at most 1.5 seconds, with no intervening assistant
  item, reuse one transcript ID and append text in order.
- An assistant item, a blank final boundary, or a longer pause closes the merge
  group so unrelated user turns remain separate.
- Transcript grouping never decides application state or slide navigation.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Ask just after the final beat | One answer is generated and spoken | Automated plus human rubric |
| Post-completion answer finishes | Phase returns to `completed`; beat count is unchanged | Automated |
| Say "answer and continue" after completion | Answer finishes in `completed`; no narration generation follows | Automated |
| Pause briefly twice inside one question | The panel shows one accumulated user row | Automated plus human rubric |
| Speak again after the assistant replies | A new user row is created | Automated |
| Pause longer than the merge window | A new user row is created | Automated |

## Edge and race cases

- Boundary race: whether speech is classified immediately before or after final
  narration commitment, the question remains answerable.
- Duplicate completion: stale narration and answer callbacks cannot recommit the
  beat or generate another answer.
- Partial answer interruption: the saved answer return phase survives and a later
  completed answer still returns to `completed`.
- Endpointing tradeoff: a 1.2-second minimum STT endpoint allows short thinking
  pauses while adding at most 0.7 seconds over the previous 0.5-second setting.
- Display-only merge: transcript coalescing improves readability but does not
  replace LiveKit turn detection; the endpoint setting prevents the corresponding
  duplicate model turns for the observed pause pattern.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Boundary question | Audible answer after final narration | `TransitionRejected` or silence | Attempt ID and backend log |
| Terminal state | Answer ends in `completed` with one committed beat | Waiting state, replay, or duplicate commit | State/events screenshot |
| User transcript | One row contains the complete paused question | Several one- or two-word rows | Transcript screenshot |
| Responsiveness | Turn timing remains visible and conversational | Fragment fix causes multi-second added delay | Timing cards |

## Exit criteria

- [x] The failed live boundary and transcript fragments are captured.
- [x] Tests are written before implementation and fail for the intended reasons.
- [x] Domain, application, adapter and provider-factory tests pass.
- [x] All earlier deterministic gates remain green.
- [ ] One bounded live retry produces an audible answer and one coherent user row.
