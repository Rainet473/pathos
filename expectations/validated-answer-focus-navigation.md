# Expectation handout: validated answer-focus navigation

## User-visible outcome

When a validated follow-up plan points to useful material on another slide, the
browser shows that slide while the answer is spoken. The presentation narration
cursor does not move. A waiting answer leaves the supporting slide visible; an
authorized or explicit continuation restores the semantic narration slide before
the preserved beat resumes.

## Inputs, outputs and boundaries

- Inputs: one application-validated answer plan, its optional `focus_slide_id`,
  the current visible slide, and the semantic/interrupted narration cursor.
- Outputs/events: an answer generation directive plus explicit `slide_changed`
  events whose reason is `question`, `restore`, or `user`.
- External boundaries: LiveKit transports the application snapshot and events;
  React renders only the supplied visible slide.
- Preconditions: cited evidence/turns, focus relevance, session version, and the
  active follow-up identity have already passed application validation.
- Non-goals: transcript-derived navigation, generated-prose parsing, answer
  interruption by manual browsing, acronym repair, and planner fallback speech.

## Behavior map

```text
validated plan with focus -> visible slide = support slide -> answer playout
  -> default wait ---------------------------> support slide stays visible
  -> authorized continuation -> restore semantic slide -> replay preserved beat

manual browse while waiting -> visible slide = user choice
  -> explicit Continue ------> restore semantic slide -> replay preserved beat
```

## Invariants

- The semantic presentation cursor and interrupted beat never change because an
  answer plan proposes visual focus.
- Only an accepted plan may apply question focus; stale, unknown, unsupported,
  or rejected focus data cannot mutate visible state.
- A question focus change is distinguishable from user navigation and semantic
  restoration by the structured `slide_change_reason`.
- Applying focus does not commit a narration beat or grant continuation.
- Direct continuation restores the semantic slide before emitting resumption and
  beat-selection events, and resumes exactly once.
- Default waiting preserves the last answer-support slide until the listener
  browses or explicitly continues.
- A same-slide focus is idempotent and emits no redundant slide-change event.
- Spoken answer text is never inspected for a slide identity.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| ABS plan cites `braking-abs` while narration is on `control-loop` | Visible slide changes to `braking-abs` with reason `question`; cursor remains on `control-loop` | Application test |
| Focused answer completes without continuation permission | Phase is waiting and `braking-abs` remains visible | Application test |
| Focused answer has explicit answer-and-continue permission | Restore event precedes resumption and the preserved beat is selected once | Application/adapter test |
| Listener clicks Continue after waiting on a support slide | Semantic slide is restored before narration generation | Application test |
| Plan focuses the already visible slide | No redundant slide event or version-only mutation is introduced by focus | Domain/application test |
| Plan is stale or focus is unsupported | No answer generation and no visible-slide mutation | Planning/application test |
| Browser manually browses while waiting | Slide event reason is `user`, never `question` | Domain/transport test |
| Live cross-slide ABS question | Supporting slide appears during the answer and narration resumes on the original semantic slide | Human rubric |

## Edge and race cases

- Empty/malformed: blank, missing, or unknown focus IDs are rejected before
  answer state begins.
- Duplicate/repeated: repeated same-slide focus is a no-op; a terminal plan still
  has exactly-once acceptance semantics.
- Late/out-of-order: a stale plan or playout callback cannot focus, restore, or
  resume a newer turn.
- Cancellation: interruption of an answer preserves the semantic cursor; no
  narration beat is committed by answer focus.
- Partial failure: a plan rejected during planning leaves the current visible
  slide unchanged and enters the existing controlled failure path.
- Recovery: explicit Continue restores from whichever support or manually browsed
  slide is visible.
- Capability mismatch: providers propose only structured focus data; they never
  own browser navigation.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Focus | Supporting slide appears before/during answer speech | Slide changes from generated prose or after stale completion | Screenshot and domain events |
| Cursor | Semantic slide/beat is unchanged | Question focus advances or rewinds narration | State snapshots |
| Waiting | Support slide remains browsable | Immediate unexplained restoration | Screenshot |
| Continuation | Restore precedes one resumed beat | Narration resumes on support slide or twice | Ordered domain events/transcript |
| Provenance | `question`, `restore`, and `user` are distinct | All changes look like manual navigation | Serialized events |

## Open assumptions

- Leaving the support slide visible while waiting is more useful than restoring
  immediately; explicit continuation remains the restoration boundary.
- The existing disabled-manual-navigation policy during answer playout remains
  unchanged.
- Acronym transcription and malformed/citation fallback remain robustness work;
  they cannot authorize focus without an accepted plan.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] A live cross-slide focus case was observed and evidence was recorded.
- [x] Deferred risks are explicit.
