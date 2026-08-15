# Expectation handout: narration commitment

## User-visible outcome

The presentation advances only after the currently selected narration beat has actually finished playing. Interrupted, cancelled, duplicated or stale speech never skips material.

## Inputs, outputs and boundaries

- Inputs: Start, beat selection, playout started/completed/interrupted events, turn ID and semantic cursor.
- Outputs/events: presentation started, beat selected, beat committed, slide changed, stale response discarded, transition rejected and presentation completed.
- External boundaries: a provider-neutral voice-runtime port reports normalized playout lifecycle events.
- Preconditions: validated ordered slide content with at least one beat.
- Non-goals: exact transcript wording, audio offsets, provider callbacks and question answering.

## Behavior map

```text
ready --Start--> presenting(cursor = first uncommitted beat)
presenting --matching playout completed--> commit once → next beat
presenting --matching playout interrupted/cancelled--> same cursor
presenting --stale or duplicate completion--> no state change
last beat --matching playout completed--> completed
```

## Invariants

- `presentation_cursor` always identifies the next uncommitted beat.
- Selecting or generating a beat does not commit it.
- Only `playout_completed` for the active turn and active cursor may commit.
- One beat can be committed at most once.
- Crossing a slide boundary changes the presentation slide through an explicit domain event.
- The cursor never advances past the final beat.
- Domain contracts contain no LiveKit, Google, OpenAI or browser SDK types.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| First beat completes | Beat commits and cursor points to the next beat | Automated |
| Final beat on a slide completes | Beat commits and a presentation slide-change event is emitted | Automated |
| Active beat is interrupted | Cursor remains on that beat | Automated |
| Completion callback arrives twice | Second callback is ignored or explicitly reported stale | Automated |
| Old turn completes after a new turn starts | No cursor mutation; stale event is observable | Automated |

## Edge and race cases

- Empty/malformed: unknown slide, missing beat, empty turn ID and mismatched cursor.
- Duplicate/repeated: repeated Start, duplicate started/completed/interrupted events.
- Late/out-of-order: completion before start, completion after interruption and old-turn completion after resumption.
- Cancellation: before playout, during playout and after completion has already committed.
- Partial failure: runtime reports start but never terminates; controller remains uncommitted and exposes active work.
- Recovery: a restored snapshot must still identify one valid next-uncommitted beat.
- Capability mismatch: a runtime without reliable playout completion cannot claim support for automatic beat advancement.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Concept coverage | Completed beat communicates its required concepts | Beat ends without the required idea | Transcript and beat ID |
| UI alignment | Visible slide changes at a conceptual boundary | Slide changes based on generated prose or before playout | Event log and recording |

## Open assumptions

- A future adapter can distinguish completed playout from completed generation. This is verified in its own slice.
- Semantic narration may vary in wording; deterministic tests assert state, while concept coverage uses a rubric.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [ ] Deterministic suite passes offline.
- [x] Live concept-coverage observations are deferred to the real-provider slice.
- [x] Runtime capability mismatch remains explicit.
