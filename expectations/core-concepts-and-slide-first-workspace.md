# Expectation handout: core concepts and slide-first workspace

## User-visible outcome

A reader can explain Pathos using a small set of plain-language concepts, and a
live-session user sees the slide deck as the primary workspace rather than one
card among equally prominent diagnostics.

## Inputs, outputs and boundaries

- Inputs: the current presentation snapshot, slides, transcript, domain events,
  timing data, and documented application contracts.
- Outputs/events: unchanged navigation, continue, stop, audio-unlock, and live
  session commands; revised documentation and layout only.
- External boundaries: browser rendering at desktop and narrow widths; GitHub
  Markdown/Mermaid/SVG rendering.
- Preconditions: the existing state reducer and LiveKit transport contracts pass.
- Non-goals: changing state transitions, transcript retention, provider behavior,
  planner policy, slide rendering endpoints, or adding a draw.io runtime dependency.

## Behavior map

```text
documentation: five concepts -> one system map -> question decision map

desktop UI:    deck rail | dominant slide stage | session inspector
               deck rail | transcript + events | session inspector

narrow UI:     dominant slide -> horizontal slide rail -> session -> transcript
```

## Invariants

- The page remains quiet and disconnected until Start.
- The visible slide and semantic presentation cursor remain distinct.
- The same application commands and disabled-state rules remain attached to
  slide navigation, Continue, Stop, New attempt, and Enable playback.
- Generated prose never controls navigation.
- A narration beat still commits only after matching verified playout completion.
- Diagnostics remain available at desktop width but may become secondary on a
  narrow display.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Desktop live session | slide is the largest surface; rail and inspector remain visible | Automated structure + human visual check |
| Narrow live session | slide stays 16:9; deck rail becomes horizontal; no horizontal page overflow | CSS contract + browser observation |
| Waiting phase | Continue remains visible and invokes the existing command | Existing application behavior |
| Reader opens concepts | five plain-language concepts precede implementation details | Documentation contract |

## Edge and race cases

- Empty/malformed: empty transcript and event states remain readable.
- Duplicate/repeated: navigation and Start guards are unchanged.
- Late/out-of-order: reducer handling is unchanged.
- Cancellation: Stop remains available in the workspace header.
- Partial failure: planning and connection failures remain visible in the
  inspector; slide-render fallback remains intact.
- Recovery: New attempt and audio unlock retain their existing conditions.
- Capability mismatch: thumbnails may fail independently without hiding slide
  titles or the primary slide fallback.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Visual hierarchy | slide clearly dominates | diagnostics compete equally with slide | desktop screenshot |
| Concept readability | names explain product behavior without code vocabulary | implementation sequence required to understand basics | rendered Markdown review |
| Narrow layout | no clipping; slide and primary controls remain first | fixed three-column canvas | 390 px screenshot |
| Behavioral continuity | controls have the same handlers and guards | layout changes state semantics | regression suite |

## Open assumptions

- GitHub-native Mermaid flowcharts are preferable to a separate draw.io source
  because they remain reviewable and render alongside the prose.
- Slide thumbnails may reuse the existing render endpoint; no new backend route
  is needed.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Documentation diagrams and the architecture SVG were visually reviewed.
- [x] Desktop and narrow UI observation cases were run.
- [x] Deferred risks are explicit.
