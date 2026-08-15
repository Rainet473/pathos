import { useEffect, useRef, useState } from "react";

import { applyFakeAction, createFakeSession, type FakePresentationAction } from "./api";
import {
  applySessionSnapshot,
  beginPresentationAction,
  failPresentationAction,
  initialPresentationUiState,
  type PresentationPhase,
} from "./state";
import { SlideVisual } from "./slideVisuals";

const GROUNDED_QUESTION = "Why does engine braking feel stronger in a low gear?";

export default function FakePresentationApp() {
  const [ui, setUi] = useState(initialPresentationUiState);
  const sessionCreationStarted = useRef(false);

  useEffect(() => {
    if (sessionCreationStarted.current) return;
    sessionCreationStarted.current = true;
    void createSession();
  }, []);

  async function createSession() {
    setUi((current) => beginPresentationAction(current));
    try {
      const snapshot = await createFakeSession();
      setUi((current) => applySessionSnapshot(current, snapshot));
    } catch (error) {
      sessionCreationStarted.current = false;
      setUi((current) => failPresentationAction(current, errorMessage(error)));
    }
  }

  async function runAction(action: FakePresentationAction) {
    const sessionId = ui.snapshot?.sessionId;
    if (sessionId === undefined || ui.actionInFlight) return;
    setUi((current) => beginPresentationAction(current));
    try {
      const snapshot = await applyFakeAction(sessionId, action);
      setUi((current) => applySessionSnapshot(current, snapshot));
    } catch (error) {
      setUi((current) => failPresentationAction(current, errorMessage(error)));
    }
  }

  const snapshot = ui.snapshot;
  if (snapshot === null) {
    return (
      <main className="presentation-shell">
        <section className="loading-card" aria-live="polite">
          <p className="eyebrow">Slice 2 · deterministic offline mode</p>
          <h1>Preparing the quiet state</h1>
          <p className="lede">No narration or provider connection starts on page load.</p>
          {ui.failure ? (
            <>
              <p className="failure">{ui.failure}</p>
              <button type="button" onClick={() => void createSession()}>
                Retry local session
              </button>
            </>
          ) : null}
        </section>
      </main>
    );
  }

  const phase = snapshot.state.phase;
  const visibleSlide =
    snapshot.slides.find((slide) => slide.id === snapshot.state.visibleSlideId) ??
    snapshot.slides[0];

  return (
    <main className="presentation-shell">
      <header className="presentation-header">
        <div>
          <p className="eyebrow">Slice 2 · deterministic offline mode</p>
          <p className="mode-note">Visual transcript only · no microphone, cloud, or model calls</p>
        </div>
        <a href="/probe">Open Slice 1 transport probe</a>
      </header>

      <section className="presentation-grid" aria-live="polite">
        <article className="slide-card">
          <div className="slide-number">One-slide fixture</div>
          <h1>{visibleSlide.title}</h1>
          <p className="slide-headline">{visibleSlide.headline}</p>
          <SlideVisual slideId={visibleSlide.id} description={visibleSlide.visualDescription} />
          <ul className="slide-labels">
            {visibleSlide.labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </article>

        <aside className="state-panel">
          <div className={`phase-badge phase-${phase}`}>
            <span className="status-dot" aria-hidden="true" />
            <div>
              <small>Application phase</small>
              <strong>{phaseLabel(phase)}</strong>
            </div>
          </div>

          <dl className="state-grid">
            <div>
              <dt>Visible slide</dt>
              <dd>{snapshot.state.visibleSlideId}</dd>
            </div>
            <div>
              <dt>Presentation cursor</dt>
              <dd>
                {snapshot.state.presentationCursor.slideId} · beat {snapshot.state.presentationCursor.beatIndex + 1}
              </dd>
            </div>
            <div>
              <dt>Turn identity</dt>
              <dd>{snapshot.state.activeTurnId ?? "none"}</dd>
            </div>
            <div>
              <dt>Session version</dt>
              <dd>{snapshot.state.sessionVersion}</dd>
            </div>
          </dl>

          <p className="phase-copy">{phaseDescription(phase)}</p>
          {snapshot.scopeMode ? <p className="scope-mode">Answer mode: {snapshot.scopeMode}</p> : null}

          <div className="actions presentation-actions">
            {phase === "ready" ? (
              <button type="button" disabled={ui.actionInFlight} onClick={() => void runAction({ type: "start" })}>
                Start presentation
              </button>
            ) : null}
            {phase === "presenting" ? (
              <>
                <button
                  type="button"
                  disabled={ui.actionInFlight}
                  onClick={() =>
                    void runAction({
                      type: "interrupt_and_ask",
                      question: GROUNDED_QUESTION,
                      continuationPreference: "ask_before_continuing",
                    })
                  }
                >
                  Interrupt · ask, then wait
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={ui.actionInFlight}
                  onClick={() =>
                    void runAction({
                      type: "interrupt_and_ask",
                      question: `${GROUNDED_QUESTION} Continue after answering.`,
                      continuationPreference: "continue_after_answer",
                    })
                  }
                >
                  Interrupt · answer and continue
                </button>
                <button
                  type="button"
                  className="quiet-button"
                  disabled={ui.actionInFlight}
                  onClick={() => void runAction({ type: "complete_playout" })}
                >
                  Complete narration playout
                </button>
              </>
            ) : null}
            {phase === "answering" ? (
              <button
                type="button"
                disabled={ui.actionInFlight}
                onClick={() => void runAction({ type: "complete_playout" })}
              >
                Complete answer playout
              </button>
            ) : null}
            {phase === "waiting" ? (
              <button
                type="button"
                disabled={ui.actionInFlight}
                onClick={() => void runAction({ type: "continue" })}
              >
                Continue presentation
              </button>
            ) : null}
            {phase === "completed" ? (
              <button type="button" disabled={ui.actionInFlight} onClick={() => void createSession()}>
                Start a fresh session
              </button>
            ) : null}
          </div>
          {ui.failure ? <p className="failure">{ui.failure}</p> : null}
        </aside>
      </section>

      <section className="evidence-grid">
        <article className="evidence-card">
          <div className="evidence-heading">
            <h2>Deterministic transcript</h2>
            <span>{snapshot.transcript.length} entries</span>
          </div>
          {snapshot.transcript.length === 0 ? (
            <p className="empty-state">Quiet. Press Start when you are ready.</p>
          ) : (
            <ol className="transcript-list">
              {snapshot.transcript.map((entry, index) => (
                <li key={`${entry.turnId}-${entry.role}-${index}`}>
                  <span>{entry.role}</span>
                  <p>{entry.text}</p>
                  <code>{entry.turnId}</code>
                </li>
              ))}
            </ol>
          )}
        </article>

        <article className="evidence-card">
          <div className="evidence-heading">
            <h2>Latest domain events</h2>
            <span>{snapshot.events.length} events</span>
          </div>
          {snapshot.events.length === 0 ? (
            <p className="empty-state">No transition has run.</p>
          ) : (
            <ol className="event-list">
              {snapshot.events.map((event, index) => (
                <li key={`${event.type}-${event.turnId ?? "state"}-${index}`}>
                  <code>{event.type}</code>
                  <span>{event.turnId ?? event.slideId ?? "state"}</span>
                </li>
              ))}
            </ol>
          )}
        </article>
      </section>
    </main>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The offline presentation request failed.";
}

function phaseLabel(phase: PresentationPhase): string {
  return {
    ready: "Ready and quiet",
    presenting: "Presenting",
    interrupted: "Interrupted",
    answering: "Answering",
    waiting: "Waiting for you",
    completed: "Presentation complete",
  }[phase];
}

function phaseDescription(phase: PresentationPhase): string {
  return {
    ready: "No playout is active. Start is the only action that begins narration.",
    presenting: "The cursor still names the uncommitted beat until playout completes.",
    interrupted: "The unfinished semantic beat is preserved while the user turn is committed.",
    answering: "The scripted answer has its own turn; the original beat remains uncommitted.",
    waiting: "The answer is complete. Narration will not resume without explicit permission.",
    completed: "Verified narration playout committed the single beat exactly once.",
  }[phase];
}
