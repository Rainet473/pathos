# Expectation handout: portable deck asset package

## User-visible outcome

A presentation is selected from one self-contained asset directory. The current
motorcycle presentation includes its authored PPTX and exact browser-ready slide
renders without changing its validated narration content or runtime behavior.
A future importer can create the same package without coupling provider or domain
code to a file format.

## Inputs, outputs and boundaries

- Inputs: `assets/<deck-id>/slide-breakdown.json`, optional `deck.pptx`, and
  optional `renders/<slide-id>.png` files.
- Outputs: the existing validated `PresentationDeck` plus a safe slide-render
  lookup used by the browser.
- External boundaries: filesystem content repository only.
- Preconditions: the normalized manifest passes the existing deck schema.
- Non-goals: parsing PPTX in the runtime, arbitrary authoring, OCR/VLM extraction,
  and additional-context retrieval in this slice. The supplied motorcycle PPTX
  contains one full-slide raster image per slide, so semantic extraction remains
  the job of the handout/import pipeline rather than the live runtime.

## Behavior map

```text
deck.pptx or another authoring source (optional, provenance)
                         |
                         v
assets/<deck-id>/slide-breakdown.json + rendered slide assets
                         |
           +-------------+-------------+
           |                           |
           v                           v
validated PresentationDeck     safe render endpoint
                         |
                         v
        fake runtime / live runtime / browser deck view
```

## Invariants

- Runtime state and provider adapters consume normalized deck data, never PPTX
  library objects.
- Deck-relative asset paths cannot escape their package directory.
- Missing optional source files do not prevent a manifest-only deck from loading.
- An invalid manifest fails before a session starts.
- A requested render must name a slide that exists in the normalized manifest.
- The supplied motorcycle renders preserve the PPTX slide order exactly.
- The deterministic one-slide fixture remains independent and available.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Load motorcycle package | Same six slides and 24 beats validate | Automated |
| Open motorcycle source | Six PPTX slides map 1:1 to six normalized slide IDs | Automated + visual |
| Browse in live UI | Exact extracted deck render changes with the visible slide | Automated + browser |
| Missing optional `deck.pptx` in another package | Manifest-backed presentation still loads | Automated |
| Invalid deck ID/path | Repository rejects it without traversal | Automated |
| Future imported deck | Importer emits the same normalized contract | Deferred human/tooling gate |

## Edge and race cases

- Empty/malformed: empty deck ID and invalid JSON are rejected.
- Duplicate/repeated: duplicate semantic IDs retain existing schema failures.
- Late/out-of-order: not applicable to immutable package loading.
- Cancellation: not applicable to synchronous local manifest loading.
- Partial failure: missing render gets a visible code-native fallback, not a crash.
- Recovery: operator fixes the package and restarts/reloads the session.
- Capability mismatch: unsupported authoring formats fail in import tooling, not
  in the presentation runtime.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Portability | One directory contains the normalized deck and its asset provenance | Content is scattered through callbacks and provider prompts | Directory tree and README |
| Runtime parity | Narration semantics remain stable while the browser shows the authored render | Packaging changes semantic order or narration | Regression output and screenshot |
| Visual fidelity | Every source slide is inspected and the extracted render is byte-identical to its embedded slide image | A reconstructed or mismatched image is shown | Hash comparison and six-slide inspection |

## Open assumptions

- `additional-context.json` is a reserved future input and is not loaded yet.
- A source `deck.pptx` remains optional for other packages; it is present for
  `motorcycle-controls`.
- Rendered slide images coexist with code-native fallback diagrams.
- Automatic PPTX-to-manifest ingestion is a later slice. This slice packages and
  verifies the user-authored source without interpreting it at session time.

## Exit criteria

- [ ] Tests were written before implementation.
- [ ] New tests were observed failing for the intended reason.
- [ ] Deterministic suite passes offline.
- [ ] Observation cases were run and evidence was recorded.
- [ ] Deferred risks are explicit.
