# Verified slice: question-reasoning context and turn provenance

## Hypothesis

The application can represent a provenance-aware follow-up chronology with
logical turn IDs, plain native messages, native tool records, and actual
interrupted text without changing the current live answer path or trusting
provider message IDs as state authority.

## Observable path

```text
recorded logical turns + provider fragments + deterministic tool actions
  -> provider-neutral provenance ledger and context trace
  -> JSON round-trip + installed LiveKit format projection
  -> operator can audit the ten-turn chronology
```

## Scope

- New real boundary: provider-neutral context items formatted through the locally
  installed LiveKit 1.5.17 OpenAI-compatible chat formatter.
- Still fake: search calls, tool results, plan submissions, and application
  decisions in the ten-turn fixture are deterministic recorded data.
- Explicitly excluded: model/provider calls, provider credits, live speech
  changes, material retrieval, plan execution/validation policy, navigation,
  continuation changes, prompt-cache claims, and provider-private wire capture.

## Entry gate

- [x] Current retained offline gates pass on this checkout.
- [x] Expectation handout exists.
- [x] First failing test is defined: the ten-turn fixture requires logical-turn,
  tool-item, decision, and formatter contracts that do not yet exist.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Automated contract | Focused provenance and context-trace tests | Missing-contract red becomes green without weakening assertions |
| Automated fixture | Serialize, parse, and reserialize the ten-turn chronology | Canonical payload is identical and every cited turn resolves |
| Installed adapter | Format the chronology with the pinned LiveKit SDK offline | Developer roles, plain messages, calls, and results retain order and native shapes |
| Regression | Full offline Python, frontend test, type, and build gates | All prior gates remain green |
| Observation | Inspect canonical fixture JSON against the handout rubric | Actual text, chronology, fidelity label, and decisions are unambiguous |

## Exit gate

- [x] Observable path succeeds repeatedly.
- [x] Failure paths for invalid citations, conflicting mappings, and malformed
  native tool items are visible and controlled.
- [x] Previous tests still pass.
- [x] No live provider request or credit is used.
- [x] Artifacts and limitations are recorded.

## Fallback or rollback

The existing role-only `.runtime/llm-context.jsonl` trace and unchanged lexical
question path remain usable. New provenance contracts can be removed without
changing presentation state, transport, or speech behavior.

## Next highest risk

Whether bounded deterministic material search and answer-plan validation can
resolve conversation and deck evidence coherently while rejecting stale,
duplicate, oversized, or invalid model proposals.

## Evidence recorded on 16 August 2026

- Entry gate before new tests: 173 Python tests passed, one opt-in LiveKit test
  skipped, 34 frontend tests passed, dependency consistency passed, and the
  production build succeeded.
- Red baseline: the two new test modules failed collection only because the
  required provenance and LiveKit formatting modules did not exist.
- Focused green gate: 15 provenance, reasoning-context, and retained context-trace
  tests passed.
- Full exit gate: 186 Python tests passed, one opt-in LiveKit test skipped, 34
  frontend tests passed, dependency consistency passed, and the production build
  succeeded. The existing large-frontend-chunk warning remains unrelated.
- Operator inspection: the recorded fixture contains 10 logical turns, 18 audit
  entries, 27 model-context items, and 27 locally provider-formatted items. Two
  accepted application decisions remain audit-only. The two interrupted
  assistant turns retain only the recorded partial text.
- Provider-format result: the local LiveKit 1.5.17 OpenAI-compatible formatter
  preserved the expected `system`, interleaved `developer`, plain
  `user`/`assistant`, native tool-call, and native tool-result chronology.

No network request, live model inference, or provider credit was used.

## Expectation clarification

The first implementation tagged both a developer annotation and its following
plain message with the logical message identity. A focused test made that
ambiguous for actual-text resolution. The representation was tightened so only
the natural user/assistant message carries `logical_turn_id`; the developer item
remains immediately adjacent metadata. No user-visible expectation changed.

## Files changed for this slice

- `backend/src/voice_presentation/domain/provenance.py`
- `backend/src/voice_presentation/transport/context_trace.py`
- `backend/src/voice_presentation/adapters/livekit/context_format.py`
- `tests/domain/test_turn_provenance.py`
- `tests/transport/test_question_reasoning_context.py`
- `tests/fixtures/question-reasoning-turn-10.json`
- `expectations/question-reasoning-context.md`
- `observations/slices/08a-question-reasoning-context.md`

## Remaining risks and deferrals

- The installed formatter result is not a provider-wire capture. The first real
  planner slice must inspect the closest observable normalized context.
- The live question path is intentionally unchanged and still uses lexical scope
  selection with no model tools.
- Search, plan validation/execution, live tool reliability, streamed answer
  generation, focus navigation, cancellation, caching, and latency evidence
  remain gated later slices.
- Provider-fragment grouping remains limited to explicit IDs and actual retained
  text; missing words are never reconstructed.
