# Verified slice: reliable live transcript delivery

## Hypothesis

AgentSession transcript lifecycle events can provide a stable provider-neutral
UI transcript even when room-native transcription events are absent.

## Observable path

```text
microphone or generated answer
  -> LiveKit AgentSession transcript event
  -> Python normalized transcript packet
  -> reliable LiveKit data topic
  -> browser validation and reducer
  -> visible transcript row
```

## Scope

- New real boundary: AgentSession transcript events to worker-published room
  data and browser state.
- Still fake: automated tests use recorded event-shaped objects and fake rooms.
- Explicitly excluded: persistent history, word timing, transcript-based domain
  decisions and paid automatic live checks.

## Entry gate

- [x] Slice 4 application-controlled presentation behavior passed manually.
- [x] Expectation handout exists.
- [x] First failing adapter and browser packet tests are defined.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Backend contract | Pydantic packet and adapter event tests | Stable IDs, roles, sequence and filtering pass |
| Browser contract | Parser, sender, attempt and ordering tests | Only valid current-attempt worker packets reach the reducer |
| Regression | Full Python/frontend/build gates | No earlier slice regresses |
| Observation | One bounded live question/answer attempt | Final user and agent rows appear exactly once |

## Exit gate

- [ ] Observable path succeeds repeatedly.
- [x] Failure path is visible and controlled.
- [x] Previous tests still pass.
- [x] Offline artifacts and live-observation limitations are recorded.

## Offline evidence: 16 August 2026

- The initial Python red gate failed collection because
  `voice_presentation.transport.transcript` did not exist.
- The initial frontend red gate failed because `src/live/transcript.ts` did not
  exist.
- The backend now normalizes user interim/final events and final assistant
  conversation items into one provider-neutral, attempt-scoped packet.
- User interim fragments reuse one entry ID; blank final events close that ID;
  unsupported roles and blank text do not publish.
- Transcript packets publish serially on a reliable, browser-targeted topic.
  Publication failure is logged without failing the conversation.
- The browser accepts only schema-valid packets from the voice worker for the
  current attempt and rejects duplicate or older sequence numbers.
- Full Python result: 148 passed and the opt-in paid LiveKit transport test
  skipped.
- Full frontend result: 8 files and 42 tests passed.
- TypeScript production build passed. Vite retains the non-blocking warning for
  the approximately 717 kB application bundle.
- The real transcript event shapes are based on the installed LiveKit Agents
  1.5.17 `user_input_transcribed` and `conversation_item_added` contracts.

The live observation remains open. It deliberately was not executed
automatically because starting the configured inference pipeline consumes
LiveKit room and inference quota.

## Fallback or rollback

Keep the existing room-native `TranscriptionReceived` listener and hide the
empty transcript panel in the release UI. Do not infer transcript text from
presentation directives or generated prose.

## Next highest risk

Paraphrases of supported questions currently exceed the deterministic lexical
resolver's robustness and can be misclassified as out of scope.
