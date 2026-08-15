# Expectation handout: six-slide deck progression

## User-visible outcome

The live presentation uses the fixed six-slide motorcycle deck. After each
verified narration playout, the application selects and speaks the next semantic
beat automatically, changes the visible slide only when the cursor crosses a slide
boundary, and completes after all 24 beats exactly once.

## Inputs, outputs and boundaries

- Inputs: validated local JSON material and correlated narration playout facts.
- Outputs/events: one provider-neutral narration directive per beat, ordered
  `beat_committed`, `beat_selected`, and slide-change events, and a final completed
  snapshot containing all committed cursors.
- External boundaries: JSON repository loading and the existing voice adapter's
  execution of application-selected directives.
- Preconditions: Slice 4's one-beat live path, interruption, question answering,
  transcript and continuation gates pass.
- Non-goals for this sub-slice: downloaded visual assets, live acoustic evaluation,
  embedding retrieval, transcript polish, or release documentation.

## Behavior map

```text
Start -> slide 1 beat 1 -> verified playout
                            |
                   commit current beat
                            |
                  select next cursor/turn
                            |
                 same slide or slide change
                            |
                     ... 24 beats ...
                            |
                    presentation complete
```

## Invariants

- The deck contains exactly the six planned slides in the locked order.
- Slide IDs and beat IDs are unique across the entire deck.
- Every slide has four short beats, curated deep-dive evidence, related terms,
  labels, and a nonblank visual description.
- Content is loaded from one JSON fixture rather than embedded in callbacks.
- Only verified narration playout commits the active beat.
- A non-final commit selects exactly one new narration turn; the model never
  decides the next slide.
- Crossing a slide boundary updates both the semantic cursor and visible slide;
  staying within a slide does not emit a slide change.
- The deterministic one-slide fake fixture remains available as the earlier
  regression/demo path.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Load full fixture | Six ordered slides and 24 globally unique beats validate | Automated |
| Complete slide 1 beat 1 | Slide 1 beat 2 is selected with a new turn | Automated |
| Complete slide 1 beat 4 | Cursor and visible slide move to slide 2 beat 1 | Automated |
| Complete final beat | Phase becomes completed with 24 committed cursors | Automated |
| Duplicate beat ID on different slides | Deck validation fails before runtime | Automated |
| Interrupt any beat | Existing uncommitted-cursor behavior remains unchanged | Regression |

## Edge and race cases

- Empty/malformed content: existing Pydantic validation rejects it at repository
  load.
- Duplicate identity: beat IDs are checked deck-wide, not only within one slide.
- Duplicate/late callback: existing turn correlation keeps a completed beat from
  selecting two successors.
- Cancellation: interruption does not invoke automatic next-beat selection.
- Partial provider failure: without verified playout, the current cursor remains
  uncommitted.
- Asset availability: executable visual assets are intentionally deferred to the
  later visual-integration sub-slice; visual descriptions remain required now.

## Exit criteria

- [x] Requirement-derived tests are observed failing before implementation.
- [x] The six-slide fixture validates with 24 unique beats.
- [x] Fake and real application sessions progress through the full deck offline.
- [x] All previous deterministic gates remain green.
- [x] Visual assets and live full-deck observations remain explicitly open.
