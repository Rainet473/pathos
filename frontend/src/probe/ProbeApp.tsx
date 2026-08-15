import { useEffect, useReducer, useRef } from "react";

import { createProbeSession } from "./api";
import { LiveKitProbeTransport } from "./livekitTransport";
import { createAttemptIdentifiers, type ProbeStatusPacket } from "./protocol";
import { initialProbeState, reduceProbeState } from "./state";

export default function ProbeApp() {
  const [state, dispatch] = useReducer(reduceProbeState, undefined, initialProbeState);
  const transport = useRef<LiveKitProbeTransport | null>(null);
  const startInFlight = useRef(false);

  useEffect(
    () => () => {
      void transport.current?.disconnect();
    },
    [],
  );

  async function startProbe() {
    if (startInFlight.current) return;
    startInFlight.current = true;
    const identifiers = createAttemptIdentifiers(crypto.randomUUID());
    const previous = transport.current;
    dispatch({ type: "start_requested", attemptId: identifiers.attemptId });

    let client: LiveKitProbeTransport;
    client = new LiveKitProbeTransport({
      onStatus: (status) => applyStatus(status, client),
      onDisconnected: () => {
        if (transport.current !== client) return;
        dispatch({ type: "failed", attemptId: identifiers.attemptId, reason: "LiveKit room disconnected." });
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
      const session = await createProbeSession(identifiers);
      await client.connect(session);
      await client.startCapture();
      dispatch({ type: "capture_started", attemptId: identifiers.attemptId });
    } catch (error) {
      if (transport.current === client) {
        dispatch({
          type: "failed",
          attemptId: identifiers.attemptId,
          reason: error instanceof Error ? error.message : "The probe could not start.",
        });
      }
      await client.disconnect();
    } finally {
      startInFlight.current = false;
    }
  }

  async function stopAndReplay() {
    if (state.attemptId === null || state.phase !== "recording") return;
    dispatch({ type: "stop_requested", attemptId: state.attemptId });
    try {
      await transport.current?.stopCapture();
    } catch (error) {
      dispatch({
        type: "failed",
        attemptId: state.attemptId,
        reason: error instanceof Error ? error.message : "The recording could not stop.",
      });
      await transport.current?.disconnect();
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

  function applyStatus(status: ProbeStatusPacket, owner: LiveKitProbeTransport) {
    if (transport.current !== owner) return;
    if (status.type === "failed") {
      dispatch({
        type: "failed",
        attemptId: status.attemptId,
        reason: status.reason ?? "The Python transport reported a failure.",
      });
      void owner.disconnect();
      return;
    }
    const metrics = status.metrics ?? { frameCount: 0, audioDurationMs: 0 };
    dispatch({ type: status.type, attemptId: status.attemptId, metrics });
  }

  const canStart = !["connecting", "recording", "transferring", "replaying"].includes(state.phase);

  return (
    <main className="probe-shell">
      <section className="probe-card" aria-live="polite">
        <p className="eyebrow">Slice 1 · transport only</p>
        <h1>Voice transport probe</h1>
        <p className="lede">
          Record a short phrase, stop, then hear the Python participant replay it once through LiveKit. Use headphones.
        </p>

        <div className={`status status-${state.phase}`}>
          <span className="status-dot" aria-hidden="true" />
          <div>
            <strong>{phaseLabel(state.phase)}</strong>
            <p>{phaseInstruction(state.phase)}</p>
          </div>
        </div>

        <div className="actions">
          <button type="button" onClick={() => void startProbe()} disabled={!canStart}>
            {state.phase === "idle" ? "Start probe" : "New attempt"}
          </button>
          <button type="button" className="secondary" onClick={() => void stopAndReplay()} disabled={state.phase !== "recording"}>
            Stop and replay
          </button>
          {state.needsAudioUnlock ? (
            <button type="button" className="secondary" onClick={() => void unlockAudio()}>
              Enable playback
            </button>
          ) : null}
        </div>

        {state.metrics ? (
          <dl className="metrics">
            <div><dt>Frames</dt><dd>{state.metrics.frameCount}</dd></div>
            <div><dt>Captured audio</dt><dd>{(state.metrics.audioDurationMs / 1000).toFixed(2)} s</dd></div>
          </dl>
        ) : null}

        {state.failure ? <p className="failure">{state.failure}</p> : null}
        {state.attemptId ? <code className="attempt">Attempt {state.attemptId}</code> : null}
      </section>
    </main>
  );
}

function phaseLabel(phase: ReturnType<typeof initialProbeState>["phase"]): string {
  return {
    idle: "Ready when you are",
    connecting: "Connecting",
    recording: "Recording",
    transferring: "Sending clip",
    replaying: "Replaying from Python",
    complete: "Replay complete",
    failure: "Probe failed",
  }[phase];
}

function phaseInstruction(phase: ReturnType<typeof initialProbeState>["phase"]): string {
  return {
    idle: "Nothing is connected and the microphone is off.",
    connecting: "Joining a private probe room and requesting microphone access.",
    recording: "Say a phrase of up to five seconds, then stop.",
    transferring: "The microphone is off. Python is finalizing the captured frames.",
    replaying: "The returned LiveKit audio track should now be audible once.",
    complete: "Start a new attempt to test again.",
    failure: "Read the message below, then make a fresh attempt.",
  }[phase];
}
