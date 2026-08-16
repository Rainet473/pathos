# Verified slice: core concepts and slide-first workspace

## Hypothesis

Pathos can adopt a slide-dominant workspace and a simpler conceptual vocabulary
without changing any live-session behavior.

## Observable path

```text
reader -> core concepts -> system and question graphs -> accurate mental model
listener -> live snapshot -> slide-first workspace -> unchanged controls/events
```

## Scope

- New real boundary: production responsive workspace layout and deck rail.
- Still fake: none; the layout consumes the existing real application snapshot.
- Explicitly excluded: domain/application changes, provider spend, semantic or
  web search, visual slide understanding, and generic deck import.

## Entry gate

- [x] Documentation/UI proposal slice passes its contract and release gate.
- [x] User approved the proposed workspace direction.
- [x] Expectation handout exists before source changes.
- [x] First failing documentation and workspace contracts were observed: five
  assertions failed for the missing concept vocabulary, role icons, layout
  regions, navigable rail, and responsive CSS; two existing checks remained
  green.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Documentation | offline contract | concept vocabulary, flowcharts, concise advantages, and emoji roles exist |
| UI structure | offline source/CSS contract | rail, dominant stage, inspector, and dock are explicit regions |
| Responsive behavior | browser at desktop and 390 px | no horizontal overflow; stage remains first and 16:9 |
| Regression | `scripts/check.sh` | all prior deterministic gates pass |

## Exit gate

- [x] Observable path succeeds at desktop and narrow widths.
- [x] Empty/failure/control states remain visible and controlled.
- [x] Previous tests still pass.
- [x] Artifacts and limitations are recorded.

## Exit evidence

- Documentation and workspace contracts: `7 passed`.
- Full deterministic release gate: `302 passed`, `3` paid-provider tests
  skipped, `39` frontend tests passed, dependency check clean, and TypeScript /
  Vite production build passed.
- Desktop browser observation at 1440 x 900: the primary slide measured
  952 x 532 px; the 152 px deck rail, 300 px inspector, transcript, and domain
  events remained available with no horizontal overflow.
- Narrow browser observation at 390 px: the slide measured 366 x 205 px, the
  deck rail became horizontally scrollable, domain events collapsed, and the
  page had no horizontal overflow.
- Architecture SVG: listener, transport, application, voice-agent, and content
  role emojis rendered without obscuring their labels.
- Runtime/provider spend: none. Visual observations used a temporary fixture
  against the production stylesheet and packaged slide renders; no fake product
  endpoint was added.

## Fallback or rollback

Revert the TSX/CSS layout while retaining the independently useful documentation
rewrite and architecture-icon changes.

## Next highest risk

Real-session transcript growth and unusually long provider/slide labels may need
additional overflow tuning after manual acoustic testing.
