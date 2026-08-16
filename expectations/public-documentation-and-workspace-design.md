# Expectation handout: public documentation and slide-first workspace design

## User-visible outcome

A first-time visitor can understand what Pathos is, see its architecture before
the motorcycle example, install and run it without private context, and find
separate conceptual, advantage, and limitation guides. A proposed application
layout makes the slide the dominant surface and keeps controls, transcript, and
diagnostics secondary without changing product behavior before approval.

## Inputs, outputs and boundaries

- Inputs: current repository contracts and evidence; public README conventions
  from Pipecat and NVIDIA Nemotron Voice Agent; the existing Pathos UI.
- Outputs: rewritten README, self-contained architecture SVG, conceptual guide,
  advantages guide, limitations guide, and an inspectable UI proposal.
- External boundaries: GitHub Markdown/SVG rendering and new-onboarder shell
  setup.
- Preconditions: the current release gate and public architecture are stable.
- Non-goals: changing voice behavior, claiming unimplemented semantic/web/visual
  retrieval, generic PPTX import, guaranteed provider caching, deployment, or
  changing the production UI before the proposal is accepted.

## Behavior map

```text
README visitor -> purpose + architecture -> quick start -> live demo placeholder
               -> concepts / advantages / limitations -> deeper references

workspace proposal -> deck rail | dominant 16:9 stage | session inspector
                                      -> bottom transcript/diagnostic dock
```

## Invariants

- The application, not generated prose, owns state, navigation, and commitment.
- LiveKit remains the transport/orchestration boundary; provider adapters share
  the small `VoiceSessionFactory` port but are not claimed to be identical.
- Prompt caching is provider-reported and variable, not an application-owned
  cache or guaranteed optimization.
- New decks require the validated normalized content package and slide renders;
  raw arbitrary slide import remains deferred.
- Citations mean validated internal provenance/evidence IDs, not a public
  bibliography or retained hidden chain-of-thought.
- The UI proposal preserves quiet start, separate visible/semantic cursors,
  verified playout commitment, and current interruption semantics.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| New visitor | Purpose, architecture, value, and quick start are visible in order | Documentation contract |
| Provider claim | Default and optional providers are distinguished from the shared port | Source audit |
| Cache claim | Variability and measurement are explicit; no guarantee is stated | Evidence audit |
| Content reuse | Normalized package path is explained with importer limitation | Schema/docs audit |
| UI proposal | Slide is visually dominant; diagnostics remain available but secondary | Human rubric |

## Edge and race cases

- Empty/malformed: documentation contract rejects missing required sections and
  broken local links.
- Duplicate/repeated: README avoids repeating entire deep guides.
- Late/out-of-order: not applicable; no runtime behavior changes in this slice.
- Cancellation: not applicable.
- Partial failure: if the architecture SVG cannot render, its alt text and the
  architecture guide still explain the system.
- Recovery: onboarding includes verification and troubleshooting pointers.
- Capability mismatch: optional provider adapters and unverified capabilities
  are labeled accurately.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| README hierarchy | purpose, architecture, why, demo, quick start, docs | use-case screenshot dominates or setup is fragmented | rendered README |
| Architecture visual | readable at GitHub width and meaningful without tiny prose | decorative logo or unreadable implementation map | SVG render |
| Concept accuracy | explains state, interruption, planning, evidence, playout | treats the LLM as the state machine | source-linked review |
| Claims | distinguishes built, observed, optional, and deferred | promises caching, arbitrary PPTX, vision, or web search | wording audit |
| Workspace hierarchy | slide occupies most space; sides/bottoms carry controls and evidence | slide competes with equal-sized diagnostics cards | mockup |
| Responsive intent | rails collapse before the slide becomes unreadable | fixed desktop canvas with clipping | mockup notes |

## Open assumptions

- “Pathos” is the intended public project name; no separate logo mark is yet
  required beyond the architecture hero wordmark.
- The production UI implementation will begin only after the user accepts or
  revises the proposed workspace.

## Exit criteria

- [x] Documentation contract tests are written before public-file changes.
- [x] New tests fail for missing architecture/concept/advantage/limitation assets.
- [x] README and all new documents pass link and claim checks.
- [x] Architecture SVG is rendered and visually inspected.
- [x] UI proposal is shown for user approval at desktop and narrow widths.
- [x] Existing deterministic release gate still passes.
- [x] Deferred risks are explicit.
