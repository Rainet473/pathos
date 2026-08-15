# Six-slide visual system expectations

## Observable behavior

- Every slide view exposes the authored `visualDescription` from the content fixture.
- The deterministic and live presentation screens render the same visual component.
- Each of the six supported slide IDs maps to a distinct, code-native diagram.
- The diagram is selected from the application-owned visible slide, not from narration text or the semantic cursor.
- A future or unknown slide ID renders a safe generic flow instead of breaking the presentation.
- The authored visual description is available to assistive technology.

## Automated gates

- Contract tests prove that fake and live application views preserve visual descriptions.
- Frontend tests prove that all six slide IDs select distinct visual specifications and that unknown IDs use the fallback.
- Existing backend and frontend suites remain green.
- The production frontend build succeeds.

## Human observation gate

Open the full live presentation and verify that slide changes replace the diagram without layout overflow at desktop and narrow viewport widths. This gate is intentionally deferred until the full-deck live run so it does not spend a separate provider session.

