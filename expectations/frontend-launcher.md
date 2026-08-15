# Expectation handout: frontend development launcher

## User-visible outcome

A developer can start the Vite frontend from any working directory with one
repository script. The launcher uses Node/npm from the currently active conda
environment and leaves Vite attached to the terminal until stopped.

## Inputs, outputs and boundaries

- Inputs: the checked-in frontend package and optional additional Vite arguments.
- Outputs/events: an attached Vite development server, normally on port 5173.
- External boundaries: the active shell environment, npm, and installed
  `frontend/node_modules`.
- Preconditions: the intended conda environment is already active and frontend
  dependencies exist.
- Non-goals: installing dependencies automatically, starting the backend, or
  producing/serving a production build.

## Behavior map

```text
invoke script
  -> resolve repository root from script location
  -> validate frontend package, installed dependencies and active environment
  -> change to frontend directory
  -> replace launcher with conda -> npm run dev -> Vite
```

## Invariants

- The launcher works when invoked outside the repository root.
- It runs the checked-in `frontend/package.json`, not a package in the caller's directory.
- It uses npm from the active conda environment and leaves Vite output attached.
- It does not select, activate or hard-code a conda environment.
- Caller-supplied arguments are forwarded through npm to Vite.
- Missing dependencies fail with an installation command rather than triggering
  an implicit network operation.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Happy path | Conda receives `npm run dev` while its working directory is `frontend/` | Automated |
| Different working directory | The checked-in frontend is still selected | Automated |
| Missing dependencies | Non-zero exit explains how to run `npm ci` | Automated |
| Local sanity check | The Vite root responds with HTTP 200 | Human rubric |

## Edge and race cases

- Empty/malformed: a missing package or dependency directory fails before npm.
- Duplicate/repeated: a second server may choose another port; the launcher does
  not terminate an existing developer process.
- Late/out-of-order: not applicable to a synchronous launcher.
- Cancellation: `Ctrl+C` reaches the foreground Vite process.
- Partial failure: missing active environment or npm fails clearly.
- Recovery: install dependencies or free the desired port, then invoke again.
- Capability mismatch: the launcher assumes a POSIX shell and conda installation.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Startup | Vite prints a local URL | Package, conda, or module error | Terminal output |
| Page | Root path returns the application HTML with HTTP 200 | Timeout or non-200 response | Curl/browser output |

## Open assumptions

- Vite's default port remains 5173 and `/api` remains proxied to backend port 8000.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Observation cases were run and evidence was recorded.
- [x] Deferred risks are explicit.

Observed locally on 2026-08-15: the launcher forwarded
`--host 127.0.0.1`, Vite 8.1.5 reported ready on port 5173, the root path
returned the application HTML with HTTP 200, and `Ctrl+C` stopped the process.
The backend was not required for this static-page check.
