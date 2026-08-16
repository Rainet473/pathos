import { useEffect, useReducer, useRef } from "react";

import type { PresentationPhase } from "./presentationTypes";
import { createLiveSession } from "./api";
import { DeckSlideVisual } from "./deckSlideVisual";
import { LiveKitConversationTransport } from "./livekitTransport";
import { createLiveAttemptIdentifiers } from "./protocol";
import { initialLiveState, reduceLiveState, type LivePhase } from "./state";
import type { LiveSessionEndReason } from "./lifecycle";
import { adjacentSlideId } from "./slideNavigation";
import {
  planningFailureMessage,
  planningStatusDescription,
  planningStatusLabel,
} from "./planningStatus";

export default function LiveConversationApp() {
  const [state, dispatch] = useReducer(reduceLiveState, undefined, initialLiveState);
  const transport = useRef<LiveKitConversationTransport | null>(null);
  const startInFlight = useRef(false);

  useEffect(
    () => () => {
      void transport.current?.disconnect();
    },
    [],
  );

  async function start() {
    if (startInFlight.current) return;
    startInFlight.current = true;
    const identifiers = createLiveAttemptIdentifiers(crypto.randomUUID());
    const previous = transport.current;
    dispatch({ type: "start_requested", attemptId: identifiers.attemptId });

    let client: LiveKitConversationTransport;
    client = new LiveKitConversationTransport({
      onConnected: (backend) => {
        if (transport.current !== client) return;
        dispatch({ type: "connected", attemptId: identifiers.attemptId, backend });
      },
      onAgentState: (agentState) => {
        if (transport.current !== client) return;
        dispatch({ type: "agent_state", attemptId: identifiers.attemptId, state: agentState });
      },
      onLocalSpeechWhileAgentSpeaking: () => {
        if (transport.current !== client) return;
        dispatch({ type: "local_speech", attemptId: identifiers.attemptId });
      },
      onTranscript: (entry) => {
        if (transport.current !== client) return;
        dispatch({ type: "transcript", attemptId: identifiers.attemptId, entry });
      },
      onDiagnostic: (event) => {
        if (transport.current !== client) return;
        dispatch({ type: "diagnostic", attemptId: identifiers.attemptId, event });
      },
      onPresentation: (update) => {
        if (transport.current !== client) return;
        dispatch({ type: "presentation", attemptId: identifiers.attemptId, update });
      },
      onEnded: (reason) => {
        if (transport.current !== client) return;
        dispatch({ type: "ended", attemptId: identifiers.attemptId, reason });
      },
      onDisconnected: () => {
        if (transport.current !== client) return;
        dispatch({
          type: "failed",
          attemptId: identifiers.attemptId,
          reason: "The live voice session disconnected.",
        });
      },
      onAudioPlaybackBlocked: () => {
        if (transport.current !== client) return;
        dispatch({ type: "audio_playback_blocked", attemptId: identifiers.attemptId });
      },
    });
    transport.current = client;
    client.primeAudio();

    try {
      await previous?.disconnect();
      const session = await createLiveSession(identifiers);
      await client.connect(session);
    } catch (error) {
      if (transport.current === client) {
        dispatch({
          type: "failed",
          attemptId: identifiers.attemptId,
          reason: error instanceof Error ? error.message : "The live session could not start.",
        });
      }
      await client.disconnect();
    } finally {
      startInFlight.current = false;
    }
  }

  async function stop() {
    if (state.attemptId === null || !isActive(state.phase)) return;
    dispatch({ type: "stopped", attemptId: state.attemptId });
    await transport.current?.disconnect();
  }

  async function continuePresentation() {
    if (state.attemptId === null) return;
    try {
      await transport.current?.continuePresentation();
    } catch (error) {
      dispatch({
        type: "failed",
        attemptId: state.attemptId,
        reason: error instanceof Error ? error.message : "Continue could not be sent.",
      });
    }
  }

  async function navigateToSlide(slideId: string) {
    if (state.attemptId === null) return;
    try {
      await transport.current?.navigateToSlide(slideId);
    } catch (error) {
      dispatch({
        type: "failed",
        attemptId: state.attemptId,
        reason: error instanceof Error ? error.message : "Slide navigation could not be sent.",
      });
    }
  }

  async function unlockAudio() {
    if (state.attemptId === null) return;
    try {
      await transport.current?.unlockAudio();
      dispatch({ type: "audio_playback_unlocked", attemptId: state.attemptId });
    } catch {
      dispatch({
        type: "failed",
        attemptId: state.attemptId,
        reason: "The browser did not allow audio playback.",
      });
    }
  }

  const canStart = ["idle", "stopped", "failure"].includes(state.phase);
  const snapshot = state.presentation;
  if (snapshot === null) {
    return (
      <main className="session-shell live-shell">
        <section className="session-card live-card" aria-live="polite">
          <p className="eyebrow">Interruptible voice presentation</p>
          <h1>Live voice presentation</h1>
          <p className="lede">
            Start connects the microphone and selected LiveKit pipeline. The page remains quiet and disconnected until then.
          </p>
          <ConnectionStatus phase={state.phase} endReason={state.endReason} />
          <div className="actions">
            <button type="button" onClick={() => void start()} disabled={!canStart}>
              {state.phase === "idle" ? "Start presentation" : "New attempt"}
            </button>
            <button type="button" className="secondary" onClick={() => void stop()} disabled={!isActive(state.phase)}>
              Stop
            </button>
            {state.needsAudioUnlock ? (
              <button type="button" className="secondary" onClick={() => void unlockAudio()}>
                Enable playback
              </button>
            ) : null}
          </div>
          {state.failure ? <p className="failure">{state.failure}</p> : null}
          {state.attemptId ? <code className="attempt">Attempt {state.attemptId}</code> : null}
        </section>
      </main>
    );
  }

  const presentationPhase = snapshot.state.phase;
  const visibleSlide =
    snapshot.slides.find((slide) => slide.id === snapshot.state.visibleSlideId) ??
    snapshot.slides[0];
  const visibleSlideIndex = snapshot.slides.findIndex(
    (slide) => slide.id === visibleSlide.id,
  );
  const previousSlideId = adjacentSlideId(snapshot.slides, visibleSlide.id, -1);
  const nextSlideId = adjacentSlideId(snapshot.slides, visibleSlide.id, 1);
  const canNavigate =
    isActive(state.phase) &&
    presentationPhase !== "answering" &&
    snapshot.planningStage === null;
  const applicationStatusLabel = snapshot.planningStage
    ? planningStatusLabel(snapshot.planningStage)
    : presentationPhaseLabel(presentationPhase);
  const applicationStatusDescription = snapshot.planningStage
    ? planningStatusDescription(snapshot.planningStage)
    : presentationPhaseDescription(presentationPhase);

  return (
    <main className="presentation-shell live-presentation-shell">
      <header className="presentation-header">
        <div>
          <p className="eyebrow">Live presentation</p>
          <p className="mode-note">LiveKit Inference · Deepgram Nova-3 + Gemma 4 + Inworld TTS</p>
        </div>
      </header>

      <section className="presentation-grid" aria-live="polite">
        <article className="slide-card">
          <div className="deck-navigation">
            <div>
              <span className="slide-number">Navigable presentation deck</span>
              <span className="slide-position">
                Slide {visibleSlideIndex + 1} of {snapshot.slides.length}
              </span>
            </div>
            <div className="deck-navigation-actions">
              <button
                type="button"
                className="secondary compact"
                disabled={!canNavigate || previousSlideId === null}
                onClick={() => previousSlideId && void navigateToSlide(previousSlideId)}
              >
                Previous
              </button>
              <select
                aria-label="Visible slide"
                value={visibleSlide.id}
                disabled={!canNavigate}
                onChange={(event) => void navigateToSlide(event.target.value)}
              >
                {snapshot.slides.map((slide, index) => (
                  <option key={slide.id} value={slide.id}>
                    {index + 1}. {slide.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="secondary compact"
                disabled={!canNavigate || nextSlideId === null}
                onClick={() => nextSlideId && void navigateToSlide(nextSlideId)}
              >
                Next
              </button>
            </div>
          </div>
          <DeckSlideVisual
            key={`${snapshot.deckId}:${visibleSlide.id}`}
            deckId={snapshot.deckId}
            slide={visibleSlide}
          />
        </article>

        <aside className="state-panel">
          <div className={`phase-badge phase-${snapshot.planningStage ? "planning" : presentationPhase}`}>
            <span className="status-dot" aria-hidden="true" />
            <div>
              <small>Application phase</small>
              <strong>{applicationStatusLabel}</strong>
            </div>
          </div>
          <dl className="state-grid">
            <div><dt>Visible slide</dt><dd>{snapshot.state.visibleSlideId}</dd></div>
            <div><dt>Presentation cursor</dt><dd>{snapshot.state.presentationCursor.slideId} · beat {snapshot.state.presentationCursor.beatIndex + 1}</dd></div>
            <div><dt>Turn identity</dt><dd>{snapshot.state.activeTurnId ?? "none"}</dd></div>
            <div><dt>Session version</dt><dd>{snapshot.state.sessionVersion}</dd></div>
          </dl>
          <p className="phase-copy">{applicationStatusDescription}</p>
          {snapshot.scopeMode ? (
            <p className="scope-mode">
              Answer mode: {snapshot.scopeMode}
              {snapshot.groundingSource ? ` · source: ${snapshot.groundingSource}` : ""}
            </p>
          ) : null}
          {snapshot.planningFailureCode ? (
            <p className="failure">
              {planningFailureMessage(snapshot.planningFailureCode)}
            </p>
          ) : null}
          <div className="actions presentation-actions">
            {presentationPhase === "waiting" ? (
              <button type="button" onClick={() => void continuePresentation()}>
                Continue presentation
              </button>
            ) : null}
            <button type="button" className="secondary" onClick={() => void stop()} disabled={!isActive(state.phase)}>
              Stop session
            </button>
            {canStart ? <button type="button" onClick={() => void start()}>New attempt</button> : null}
            {state.needsAudioUnlock ? (
              <button type="button" className="secondary" onClick={() => void unlockAudio()}>
                Enable playback
              </button>
            ) : null}
          </div>
          {state.backend ? (
            <dl className="metrics live-provider">
              <div><dt>Provider</dt><dd>{state.backend.provider}</dd></div>
              <div><dt>Connection state</dt><dd>{phaseLabel(state.phase, state.endReason)}</dd></div>
            </dl>
          ) : null}
          {state.failure ? <p className="failure">{state.failure}</p> : null}
        </aside>
      </section>

      <section className="evidence-grid">
        <article className="evidence-card">
          <div className="evidence-heading"><h2>Live transcript</h2><span>{state.transcript.length} segments</span></div>
          {state.transcript.length === 0 ? <p className="empty-state">Narration is preparing.</p> : (
            <ol className="transcript-list live-transcript">
              {state.transcript.map((entry) => (
                <li key={entry.id}><span>{entry.role}</span><p>{entry.text}</p></li>
              ))}
            </ol>
          )}
        </article>
        <article className="evidence-card">
          <div className="evidence-heading"><h2>Latest domain events</h2><span>{snapshot.events.length} events</span></div>
          {snapshot.events.length === 0 ? <p className="empty-state">No transition has run.</p> : (
            <ol className="event-list">
              {snapshot.events.map((event, index) => (
                <li key={`${event.type}-${event.turnId ?? "state"}-${index}`}>
                  <code>{event.type}</code><span>{event.turnId ?? event.slideId ?? "state"}</span>
                </li>
              ))}
            </ol>
          )}
          {hasTiming(state.timing) ? (
            <section className="live-timing" aria-label="Latest response timing">
              <h2>Latest response timing</h2>
              <dl className="metrics">
                <Timing label="Follow-up planning" value={state.timing.planningDurationMs} />
                <Timing label="End-of-turn detection" value={state.timing.endOfUtteranceDelayMs} />
                <Timing label="LLM first token" value={state.timing.llmTtftMs} />
                <Timing label="TTS first audio" value={state.timing.ttsTtfbMs} />
                <Timing label="Interruption detection" value={state.timing.interruptionDetectionDelayMs} />
              </dl>
            </section>
          ) : null}
        </article>
      </section>
      {state.attemptId ? <code className="attempt live-attempt">Attempt {state.attemptId}</code> : null}
    </main>
  );
}

function ConnectionStatus({
  phase,
  endReason,
}: {
  phase: LivePhase;
  endReason: LiveSessionEndReason | null;
}) {
  return (
    <div className={`status status-${phase}`}>
      <span className="status-dot" aria-hidden="true" />
      <div><strong>{phaseLabel(phase, endReason)}</strong><p>{phaseInstruction(phase, endReason)}</p></div>
    </div>
  );
}

function Timing({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  return <div><dt>{label}</dt><dd>{formatMilliseconds(value)}</dd></div>;
}

function hasTiming(timing: import("./state").LiveTimingSummary): boolean {
  return Object.values(timing).some((value) => value !== null);
}

function formatMilliseconds(value: number): string {
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(2)} s`;
}

function isActive(phase: LivePhase): boolean {
  return ["connecting", "listening", "thinking", "speaking", "interrupted"].includes(phase);
}

function phaseLabel(
  phase: LivePhase,
  endReason: LiveSessionEndReason | null = null,
): string {
  if (endReason === "idle_timeout") return "Session ended after inactivity";
  if (endReason === "absolute_timeout") return "15-minute session limit reached";
  return {
    idle: "Quiet and disconnected",
    connecting: "Connecting",
    listening: "Listening",
    thinking: "Thinking",
    speaking: "Speaking",
    interrupted: "Interrupted — listening to you",
    stopped: "Session stopped",
    failure: "Live session failed",
  }[phase];
}

function phaseInstruction(
  phase: LivePhase,
  endReason: LiveSessionEndReason | null = null,
): string {
  if (endReason === "idle_timeout") {
    return "The room and microphone were released after two quiet minutes.";
  }
  if (endReason === "absolute_timeout") {
    return "The room and microphone were released at the absolute safety limit.";
  }
  return {
    idle: "No room, microphone or model connection exists until Start.",
    connecting: "Starting the selected provider and requesting microphone access.",
    listening: "The assistant is waiting for your voice.",
    thinking: "Your turn was received; the assistant is preparing a response.",
    speaking: "Speak over the response to test interruption.",
    interrupted: "Your speech arrived while the assistant was speaking.",
    stopped: "Microphone, room and model session have been released.",
    failure: "Read the error, check the backend log, then start a fresh attempt.",
  }[phase];
}

function presentationPhaseLabel(phase: PresentationPhase): string {
  return {
    ready: "Ready and quiet",
    presenting: "Presenting",
    interrupted: "Interrupted",
    answering: "Answering",
    waiting: "Waiting for you",
    completed: "Presentation complete",
  }[phase];
}

function presentationPhaseDescription(phase: PresentationPhase): string {
  return {
    ready: "No narration is active.",
    presenting: "The selected beat remains uncommitted until its audio finishes. Browsing another slide interrupts narration and pauses the cursor.",
    interrupted: "The unfinished beat is preserved while your question is prepared.",
    answering: "The answer has its own turn; the original beat remains uncommitted.",
    waiting: "Narration is paused. Browse freely; Continue restores the semantic cursor.",
    completed: "Verified narration playout committed the beat exactly once. The deck remains browsable.",
  }[phase];
}
