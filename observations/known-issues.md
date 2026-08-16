# Known issues and deferred refinements

This ledger records observed behavior that does not invalidate the current slice
but must remain visible during later breadth and release work.

## KI-001 — Answer-and-continue response asks for redundant permission

- **Status:** deferred to prompt-quality hardening.
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
- **Later acceptance case:** an answer with `continue_after_answer` contains no
  permission-seeking or promise to wait; application-owned resumption still occurs
  only after verified answer playout.

## KI-002 — Transcript discontinuity at interruption boundaries

- **Status:** deferred to transcript presentation hardening.
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
- **Later acceptance case:** interrupted segments are represented coherently and
  related STT fragments share an explicit turn identity where the provider exposes
  one; missing provider text remains visibly incomplete rather than invented.

## KI-003 — Motorcycle paraphrases can be falsely marked out of scope

- **Status:** mitigated offline; live verification pending.
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
- **Remaining acceptance case:** repeat the relevant spoken variants in a bounded
  live full-deck observation and verify that STT wording still resolves to the
  intended mode. Generated prose must remain unable to choose navigation.

## KI-004 — Manual navigation during answer playout is deferred

- **Status:** deferred to multi-modal interaction hardening.
- **Behavior:** the navigable deck is enabled before narration, during narration,
  while waiting, and after completion. It is intentionally disabled while an
  answer is speaking in the first manual-navigation slice.
- **Reason:** interrupting an answer to browse raises a separate product choice:
  discard the answer, preserve a resumable answer cursor, or treat the slide
  change as contextual input to a replacement answer. That transition should be
  specified rather than inferred from narration semantics.
- **Later acceptance case:** choose and test one explicit answer-interruption
  policy, including late/stale provider callbacks and repeated slide selections.

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
