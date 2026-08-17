# Expectation handout: citation-tolerant answer planning

## User-visible outcome

When the model finds valid presentation evidence and prepares a grounded answer,
an unrelated citation metadata error does not downgrade the answer to extended
knowledge. Pathos removes the unusable citation, preserves the model's answer
brief and valid evidence, and continues with the grounded response. Citation
repairs are visible only in private diagnostics, not in the presentation UI.

## Observable path

```text
model answer-plan proposal
  -> validate scope/source shape without trusting citation coherence
  -> resolve turn, evidence, slide, and focus references
  -> filter invalid optional references
  -> enough support remains for the declared grounded mode?
       yes -> accept normalized plan -> grounded answer
       no  -> reject -> existing safe recovery
  -> record every removed or derived reference in planning diagnostics
```

## Required behavior

- The active follow-up turn is never accepted as supporting conversation
  evidence. It is removed and logged.
- Unknown or ineligible conversation IDs are removed.
- Evidence IDs absent from the current planning transaction are removed as
  direct evidence, but their structured deck/slide prefix may still be used to
  derive a candidate slide after validating it against the packaged deck.
- Unknown slide IDs are removed. An unsupported or unknown focus slide becomes
  `null`, so navigation failure cannot suppress an otherwise valid answer.
- Trusted slide IDs are derived from retained or structurally parseable evidence
  IDs when the model omitted or misspelled `supportingSlideIds`.
- When a valid slide is the only surviving citation, the application derives a
  bounded summary evidence hit from that packaged slide. This keeps the answer
  grounded in real material rather than trusting the model's unsupported text.
- If a focus slide is invalid and one verified evidence-derived slide is
  available, that slide becomes the normalized focus. Otherwise focus becomes
  `null`.
- `groundingSource: presentation` retains valid deck evidence and uses no
  conversation citations.
- `groundingSource: conversation` retains only eligible preceding turns and no
  deck evidence.
- Grounded plans use the support that actually survives: combined when both
  conversation and presentation survive, presentation when evidence or a valid
  slide survives, and conversation when only an eligible preceding turn
  survives.
- The model's `scope`, `answerBrief`, clarification policy, and valid evidence
  remain unchanged.
- Citation relationships are intentionally tolerant on the model-proposal type;
  only the application-normalized `ValidatedAnswerPlan` enforces the strict
  grounding and focus invariants used by answer generation.

## Fail-closed boundary

Filtering is tolerant only when the resulting plan remains truthful:

- A grounded plan remains grounded whenever at least one eligible preceding
  turn, current valid evidence ID, or verified slide reference survives.
- A verified slide reference is converted into bounded packaged evidence before
  answer generation; the slide ID alone is never passed to speech as if it were
  textual support.
- Only a grounded plan with no surviving turn, evidence, or valid/derivable slide
  support is rejected and converted by the existing recovery path to extended
  knowledge.
- Stale session/follow-up identity, timeout, duplicate terminal calls, and
  unsupported actions remain hard failures.

## Examples

| Proposal | Normalized result | User-visible mode |
|---|---|---|
| Valid ABS evidence plus active question in `supportingTurnIds` | active question removed; evidence retained | grounded / presentation |
| Valid engine-braking evidence plus unknown focus slide | slide/focus derived from evidence ID; answer retained | grounded / presentation |
| Combined support with invalid turn but valid deck evidence | source narrows to presentation | grounded / presentation |
| Unknown evidence segment whose ID names a valid deck slide | slide verified; packaged summary evidence derived | grounded / presentation |
| Conversation plan whose active turn is invalid but whose slide is valid | turn removed; packaged slide evidence derived | grounded / presentation |
| Plan with no valid turn, evidence, explicit slide, or evidence-derived slide | rejected; safe recovery | extended knowledge fallback |

## Diagnostics

The silent-planning JSONL and application trace record:

- original terminal tool arguments;
- removed unknown and ineligible turn IDs;
- removed evidence and slide IDs;
- derived evidence slide IDs;
- evidence IDs synthesized from verified slide references;
- removed focus slide, if any;
- normalized focus slide, if one can be derived;
- grounding-source normalization; and
- `accepted_with_filtered_citations` when the normalized plan is accepted.

The application-decision trace records only normalized turn citations. Its
paired function-call trace retains the raw model arguments, while the paired
function-result trace proves which IDs were removed. This keeps later reasoning
snapshots replayable even when the model invented a turn ID.
Rejected zero-support plans also carry the private filter report; a rejected
decision endorses no turn citations.

No citation-repair warning is added to the public presentation view.

## Exit criteria

- [x] Tests fail first against the strict rejection behavior.
- [x] The two observed ABS/engine-braking plan shapes normalize to grounded
  presentation plans.
- [x] A verified slide-only citation derives bounded packaged evidence.
- [x] Only plans with no remaining truthful support fall back to extended
  knowledge.
- [x] Focused and full offline regression gates pass.
- [ ] A live run verifies grounded UI mode and private repair diagnostics.
