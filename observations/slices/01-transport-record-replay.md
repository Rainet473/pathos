# Verified slice: controlled audio record/replay

## Hypothesis

The browser can publish microphone audio through LiveKit Cloud to a Python participant, which can buffer one explicit attempt and publish the same intelligible clip back exactly once after capture stops.

## Observable path

```text
user gesture -> browser microphone -> LiveKit room -> Python probe participant
             -> buffered PCM frames -> LiveKit replay track -> browser audio + metrics
```

## Scope

- New real boundary: browser and Python participants exchanging realtime media and reliable control packets through LiveKit Cloud.
- Still fake: voice model, presentation controller, slide content and all narration/question behavior.
- Explicitly excluded: continuous self-echo, byte-for-byte codec parity, VAD, model tools and UI polish.

## Entry gate

- [x] Slice 0 contract harness collected and failed for the intended missing-domain reason.
- [x] `expectations/transport-record-replay.md` defines the observable behavior and acoustic rubric.
- [x] Slice 1 transport tests failed for missing transport implementation rather than a broken runner.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Automated backend | Run transport/bootstrap pytest files with fake token, room and session adapters | Validation, idempotency, stale-event rejection, timeout, shutdown and safe failure tests pass offline |
| Automated frontend | Run Vitest against the attempt reducer, wire protocol and mocked LiveKit transport | Quiet initial state, one stop/replay, stale-event rejection and microphone cleanup pass offline |
| Observation | Run five three-second clips with headphones through LiveKit Cloud | Every clip is intelligible and completes without restarting either process |
| Failure observation | Disconnect once during capture, then start a fresh attempt | Failure is visible and the next attempt can succeed |
| Instrumentation | Keep attempt IDs, phase timestamps, frame/sample counts and duration | Logs distinguish capture, transfer, replay and completion for each attempt |

## Exit gate

- [ ] Observable path succeeds five consecutive times.
- [ ] A mid-capture disconnect fails visibly and a new attempt recovers.
- [x] Slice 1 deterministic tests pass; Slice 0's intentionally red domain oracle remains unchanged.
- [ ] Logs, screenshot/recording status and limitations are recorded below.

## Fallback or rollback

If LiveKit credentials or networking block the live gate, retain the passing offline contracts and run the same attempt flow through an explicitly labelled browser-to-FastAPI upload/replay fallback. Do not count that fallback as proof of the LiveKit boundary.

## Next highest risk

The complete quiet-start, interruption, answer, wait/resume interaction through a deterministic fake voice runtime.

## Run evidence

- Date: 15 August 2026.
- Runtime: Python 3.12.13, Node 24.19.0 and npm 11.17.0.
- Python SDKs: `livekit==1.1.14`, `livekit-api==1.2.0`, `fastapi==0.139.2` and `pydantic==2.13.4`.
- Browser SDK/tooling: `livekit-client==2.21.0`, Vite 8.1.5 and Vitest 4.1.10.
- First Python red gate: 18 failures, all caused by the absent `voice_presentation` transport/server modules.
- Second Python red gate: 7 failures, all caused by the absent versioned signal contract and LiveKit session launcher.
- Frontend red gates: missing `state.ts`, then missing `protocol.ts`; the already-authored reducer tests continued to pass during the second gate.
- Review regression red gate: two backend failures exposed missing worker timeout/application shutdown, two frontend failures exposed microphone/failure cleanup behavior, and a final SDK-source check exposed an unhandled blocked-playback rejection before those fixes were added.
- Offline Python command: `python -m pytest -q tests/transport tests/server tests/adapters`.
- Offline Python result: 32 passed in 0.49 seconds.
- Frontend command: `npm test`.
- Frontend result: 3 files and 11 tests passed in 0.18 seconds.
- Build command: `npm run build`.
- Build result: successful Vite production build; the LiveKit-containing JavaScript chunk is 689.29 kB before gzip and remains an accepted Slice 1 optimization deferral.
- Server smoke: the configured FastAPI factory bound locally and `GET /api/health` returned `{"status":"ok"}`.
- Frontend smoke: the Vite server bound locally and returned the probe page HTML.
- Visual browser smoke: not captured because no controllable browser instance was available in this workspace session; the TypeScript build and served-HTML checks passed.
- Full Python suite: 32 Slice 1 tests pass and the unchanged 27 Slice 0 domain tests remain intentionally red until Slice 2 implements the domain package.
- Live/manual observation: pending. No local `.env` exists, so no LiveKit credentials were available for a microphone/replay attempt, five-run table, disconnect recovery or recording.
- Important limitation: Python `AudioSource.wait_for_playout()` establishes that the Python source queue drained; it does not prove that browser playout finished. This probe must not be reused as narration-beat commitment evidence without a later browser acknowledgement.
