# Expectation handout: model-directed presentation continuation

## User-visible outcome

When Pathos is interrupted or waiting, a natural standalone request such as
“Would you carry on with the presentation from there?” resumes narration. The
listener does not hear an acknowledgement, an explanation of the command, or a
second prompt asking whether to continue.

## Inputs, outputs and boundaries

- Input: a completed follow-up transcript while the presentation is
  `interrupted` or `waiting`.
- Model output: exactly one provider-neutral `continue_presentation` action
  proposal tied to the active follow-up turn and session version.
- Application output: a validated resume transition and one new narration turn.
- Fast boundary: canonical variants are recognized by the local bounded matcher
  and do not call the model.
- Semantic boundary: unmatched natural variants go through the existing silent
  planner, which may propose the typed action.
- Non-goals: letting generated prose control state, broad fuzzy matching,
  resuming a completed deck, or changing answer-and-continue policy.

## Required invariants

- The action proposal is terminal and mutually exclusive with an answer plan.
- Search is unnecessary for a standalone continuation request.
- The application verifies the follow-up ID, session version, and presentation
  phase before executing the action.
- A successful action creates narration, not an answer turn.
- The resumed beat remains uncommitted until verified playout completion.
- After that completion, ordinary narration automatically selects the next beat;
  the listener is not asked to continue again.
- Negative and compound requests remain answers: “do not continue,” “what does
  continue mean?”, and “explain ABS, then continue.”

## Matcher grammar

The local fast path may tolerate up to three bounded connector words around the
presentation target, such as “continue on with the presentation.” The connector
vocabulary is allowlisted (`on`, `with`, `the`, `your`, `our`) and matched
against the whole normalized utterance. It must not use an unrestricted wildcard
that could turn “continue searching the presentation” into a command.

## Observation rubric

| Case | Acceptable | Unacceptable |
|---|---|---|
| Canonical phrase | immediate narration; no planner/search | planning delay or answer |
| Natural standalone phrase | one action proposal, then narration | acknowledgement answer or waiting state |
| Resumed beat completes | next beat begins normally | asks to continue again |
| Compound question | answer flow retains continuation preference | direct resume before answering |
| Negated command | no resume | substring match changes state |

## Exit criteria

- [x] Tests fail first for matcher, planning contract, and bridge behavior.
- [x] Focused deterministic tests pass offline.
- [x] Full backend and frontend regression gates pass.
- [ ] A live microphone observation remains an explicit user gate.
