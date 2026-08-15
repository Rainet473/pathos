# Slice 5c - Six-slide visual system

## Entry gate

- Six-slide content and automatic beat progression are committed.
- Full-deck deterministic question resolution is committed.
- Both required live interruption paths have passed.

## Boundary under test

The application view transports authored visual intent, and both presentation clients render a deterministic diagram selected solely by the visible slide ID.

## Expected evidence

- Focused backend contract tests.
- Focused frontend visual-selection tests.
- Retained full backend and frontend test suites.
- Production frontend build.
- One combined full-deck live observation run after this offline gate passes.

## Exit evidence

- Focused backend visual-context contract: `2 passed`.
- Focused frontend visual selection contract: `2 passed`.
- Retained backend suite: `179 passed, 1 skipped`; the skipped test is the quota-spending LiveKit probe.
- Retained frontend suite: `44 passed` across 9 files.
- Production frontend build passed. Vite retained its existing advisory that the main bundle is larger than 500 kB.
- Six distinct code-native diagrams now cover the six authored slide IDs, with an accessible generic fallback.
- A sandboxed browser observation could not bind the local backend port. No visual observation is claimed; desktop and narrow-viewport inspection remains part of the combined full-deck live gate.
