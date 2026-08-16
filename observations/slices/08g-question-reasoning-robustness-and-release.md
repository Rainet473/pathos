# Verified slice: question-reasoning robustness, caching, and release evidence

## Hypothesis

The richer follow-up path remains bounded, safe, understandable, and fast enough
across natural wording and adversarial lifecycle conditions, including graceful
speech after recoverable plan-content failures.

## Observable path

```text
natural spoken follow-up -> bounded planning/search -> validated or recovered directive
  -> tool-disabled streamed answer -> verified wait/resume
  -> retained trace, cache, latency, lifecycle, transcript, and browser evidence
```

## Scope

- New behavior boundary: recoverable planner content failure may become one new
  application-owned, citation-free answer directive.
- Existing real boundaries under evaluation: STT wording, Gemma tool calls,
  LiveKit cancellation/disconnect, streamed Gemma answer, Inworld TTS, browser
  status/focus, and provider token/timing metrics.
- Still fake: deterministic tests inject malformed tool calls, stale identities,
  cancellation points, disconnects, and repeated callbacks without spending
  provider credits.
- Explicitly excluded: embeddings/network search, arbitrary ASR rewriting,
  provider replacement, manual slide browsing during answer audio, and private
  provider representations not exposed by LiveKit.

## Entry gate

- [x] Slice 5 deterministic and live answer-focus gates pass.
- [x] Attempt `6729e607-f271-487c-9859-bfdf61c5d44b` completed the cross-slide
  ABS focus/restore/continue case.
- [x] KI-007 acronym drift and KI-008 silent recoverable failures have retained
  attempt evidence.
- [x] Expectation handout exists before source changes.
- [x] First failing fallback and robustness tests are defined and observed.

## Sub-gates

1. **Validated fallback:** malformed/citation-invalid plans either self-correct
   once or produce one safe citation-free directive; nonrecoverable boundaries
   stay fail-closed.
2. **Language and lifecycle robustness:** phrase variation, references, claims,
   corrections, incomplete turns, continuation, acronym drift, cancellation,
   stale results, repeated calls, unsupported tools, and disconnect are covered.
3. **Performance and release evidence:** cache/token and stage latency are
   summarized, the browser rubric is exercised, prior gates rerun, and public
   docs/limitations are updated without private rationale.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Application fallback | New red application tests | new directive has no rejected citations/focus, correct disclosure/boundary, unchanged cursor |
| Bridge fallback | Fake rejected/malformed planner | one answer is streamed and settles with default/explicit continuation; duplicate callbacks cannot repeat it |
| Fail-closed matrix | Planner/bridge tests | timeout/provider/stale/cancel/disconnect/unknown tool never produce fallback speech |
| Phrase matrix | Recorded deterministic cases plus bounded live prompts | all required modes and utterance forms produce recorded plan/result or honest limitation |
| Acronym behavior | `ABS`, `A B S`, `APS` cases | original transcript retained; unique deck resolution or clarification is explicit |
| Cancellation/races | Existing and strengthened tests | no late result, focus, answer, beat commit, or duplicate resume |
| Cache/latency | JSONL evidence summary | cached/total ratio and endpoint/planning/search/TTFT/TTS distributions are reported separately |
| Browser | Repeatable observation rubric | modes, waiting, continuation, interruption, and focus are understandable and coherent |
| Regression | `scripts/check.sh` plus focused suites | all retained deterministic gates and production build pass |

## Exit gate

- [x] All three sub-gates pass or any exception is explicitly accepted and
  recorded as a known limitation.
- [x] Recoverable failure path is useful, visible, and controlled.
- [x] Previous offline and live evidence remains valid.
- [x] Cache behavior and non-search latency regression are quantified.
- [x] Artifacts, usage bounds, and remaining limitations are recorded.

## Red evidence

The first focused run executed 33 application and silent-planner tests. Nineteen
existing cases passed and fourteen new assertions failed for the intended
reasons:

- twelve application cases found no `recover_answer_plan` transition, covering
  one related disclosed answer, clarification, safety boundary, and nine
  explicitly nonrecoverable failure codes;
- one malformed-JSON case cancelled after its first provider response instead of
  accepting a corrected terminal call; and
- one repeated-malformed case stopped after one request instead of allowing
  exactly one correction and then failing.

No source code had changed when this baseline was captured.

## Verified fallback and lifecycle evidence

- Focused backend recovery/planner/bridge suite: `46 passed`.
- Focused frontend planning/state/transport suite: `21 passed`.
- Acronym and full-deck policy suite: `61 passed` after the terminology boundary
  was added.
- Cancellation/disconnect additions prove that a cancelled provider request is
  recorded and re-raised, and browser disconnect cancels in-flight planning with
  no answer or fallback speech.
- Full retained gate after all Slice 6 changes: `291 passed, 3 skipped`;
  frontend `37 passed`; production build passed. The three skips are explicit
  paid LiveKit transport, planner, and robustness opt-ins.
