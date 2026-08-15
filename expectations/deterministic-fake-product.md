# Expectation handout: deterministic fake product

## User-visible outcome

Without network access or provider credentials, a viewer can open a quiet one-slide presentation, start one scripted narration beat, interrupt it with a scripted question, hear or read a deterministic answer, and observe either waiting or explicitly authorized direct resumption from the same unfinished beat.

## Inputs, outputs and boundaries

- Inputs: create offline session, Start, interrupt with a committed scripted question, playout completion and Continue.
- Outputs/events: validated slide data, provider-neutral domain events, normalized fake playout events, deterministic transcript entries and a versioned UI snapshot.
- External boundaries: React communicates with a local FastAPI fake-session API; the fake voice adapter crosses the same normalized lifecycle port expected of a future live adapter.
- Preconditions: the Slice 2 content fixture validates and contains one slide with one narration beat.
- Non-goals: microphone capture, audible generated speech, LiveKit Cloud, Gemini/Google, `AgentSession`, six-slide breadth, model tools, visual polish and public documentation.

## Behavior map

```text
page load -> ready, quiet, no active turn or transcript
Start -> presenting beat B -> fake playout started
presenting B -> interrupt + committed question -> answering, B uncommitted
answer playout completed
  -> plain question -> waiting, B still uncommitted
  -> explicit answer-and-continue -> presenting B again under a new turn
waiting -> Continue -> presenting B again under a new turn
matching narration playout completed -> commit B exactly once -> completed
late or duplicate event from an old turn -> no mutation
```

## Invariants

- The page and fake runtime remain inactive until Start.
- The controller is the only owner of presentation phase, cursors and legal transitions.
- `presentation_cursor` identifies the next uncommitted beat and remains distinct from `visible_slide_id`.
- Only normalized matching `playout_completed` commits a narration beat.
- Interruption preserves the active uncommitted beat and supersedes its turn.
- Default answer completion enters `waiting`; only `continue_after_answer` resumes directly.
- A question slide proposal is validated and never rewrites the presentation cursor.
- A stale or duplicate turn event cannot mutate controller or UI state.
- The domain package imports no LiveKit, Google, OpenAI or browser SDK.
- Question decisions remain structured as grounded, disclosed extended knowledge, clarification or out of scope; generated text is never parsed for navigation.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Initial render | Ready phase, first slide visible, no turn and no transcript | Automated plus browser observation |
| Start | Narration turn and active fake playout appear; cursor is still beat 0 | Automated |
| Plain question interrupts | Answer completes in waiting; beat 0 remains next | Automated plus browser observation |
| Answer and continue | Answer completion creates a new narration turn for beat 0 | Automated plus browser observation |
| Question proposes another known slide | Visible slide may change while the presentation cursor does not | Automated domain fixture |
| Old narration completion arrives after interruption | State and version remain unchanged | Automated |

## Edge and race cases

- Empty/malformed: blank turn IDs, invalid cursors, blank questions, malformed action payloads and unknown sessions are rejected.
- Duplicate/repeated: repeated Start, completion and interruption cannot double-commit or silently change phase.
- Late/out-of-order: old turn completion and an older UI snapshot are discarded.
- Cancellation: interruption maps to normalized playout interruption; no narration completion is synthesized.
- Partial failure: illegal fake-session actions return a controlled conflict and leave state recoverable.
- Recovery: a fresh offline session starts from a validated ready snapshot without reusing previous turn IDs.
- Capability mismatch: the fake advertises deterministic playout lifecycle and no audio output, VAD or semantic turn detection.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Quiet start | No active turn, transcript or automatic progression before Start | Fake speech or progress begins on load | Initial screenshot and snapshot |
| State clarity | Phase, visible slide, semantic cursor and turn ID are legible throughout | Progress is implicit or inferred from transcript prose | Screenshots and action/event log |
| Waiting | Plain question visibly ends in waiting | Narration resumes without permission | Screenshot and deterministic transcript |
| Direct resume | Explicit permission restores the presentation slide and same beat under a new turn | Cursor skips, repeats as committed or stays on a question slide | Screenshot and event log |
| Repeatability | A fresh session produces the same scripted words and transition shape | Timing or provider variability changes the result | Automated scenario result |

## Open assumptions

- Slice 2 treats visible scripted text plus explicit playout controls as the deterministic fake voice observation; audible and acoustic quality remain Slice 1 and later live-provider gates.
- The public fake fixture contains one narration slide. Cross-slide question navigation remains covered by the independent two-slide domain oracle until content breadth is introduced.

## Exit criteria

- [x] Existing requirement-derived tests were re-run before implementation.
- [x] The 27-test red baseline fails only because `voice_presentation.domain` is absent.
- [x] New fake runtime, API/scenario and UI state tests failed for the intended missing seams.
- [x] All deterministic Python and frontend suites pass offline.
- [x] The browser observation is run and evidence is recorded.
- [x] Paid/live gates were excluded from this slice; the then-open Slice 1 manual gates were tracked separately and later completed.
