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

- [x] Observable path succeeds five consecutive times.
- [x] A mid-capture disconnect fails visibly and a new attempt recovers.
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
- The five spoken clips, human intelligibility judgement, screenshot and disconnect/recovery observations were completed in the manual gate below.

### Completed manual browser gate: 16 August 2026

Result: five consecutive spoken clips replayed intelligibly and exactly once
through the browser-to-Python LiveKit path. A network disconnect during capture
produced an obvious failure, and a fresh attempt after restoring the network
succeeded without restarting the backend.

- Local ledger baseline before this gate: 6 attempts and 12 participant-minutes upper bound.
- Maximum new attempts: 7 (five consecutive successes, one forced disconnect and one recovery).
- Conservative incremental cap: 21 participant-minutes, allowing up to 3 per attempt for worker startup/timeout rounding plus the capped browser participant.
- Provider scope: LiveKit WebRTC only. LiveKit Inference, Google AI and OpenAI model calls remain zero.
- Retained seven-attempt sequence: six completed and one deliberately failed, adding 14 participant-minutes—inside the announced 21-minute cap.
- Six unretained setup/retry attempts occurred between the baseline and retained sequence: four completed and two failed, adding another 13 participant-minutes. They count toward usage but not toward the acoustic acceptance claim.
- Post-gate local ledger: 19 attempts and 39 participant-minutes upper bound. This is not the authoritative LiveKit account balance.
- The deliberate disconnect surfaced `LiveKit room disconnected.` after 47.085 seconds. The backend was not restarted, and the following attempt completed normally.

The operator used short numbered phrases and retained screenshots of the
successful sequence, visible failure and recovery. The evidence rows are below.

| Run | Role | Attempt ID | Final phase | Frames | Captured seconds | Intelligible once? | Notes |
|---:|---|---|---|---:|---:|---|---|
| 1 | consecutive clip | `7589606b-8ae3-4a5e-b36e-f3aec15be188` | complete | 169 | 3.38 | yes | Screenshot and evaluator confirmation |
| 2 | consecutive clip | `ecbdc862-5564-4ab8-aa7a-47b0e6cb3b33` | complete | 161 | 3.22 | yes | Screenshot and evaluator confirmation |
| 3 | consecutive clip | `de26c4fa-0b84-436c-8480-ad9bb5ff0b71` | complete | 177 | 3.54 | yes | Screenshot and evaluator confirmation |
| 4 | consecutive clip | `6b3f306a-d395-4dee-a320-91426243189c` | complete | 186 | 3.72 | yes | Screenshot captured replaying; completion evaluator-confirmed and ledger-confirmed |
| 5 | consecutive clip | `44c641fc-4b0f-47cb-8ecb-4d7b91be88c2` | complete | 133 | 2.66 | yes | Screenshot and evaluator confirmation |
| 6 | forced disconnect | `a02242bb-35bf-4a8e-b543-abf33f1cc037` | failure | n/a | n/a | n/a | Visible `LiveKit room disconnected.` |
| 7 | recovery clip | `c05c3e46-dfd2-464f-8b6e-f4698933ede6` | complete | 161 | 3.22 | yes | Screenshot; backend not restarted |

The six successful clips total 987 received frames and 19.74 seconds of
captured audio. The evaluator reported every clip intelligible and played once,
with no feedback loop. Screenshots are retained in the evaluation conversation,
not copied into the repository; no independent audio recording was retained.

## Advancement decision

Slice 1 is complete. The real Cloud observations, the five consecutive spoken
clips, the visible disconnect and the successful fresh attempt establish the
bidirectional browser-to-Python transport and its required recovery behavior.
This remains a transport-only result: it does not prove model voice quality,
semantic interruption behavior or narration-beat commitment through a real
provider. The local ledger is an upper bound for this repository's observed
attempts, not an authoritative account-wide usage balance.
