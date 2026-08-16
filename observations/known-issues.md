# Known issues and deferred refinements

This ledger records observed behavior that does not invalidate the current slice
but must remain visible during later breadth and release work.

## KI-001 — Answer-and-continue response asks for redundant permission

- **Status:** closed for the current assignment. The user accepted the offline
  prevention and subsequent live answer-and-continue behavior on 17 August 2026.
- **Observed:** 16 August 2026, attempt
  `81045d4f-104d-4f9f-a15f-f943738da0d7`.
- **Behavior:** after the listener explicitly authorized continuation, the answer
  ended with “Please let me know when you are ready to continue.” The application
  correctly resumed without another button press or voice command.
- **Impact:** state and narration progression are correct, but the spoken answer
  contradicts the already-authorized automatic continuation.
- **Likely seam:** the answer generation directive forbids model-owned navigation
  but does not tell the model that continuation is already authorized and will be
  performed by the application.
- **Regression case:** an answer with `continue_after_answer` contains no
  permission-seeking or promise to wait; application-owned resumption still occurs
  only after verified answer playout.
- **Offline mitigation:** the validated-plan answer directive now explicitly
  forbids another permission request when continuation is already authorized, and
  the LiveKit bridge proves resumption starts only after answer playout settles.

## KI-002 — Transcript discontinuity at interruption boundaries

- **Status:** incomplete-continuation fragments hardened offline; broader live
  transcript verification remains open.
- **Observed:** 16 August 2026, attempts
  `2baa9b74-1d4e-4da4-8bab-0e7804b54de2` and
  `81045d4f-104d-4f9f-a15f-f943738da0d7`.
- **Behavior:** normalized transcript rows are delivered, but an interruption can
  leave a visibly truncated assistant segment or a discontinuous user utterance.
  Timing-based user-fragment grouping does not reconstruct text across every
  provider turn/interruption boundary.
- **Impact:** audible interruption and continuation work, but the transcript is not
  yet a perfectly continuous reading record.
- **Constraint:** do not fabricate missing words or merge across an intervening
  assistant turn merely to improve appearance.
- **Offline mitigation:** an STT turn ending in an incomplete continuation tail,
  such as “Then”, waits for one bounded adjacent fragment. If that fragment
  arrives before answer preparation begins, the application plans the combined
  native text once. Ordinary completed turns retain their existing latency.
- **Later acceptance case:** interrupted segments are represented coherently and
  related STT fragments share an explicit turn identity where the provider exposes
  one; missing provider text remains visibly incomplete rather than invented.

## KI-003 — Motorcycle paraphrases can be falsely marked out of scope

- **Status:** closed for the current assignment. The user accepted the bounded
  reasoning behavior after live testing on 17 August 2026.
- **Observed:** 16 August 2026, attempts
  `2baa9b74-1d4e-4da4-8bab-0e7804b54de2` and
  `81045d4f-104d-4f9f-a15f-f943738da0d7`.
- **Behavior:** the UI showed `out_of_scope` during motorcycle-domain questions
  involving lower gears, engine speed, or rev matching. The one-slide lexical
  resolver lacks the material breadth and phrase coverage needed for these forms.
- **Impact:** the generated answer may still sound relevant, but the disclosed
  scope mode and selected evidence are unreliable for natural paraphrases.
- **Offline mitigation:** Slice 5b adds the six-slide evaluation, bounded
  gear/rev/braking aliases, concept-weighted matching, and a two-term grounding
  floor. The fixed cases and four recorded paraphrases now pass deterministically.
- **Regression case:** retain the spoken variants in future bounded full-deck
  observations. Generated prose must remain unable to choose navigation.

## KI-004 — Manual navigation during answer playout

- **Status:** implemented and verified offline; one acoustic browser acceptance
  run remains in the public demo rubric.
- **Behavior:** once answer playout is active, the deck controls remain available
  and disclose that browsing stops the answer. A valid new selection interrupts
  and abandons the answer, preserves the semantic cursor, clears any automatic
  continuation permission, and enters waiting. Continue restores and replays the
  preserved narration beat. Browsing after a post-completion answer remains
  completed.
- **Safety:** an unknown slide is rejected and selecting the already visible
  slide is a no-op before provider audio is touched. Late or duplicate answer
  completion callbacks cannot resume narration or mutate state.
- **Verified:** domain, application, LiveKit bridge, and frontend policy tests
  cover ordinary answers, answer-and-continue, invalid and duplicate targets,
  stale callbacks, preserved-cursor replay, and post-completion behavior.
- **Remaining acceptance case:** run step 4 of `docs/demo-script.md` with live
  audio and confirm that speech stops promptly and the explanatory copy is clear.

