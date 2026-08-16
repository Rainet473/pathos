# Verified slice: spoken presentation continuation

## Hypothesis

A bounded, provider-neutral spoken command can resume a preserved narration beat
without invoking follow-up planning or giving the model ownership of state.

## Observable path

```text
listener -> final speech transcript -> deterministic intent match
  -> application continue transition -> new narration playout
```

## Scope

- New real boundary: final LiveKit user turns may select an application-owned
  continuation command before the follow-up planner.
- Still fake: deterministic speech handles and planner spies prove ordering.
- Explicitly excluded: open-ended voice-command NLU, completed-deck restart,
  navigation by speech, and provider-specific intent APIs.

## Entry gate

- [x] Existing interruption, waiting, button continuation, and answer-and-continue
  tests pass.
- [x] Expectation handout exists.
- [x] First failing matcher/domain/bridge tests were observed: the matcher module
  was absent, the domain rejected `interrupted`, and both spoken commands became
  answer instructions instead of continuation.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Command policy | Offline matcher matrix | positive variants match; negative/compound phrases do not |
| State | Domain/application tests | interrupted and waiting cursors replay with a new turn |
| Adapter | Fake LiveKit session and planner spy | command bypasses planner and issues narration exactly once |
| Observation | Live microphone | spoken command resumes without an answer or planning delay |

## Exit gate

- [x] Observable path succeeds repeatedly in deterministic adapter tests.
- [x] Negative, compound, and completed-phase paths are controlled.
- [x] Previous focused and adjacent tests still pass.
- [x] Automated artifacts and the remaining acoustic gate are recorded.

## Exit evidence

- Matcher, domain, application, and LiveKit bridge gate: `52 passed`.
- Positive variants include Continue, Resume, Go on, Carry on, polite prefixes,
  and presentation/narration wording.
- Negative coverage includes explicit negation, compound answer-and-continue,
  unrelated questions, and a completed deck.
- Runtime/provider spend: none. A live microphone observation remains for the
  user because it depends on speech recognition and acoustic conditions.
- Retained repository gate after both Slice 12 changes: `323 passed`, `3` paid
  provider tests skipped, Python compilation clean, and no broken requirements.

## Fallback or rollback

Remove the voice-command branch; the existing Continue button and same-utterance
answer-and-continue behavior remain available.

## Next highest risk

Acoustic transcription may produce variants outside the bounded grammar; retain
the transcript when proposing additions rather than broadening matches blindly.
