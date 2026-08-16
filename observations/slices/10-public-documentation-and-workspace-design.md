# Verified slice: public documentation and slide-first workspace design

## Hypothesis

Pathos can present itself like a mature open-source voice-agent repository while
remaining precise about its implemented boundaries, and the slide-first UI can
be evaluated before production behavior or layout is changed.

## Observable path

```text
new contributor -> README architecture + quick start -> running quiet-start app
reviewer -> concept/advantage/limitation guides -> evidence-backed boundaries
product owner -> workspace proposal -> approve or revise production UI slice
```

## Scope

- New real boundary: GitHub-facing architecture asset and onboarding contract.
- Still fake: the workspace is a design proposal, not the production React UI.
- Explicitly excluded: `additional-context.json`, generic deck import, semantic
  or web search, slide-image understanding, deployment, and live provider spend.

## Entry gate

- [x] Slice 9 branch is clean and tracks the pushed feature branch.
- [x] Current release gate passed with 295 Python tests, 3 paid skips, 39
  frontend tests, dependency checks, and production build.
- [x] Expectation handout exists before public documentation/source changes.
- [x] First failing documentation contract is defined and observed: three tests
  failed for the missing architecture hero, public guides, and README sections;
  the existing-link baseline passed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Reference structure | Inspect official GitHub READMEs | README hierarchy is adapted, not copied |
| Claims | Trace protocols, planner, search, context, and diagnostics | each advantage/limitation matches code or retained evidence |
| Documentation | Offline contract test | required headings, files, links, and SVG exist |
| Architecture visual | Render SVG | labels are readable and the core loop is clear |
| UI proposal | Inspectable mockup | slide dominates; controls/evidence remain usable |
| Regression | `scripts/check.sh` | all existing gates remain green |

## Exit gate

- [x] README supports a clean first-time setup path.
- [x] Concept, advantages, and limitations documents are independently useful.
- [x] Architecture visual is accurate and readable.
- [x] UI proposal is delivered for explicit approval or revision.
- [x] Previous tests still pass.
- [x] Artifacts and limitations are recorded.

## Exit evidence

- Public documentation contract: `4 passed`.
- Full deterministic gate: `299 passed`, `3` paid-provider tests skipped,
  `39` frontend tests passed, dependency check clean, TypeScript and Vite
  production build passed.
- Architecture hero: rendered in Chrome at its native wide aspect ratio; all
  labels, boundaries, and directional links remained readable.
- Workspace proposal: inspected at desktop and 390 px viewport widths. It had no
  horizontal overflow; the 16:9 stage measured 954 x 537 px at desktop and
  348 x 196 px at the narrow viewport. The deck rail became horizontal and the
  secondary domain-event panel collapsed at the narrow breakpoint.
- Runtime/provider spend: none. This slice changes public documentation and
  provides a concept-only UI surface; the production React UI is unchanged.

## Fallback or rollback

Retain the current production UI and existing architecture guide. Documentation
files and the architecture asset can be revised independently without touching
runtime behavior.

## Next highest risk

Whether the approved slide-first hierarchy remains usable with real transcript
growth, long provider labels, narrow displays, and answer-interruption states.
