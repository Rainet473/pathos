# Expectation handout: manual navigation during answer playout

## User-visible outcome

A listener may browse to another authored slide while an answer is speaking.
The selection stops and abandons that answer, shows the requested slide, and
pauses the presentation without advancing its semantic narration cursor. The
listener can browse freely and use Continue to restore and replay the preserved
narration beat. If the presentation was already complete, browsing returns to
the completed state and does not offer an impossible continuation.

## Inputs, outputs and boundaries

- Inputs: Previous, Next, or direct authored-slide selection while an answer is
  active; answer playout lifecycle callbacks; Continue.
- Outputs/events: verified answer interruption, user slide change, waiting or
  completed state, and later restoration to the semantic cursor when applicable.
- External boundaries: React controls, LiveKit data command, Python session
  bridge, application/controller state, and provider speech handle.
- Preconditions: an application-issued answer turn and a validated deck target.
- Non-goals: resuming the abandoned answer, changing answer context after a
  browse, model-owned navigation, exact audio offsets, or browsing while silent
  follow-up planning is still in flight.

## Behavior map

```text
answer speaking on support slide B; semantic cursor A/beat 2
  -> listener selects authored slide C
  -> validate C before touching audio
  -> interrupt and settle answer exactly once
  -> clear answer continuation/return metadata
  -> visible=C; cursor=A/2; phase=waiting
  -> late answer completion is stale
  -> Continue restores visible=A and replays A/2 with a new narration turn

answer after completed deck -> browse -> visible target; phase=completed
```

## Invariants

- Navigation never commits or advances the semantic presentation cursor.
- The selected slide is validated before active answer audio is interrupted.
- Selecting the already visible slide is an idempotent no-op and does not stop
  the answer.
- Browsing supersedes answer-and-continue permission; abandoned answer playout
  can never trigger automatic narration resumption.
- Answer interruption and any late or duplicate completion settle at most once.
- Continue resumes narration, never the abandoned answer.
- A post-completion answer returns to completed after browsing.
- Controls remain disabled while a follow-up plan is being prepared and during
  the brief pre-playout answer generation interval; they become available after
  verified answer playout starts.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Browse during ordinary answer | Answer stops, selected slide appears, state waits | Domain/bridge/frontend |
| Browse during answer-and-continue | Answer stops and no automatic narration starts | Bridge |
| Continue after browsing | Semantic slide restores and preserved beat replays once | Application/bridge |
| Browse during post-completion answer | Selected slide appears and state is completed | Domain |
| Select current slide | Answer continues; no command-side state mutation | Bridge/frontend |
| Select unknown slide | Command is rejected before speech interruption | Bridge |
| Late answer completion | No state change, answer completion, or resume | Bridge |

## Edge and race cases

- Empty/malformed: transport parsing rejects missing or blank slide IDs.
- Duplicate/repeated: the same target does not interrupt twice or advance the
  session version.
- Late/out-of-order: a completion callback from the abandoned answer is stale.
- Cancellation: provider speech is interrupted and correlated before navigation
  is applied.
- Partial failure: an invalid target leaves both audio and state untouched.
- Recovery: Continue restores the semantic slide and generates a new narration
  turn; post-completion browsing remains terminal.
- Capability mismatch: if the speech handle cannot interrupt, the application
  must not claim that browsing succeeded.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Discoverability | Controls remain available and explain that browsing stops the answer | Controls silently disable or consequence is hidden | Screenshot |
| Audible behavior | Answer stops promptly after selecting another slide | Answer continues over the newly visible slide | Recording/timestamp |
| Cursor safety | Visible slide changes while semantic cursor stays fixed | Browse commits or advances a beat | State/events |
| Continuation | Continue restores and replays narration once | Abandoned answer or automatic resume restarts | Transcript/events |
| Completion | Browsing a post-deck answer remains completed | UI offers unusable Continue | Screenshot/state |

## Open assumptions

- Abandoning the answer is preferable to maintaining a second resumable audio
  cursor for this release.
- A slide change during silent planning remains disabled because it would make
  the planning snapshot stale by design.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic focused and adjacent suites pass offline.
- [ ] Browser observation confirms the controls and explanatory copy.
- [ ] Acoustic answer interruption remains recorded as a repeatable user gate if
  microphone/provider use is not performed automatically.
- [x] Deferred risks are explicit.
