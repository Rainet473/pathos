# Verified slice: portable deck asset package

## Hypothesis

The fixed motorcycle content can become a self-contained package while every
existing consumer continues to depend only on the normalized deck contract.

## Observable path

```text
deck.pptx -> exact extracted renders -> browser slide canvas
                         |
slide-breakdown.json -> filesystem repository -> validated PresentationDeck
                         |
                         v
              fake/live presentation policy
```

## Scope

- New real boundaries: deck-ID-based filesystem resolution and a safe PNG render
  endpoint selected by normalized deck/slide IDs.
- Still fake: future authoring-format importer and optional additional context.
- Explicitly excluded: runtime PPTX parsing and OCR/VLM extraction.

## Entry gate

- [x] Current six-slide manifest passes all existing gates.
- [x] Expectation handout exists.
- [x] Package test initially failed because `DeckPackageRepository` did not exist.
- [x] Source/render test initially failed because `deck.pptx`, `render_path`, and
  the HTTP render endpoint did not exist.
- [x] Frontend render test initially failed because the deck visual component did
  not exist.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Contract | Load the packaged manifest | Same deck ID, six slides and 24 beats |
| Source fidelity | Compare each PPTX embedded image with its named render | Six byte-identical pairs |
| Safety | Invalid/traversal deck IDs | Rejected before filesystem escape |
| Regression | Existing backend/frontend suites | No content or state regression |
| Observation | Inspect all source slides and render endpoint | Six coherent authored slides; PNG is served without a voice session |

## Exit gate

- [x] The package contract, six-slide progression, grounding, fake, and LiveKit
  bridge focused gate passes (42 tests).
- [x] Invalid and traversing deck IDs are rejected.
- [x] The manifest moved without changing six-slide/24-beat semantics.
- [x] The supplied PPTX is preserved byte-for-byte and its six browser renders
  match the six embedded images exactly.
- [x] All six slides were inspected at full size; order matches the normalized
  control-loop through braking/ABS progression.
- [x] PPTX-to-manifest import and additional context remain explicit future boundaries.

## Automated evidence: 16 August 2026

- Focused asset/progression/grounding/fake/bridge gate: 42 passed.
- Staged feature-slice Python regression: 203 passed, one opt-in paid test skipped.
- Full frontend regression: 54 passed; production build passed.
- The source and packaged PPTX SHA-256 values both equal
  `1cd737eabd63ed6932db1e76e2dfb1ba6017bfd818b23c5012fd718d3cecc548`.

## Fallback or rollback

Retain the existing direct manifest path while documenting the target package
layout; do not introduce provider-specific content loading.

## Next highest risk

A deterministic import command that turns a supplied deck plus handout into the
normalized package, using direct extraction for image-only decks and producing
an operator-review report before activation.
