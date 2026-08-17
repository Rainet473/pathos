# Verified slice: full-height live transcript

## Hypothesis

The live transcript can use the full workspace-dock height on desktop without
changing transcript data, expanding the overall workspace, or regressing the
bounded compact layout.

## Observable path

```text
bounded workspace dock
  -> transcript card keeps its heading visible
  -> message viewport fills the remaining card height
  -> additional messages scroll inside that viewport
```

## Scope

- New real boundary: desktop transcript sizing and overflow behavior.
- Explicitly excluded: transcript retention, ordering, automatic scrolling,
  domain events, provider behavior, and application state.

## Entry gate

- [x] The slide-first workspace and its responsive contract already pass.
- [x] The reported screenshot exposes unused transcript-card height.
- [x] The expectation handout exists before source changes.
- [x] The regression test failed against the old `138px` desktop cap.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Desktop CSS contract | offline test | transcript is a flex child with no desktop maximum height |
| Desktop rendering | browser at 2048 x 1245 | list reaches the card's bottom padding and owns overflow |
| Compact rendering | browser at 390 x 844 | 300px cap remains and page has no horizontal overflow |
| Frontend regression | Vitest and production build | all tests and build pass |

## Exit evidence

- The new contract failed before implementation because the full-height
  transcript rule did not exist, then passed after the CSS correction.
- Workspace contract: `5 passed`.
- Frontend suite: `43 passed`.
- TypeScript and Vite production build: passed.
- Desktop observation at 2048 x 1245: transcript card height `290px`, list
  viewport height `231px`, `max-height: none`, `overflow-y: auto`, and `15px`
  between the list and card bottom (the card padding).
- Compact observation at 390 x 844: transcript viewport remained capped at
  `300px`, retained internal overflow, and page scroll width equalled the
  `390px` viewport.
- Runtime/provider spend: none. The browser check used a temporary static
  fixture against the production stylesheet; the fixture was removed after
  observation.

## Deferred risk

Automatic scrolling to the newest final or interim transcript entry is a
separate behavior. This slice only ensures that the existing scroll surface
uses its available space.
