# Expectation handout: full-height live transcript panel

## User-visible outcome

On a desktop live-presentation workspace, the transcript uses all vertical space
available below its heading. When the transcript grows, messages scroll through
that full-height area instead of being confined to a short strip at the top of
an otherwise empty card.

## Inputs, outputs and boundaries

- Inputs: zero, one, or many transcript entries rendered in the existing
  workspace dock.
- Outputs/events: no new events; this is a layout-only correction.
- External boundaries: browser CSS layout at desktop and compact widths.
- Preconditions: the slide-first workspace allocates a bounded dock row and the
  transcript card remains inside it.
- Non-goals: changing transcript retention, ordering, content, auto-scrolling,
  domain events, timing metrics, or the height of the overall workspace dock.

## Behavior map

```text
workspace dock row
  -> transcript card
     -> fixed heading
     -> transcript list fills remaining height
        -> overflow scrolls inside that full-height list
```

## Invariants

- The transcript card remains bounded by the workspace dock on desktop.
- The transcript heading and segment count remain visible while messages scroll.
- Existing compact-screen behavior remains bounded and page-readable.
- Empty transcript copy remains visible without manufacturing unused messages.
- Transcript data and application state remain unchanged.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| A few entries on desktop | list viewport extends from the heading to the bottom of the card | CSS contract + browser observation |
| Many entries on desktop | messages scroll within the full available card height | CSS contract + browser observation |
| Empty transcript | preparation copy remains below the heading | Existing component contract |
| Compact screen | transcript retains the existing compact maximum height | CSS contract |

## Edge and race cases

- Empty/malformed: layout does not depend on a minimum message count.
- Duplicate/repeated: duplicate handling remains owned by the existing reducer.
- Late/out-of-order: transcript ordering logic is unchanged.
- Cancellation: interrupted and partial entries use the same available height.
- Partial failure: the transcript remains readable if domain diagnostics fail.
- Recovery: a new attempt still replaces transcript state through the reducer.
- Capability mismatch: no browser API or provider capability is introduced.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Desktop height use | transcript viewport reaches the card bottom | viewport stops near the heading while the card remains empty | desktop screenshot |
| Overflow | long transcript scrolls inside the card | messages are clipped or expand the dock over the slide | desktop screenshot |
| Compact layout | transcript remains bounded and usable | transcript forces excessive page height or clipping | narrow screenshot or CSS review |

## Open assumptions

- The reported issue is the desktop `138px` list cap visible in the supplied
  screenshot, not a request to make individual message cards stretch vertically.
- Automatic scrolling to the newest transcript entry is a separate behavior and
  is intentionally deferred.

## Exit criteria

- [x] Tests were written before implementation.
- [x] New tests were observed failing for the intended reason.
- [x] Deterministic suite passes offline.
- [x] Desktop layout was observed with the transcript using the full card height.
- [x] Compact-screen behavior remains bounded.
- [x] Deferred risks are explicit.
