# Expectation handout: interruption and resumption

## User-visible outcome

When the user speaks over narration, agent audio stops promptly, the unfinished semantic beat remains saved, the question can temporarily use another slide, and presentation narration resumes from the same beat only when continuation is authorized.

## Inputs, outputs and boundaries

- Inputs: speech-start/interruption event, usable committed utterance, question result, continuation preference and playout lifecycle.
- Outputs/events: playout interrupted, question classified, temporary slide change, answer completed, presentation waiting, slide restored and presentation resumed.
- External boundaries: voice runtime supplies interruption and committed-turn events; the model may propose bounded intent but cannot mutate state.
- Preconditions: narration has started and an active uncommitted beat exists.
- Non-goals: exact word-level restart, mandatory automatic continuation and treating every sound as a question.

## Behavior map

```text
presenting(active beat B)
  └─ speech starts → interrupted(saved beat B)
       ├─ unusable/no committed turn → preserve B; no fabricated question
       └─ usable question → answering
            ├─ plain question → waiting
            ├─ stay paused → waiting
            └─ answer and continue → restore presentation slide → presenting(B)
```

## Invariants

- Interruption immediately supersedes the active narration turn.
- The active uncommitted beat is preserved; partially heard narration is never silently committed.
- `presentation_cursor` and `visible_slide_id` remain independent.
- A question-driven slide change cannot overwrite the saved presentation cursor.
- Default after a completed answer is waiting.
- Only explicit `continue_after_answer` permits direct resumption.
- Resumption replays the same interrupted beat from its beginning, optionally with a short bridge.
- Events from superseded turns cannot speak, navigate or advance state.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Plain question interrupts beat B | Answer ends in waiting; cursor still identifies B | Automated |
| “Answer and continue” interrupts B | Original slide is restored and B is selected again | Automated |
| ABS question while clutch slide is active | ABS may be visible during answer; clutch cursor is unchanged | Automated |
| User interrupts the answer | Answer playout stops; original presentation cursor remains B | Automated |
| Cough causes speech-start but no usable turn | Audio may stop, but no fabricated question or cursor advance occurs | Automated plus observation |

## Edge and race cases

- Empty/malformed: interruption without active playout, unusable utterance and missing continuation preference.
- Duplicate/repeated: repeated speech-start, repeated continue and answer completion twice.
- Late/out-of-order: old narration completion after interruption and old answer completion after a follow-up.
- Cancellation: narration, answer and resume bridge can each be cancelled independently.
- Partial failure: answer fails after temporary navigation; presentation cursor remains valid and the UI enters a recoverable waiting/error state.
- Recovery: reconnect may restart clearly or restore a validated compact snapshot; it must not infer progress from model history.
- Capability mismatch: runtimes with delayed transcription may interrupt promptly while committing the question later.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Audible interruption | Agent stops quickly enough to permit natural barge-in | Agent continues talking over the question | Speech-start/playout-stop timestamps and recording |
| Resume coherence | Short bridge or replay makes the repeated beat understandable | Half-sentence restart or skipped concept | Recording, transcript and cursor log |
| Waiting clarity | User can tell the answer is complete and narration is paused | Agent silently resumes or state is ambiguous | Screenshot and recording |

## Open assumptions

- The exact acceptable interruption latency is measured rather than invented in Slice 0.
- Whether a false interruption automatically retries the preserved beat or visibly waits is deferred to the transport/runtime probe. Either policy must avoid fabricating a question or advancing the cursor.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [ ] Deterministic suite passes offline.
- [x] Acoustic observations are deferred with a repeatable rubric.
- [x] Reconnect policy remains an explicit MVP limitation until its slice.