## KI-005 — Authoring-format import is not implemented

- **Status:** deferred to the presentation-ingestion slice.
- **Behavior:** `assets/<deck-id>/slide-breakdown.json` is the portable runtime
  contract. The motorcycle package now includes the user-authored `deck.pptx`
  and exact extracted slide renders, but no general import command parses a new
  deck or produces the normalized handout yet. `additional-context.json` remains
  reserved and unloaded.
- **Reason:** PPTX is an authoring source, while the application requires stable
  semantic slide IDs, narration beats, evidence, and visual descriptions that a
  raw deck does not guarantee. The current source is especially illustrative:
  every PowerPoint slide is one full-slide raster image with no editable semantic
  structure for the runtime to consume.
- **Later acceptance case:** a deterministic importer turns a supplied deck plus
  handout into a validated package and emits a review report before runtime use.

## KI-006 — Referential follow-up questions can lose their antecedent

- **Status:** closed for the current assignment. The user accepted the bounded
  provenance behavior after live testing on 17 August 2026.
- **Observed:** 16 August 2026, attempt
  `35a5be63-5af1-447d-871d-e76ce8cdc3b8`.
- **Behavior:** short follow-ups such as “Can you explain me once again how this
  ratio helped?” and “What is the jerk you mentioned about?” were disclosed as
  `out_of_scope`, even though the captured conversation contained the antecedent
  and the packaged material contains the relevant concepts.
- **Impact:** provider context delivery is intact, but the application-selected
  answer mode can be wrong. Model history cannot repair that decision because
  application code selects and validates the evidence before generation.
- **Likely seam:** the deterministic question resolver receives the current
  utterance and visible-slide preference, but no bounded conversational
  antecedent or explicit follow-up identity.
- **Constraint:** do not make generated prose responsible for navigation or
  silently let the provider override the disclosed answer mode.
- **Regression case:** resolve a bounded recent antecedent into explicit
  application input, prove the same question is classified consistently after
  interruption and manual navigation, and retain the current deterministic
  transition checks.
- **Offline mitigation:** logical-turn provenance now retains actual interrupted
  assistant text, the silent planner can cite that turn or bounded deck evidence,
  and only a current application-validated plan can reach answer generation.

## KI-007 — Spoken acronyms can be transcribed as nearby letter sequences

- **Status:** mitigated with bounded authored-term hints; raw planner quality
  limitation retained.
- **Observed:** 17 August 2026, attempt
  `3536b0b3-9285-4934-9290-9c60342a7c30`.
- **Behavior:** the first spoken `ABS` request arrived as `APS`. The planner
  searched the incorrect acronym twice and found no presentation evidence. A
  repeated utterance transcribed as `a b s`, normalized to the correct search,
  and completed successfully.
- **Impact:** the bounded reasoning path cannot recover domain intent when the
  authoritative STT text changes a short acronym.
- **Constraint:** do not silently rewrite arbitrary acronyms. Any correction must
  be deck-bounded, observable, and preserve the original transcript.
- **Mitigation:** exact `ABS` and spaced `A B S` resolve against the authored ABS
  term. `APS` records one phonetic-neighbor hint without changing the transcript;
  if planning still fails, the application asks “Did you mean ABS?” and waits.
  Unrelated `AWS` is not rewritten.
- **Remaining limitation:** in the bounded live planner probe, Gemma searched the
  correct `ABS` candidate but then cited the active user turn. Validation rejected
  the plan and the clarification fallback remained safe; direct acceptance still
  depends on provider plan quality.

## KI-008 — Recoverable planner validation failures can produce no spoken answer

- **Status:** mitigated offline and wired into the production bridge; a forced
  live fallback observation remains optional.
- **Observed:** 17 August 2026, attempts
  `f15cc0d8-9222-441f-a91c-74217dbcacd5` and
  `3536b0b3-9285-4934-9290-9c60342a7c30`.
- **Behavior:** unknown citations or malformed terminal arguments can exhaust the
  bounded planner and leave only a visible failure, even when a useful answer
  could still be delivered safely.
- **Implemented behavior:** first attempt bounded correction. If support still
  cannot be validated, discard citations and focus navigation, then deliver a
  disclosed model-knowledge or boundary response when the request is safe and
  answerable.
- **Constraint:** graceful degradation must create a newly valid application-owned
  directive; it must never speak an invalid plan, preserve unsupported focus, or
  bypass clarification and safety boundaries.
- **Verified:** citation and schema failures each produce at most one new
  application-owned fallback, retain default/explicit continuation semantics,
  and never mutate the semantic cursor. Timeout, provider, stale, cancellation,
  disconnect, unknown-tool, and multiple-tool failures remain fail-closed.
