# Verified slice: deterministic follow-up planning and material search

## Hypothesis

Recorded model actions can complete the full bounded reasoning transaction
offline—conversation citation or deck search followed by one validated terminal
plan—while invalid actions remain unable to affect presentation state.

## Observable path

```text
recorded follow-up tool actions + provenance ledger + packaged deck
  -> bounded search and planning session
  -> native call/result trace + application decision
  -> immutable accepted plan or explicit controlled rejection
```

## Scope

- New real boundary: deterministic retrieval over the shipped six-slide deck
  package and validation against Slice 1 logical-turn provenance.
- Still fake: model actions are recorded fixtures executed by a deterministic
  test harness; no fake product endpoint is added.
- Explicitly excluded: LiveKit tool registration, Gemma inference, speech,
  controller mutation, answer-focus navigation, continuation, browser UI,
  embeddings, network search, caching, and provider credits.

## Entry gate

- [x] Context/provenance slice is committed and its focused/full gates passed.
- [x] Expectation handout exists.
- [x] First failing tests are defined for missing reasoning contracts, material
  search, planning validation, and the recorded harness.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Contract | Schema/bounds/coherence tests | Invalid model-shaped payloads fail independently of implementation behavior |
| Retrieval | Fixed queries over packaged deck | Ranking, filters, evidence IDs, neighbors, and byte ceiling are deterministic |
| Vertical harness | Conversation and material-search recorded action fixtures | Each ends in exactly one accepted traceable plan |
| Adversarial | Stale, invalid, duplicate, cancelled, timed-out, and excess-step cases | Explicit terminal codes; no accepted plan or controller mutation |
| Regression | Repository check script | All retained offline Python/frontend/package/build gates pass |
| Observation | Inspect both accepted trace chronologies and resolved support | Operator can follow every call, result, decision, and citation |

## Exit gate

- [x] Both accepted observable paths succeed repeatedly.
- [x] Invalid/stale/duplicate/cancelled/timeout paths are visible and controlled.
- [x] Presentation controller state remains unchanged by planning.
- [x] Previous tests still pass.
- [x] No provider request or credit is used.
- [x] Artifacts, limitations, and next risk are recorded.

## Recorded evidence

### Red baseline

The three new test modules were collected before implementation and failed with
three intended import errors: `voice_presentation.domain.reasoning`,
`voice_presentation.content.search`, and
`voice_presentation.application.follow_up_planning` did not yet exist.
The final authority audit then added eligibility and missing-terminal-decision
tests before their fix; the targeted run stopped at the intended missing
`ineligible_turn` contract during collection.

### Automated gates

- Focused Slice 1 + Slice 2 gate: `57 passed in 1.03s`.
- Repository gate: `230 passed, 1 skipped in 2.50s`; the skipped LiveKit audio
  transport test remains explicitly opt-in because it spends quota.
- Dependency gate: `pip check` reported no broken requirements.
- Frontend gate: 7 files and 34 tests passed.
- Production frontend type-check/build passed. Vite retained the pre-existing
  approximately 708 kB chunk-size warning.
- `git diff --check` passed.

### Operator observation

The recorded suite was replayed directly against the packaged deck and Slice 1
provenance ledger:

- `conversation-citation` accepted `answer-plan-0003` with logical turn
  `narration-0002`, zero searches, and trace chronology function call -> function
  result -> application decision.
- `material-search` accepted `answer-plan-0007` with evidence
  `motorcycle-controls.clutch-and-gears.narration.1`, focus slide
  `clutch-and-gears`, one search, and trace chronology search call -> result ->
  submit call -> result -> application decision.
- Replaying both cases produced byte-identical serialized runs.

This observation was wholly offline. It made no LiveKit, model, TTS, embedding,
or network request and used no provider credit.

## Oracle corrections made before exit

- Clarification and out-of-scope examples were corrected to their valid schema
  shapes before implementation instead of preserving a contradictory draft
  expectation.
- Presentation-grounded plans may also cite a contextual conversation turn, but
  deck evidence remains mandatory; this matches the approved recorded case while
  keeping grounding-source validation strict.
- Explicit current-slide evidence is a valid zero-search grounding source. It is
  validated as belonging to the current slide and is session-local just like
  searched evidence.

## Files in this slice

- `backend/src/voice_presentation/domain/reasoning.py`
- `backend/src/voice_presentation/content/search.py`
- `backend/src/voice_presentation/application/follow_up_planning.py`
- `tests/domain/test_follow_up_reasoning_contracts.py`
- `tests/content/test_material_search.py`
- `tests/application/test_follow_up_planning.py`
- `tests/fixtures/follow-up-planner-actions.json`
- `expectations/deterministic-follow-up-planning.md`
- `observations/slices/08b-deterministic-follow-up-planning.md`

The existing live lexical question path, transport adapters, controller, speech,
and browser code are unchanged.

## Remaining risks and deferred work

- Recorded actions prove the application contract, not that LiveKit Inference
  Gemma will emit the required native tool sequence reliably.
- The 10-second deadline is an offline safety bound, not measured live latency.
- Lexical retrieval is adequate for this six-slide package only; no claim is made
  for larger decks, embeddings, or semantic recall.
- Tool-disabled streaming answers, application-applied focus navigation,
  continuation after verified playout, prompt-cache measurements, and browser
  qualitative evidence remain gated future slices.

## Fallback or rollback

The committed context/provenance slice and unchanged lexical live answer path
remain runnable. The deterministic planning modules can be removed without
altering transport, controller, narration, or live speech behavior.

## Next highest risk

Whether the selected LiveKit Inference Gemma adapter can reliably emit the native
bounded tool sequence and terminal plan without speech, role normalization loss,
or validation bypass.
