# Expectation handout: release-finish surface and maintainability

## User-visible outcome

Opening the application root presents the quiet live voice experience. The
configured production server exposes only the live session bootstrap and the
health/deck-render support needed by that experience. Historical fake and
transport-probe harnesses remain testable without appearing in the production
API or UI.

## Inputs, outputs and boundaries

- Inputs: environment configuration, Start/Stop, microphone speech, validated
  deck navigation, and the packaged motorcycle deck.
- Outputs/events: browser-visible presentation state, transcript, timing,
  lifecycle, and deck images; private JSONL diagnostics/context when configured.
- External boundaries: browser WebRTC, LiveKit Cloud, and the selected voice
  factory behind `VoiceSessionFactory`.
- Preconditions: an active Python 3.12 conda environment, installed frontend
  dependencies, LiveKit project credentials, and the packaged deck.
- Non-goals: deployment automation, a generic PPTX importer, a second production
  voice provider, external retrieval, and prompt-quality/semantic-retrieval work.

## Behavior map

```text
/ -> live React client -> POST /api/live/sessions -> LiveKit conversation
                                       -> application-owned presentation state

offline/probe tests -> explicit test app composition -> same contracts/adapters
```

## Invariants

- The page and provider stay quiet until Start.
- The configured production OpenAPI surface contains no fake/probe session
  endpoints.
- Fake and probe contracts remain covered offline; release cleanup does not
  erase the earlier evidence ladder.
- Provider-specific constructors remain behind `VoiceSessionFactory`; the base
  class owns only shared validation, identity, and safe representation.
- The application owns state, semantic cursor validation, and playout
  commitment. Adapter refactoring cannot move those decisions into a model.
- Default installation supports the verified LiveKit inference pipeline;
  optional realtime adapters do not force unused provider plugins into the
  default dependency set.
- Public documentation never exposes credentials or private context logs.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Production API | health, deck render and live bootstrap are registered | Automated OpenAPI test |
| Historical harness | fake/probe endpoints are absent from configured app but explicit harness apps remain testable | Automated API tests |
| Provider factory | all factories validate nonblank instructions and redact credentials | Automated factory contract tests |
| Root route | `/` renders the live application with no internal-slice navigation link | Build/source contract |
| Real-world sanity case | Start remains quiet before click; navigation/interruption/completion behave as observed in attempt `35a5be63-…` | Human rubric and retained report |

## Edge and race cases

- Empty/malformed: missing credentials and blank factory inputs fail before a
  provider connection.
- Duplicate/repeated: existing application and launcher idempotency tests remain.
- Late/out-of-order: stale playout and navigation callbacks retain their tests.
- Cancellation: shutdown closes active live sessions and internal harnesses.
- Partial failure: provider launch failures remain redacted and visible as 503.
- Recovery: a fresh attempt can start after stop/failure.
- Capability mismatch: optional realtime adapters keep distinct construction;
  no lowest-common-denominator provider base is introduced.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Quiet start | no room/microphone/model before Start | automatic provider connection | screenshot/manual note |
| Navigation | visible slide may differ from semantic cursor without corrupting progress | browse commits or skips a beat | attempt ID and screenshots |
| Context | interrupted history is marked and application directives are visible | state inferred from prose | sanitized context audit |
| Onboarding | new reader can identify runtime, boundaries, commands and limitations | private handoff required to run project | public README and architecture guide |

## Open assumptions

- No software license is selected by this engineering slice; public release
  still requires an explicit owner decision about licensing.
- The fixed LiveKit inference pipeline remains the production default while the
  realtime adapters are optional comparison implementations.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Production frontend build passes and defaults to the live experience.
- [x] Configured OpenAPI excludes fake/probe sessions.
- [x] Release/onboarding documentation is sufficient without private handoff files.
- [x] Attempt `35a5be63-…` evidence and deferred context limitations are recorded.
- [x] Deferred risks are explicit.
