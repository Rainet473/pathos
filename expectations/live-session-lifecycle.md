# Expectation handout: live-session lifecycle

## User-visible outcome

A live presentation remains connected while the listener or presenter is active,
ends quietly after two minutes of genuine inactivity, and cannot consume provider
resources beyond a fifteen-minute absolute safety ceiling. Finishing the deck
starts a fresh inactivity window so post-completion questions remain possible.
Only an unexpected transport or provider loss is reported as a failure.

## Inputs, outputs and boundaries

- Inputs: browser microphone and room activity, agent/user state changes,
  transcript and presentation data, verified presentation completion, and elapsed
  idle/absolute time.
- Outputs: a graceful terminal reason (`idle_timeout` or `absolute_timeout`),
  released browser media, a closed Python worker, and a failure only for an
  unexpected disconnect or provider error.
- External boundaries: browser timers, LiveKit room lifecycle, AgentSession
  lifecycle, application-owned presentation state, and the local usage ledger.
- Preconditions: full-deck progression, interruption recovery, answer waiting,
  and explicit answer-and-continue already pass their deterministic gates.
- Non-goals: reconnecting a failed room, preserving a session across page reloads,
  or removing the absolute ceiling in this slice.

## Behavior map

```text
meaningful activity ------------------------> reset idle deadline
       |                                              |
       +-- no activity for 120 s --------------------> graceful idle end

presentation_completed -----------------------------> reset idle deadline
post-completion question ----------------------------> remain conversational
absolute age reaches 900 s --------------------------> graceful safety end
unexpected room/provider loss -----------------------> failure
```

## Invariants

- The page remains disconnected and quiet until Start.
- The backend supplies one lifecycle policy to the browser: 120 seconds idle and
  900 seconds absolute by default.
- Meaningful user, agent, transcript, presentation, or subscribed-audio activity
  resets only the idle deadline; it never extends the absolute deadline.
- A completed presentation snapshot remains conversational until inactivity or
  the absolute ceiling releases the room.
- Idle expiry and absolute expiry do not show the red
  "live voice session disconnected" failure.
- Unexpected worker departure, room loss, or provider error remains a failure.
- Browser and Python worker release microphone, audio elements, AgentSession, and
  room resources once for every terminal path.
- Application-controlled turn preparation does not use speculative preemptive
  generation because it mutates the turn context after endpointing.
- Per-turn timing is read from supported conversation-item metrics; the deprecated
  `metrics_collected` event is not registered.

## Examples

| Situation | Expected observation | Oracle |
|---|---|---|
| Listener pauses for less than two minutes, then speaks | Same session answers; idle deadline moved | Automated |
| No meaningful activity for two minutes | Neutral inactivity message; media and worker close | Automated plus browser |
| Conversation stays active for fifteen minutes | Neutral safety-limit message; session closes | Automated |
| Final narration commits the last beat | Completed snapshot appears and questions remain possible | Automated plus browser |
| Worker disappears mid-presentation | Red unexpected-disconnect failure | Automated |
| Backend starts the pipeline | No deprecated metrics or preemptive-generation warning | Automated registration/configuration |

## Edge and race cases

- Activity and idle expiry at the same instant may choose either ordering, but
  cleanup remains idempotent and no failure is fabricated.
- Presentation completion and the idle deadline may arrive together; the
  completion update counts as activity and starts a fresh idle window.
- The browser timer is a local cleanup fallback. Backend lifecycle remains the
  resource authority when the browser is suspended or gone.
- Provider activity while audio is being generated or played counts as activity,
  so a long legitimate response is not mistaken for listener abandonment.

## Observation rubric

| Dimension | Acceptable | Unacceptable | Evidence to keep |
|---|---|---|---|
| Idle end | Neutral inactivity status after the configured quiet window | Red disconnect failure | State screenshot and attempt ID |
| Absolute end | Neutral fifteen-minute safety message | Hidden three-minute cutoff | Attempt duration and state screenshot |
| Deck completion | Final state remains available for follow-up questions | Completion immediately closes the room | Final state/events screenshot |
| Unexpected loss | Explicit failure remains visible | Loss silently looks successful | State screenshot and backend log |
| Backend warnings | No deprecated metrics/preemptive warning | Either warning repeats | Backend log excerpt |

## Exit criteria

- [x] Tests are written before implementation and fail for the intended reasons.
- [x] Session bootstrap exposes the 120-second idle and 900-second absolute policy.
- [x] Backend and browser distinguish all graceful terminal reasons from failure.
- [x] Activity resets the idle deadline without extending the absolute deadline.
- [x] Presentation completion resets inactivity without blocking follow-up questions.
- [x] Deprecated metrics and preemptive-generation warnings are removed at source.
- [x] All preserved deterministic gates remain green.
- [ ] One bounded browser observation confirms normal full-deck cleanup.
