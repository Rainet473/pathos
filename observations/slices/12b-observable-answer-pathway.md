# Verified slice: observable answer pathway

## Hypothesis

The existing sanitized planning-stage stream is sufficient to render a truthful,
node-by-node answer pathway without exposing hidden reasoning or changing the
backend protocol.

## Observable path

```text
presentation stage updates -> frontend trail reducer -> connected inspector nodes
```

## Scope

- New real boundary: the frontend retains the stages observed for the current
  follow-up and visualizes their progress.
- Still fake: deterministic snapshot sequences drive component/state tests.
- Explicitly excluded: chain-of-thought, token streaming, tool-call payloads,
  backend schema changes, and provider-specific traces.

## Entry gate

- [x] Spoken-continuation slice exits green with `52 passed`.
- [x] Existing planning statuses and responsive inspector pass.
- [x] Expectation handout exists.
- [x] First failing tests were observed: no pathway module or reducer state
  existed, and the inspector source contract could not find the component.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| State | Vitest stage-sequence matrix | complete/active/skipped/pending states are truthful |
| UI | Component/source contract | four labeled, connected, accessible nodes render in inspector |
| Responsive | Browser desktop and 390 px | no horizontal page overflow; active node remains legible |
| Regression | Full frontend suite/build | existing controls and layout remain green |

## Exit gate

- [x] Observable path succeeds for direct and searched answers.
- [x] Failure/reset paths are visible and controlled.
- [x] Previous frontend and workspace tests still pass.
- [x] Visual measurements and limitations are recorded.

## Exit evidence

- Path-state and live-state tests: `12 passed`; workspace contracts: `4 passed`.
- Complete frontend gate: `43 passed`; TypeScript check and Vite production build
  passed. Output remains split into a 217.28 kB initial application chunk and a
  496.93 kB on-demand LiveKit transport chunk.
- Desktop observation at 1440 x 900: the pathway measured 259 x 241 px inside
  the 300 px inspector, all four nodes were visible, the active node had the
  intended orange glow, and page width equalled viewport width.
- Narrow observation at 390 x 844: the pathway measured 350 x 127.5 px, four
  80 px nodes fit without internal or page horizontal overflow, and the active
  node and connectors remained legible.
- Visual inspection used a temporary static state fixture with production markup
  and CSS, not a paid live provider. Vite intentionally blocked the fixture's
  out-of-root slide-image URLs; that did not affect pathway layout evaluation.
- Retained repository gate: `323 passed`, `3` paid provider tests skipped,
  Python compilation clean, and no broken requirements.

## Fallback or rollback

Remove the pathway component and derived trail while retaining the existing phase
heading and descriptions.

## Next highest risk

Very rapid provider stage transitions may make intermediate active glows brief;
the completed trail should still preserve which route occurred.