- A final red/green wording check proved recovered speech discloses that
  presentation support could not be validated instead of falsely claiming the
  deck lacks the answer: `2 failed` before the prompt distinction, then
  `2 passed`.

The terminology resolver retains the authoritative transcript and records only
deck-authored candidates. Exact `ABS` and spaced `A B S` select the authored ABS
material. `APS` produces one `phonetic_neighbor` candidate for `ABS`; `AWS`
produces no candidate. If a recoverable planner failure remains for `APS`, the
application asks “Did you mean ABS?” and waits rather than rewriting it.

## Bounded live planner robustness observation

The paid test was announced as three silent cases, no audio, and at most nine
requests. The first sandboxed attempt produced provider connection errors and
was excluded. The network-enabled run retained all requests in
`.runtime/livekit-silent-planning.jsonl`:

| Case | Provider requests | Result | Observation |
|---|---:|---|---|
| anti-lock phrase variation | 2 | accepted | searched `braking-abs`, cited deep-dive evidence, grounded answer/focus |
| listener correction | 2 | accepted | corrected “ABS creates grip” from current braking evidence |
| `APS` acronym neighbor | 3 | recoverable rejection | first run repeated `APS`; after prompt tightening the retry searched `ABS` and found the right evidence, but cited the active user turn and was rejected as `ineligible_turn` |

The raw acronym plan remains an honest planner-quality limitation. It is not a
production silent failure: `ineligible_turn` is recoverable, so the bridge drops
the rejected citation and focus and the application emits the bounded ABS
clarification proved offline. Validation was not relaxed.

## Deterministic language and race matrix

| Case | Result |
|---|---|
| Earlier-turn reference | eligible logical turn citation accepted; active/future/provider IDs rejected |
| Phrase variation and related knowledge | bounded search/grounding or disclosed model knowledge |
| Listener claim/correction | grounded correction from current presentation evidence |
| Incomplete adjacent STT fragment | combined once before planning; completed turns are not delayed |
| Default wait / explicit continuation | clarification waits; other answers resume only after verified playout when authorized |
| Malformed JSON/schema | one native correction at most, then eligible fresh fallback |
| Timeout/provider/stale/cancel/disconnect | fail-closed with no fallback speech or late state mutation |
| Duplicate/repeated callbacks | one answer and one settlement at most |
| Unsupported or multiple tools | fail-closed and visible |

## Retained cache and latency measurement

The reproducible command is:

```bash
PYTHONPATH=backend/src python -m voice_presentation.transport.reasoning_evidence \
  .runtime/conversation-diagnostics.jsonl --attempt-id <attempt-id>
```

Across the four retained reasoning attempts `a4df4e08…`, `f15cc0d8…`,
`3536b0b3…`, and `6729e607…`:

- 19 planning records: 11 accepted, 5 cancelled, and 3 rejected;
- provider-reported cached planning input: 20,352 / 104,842 tokens, or 19.4%,
  with nonzero cache in 6 records;
- accepted non-search planning: 6 records, 1.653 s median, 5.933 s p95/max;
- accepted search planning: 5 records, 3.393 s median and 4.299 s p95/max;
- endpointing: 12 records, 1.201 s median and 1.202 s p95;
- historical pipeline LLM TTFT: 72 unscoped records, 650.5 ms median and
  1.180 s p95;
- historical pipeline TTS first audio: 72 unscoped records, 680 ms median and
  1.061 s p95.

Those historical pipeline records predate purpose tagging, so they cannot be
claimed as answer-only measurements. New diagnostics attach application turn ID
and purpose, and the summarizer reports answer LLM/TTS separately once a new
voice attempt is made. Cache is measured as provider reported; individual turns
with zero cached tokens remain valid results.

## Browser observation

The production backend and frontend launchers were started from the configured
Python 3.12 conda environment and opened in Chrome at
`http://127.0.0.1:5173/`. Before Start, the DOM and rendered page both showed
`Quiet and disconnected`, Start enabled, Stop disabled, and no room,
microphone, or model connection. The browser console contained no warnings or
errors. The processes were then shut down cleanly.

Automated browser observation did not activate the microphone or transmit new
audio. The listener's retained manual voice run supplies the qualitative
answer/continue evidence, while deterministic frontend tests verify that a
recovered answer visibly explains that rejected support and slide focus were
discarded. A future voice attempt will populate the new answer-scoped LLM/TTS
metrics; historical timings remain labeled unscoped rather than retroactively
inferred.

## Fallback or rollback

Retain the current controlled waiting failure and explicit retry path for every
planner failure. The fallback transition can be removed without changing the
accepted-plan, streaming, focus, or continuation paths.

## Remaining limitation

The live Gemma planner can still cite the active user turn after correctly
searching the `ABS` candidate for an `APS` transcript. Application validation
rejects that plan and the new recovery asks a bounded clarification, so the
limitation affects answer directness rather than state safety. One new acoustic
run is also needed if answer-only LLM/TTS distributions are required; the
instrumentation is now present and the summarizer reports those fields without
mixing narration.
