# Verified slice: manual deck navigation and contextual questions

## Hypothesis

Manual browsing can interrupt narration and influence question retrieval without
giving up application-owned cursor, playout, or slide-selection invariants.

## Observable path

```text
listener -> deck control -> LiveKit data command -> application validation
  -> playout interruption + user-visible slide -> contextual question retrieval
  -> answer -> deterministic restoration and resume
```

## Scope

- New real boundary: browser-originated slide-selection command during a live
  presentation.
- Still fake: deterministic playout and transcript cases precede the acoustic
  observation.
- Explicitly excluded: runtime PPTX parsing, free-form deck authoring, model-owned
  navigation, and manual navigation during answer playout.

## Entry gate

- [x] Existing full-deck automatic presentation completed successfully live.
- [x] Expectation handout exists.
- [x] Focused red gate observed: 10 failures and 29 passes before implementation.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Domain | Navigation transition tests | Cursor/commit unchanged; invalid and duplicate commands safe |
| Application | Fake end-to-end browse/question/resume scenario | Preferred visible slide grounds only when relevant; full-deck fallback works |
| Browser | Reducer/control tests | Controls emit validated IDs and render distinct cursor/visible state |
| Live observation | Navigate during narration, ask two questions, continue | Audible stop, correct grounding, cursor restoration and completion |
| Instrumentation | Correlated command/domain events | Cancelled turn cannot later commit |

## Exit gate

- [x] Domain, application, fake, transport, and adapter focused gates pass.
- [x] Unknown slides and malformed commands fail before mutation.
- [x] Cursor restoration and full-deck retrieval override are covered.
- [x] Answer-playout navigation is explicitly deferred in the known-issues ledger.

## Automated evidence: 16 August 2026

- Staged feature-slice Python gate: 203 passed, one opt-in paid LiveKit test skipped.
- Full frontend gate: 11 files and 54 tests passed.
- Production TypeScript/Vite build passed; the existing approximately 726 kB
  chunk advisory remains.
- Browser quiet-start observation passed without starting a room, microphone, or
  provider session. The live acoustic click-during-narration case remains for the
  next user-run observation because accepting microphone permission and spending
  provider quota were not part of this automated gate.

## Fallback or rollback

Keep read-only Previous/Next browsing in ready/waiting/completed phases and defer
live playout interruption until cancellation correlation is proven.

## Next highest risk

Generalizing the now-packaged PPTX/handout path into a reviewed import command
without losing semantic IDs, visual fidelity, or provenance.
