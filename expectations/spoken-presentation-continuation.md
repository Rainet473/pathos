# Expectation handout: spoken presentation continuation

## User-visible outcome

After narration is interrupted or an answer leaves the presentation waiting, a
listener can say a short command such as “continue the presentation” or “resume
the narration.” Pathos immediately restores the semantic presentation cursor and
replays its preserved, uncommitted beat. It does not search, prepare an answer,
or require the Continue button.

## Inputs, outputs and boundaries

- Inputs: a final user transcript containing a standalone continuation request.
- Outputs/events: `presentation_resumed`, `beat_selected`, a new narration turn,
  and no follow-up planning request or answer turn.
- External boundaries: LiveKit final-turn hook, provider-neutral command matcher,
  silent-planner action proposal, LiveKit presentation bridge, application
  session, and domain controller.
- Preconditions: the presentation is `interrupted` or `waiting` and retains a
  valid semantic cursor.
- Non-goals: model-owned state changes, resuming a completed deck, treating
  “explain this and then continue” as a standalone command, or changing
  UI-button continuation.

## Behavior map

```text
final user transcript
  -> exact bounded command match?
     -> no: silent planner classifies the request
        -> typed continue action: application validates and resumes
        -> answer plan: existing answer path
     -> yes: application phase interrupted/waiting?
        -> no: existing follow-up planning path
        -> yes: settle interrupted speech -> continue_presentation
             -> restore semantic slide -> replay preserved beat
             -> suppress answer generation for the command turn
```

## Invariants

- Application code—not generated prose—authorizes and executes continuation.
- The interrupted beat remains uncommitted and is replayed with a new turn ID.
- A canonical standalone command never invokes search or the silent planner.
- A natural standalone variant may invoke the silent planner, but it terminates
  with a typed continuation action rather than an answer plan.
- The model proposes intent; the application validates the active follow-up,
  session version, and legal presentation phase before changing state.
- Negative and compound utterances such as “do not continue” and “explain ABS,
  then continue” are not standalone commands.
- Unknown phrases remain on the existing answer-planning path.
- Repeated or late completion callbacks cannot commit the preserved beat twice.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Waiting + “continue the presentation” | narration resumes from saved cursor without planner call | Adapter test |
| Interrupted + “resume narration” | interrupted speech settles, then the same beat replays | Domain/adapter test |
| Waiting + “please go on” | bounded polite variant resumes | Matcher test |
| Waiting + “would you carry on with the presentation from there?” | planner proposes continuation; application resumes without an answer | Planner/adapter test |
| Waiting + “do not continue” | normal follow-up path; no direct resume | Matcher/adapter test |
| “Explain ABS, then continue” | answer-and-continue policy remains unchanged | Existing regression |
| Completed deck + “continue” | no impossible direct continuation | Adapter test |

## Edge and race cases

- Empty/malformed: blank transcripts never match.
- Duplicate/repeated: a second command outside `interrupted`/`waiting` cannot
  create a second direct resume.
- Late/out-of-order: the prior speech binding is settled exactly once before
  continuation.
- Cancellation: session shutdown still cancels the turn hook and generation.
- Partial failure: if continuation is invalid, existing transition rejection is
  not hidden by the matcher.
- Recovery: the Continue button remains available as the deterministic fallback.
- Capability mismatch: speech recognition variants outside the bounded grammar
  use the typed model decision instead of widening the regex without limit.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Latency | narration begins without silent-planner/search delay | planning stages appear before resume | screen recording/events |
| Cursor safety | the preserved beat and semantic slide replay | narration skips or advances | state/events |
| Audible behavior | no synthetic answer to the word “continue” | model explains or acknowledges the command | transcript/recording |
| Negative command | “do not continue” does not resume | substring match resumes accidentally | transcript/events |

## Open assumptions

- A deliberately bounded grammar is the zero-latency path; the model handles
  natural variants through a validated action contract.
- “Continue” spoken during `interrupted` means replay the interrupted beat; spoken
  while `waiting` means restore and replay the saved semantic cursor.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic focused and adjacent suites pass offline.
- [ ] A live microphone observation is run or retained as an explicit user gate.
- [x] Deferred recognition variants are explicit.
