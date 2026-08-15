# Verified slice: contract and harness

## Hypothesis

The product's locked content, state, event and transition behavior can be specified and tested without importing a voice-provider, LiveKit or browser SDK.

## Observable path

```text
product requirements → expectation handouts → executable pytest contracts
                     → failures that identify missing domain implementation
```

## Scope

- New real boundary: Python test runner loading the future public `voice_presentation` package contract.
- Still fake: all audio, transport, model behavior, UI rendering and persistence.
- Explicitly excluded: controller implementation, provider packages, FastAPI, React and live observation.

## Entry gate

- [x] Relevant repository instructions and private product requirements were reviewed.
- [x] Expectation handouts exist for transport, narration commitment, interruption/resumption and question scope.
- [x] The first failing test or probe is defined and executed.

## Evidence plan

| Evidence | Method | Pass condition |
|---|---|---|
| Automated | Run the offline pytest contract/domain suite | Tests are collected and fail because the named domain contracts do not exist yet |
| Observation | Review failure output against the expectation handouts | No syntax, environment or provider/network error masks the intended failure |
| Instrumentation | Retain command, versions, test IDs and failure summary here | Another agent can repeat the same failing run |

## Exit gate

- [x] Test runner collects the authored contract/behavior tests.
- [x] Failures point to missing domain implementation rather than a broken harness.
- [x] No provider or frontend dependency is required by the default suite.
- [x] Command and limitations are recorded below.

## Fallback or rollback

If pytest cannot run in the configured environment, use the standard-library unittest runner only long enough to isolate the environment problem; do not change behavioral expectations to fit the tool failure.

## Next highest risk

Browser → LiveKit Cloud → Python → browser controlled audio record/replay.

## Run evidence

- Date: 15 August 2026.
- Runtime: Python 3.12.13 in the workspace's configured conda environment.
- Test runner: pytest 9.1.1.
- Collection command: `python -m pytest --collect-only -q`.
- Collection result: 27 tests collected successfully in 0.03 seconds.
- Red-gate command: `python -m pytest -q`.
- Red-gate result: 27 failed in 0.10 seconds.
- Shared failure reason: `ModuleNotFoundError: No module named 'voice_presentation'`.
- Interpretation: intended failure. The behavioral oracle loads correctly and the application package has not been implemented.
- Live/manual observation: not applicable to this contract-only slice; acoustic rubrics remain explicitly deferred.
