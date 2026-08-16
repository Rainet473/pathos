# Expectation handout: validated streaming follow-up answer

## User-visible outcome

After a listener follow-up, the application shows observable preparation, waits
for one application-validated answer plan, and then streams a concise answer
through the existing LLM-to-TTS path. A normal answer waits afterward; explicit
answer-and-continue permission resumes the preserved narration beat only after
verified answer playout.

## Inputs, outputs and boundaries

- Inputs: a completed plain-text listener follow-up, application-owned
  conversation provenance, the current presentation snapshot, and one accepted
  bounded planning result.
- Outputs/events: observable planning stage, one provider-neutral answer
  generation directive, one tool-disabled LiveKit generation call, answer
  playout lifecycle events, and either waiting or a newly selected narration
  turn after settlement.
- External boundaries: the existing silent planner and the selected LiveKit
  Inference LLM-to-Inworld-TTS streaming path.
- Preconditions: the provenance, deterministic planning/search, and minimum real
  silent-planner gates remain green.
- Non-goals: answer-focus slide changes, prose-derived navigation, prompt-cache
  optimization, alternate providers, new retrieval methods, or scripted
  `session.say()` output.

## Behavior map

```text
completed user follow-up + current logical history
  -> visible understanding/searching/preparing status
  -> silent bounded planning
  -> accepted plan and still-current identity check
  -> application creates answer turn and evidence-only directive
  -> LiveKit generate_reply with tools disabled streams LLM text into TTS
  -> verified/interrupted answer playout settles application state
  -> wait by default OR restore/replay the saved beat when already authorized
```

## Invariants

- Planning cannot speak, navigate, resume, or begin an answer turn.
- The current session version and follow-up identity are rechecked before an
  accepted plan becomes an answer directive.
- Rejected, cancelled, timed-out, stale, or malformed planning results produce
  no answer generation and leave a visible controlled failure/waiting state.
- The answer directive contains only the accepted brief and resolved cited
  conversation/deck evidence; unsupported IDs cannot enter it.
- Scope and grounding source remain separate and observable.
- Extended-knowledge answers must disclose the deck gap.
- Clarification plans ask exactly the accepted clarification question.
- Answer generation has no tools and does not parse prose for state changes.
- Answer playout never commits a narration beat.
- Normal and stay-paused answers end in waiting.
- Explicit continuation produces no redundant permission request and cannot
  resume until verified answer playout completes.
- Interruption of an answer preserves the original semantic narration cursor;
  late completion from the interrupted answer is stale.
- User and assistant messages remain plain native chat content with compact
  logical-turn annotations in planning context only.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Conversation-cited answer | Accepted plan cites retained assistant wording; streamed directive contains that wording and no deck claim | Automated adapter/application test |
| Presentation answer | Accepted search evidence is resolved into the directive; provider tools are disabled for speech | Automated adapter test |
| Normal answer | Answer playout completion enters waiting and commits no narration beat | Automated bridge test |
| Answer and continue | Directive forbids asking permission again; the same saved beat is selected only after answer completion | Automated bridge test |
| Interrupted answer | Answer handle interruption settles once and no stale completion resumes narration | Automated bridge test |
| Stale/rejected plan | No `generate_reply` call is made; controlled planning failure is published | Automated failure test |
| Live sanity case | Spoken answer starts through streamed generation, sounds grounded, then waits or resumes as requested | Human rubric |

## Edge and race cases

- Empty/malformed: blank follow-ups are rejected before planning; unusable plan
  output never creates an answer directive.
- Duplicate/repeated: one follow-up has at most one accepted answer turn;
  repeated terminal or speech completion callbacks are idempotent/stale.
- Late/out-of-order: a plan whose version or follow-up ID is no longer active is
  discarded before generation.
- Cancellation: a new user turn, disconnect, or manual state change cancels the
  active planning identity and cannot fall through to speech.
- Partial failure: planning/provider failure is visible and preserves the saved
  cursor without an unvalidated answer.
- Recovery: the listener can retry from the controlled waiting state in the same
  session, or start a fresh session after provider failure.
- Capability mismatch: if LiveKit cannot stream tool-disabled generation from
  accepted instructions, retain the silent-planner gate and document the
  measured limitation before considering a fallback.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Validation boundary | Answer turn begins only after an accepted current plan | Speech starts from raw/rejected tool output | Structured planner and presentation records |
| Streaming | `generate_reply` feeds the existing LLM-to-TTS path with tools disabled | Full answer is collected then sent through `session.say()` | Adapter call trace and timing |
| Grounding | Spoken content follows accepted brief/evidence and disclosures | Unsupported deck claim or internal tool/status narration | STT transcript plus accepted plan |
| Continuation | Normal waits; authorized continuation resumes after playout without asking again | Premature resume or redundant permission request | Domain events and transcript |
| Interruption | Answer can be interrupted without cursor advance or stale settlement | Narration commits/resumes from a late callback | Turn IDs and cursor snapshots |
| Status | Preparation is visible without chain-of-thought | Hidden or fabricated reasoning transcript | Browser screenshot/status trace |

## Open assumptions

- LiveKit's `on_user_turn_completed` hook can await the bounded silent planner
  before the session begins tool-disabled answer generation.
- The selected pipeline continues to stream `generate_reply` output into TTS
  when the agent itself exposes no tools.
- The real provider/browser observation is required to evaluate spoken quality,
  answer TTFT, TTS first audio, and acoustic interruption; offline tests prove
  only contracts and lifecycle ordering.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Accepted-plan evidence and identity checks pass offline.
- [x] Tool-disabled streamed answer generation passes the bridge tests.
- [x] Waiting, explicit continuation, answer interruption, and failure paths pass.
- [x] Previous deterministic and frontend gates pass.
- [x] The bounded live/browser observation is run and evidence is recorded, or a
  concrete external blocker is recorded without claiming acoustic completion.
- [ ] Deferred focus navigation and caching risks remain explicit.
