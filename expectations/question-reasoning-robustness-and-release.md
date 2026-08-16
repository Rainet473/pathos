# Expectation handout: question-reasoning robustness and release evidence

## User-visible outcome

Natural listener follow-ups remain bounded and understandable across wording
variation, interruption, and provider-plan mistakes. A recoverable malformed or
citation-invalid plan never reaches speech as if it were valid; after at most one
planner correction, the application may issue one newly valid, citation-free
fallback answer. Stale, cancelled, timed-out, disconnected, or provider-failed
work remains fail-closed. Operators can measure latency and cache behavior from
retained diagnostics instead of inferring either from prompt shape.

## Inputs, outputs and boundaries

- Inputs: authoritative STT text, logical-turn history, deck-local search,
  application state/version, planner tool calls, provider usage/timing, and
  verified playout facts.
- Outputs/events: an accepted answer directive, a controlled planning failure, or
  one explicitly recovered answer with scope/source disclosure and no unvalidated
  citations or focus.
- External boundaries: Deepgram STT, LiveKit Inference Gemma planning/speaking,
  Inworld TTS, LiveKit room lifecycle, and browser rendering.
- Preconditions: Slice 5 focus/navigation, validated streaming answers, bounded
  search, provenance, and the 30-second total planning deadline are green.
- Non-goals: embeddings, network search, arbitrary transcript rewriting,
  provider replacement, hidden chain-of-thought, manual browsing during answer
  playout, and exact word/audio resumption.

## Behavior map

```text
follow-up -> bounded planner -> accepted plan -> streamed answer -> wait/resume
                         |
                         +-> one native correction when budget permits
                                  |
                                  +-> accepted plan
                                  +-> recoverable content failure
                                        -> discard plan citations/focus
                                        -> fresh app-owned fallback directive
                                        -> streamed answer -> wait/resume

timeout/provider/stale/cancel/disconnect -> controlled failure; no fallback speech
```

## Invariants

- No rejected or schema-invalid plan is spoken, focused, or treated as accepted.
- A fallback is a new application-owned directive, not a relaxed validation path.
- Fallback directives contain no planner turn/evidence citations and never change
  the visible slide from plan data.
- Only invalid tool arguments and current-turn plan-validation/coherence failures
  are eligible for fallback. Timeout, provider error, missing/unknown tools,
  cancellation, stale context/identity, and disconnect remain fail-closed.
- Safety and ambiguity can only narrow fallback behavior to clarification or a
  boundary response; they cannot be promoted to unconstrained model knowledge.
- At most one spoken response is created for one follow-up, whether normal or
  recovered.
- Continuation permission remains derived from the original listener utterance.
  Clarification always waits; other recovered answers resume only after verified
  playout when explicit permission already exists.
- The semantic cursor and interrupted beat never move because planning or
  fallback failed. Fallback playout commits no narration beat.
- The authoritative transcript remains unchanged. Any acronym handling must be a
  deck-bounded hint or clarification that is observable separately.
- Prompt caching is an optimization metric, never a correctness dependency.
  Zero cached tokens is a valid measured result.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Invalid evidence citation after correction is exhausted | One citation-free disclosed fallback is generated; no question-focus event occurs | Application/bridge tests |
| Repeated malformed terminal arguments | One correction attempt at most, then one safe fallback; the malformed payload is never spoken | Planner/bridge tests |
| Unsafe exact repair request with malformed plan | Boundary response, no model-knowledge repair instructions, no focus | Application test |
| Ambiguous “Why does it jerk?” with malformed plan | One focused clarification and waiting state | Application test |
| Timeout, provider error, stale result, cancellation, or disconnect | Visible controlled failure or session end, with no fallback generation | Adapter tests |
| `ABS`, `A B S`, and nearby `APS` transcript | Original transcript is retained; unique authored intent may be hinted, otherwise clarify | Evaluation plus human rubric |
| Repeated follow-ups | Cached and total input tokens, request count, planning/search duration, answer TTFT, and TTS first audio are recorded | Diagnostics analysis |
| Direct earlier-turn reference | Conversation-cited plan answers without search and remains within the accepted latency envelope | Live observation |
| Cross-slide answer and continue | Supporting slide focuses, answer plays, semantic slide restores, and preserved beat resumes once | Live observation |

## Edge and race cases

- Empty/malformed: blank STT remains rejected; invalid JSON/schema gets no more
  than one provider correction and one eligible application fallback.
- Duplicate/repeated: duplicate terminal calls and repeated failure callbacks
  cannot generate a second answer or second resumption.
- Late/out-of-order: a late plan or fallback for an old version/turn is discarded
  without speech or navigation.
- Cancellation: cancellation before, during, or after search cannot be converted
  into fallback speech; an accepted answer interrupted during playout settles once.
- Partial failure: recoverable plan-content failure degrades without citations;
  provider/transport failure remains visible and retryable.
- Recovery: a fresh follow-up after controlled failure starts a new planning
  transaction; explicit Continue restores the preserved narration cursor.
- Capability mismatch: unsupported tool behavior fails closed and is recorded;
  fallback does not pretend the provider honored the planning protocol.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Conversation citation | prior logical turn is cited and explained without search | provider item ID or invented unheard text is treated as support | transcript, plan, trace |
| Presentation search | different wording finds bounded deck evidence | unbounded/repeated search or uncited grounding claim | search hits and timing |
| Extended knowledge | short spoken disclosure precedes a related answer | answer is presented as deck-grounded | transcript and scope/source |
| Clarification | exactly one useful question and no automatic resume | generic failure or resumed narration | transcript and state |
| Out of scope/safety | concise boundary without risky specifics | unsafe answer or false grounding | transcript and plan |
| Fallback | useful safe speech after recoverable content failure; no citations/focus | invalid plan spoken, silent failure, or duplicate answer | trace, events, transcript |
| Waiting/continuation | default waits; explicit permission resumes after answer playout | model prose grants continuation or narration resumes early | ordered events |
| Interruption/disconnect | active work cancels or fails visibly without stale settlement | late speech/state mutation | diagnostics and lifecycle |
| Acronym variation | original STT visible; correction is uniquely deck-bounded or clarified | arbitrary silent rewrite | STT, hint/plan, transcript |
| Cache/latency | provider-reported cached/total tokens and stage timings are quantified | cache hit is assumed or planning is folded into answer TTFT | JSONL summary |
| Slide focus | question/restore/user reasons remain distinct | prose-derived or stale navigation | screenshot and events |

## Open assumptions

- The retained deterministic scope policy is conservative enough to decide
  whether a citation-free fallback may use disclosed model knowledge, ask a
  clarification, or give a boundary response. It does not validate the rejected
  plan and cannot authorize focus.
- Live cache hits may remain sparse or zero for this provider. The release gate
  requires measurement and explanation, not a positive hit ratio.
- Phrase/acronym evaluation may close with a documented clarification behavior
  rather than automatic correction when the authored deck term is not unique.

## Exit criteria

- [x] Expectation and evidence plan exist before source changes.
- [x] New tests were observed failing for the intended reason.
- [x] Recoverable fallback and fail-closed boundaries pass offline.
- [x] Phrase, reference, claim, correction, incomplete-turn, and continuation
  evaluations are recorded.
- [x] Cancellation, stale result, disconnect, repeated call, and unsupported-tool
  gates pass.
- [x] Cache ratio and stage latency are measured from provider-reported fields.
- [x] Previous backend/frontend/build gates remain green.
- [x] Browser/provider observation cases are recorded or explicitly left open
  with a reproducible script and usage bound.
- [x] Public documentation and known limitations match the verified behavior.
