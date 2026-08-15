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
- [x] Logs, screenshot/recording status and limitations are recorded below.

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
- Post-credential review red gate: six regressions exposed browser-minute undercounting, EOS incorrectly authorizing replay, a per-frame rather than global drain timeout, handled failures recorded as completed, terminal UI blocked behind ACK, and a weak opt-in live oracle. Each received an expectation update and a failing test before its fix.
- Offline Python command: `python -m pytest -q tests/transport tests/server tests/adapters tests/scripts tests/live`.
- Final offline Python result on 16 August 2026: 48 passed and the opt-in live test skipped by default in 1.59 seconds. This includes six backend/frontend launcher tests.
- Frontend command: `npm test`.
- Final frontend result: 3 files and 16 tests passed in 0.18 seconds.
- Build command: `npm run build`.
- Build result on 16 August 2026: successful Vite production build; the LiveKit-containing JavaScript chunk is 690.38 kB before gzip and remains an accepted Slice 1 optimization deferral.
- Server launcher smoke: `scripts/run-backend.sh` loaded the ignored environment, the configured FastAPI factory bound locally, and `GET /api/health` returned `{"status":"ok"}`. No probe session was created.
- Frontend launcher smoke: `scripts/run-frontend.sh --host 127.0.0.1` started Vite 8.1.5 and the root path returned the probe page HTML with HTTP 200.
- Visual browser smoke: not captured because no controllable browser instance was available in this workspace session; the TypeScript build and served-HTML checks passed.
- Full-suite baseline on 16 August 2026: 27 expected Slice 0 failures, 48 passes and one opt-in live skip. Every failure is the deliberate missing `voice_presentation.domain` seam that Slice 2 will implement.
- A local `.env` became available on 15 August 2026. It stayed ignored, its permissions were tightened from `0644` to `0600`, and no value was printed or copied.
- Important limitation: Python `AudioSource.wait_for_playout()` establishes that the Python source queue drained; it does not prove that browser playout finished. This probe must not be reused as narration-beat commitment evidence without a later browser acknowledgement.

### Bounded LiveKit Cloud observations

The browser-control surface had no available browser instance, so the two credential checks used the opt-in synthetic 440 Hz client in `tests/live/test_livekit_record_replay.py`. They prove transport mechanics, not spoken intelligibility.

| Attempt | Worker duration | Observed result | Local participant-minute upper bound |
|---|---:|---|---:|
| `492b4b64` | 24.670 s | Timed out before replay completion; exposed reliance on media end-of-stream after unpublish | 2 |
| `988f30c1` | 8.966 s | Received `replay_started` and 82,560 returned samples, but lost the final completion packet when the worker disconnected | 2 |

- Total LiveKit attempts: 2. No automatic retry loop ran.
- Conservative local WebRTC consumption: 4 participant-minutes.
- Historical version-one rows from these two runs remain readable; new rows separately record worker connection minutes and the application's one-minute browser upper bound.
- LiveKit Inference, Google AI and OpenAI model consumption: zero.
- If the project began with the current 5,000-minute free WebRTC allowance and had no prior usage, the local estimate leaves 4,996 minutes. This is not the authoritative account balance; prior usage must come from the LiveKit dashboard.
- The first observation produced the deterministic `capture_stopped` bounded-drain regression. The second showed that worker completion succeeded but the final status could be lost on immediate disconnect, producing the `replay_acknowledged` handshake regression.
- Both regressions pass offline. The handshake was deliberately not re-run against Cloud in this session, keeping consumption at the announced two-attempt cap.
- The five spoken clips, human intelligibility judgement, screenshot/recording and disconnect/recovery observation remain open.

## Advancement decision

Slice 1 is not labelled complete: its human browser/acoustic and recovery gates
remain open and must be run before release. The real Cloud observations do,
however, establish bidirectional media transport and expose the lifecycle races
now covered offline. Because Slice 2 introduces no provider or transport
dependency, work may advance to the deterministic fake product while these
manual Slice 1 gates remain explicitly tracked. Slice 2 results must not be used
to claim that browser microphone intelligibility or acoustic interruption has
passed.
