# Expectation handout: follow-up planning recovery

## User-visible outcome

A listener follow-up produces one validated spoken answer even when planning is
close to its deadline, the model first cites evidence from an earlier planning
turn, or speech recognition finalizes one natural request as adjacent fragments.
After recovery begins, the UI no longer shows a stale planning failure.

## Inputs, outputs and boundaries

- Inputs: finalized STT text, provenance-aware planning context, bounded material
  search results, provider tool-call chunks, and application continuation state.
- Outputs/events: one logical follow-up, at most one accepted answer plan, one
  tool-disabled streamed answer, and either waiting or authorized narration
  resumption after verified answer playout.
- External boundaries: LiveKit end-of-turn callbacks and the selected inference
  LLM. Deterministic tests use recorded collaborators and do not call providers.
- Preconditions: context/provenance, deterministic planning/search, silent
  planning, and validated streaming-answer gates remain green.
- Non-goals: focus-slide navigation, transcript word repair, embeddings, network
  retrieval, provider replacement, or hidden retry loops without bounds.

## Behavior map

```text
adjacent finalized STT fragments
  -> one stable logical follow-up
  -> bounded provider request(s)
  -> current-turn evidence validation
       historical evidence cited first -> visible tool rejection -> bounded replan
  -> terminal response received before deadline -> local parse and validation
  -> accepted plan -> clear prior failure -> streamed answer
  -> verified playout -> wait or authorized resume
```

## Invariants

- Historical tool traces may remain audit history, but their evidence IDs are not
  valid in a new planning turn until a current search returns them.
- A recoverable terminal rejection cannot speak or mutate presentation state.
- Recovery remains inside the existing request, search, step, and wall-clock
  bounds; it cannot retry indefinitely.
- The planning deadline bounds provider waiting. Once a complete provider
  response has arrived within that deadline, local parsing and validation are
  allowed to settle it without asynchronous cancellation.
- Planning failure remains visible while waiting, then clears when a new
  follow-up is accepted or narration recovery starts.
- Adjacent fragments are merged only before any assistant response begins and
  without inventing missing words.
- Explicit continuation is derived from the complete merged utterance and still
  has no effect until answer playout completes.
- Cursor, visible slide, turn identity, and playout commitment remain
  application-owned.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Current ABS search reaches the deadline edge | A complete terminal tool response is locally validated and accepted | Offline adapter test |
| Plan cites an ABS evidence ID from a prior turn | The rejection is returned to the planner; a bounded current search and corrected plan can succeed | Offline adapter test |
| Continue after a failed plan | Narration starts and the stale red planning failure is cleared | Application and frontend tests |
| “Explain AWS. Then” followed immediately by “continue narration.” | One logical follow-up retains the full explicit answer-and-continue intent | Adapter/application test |
| Incomplete “What is the” with no adjacent completion | Controlled clarification/failure; no fabricated completion or free-form speech | Offline failure test |
| Live ABS and AWS cases | Each produces one answer and resumes only after verified answer playout | Human rubric |

## Edge and race cases

- Empty/malformed: blank fragments never start planning; malformed terminal tool
  arguments remain controlled failures.
- Duplicate/repeated: duplicate fragment delivery and repeated terminal calls do
  not create multiple accepted plans or answer turns.
- Late/out-of-order: a fragment or plan for a superseded session identity is
  discarded.
- Cancellation: a new unrelated turn, navigation, disconnect, or session stop
  cancels pending coalescing/planning without delayed speech.
- Partial failure: exhausted provider deadline or request budget enters waiting
  with a sanitized reason code.
- Recovery: retrying or continuing clears stale failure presentation without
  erasing the prior diagnostic record.
- Capability mismatch: if LiveKit cannot expose a stable fragment identity,
  merge only within the bounded application window and retain raw transcript
  evidence.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Turn integrity | One complete user intent and one answer | Fragments become competing plans or narration | Raw and logical transcripts |
| Validation | Only current-turn evidence reaches the answer directive | Historical evidence silently bypasses validation | Planner trace and decision codes |
| Deadline | Complete terminal response settles | Received tool call is cancelled during local validation | Request and planning timestamps |
| Recovery UI | Failure disappears when recovery starts | Red error persists while presenting or answering | State snapshots/screenshots |
| Continuation | Resume follows answer playout | Resume is lost, premature, or model-owned | Domain event ordering |

## Open assumptions

- A short bounded coalescing window is sufficient for the observed adjacent
  finalized-fragment case without making ordinary responses feel sluggish.
- The provider stream boundary reliably indicates when a complete tool-call
  response has been received.
- Live acoustic verification is still required after deterministic coverage.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reasons.
- [x] Planner recovery and timeout settlement pass offline.
- [x] Fragment coalescing and continuation ownership pass offline.
- [x] Previous deterministic and frontend gates pass.
- [ ] Live ABS and AWS observation cases pass, or remain explicitly open with a
  reproducible command and rubric.
