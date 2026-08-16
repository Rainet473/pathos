# Expectation handout: deterministic follow-up planning and material search

## User-visible outcome

An operator can replay recorded follow-up planning actions offline and see either
one validated answer plan with traceable conversation/deck support or one bounded,
explicit rejection. Planning never speaks, navigates, resumes, or mutates the
presentation controller.

## Inputs, outputs and boundaries

- Inputs: active session/follow-up identity, logical-turn ledger, packaged
  presentation deck, zero to two bounded `search_material` calls, and one
  terminal `submit_answer_plan` proposal.
- Outputs/events: stable search query/evidence IDs, bounded search hits, native
  function call/result trace records, one application acceptance/rejection
  decision, and an immutable accepted answer plan when valid.
- External boundaries: the checked-in `slide-breakdown.json` package only; no
  network, embedding model, provider SDK, model call, speech, or browser state.
- Preconditions: the context/provenance slice and all retained offline gates pass.
- Non-goals: real Gemma tools, prompt design, streaming answer generation, TTS,
  focus-slide application, controller transitions, cache measurement, vector
  retrieval, or public fake-product endpoints.

## Behavior map

```text
plain follow-up + logical-turn ledger + active deck/session snapshot
  -> optional bounded deterministic material search (maximum two)
  -> exactly one terminal answer-plan proposal
  -> validate session, turn, evidence, slides, scope/source, focus, and bounds
  -> accepted immutable plan OR controlled terminal rejection
```

## Invariants

- Search is case-insensitive, deterministic, deck-local, and has no network or
  embedding dependency.
- Search accepts one to eight keywords, up to four phrases, up to six valid slide
  filters, and one to five requested results; normalized query text is at most
  512 characters.
- Search results serialize to at most 8192 UTF-8 bytes by default and include no
  more than one previous and one next same-slide segment per hit.
- Exact phrases and multi-term matches outrank broad single-term matches; a
  preferred slide breaks comparable scores but cannot defeat clearly stronger
  evidence elsewhere.
- Evidence IDs are stable functions of deck, slide, section, and segment index.
- A planning session permits at most two search calls, one terminal submission,
  and three total tool steps.
- Every cited logical turn resolves through the active application ledger and is
  delivered conversation history preceding the active follow-up.
- Every cited evidence ID came from a successful search in the same active
  planning session or from explicitly supplied current-slide evidence; every
  cited slide exists in the active deck.
- Scope and grounding source remain separate and coherent.
- A focus slide must be cited, valid, and supported by the plan; accepting a focus
  proposal does not change `visible_slide_id`.
- Continuation permission is absent from model plan input and cannot be granted
  by planning.
- Stale session/follow-up identity, timeout, explicit cancellation, repeated
  terminal calls, calls after terminal state, or excess steps cannot produce an
  accepted plan.
- Invalid proposals do not navigate, resume, generate an answer directive, or
  mutate presentation state.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Conversation reference | Zero-search grounded/conversation plan cites the interrupted logical turn and is accepted | Automated recorded case |
| Deck search | Search for friction-zone plate slip returns stable clutch evidence; grounded/presentation plan cites it | Automated recorded case |
| Mixed support | Grounded/conversation-and-presentation plan requires both a turn and searched evidence | Automated |
| Extended knowledge | Related uncovered question uses `extended_knowledge` + `model_knowledge` and no deck evidence claim | Automated |
| Clarification | Ambiguous reference uses `needs_clarification` + `none` and exactly one concise question | Automated |
| Out of scope | Unsupported or unsafe request uses `out_of_scope` + `none` with no focus or grounding citations | Automated |
| Invalid citation | Unknown or ineligible turn/evidence/slide rejects terminally without an accepted plan | Automated |
| Stale/cancelled/duplicate | Late or repeated actions return bounded rejection codes and no side effects | Automated |
| Operator sanity case | Recorded function/result/decision chronology makes both accepted paths auditable | Human rubric |

## Edge and race cases

- Empty/malformed: schema validation rejects blank/oversized queries, briefs,
  identifiers, malformed clarification, and unsupported scope/source pairs.
- Duplicate/repeated: query terms normalize deterministically; duplicate terminal
  submission and calls after terminal state are rejected.
- Late/out-of-order: search or submit with a stale session version or different
  active follow-up cancels the planning session.
- Cancellation: cancellation before work, after search, or after terminal state is
  idempotent and cannot create or replace an accepted plan.
- Partial failure: invalid search filters or plan citations yield one explicit
  code; the harness never falls through to free-form answering.
- Recovery: a fresh planning session can replay the same recorded actions and
  produce byte-identical search/plan data.
- Capability mismatch: provider tool-shape behavior remains deferred to the
  minimum real planner slice; this oracle uses provider-neutral recorded calls.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Traceability | Accepted plan support resolves to exact logical turns and/or stable deck evidence | Unresolved IDs or implicit prose-derived support | Recorded case summary and trace JSON |
| Bounds | Search, bytes, steps, terminal count, timeout, and cancellation are visible | Silent truncation or unbounded retry loop | Focused test output |
| State ownership | Controller snapshot is unchanged and result contains data only | Planning directly navigates, resumes, or creates speech | State comparison and accepted-plan schema |

## Open assumptions

- A default 10-second offline planning deadline is a safety bound, not a measured
  live latency target; the real Gemma planner slice must measure and revise it if
  necessary.
- Keyword/phrase retrieval over authored beats and deep dives is expected to be
  sufficient for six slides; embedding retrieval remains evidence-gated.
- `related_terms` may improve slide relevance but do not alone prove a grounded
  factual claim.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Conversation-citation and material-search recorded cases pass offline.
- [x] Search ranking, stable IDs, filters, neighbors, and byte bounds pass.
- [x] Plan coherence, citations, focus, stale/duplicate, cancellation, timeout,
  and step limits pass.
- [x] Invalid proposals cannot mutate presentation state or produce an accepted
  plan.
- [x] Deterministic backend and frontend regression gates pass.
- [x] Observation case was run and evidence recorded.
- [x] Deferred provider, streaming, navigation, caching, and latency risks remain
  explicit.
