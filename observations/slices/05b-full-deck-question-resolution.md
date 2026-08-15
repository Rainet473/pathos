# Verified slice: full-deck question resolution

## Hypothesis

A bounded, content-aware deterministic resolver can cover the fixed full-deck
evaluation and recorded paraphrase family without moving state authority into the
LLM or adding embeddings.

## Observable path

```text
question -> deterministic mode/evidence/slide -> controller validation
  -> provider-neutral answer directive -> temporary slide -> validated restoration
```

## Scope

- New behavior: six-slide evaluation and bounded lexical normalization.
- Existing boundary reused: application answer generation and temporary slide
  restoration.
- Still fake: provider prose quality is represented by instructions in automated
  tests; a live observation remains separate.
- Explicitly excluded: arbitrary paraphrase robustness, vector search, prompt
  permission wording, and transcript interruption rendering.

## Entry gate

- [x] Six-slide fixture and automatic 24-beat progression pass offline.
- [x] KI-003 records the observed false out-of-scope behavior.
- [x] Expectation handout exists.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Fixed evaluation | Parameterized policy tests | All grounded/extended/clarify/out cases match |
| Recorded paraphrases | Parameterized policy tests | Relevant variants do not become out of scope |
| Evidence boundary | Inspect deterministic decision | Grounded evidence is nonempty and slide ID is valid |
| Visual context | Application interruption/answer/continue test | Visible slide changes temporarily; cursor never changes; restore is exact |
| Regression | Full offline gates | All earlier suites pass |

## Exit gate

- [x] Full offline observable path passes.
- [x] Failure boundary is deterministic and visible.
- [x] Previous tests pass.
- [x] Live response-quality observation remains explicitly open.

## Offline evidence: 16 August 2026

- The first focused run passed 13 evaluation cases and failed three bounded
  phrasing cases for observable reasons: an overview-slide tie, no normalization
  between “decrease” and “slows,” and no normalization between “quickly” and
  “abrupt.”
- The resolver now gives curated concept terms more weight than generic explanation
  words and applies a small explicit alias table for gear/rev/braking language.
- Exact related terms are checked before grounded overlap, preserving disclosed
  extended mode for slipper clutch, quickshifter, and cornering ABS.
- An added adversarial case initially misclassified “Which motorcycle movie should
  I watch?” as grounded. Grounding now requires two distinct material overlaps as
  well as the weighted score, so a generic domain word is insufficient.
- The fixed evaluation, four recorded paraphrases, unrelated/unsafe cases, and
  full-deck temporary ABS slide restoration all pass offline.
- Focused result: 24 tests passed.
- Full Python result: 177 passed; the opt-in paid LiveKit test skipped.
- Full frontend result: 8 files and 42 tests passed.
- TypeScript production build passed with the known approximately 717 kB bundle
  advisory.

## Deferred gate

No paid live response-quality run was started automatically. The offline result is
bounded to the named evaluation phrases and must not be reported as general semantic
paraphrase robustness.

## Fallback or rollback

Retain exact curated evaluation phrases and report unsupported variants as a known
limitation. Do not add model-directed navigation or embeddings without a measured
failure that the bounded resolver cannot address safely.
