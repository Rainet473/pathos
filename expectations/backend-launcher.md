# Expectation handout: backend development launcher

## User-visible outcome

A developer can start the FastAPI backend from any working directory with one
repository script. The launcher loads the repository's private `.env`, uses
the currently active conda environment, and leaves Uvicorn logs attached to
the terminal until the developer stops it.

## Inputs, outputs and boundaries

- Inputs: repository-root `.env` and optional additional Uvicorn arguments.
- Outputs/events: an attached Uvicorn process listening on `127.0.0.1:8000`.
- External boundaries: the active shell environment and its Uvicorn executable.
- Preconditions: `.env` exists and the intended conda environment is already active.
- Non-goals: installing dependencies, starting the frontend, creating a LiveKit
  room, or supervising/restarting a crashed server.

## Behavior map

```text
invoke script
  -> resolve repository root from script location
  -> validate .env and active conda environment
  -> export .env values to the child process
  -> replace launcher with conda -> uvicorn -> FastAPI factory
```

## Invariants

- The launcher works when invoked outside the repository root.
- It never prints credential values itself.
- It uses `voice_presentation.server.app:create_configured_app` as a factory.
- The launcher does not select, activate or hard-code a conda environment.
- Missing active-environment or Uvicorn prerequisites fail clearly.
- It enables development reload and forwards caller-supplied Uvicorn arguments.
- A missing `.env` fails before conda or Uvicorn is invoked.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Happy path | Conda receives the complete Uvicorn command and exported environment | Automated |
| Different working directory | Repository paths still resolve from the script location | Automated |
| Missing `.env` | Non-zero exit with a concise error | Automated |
| Local sanity check | `/api/health` returns `{"status":"ok"}` | Human rubric |

## Edge and race cases

- Empty/malformed: malformed `.env` is rejected by the shell while sourcing.
- Duplicate/repeated: each invocation is an independent foreground server.
- Late/out-of-order: not applicable to a synchronous launcher.
- Cancellation: `Ctrl+C` reaches the foreground Uvicorn process.
- Partial failure: missing `.env` or conda produces a non-zero exit.
- Recovery: fix the prerequisite and invoke the script again.
- Capability mismatch: the launcher assumes a POSIX shell and conda installation.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Startup | Uvicorn reports listening on `127.0.0.1:8000` | Import or environment error | Terminal output |
| Health | `/api/health` returns HTTP 200 and `{"status":"ok"}` | Timeout or non-200 response | Curl output |

## Open assumptions

- Port `8000` remains the Vite proxy target during local development.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Observation cases were run and evidence was recorded.
- [x] Deferred risks are explicit.

Observed locally on 2026-08-15: the launcher started Uvicorn with WatchFiles,
`GET /api/health` returned HTTP 200 with `{"status":"ok"}`, and `Ctrl+C`
completed FastAPI application shutdown. No probe session was created.
