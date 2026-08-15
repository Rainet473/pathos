# Expectation handout: full-deck question resolution

## User-visible outcome

Natural questions about the six-slide motorcycle material select the correct
curated evidence and, when useful, temporarily show its slide. Related uncovered
concepts are disclosed as extended knowledge, ambiguous questions request one
clarification, and unsafe or unrelated requests remain out of scope.

## Inputs, outputs and boundaries

- Inputs: one committed transcript question and the validated six-slide deck.
- Outputs: one deterministic scope mode, selected evidence, an optional known
  supporting slide, and an application-issued answer directive.
- Boundaries: transcript text to deterministic material policy, then validated
  policy result to application state and provider-neutral generation instructions.
- Preconditions: the full deck and 24-beat automatic progression pass offline.
- Non-goals: open-domain semantic search, embeddings, unrestricted paraphrase
  equivalence, or deterministic grading of generated answer prose.

## Behavior map

```text
committed question
  -> safety/ambiguity boundary
  -> normalized material terms
     -> curated evidence match: grounded + supporting slide
     -> related-term match: extended + disclosure
     -> no safe match: out of scope
  -> controller validates temporary visible slide
  -> answer finishes -> wait or restore saved presentation slide
```

## Invariants

- The four scope modes remain explicit and mutually exclusive.
- Grounded mode contains nonempty curated evidence from one known slide.
- Extended mode contains no fabricated deck evidence and requires disclosure.
- Clarification has no supporting slide and asks one focused question.
- Unsafe exact repair values and unrelated requests cannot become grounded through
  loose term overlap.
- A supporting slide changes only `visible_slide_id`; the semantic presentation
  cursor remains on the original uncommitted beat.
- Continue restores the original presentation slide before narration resumes.
- Generated answer prose never determines scope, cursor, or slide selection.

## Fixed evaluation cases

| Question | Expected mode | Supporting slide |
|---|---|---|
| Why does a motorcycle need a clutch? | grounded | clutch-and-gears |
| Why does engine braking feel stronger in a low gear? | grounded | engine-braking |
| What is the purpose of rev matching? | grounded | rev-matching |
| Does ABS increase grip? | grounded | braking-abs |
| What is a slipper clutch? | extended_knowledge | clutch-and-gears or engine-braking |
| What is a quickshifter? | extended_knowledge | clutch-and-gears |
| What is cornering ABS? | extended_knowledge | braking-abs |
| Why does it jerk? | needs_clarification | none |
| What exact torque should I use for my axle nut? | out_of_scope | none |
| Who won last night's football match? | out_of_scope | none |

## Bounded paraphrase cases

- “How does a lower gear give higher revs during engine braking?” remains grounded
  on engine braking.
- “How does a lower gear help decrease speed?” remains grounded on engine braking.
- “Why do the revs rise in a lower gear?” resolves to drivetrain or rev-matching
  evidence rather than out of scope.
- “What happens if I let the clutch out too quickly?” remains grounded on the
  clutch slide.

These cases prove the recorded phrasing family only; they do not establish general
semantic equivalence.

## Edge and race cases

- Blank questions fail before state mutation.
- Repeated questions do not advance the presentation cursor.
- A late answer callback remains correlated to its issued turn.
- Interruption during the answer preserves the original cursor and eventual return
  phase.
- Content reload rejects duplicate identities instead of silently changing the
  resolver's target.

## Exit criteria

- [x] Tests fail first for the unsupported bounded paraphrases.
- [x] The fixed evaluation set produces the expected modes and slides.
- [x] Temporary full-deck slide selection and restoration pass offline.
- [x] Existing state, transcript, latency and progression regressions remain green.
- [x] Live qualitative response evaluation remains opt-in and open.
