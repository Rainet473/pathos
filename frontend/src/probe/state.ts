export type ProbePhase =
  | "idle"
  | "connecting"
  | "recording"
  | "transferring"
  | "replaying"
  | "complete"
  | "failure";

export interface ProbeMetrics {
  frameCount: number;
  audioDurationMs: number;
}

export interface ProbeState {
  phase: ProbePhase;
  attemptId: string | null;
  metrics: ProbeMetrics | null;
  failure: string | null;
  needsAudioUnlock: boolean;
}

export type ProbeAction =
  | { type: "start_requested"; attemptId: string }
  | { type: "capture_started"; attemptId: string }
  | { type: "stop_requested"; attemptId: string }
  | { type: "replay_started"; attemptId: string; metrics: ProbeMetrics }
  | { type: "replay_completed"; attemptId: string; metrics: ProbeMetrics }
  | { type: "audio_playback_blocked"; attemptId: string }
  | { type: "audio_playback_unlocked"; attemptId: string }
  | { type: "failed"; attemptId: string; reason: string };

export function initialProbeState(): ProbeState {
  return {
    phase: "idle",
    attemptId: null,
    metrics: null,
    failure: null,
    needsAudioUnlock: false,
  };
}

export function reduceProbeState(state: ProbeState, action: ProbeAction): ProbeState {
  if (action.type === "start_requested") {
    if (!action.attemptId || state.phase === "connecting" || state.phase === "recording") {
      return state;
    }
    return {
      phase: "connecting",
      attemptId: action.attemptId,
      metrics: null,
      failure: null,
      needsAudioUnlock: false,
    };
  }

  if (action.attemptId !== state.attemptId) {
    return state;
  }

  switch (action.type) {
    case "capture_started":
      return state.phase === "connecting" ? { ...state, phase: "recording" } : state;
    case "stop_requested":
      return state.phase === "recording" ? { ...state, phase: "transferring" } : state;
    case "replay_started":
      return state.phase === "transferring"
        ? { ...state, phase: "replaying", metrics: action.metrics }
        : state;
    case "replay_completed":
      return state.phase === "replaying"
        ? {
            ...state,
            phase: "complete",
            metrics: action.metrics,
            needsAudioUnlock: false,
          }
        : state;
    case "audio_playback_blocked":
      return state.phase === "replaying" ? { ...state, needsAudioUnlock: true } : state;
    case "audio_playback_unlocked":
      return { ...state, needsAudioUnlock: false };
    case "failed":
      return state.phase === "complete" || state.phase === "failure"
        ? state
        : {
            ...state,
            phase: "failure",
            failure: action.reason,
            needsAudioUnlock: false,
          };
    default:
      return state;
  }
}
