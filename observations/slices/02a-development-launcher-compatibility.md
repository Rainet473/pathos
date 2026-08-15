# Verified slice: combined development launcher compatibility

## Hypothesis

The existing standard backend launcher can serve the deterministic fake product and the configured LiveKit transport probe from one FastAPI process without launching a LiveKit room when only the fake route is used.

## Observable path

```text
scripts/run-backend.sh -> create_configured_app
                       -> POST /api/fake/sessions -> ready snapshot, zero probe launch
                       -> POST /api/probe/sessions -> retained Slice 1 contract
```

## Scope

- New real boundary: both already-implemented route families mounted by the standard configured application factory.
- Still fake: all Slice 2 voice behavior.
- Explicitly excluded: changing transport behavior, starting a Cloud room during the launcher check, changing credentials, or adding a second server process.

## Entry gate

- [x] Slice 2 deterministic and evaluator-observed visual gates pass.
- [x] The reported failure is reproduced from evidence: the default UI received `404` from `/api/fake/sessions` while `/api/probe/sessions` existed.
- [x] `expectations/backend-launcher.md` defines the combined-route behavior before source changes.
- [x] The first failing test targets the configured application factory, not shell mechanics or LiveKit Cloud.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Red regression | Request a fake session from `create_configured_app` with fake credentials | Fails `404` before the fix |
| Configured factory | Repeat the request after mounting the fake store | Returns ready/version 0 and creates no probe session |
| Retained routes | Run fake-session and probe-session server suites | Both route contracts pass offline |
| Launcher observation | Start `scripts/run-backend.sh`, request health and a fake session only | Both return success; no probe room is launched |
| Regression | Run all Python/frontend/build gates | No earlier slice regresses |

## Exit gate

- [x] The red regression fails for the intended missing-route reason, then passes.
- [x] The standard launcher serves both required local surfaces.
- [x] No LiveKit Cloud attempt is created during this compatibility check.
- [x] Previous automated gates remain green.
- [x] Exact results and limitations are recorded below.

## Fallback or rollback

Retain `create_offline_app` as the credential-free factory and the existing configured probe factory separately if combining the routes causes lifecycle or credential leakage. Do not duplicate controller behavior or launch a second backend.

## Next highest risk

At the time of this compatibility change, the still-open human acoustic and disconnect/recovery observations at the existing LiveKit browser-to-Python transport boundary. They were subsequently completed in the Slice 1 ledger.

## Run evidence

- Date: 16 August 2026.
- Pre-fix report: the normal launcher served `/api/probe/sessions` but returned `404 Not Found` for `/api/fake/sessions`.
- Red regression: the configured-factory fake-session request returned HTTP 404 before the fix.
- Focused green gate: 17 fake-session, probe-session and launcher tests passed in 1.24 seconds.
- Full Python gate: 90 passed and the opt-in paid/live test skipped in 2.33 seconds.
- Frontend gate: 4 files and 20 tests passed in 0.205 seconds.
- Production build: successful; 25 modules transformed. The existing 698.14 kB pre-gzip chunk warning remains an accepted optimization deferral.
- Process observation: `scripts/run-backend.sh` started the configured factory; health returned HTTP 200 and a fake session returned HTTP 201 in `ready` with no active turn, transcript or events. The server then completed application shutdown after `Ctrl+C`. No probe session was requested.

## Advancement decision

The compatibility slice is complete. The normal development launcher now
serves Slice 2 and retains Slice 1 from one process, while the offline product
path does not initiate the provider boundary. Slice 1's acoustic and recovery
observations remained a separate live gate and were subsequently completed.
