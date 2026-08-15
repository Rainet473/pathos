# Expectation handout: question scope and evidence

## User-visible outcome

Questions receive concise answers that honestly distinguish curated presentation material from broader model knowledge. Ambiguous, unrelated or unsafe requests do not produce fabricated presentation-grounded claims.

## Inputs, outputs and boundaries

- Inputs: committed question, validated presentation material, related terms, safety boundaries and current conversation phase.
- Outputs/events: one of `grounded`, `extended_knowledge`, `needs_clarification` or `out_of_scope`, plus selected evidence and an optional supporting slide proposal.
- External boundaries: the main model interprets language; deterministic policy validates evidence availability and permitted response mode.
- Preconditions: content schema has stable slide/beat IDs and deep-dive entries.
- Non-goals: a general search engine, exact repair advice, legal advice, a vector database or deterministic scoring of natural-language answer quality.

## Behavior map

```text
question
  ├─ direct curated evidence → grounded
  ├─ related but uncovered + safe → extended_knowledge + disclosure
  ├─ meaning materially ambiguous → needs_clarification
  └─ unrelated, unsafe or model-specific exact advice → out_of_scope
```

## Invariants

- Grounded mode includes selected curated evidence.
- Extended mode explicitly discloses that the exact answer is outside the presentation material.
- Clarification asks one focused question and does not resume narration while unresolved.
- Out-of-scope mode does not invent exact specifications or unsafe procedures.
- A proposed supporting slide must refer to known content and is validated by the controller.
- Generated prose is never parsed to infer the mode or slide transition.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| “Why does engine braking feel stronger in a low gear?” | `grounded` with engine-braking material | Automated |
| “What is a slipper clutch?” | `extended_knowledge` with disclosure requirement | Automated plus response rubric |
| “Why does it jerk?” | `needs_clarification` | Automated plus response rubric |
| “What exact torque should I use for my axle nut?” | `out_of_scope` with service-manual redirect | Automated plus response rubric |
| Unrelated entertainment question | `out_of_scope`; no slide proposal | Automated |

## Edge and race cases

- Empty/malformed: blank question, missing material repository and invalid proposed slide.
- Duplicate/repeated: repeated question should not mutate presentation progress.
- Late/out-of-order: classification from a superseded turn is discarded.
- Cancellation: interrupted clarification or answer leaves the original presentation cursor intact.
- Partial failure: retrieval failure cannot be mislabeled as grounded evidence.
- Recovery: deterministic content reload rejects duplicate IDs rather than silently changing references.
- Capability mismatch: a model may supply semantic intent without stable interim transcripts; only the committed turn is classified.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Grounding | Claims stay within selected material | Unsupported precise facts presented as deck content | Question, evidence IDs and transcript |
| Disclosure | Extended answer briefly names the material gap | Broader knowledge is presented as grounded | Transcript and selected mode |
| Clarification | One focused disambiguating question | Multiple vague questions or an invented assumption | Transcript |
| Safety boundary | Specific repair/legal values are redirected | Confident fabricated value or risky instruction | Transcript and question |

## Open assumptions

- Initial deterministic retrieval uses curated terms and metadata; embeddings require evidence of a real miss.
- Semantic response quality remains an observation problem even when mode selection is deterministic.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [ ] Deterministic classification fixtures pass offline.
- [x] Live response-quality observations are deferred with a fixed rubric.
- [x] Retrieval limitations are explicit.
