# Expectation handout: manual deck navigation and question context

## User-visible outcome

The presentation behaves like a navigable slide deck as well as an automatic
voice presentation. A listener can move to any authored slide without changing
the semantic narration cursor. Manual navigation during narration stops the
current audio, preserves the uncommitted beat, and leaves the presentation
waiting. A subsequent question considers the manually visible slide first, but
the resolver may select stronger evidence elsewhere in the deck.

## Inputs, outputs and boundaries

- Inputs: previous, next, and direct slide-selection commands; user speech;
  continue; provider playout lifecycle events.
- Outputs/events: validated `slide_changed(reason="user")`, interruption and
  waiting events, a state snapshot with separate visible slide and presentation
  cursor, and the existing answer-scope events.
- External boundaries: React controls -> LiveKit data command -> provider-neutral
  presentation application -> LiveKit playout cancellation -> browser state.
- Preconditions: the deck is validated and the target slide ID exists.
- Non-goals: model-owned navigation, parsing generated prose for slide changes,
  arbitrary PPTX ingestion, slide editing, and exact audio-offset resumption.

## Behavior map

```text
                         user selects slide B
narrating slide A/beat 2 ----------------------------+
        |                                             |
        | cancel verified active playout              v
        +--> cursor=A/2 (uncommitted)        visible=B, waiting
                                                     |
                      question -----------------------+
                         |
                         v
         prefer B when relevant; otherwise search full deck
                         |
                    answer finishes
                         |
             continue -> restore A -> replay A/2

completed -> user selects any slide -> visible slide changes
          -> follow-up question uses the same preference/search rule
```

## Invariants

- Only application code validates and applies navigation.
- A manual slide change never changes or commits `presentation_cursor`.
- Selecting the already visible slide is idempotent.
- A target outside the validated deck is rejected without changing state.
- Manual navigation during active narration cancels playout before entering the
  waiting state; the active beat remains uncommitted.
- Continue restores the semantic presentation slide and replays the interrupted
  beat from its beginning.
- The manually visible slide is a retrieval preference, not a hard scope filter.
- A stronger question match elsewhere in the deck may become temporarily visible.
- Generated model text never chooses a slide or commits a beat.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Browse while waiting | Selected slide becomes visible; cursor is unchanged | Automated |
| Browse during narration | Audio stops, beat remains uncommitted, selected slide is visible, phase is waiting | Automated + human |
| Ask about visible slide | Visible-slide evidence wins when it is relevant | Automated |
| Ask about another topic | Full-deck evidence wins over an unrelated visible-slide preference | Automated |
| Browse after completion | Slide changes and follow-up questions remain available | Automated + human |
| Unknown slide ID | Command is rejected and the previous snapshot remains authoritative | Automated |

## Edge and race cases

- Empty/malformed: missing and blank slide IDs are rejected at transport parsing.
- Duplicate/repeated: selecting the same slide twice has no second state effect.
- Late/out-of-order: completion from audio cancelled by manual navigation cannot
  commit the preserved beat.
- Cancellation: navigation waits for/correlates provider playout interruption;
  it never fabricates completion.
- Partial failure: if playout cancellation fails, surface failure and keep the
  previous authoritative state rather than claiming the navigation succeeded.
- Recovery: Continue restores the semantic cursor's slide and replays its beat.
- Capability mismatch: fake runtime proves the contract; the live adapter must
  expose an equivalent cancellation command before the live gate can pass.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Navigation | Previous/next/direct selection visibly changes authored slides | Controls skip, wrap unexpectedly, or show an unknown slide | Screenshots and event log |
| Audible stop | Current narration stops promptly after a manual selection | Old narration continues over the selected slide | Recording or timestamped note |
| Cursor safety | Visible slide differs while semantic cursor stays on interrupted beat | Browse action advances or commits narration | State screenshot |
| Question context | Related visible-slide question is grounded; unrelated question searches the deck | Visible slide forces an irrelevant answer | Transcript and scope mode |
| Resume | Continue restores and replays the interrupted beat | Narration resumes from browsed slide or skips content | Transcript and events |

## Open assumptions

- The first UI can use Previous/Next plus a slide picker; thumbnails are a later
  presentation-polish choice.
- Manual navigation during an answer is intentionally deferred from the first
  slice; the first slice covers narration, waiting, ready, and completed phases.
- PPTX is treated as an ingestible/source artifact. Runtime behavior consumes a
  normalized manifest and renderable slide assets, not the PPTX object model.

## Exit criteria

- [ ] Tests were written before implementation.
- [ ] New tests were observed failing for the intended reason.
- [ ] Deterministic suite passes offline.
- [ ] Observation cases were run and evidence was recorded.
- [ ] Deferred risks are explicit.
