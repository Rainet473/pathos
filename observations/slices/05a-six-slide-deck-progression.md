# Verified slice: six-slide deck progression

## Hypothesis

The application-owned one-beat architecture can scale to the fixed 24-beat deck
by adding automatic application selection after each verified commit, without
changing interruption or question-state semantics.

## Observable path

```text
validated six-slide JSON -> application narration directive -> voice playout fact
  -> controller beat commit -> next application directive -> slide boundary event
  -> final completed state
```

## Scope

- New content boundary: the fixed six-slide motorcycle deck.
- New orchestration behavior: automatic next-beat selection after a non-final
  verified narration playout.
- Still fake: automated playout uses deterministic or event-shaped adapters.
- Explicitly excluded: paid live runs, external/downloaded assets, styling, and
  semantic paraphrase expansion.

## Entry gate

- [x] Slice 4 live interruption and both continuation variants pass.
- [x] Remaining prompt, transcript and scope issues are retained in
  `observations/known-issues.md`.
- [x] Expectation handout exists.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Content contract | Load full JSON and inspect IDs/required fields | Six ordered slides, four beats each, global uniqueness |
| Controller selection | Commit then select next narration turn | One correlated `beat_selected` event; invalid overlap rejected |
| Application progression | Drive every generated directive to completion | 24 commits in order, correct slide boundaries, terminal completion |
| Fake parity | Complete deterministic full-deck playouts | Same ordered cursor sequence and terminal phase |
| Regression | Full offline Python/frontend/build gates | All earlier behavior remains green |

## Exit gate

- [x] The full offline observable path passes.
- [x] Failure paths are deterministic and visible.
- [x] Previous tests still pass.
- [x] Deferred visual and live gates are recorded.

## Offline evidence: 16 August 2026

- The initial focused gate failed four tests because the full fixture did not
  exist and cross-slide duplicate beat IDs were accepted.
- The fixed deck now contains six ordered slides, four beats per slide, globally
  unique semantic IDs, curated deep-dive evidence, related terms, labels, and
  nonblank visual descriptions.
- The first automatic-progression implementation exposed a duplicate-callback
  race: a stale completion attempted to select another successor turn. A dedicated
  red regression test reproduced it before the selection guard was corrected.
- Both `ApplicationPresentationSession` and `FakePresentationSession` now traverse
  all 24 beats using application-issued turn IDs and verified playout completion.
- The configured live runtime loads `content/motorcycle-controls.json`; the earlier
  one-slide deterministic route continues to load `content/slice-two.json`.
- Focused result: 6 tests passed.
- Full Python result: 160 passed; the opt-in paid LiveKit test skipped.
- Full frontend result: 8 files and 42 tests passed.
- TypeScript production build passed with only the known approximately 717 kB
  bundle advisory.

## Deferred gates

- No paid live six-slide run has been started automatically.
- Slide-specific visual assets and their provenance are not yet integrated;
  `visual_description` is the contract for the next visual sub-slice.
- Deterministic scope/paraphrase evaluation and temporary question-slide
  restoration against the full deck are the next Slice 5 risk.

## Fallback or rollback

Keep the validated six-slide fixture while retaining the one-slide runtime route.
If automatic chaining exposes lifecycle ambiguity, stop after each committed beat
and repair application selection rather than giving navigation to the model.
