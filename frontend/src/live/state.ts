import type { VoiceBackendIdentity } from "./protocol";
import type { ConversationDiagnosticEvent } from "./diagnostics";
import type { LivePresentationView, PresentationStateUpdate } from "./presentation";
import type { LiveSessionEndReason } from "./lifecycle";

export type LivePhase =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "stopped"
  | "failure";

export type NormalizedAgentState = "listening" | "thinking" | "speaking";

export interface TranscriptEntry {
  id: string;
  role: "user" | "agent";
  text: string;
  final: boolean;
}

export interface LiveState {
  phase: LivePhase;
  attemptId: string | null;
  backend: VoiceBackendIdentity | null;
  transcript: TranscriptEntry[];
  presentation: LivePresentationView | null;
  failure: string | null;
  endReason: LiveSessionEndReason | null;
  needsAudioUnlock: boolean;
  timing: LiveTimingSummary;
}

export interface LiveTimingSummary {
  planningDurationMs: number | null;
  providerResponseStartGapMs: number | null;
  modelTtftMs: number | null;
  llmTtftMs: number | null;
  ttsTtfbMs: number | null;
  endOfUtteranceDelayMs: number | null;
  interruptionDetectionDelayMs: number | null;
}

export type LiveAction =
  | { type: "start_requested"; attemptId: string }
  | { type: "connected"; attemptId: string; backend: VoiceBackendIdentity }
  | { type: "agent_state"; attemptId: string; state: NormalizedAgentState }
  | { type: "local_speech"; attemptId: string }
  | { type: "transcript"; attemptId: string; entry: TranscriptEntry }
  | { type: "diagnostic"; attemptId: string; event: ConversationDiagnosticEvent }
  | { type: "presentation"; attemptId: string; update: PresentationStateUpdate }
  | { type: "audio_playback_blocked"; attemptId: string }
  | { type: "audio_playback_unlocked"; attemptId: string }
  | { type: "stopped"; attemptId: string }
  | { type: "ended"; attemptId: string; reason: LiveSessionEndReason }
  | { type: "failed"; attemptId: string; reason: string };

export function initialLiveState(): LiveState {
  return {
    phase: "idle",
    attemptId: null,
    backend: null,
    transcript: [],
    presentation: null,
    failure: null,
    endReason: null,
    needsAudioUnlock: false,
    timing: emptyTiming(),
  };
}

export function reduceLiveState(state: LiveState, action: LiveAction): LiveState {
  if (action.type === "start_requested") {
    if (
      !action.attemptId ||
      !["idle", "stopped", "failure"].includes(state.phase)
    ) {
      return state;
    }
    return {
      phase: "connecting",
      attemptId: action.attemptId,
      backend: null,
      transcript: [],
      presentation: null,
      failure: null,
      endReason: null,
      needsAudioUnlock: false,
      timing: emptyTiming(),
    };
  }

  if (action.attemptId !== state.attemptId) return state;

  switch (action.type) {
    case "connected":
      return state.phase === "connecting"
        ? { ...state, phase: "listening", backend: action.backend }
        : state;
    case "agent_state":
      return ["listening", "thinking", "speaking", "interrupted"].includes(
        state.phase,
      )
        ? { ...state, phase: action.state }
        : state;
    case "local_speech":
      return state.phase === "speaking" ? { ...state, phase: "interrupted" } : state;
    case "transcript": {
      if (["idle", "connecting", "stopped", "failure"].includes(state.phase)) {
        return state;
      }
      const index = state.transcript.findIndex((entry) => entry.id === action.entry.id);
      if (index === -1) {
        return { ...state, transcript: [...state.transcript, action.entry] };
      }
      const transcript = [...state.transcript];
      transcript[index] = action.entry;
      return { ...state, transcript };
    }
    case "diagnostic":
      return {
        ...state,
        timing: mergeTiming(state.timing, action.event.fields),
      };
    case "presentation":
      if (action.update.attemptId !== action.attemptId) return state;
      if (action.update.view.sessionId !== action.attemptId) return state;
      if (
        state.presentation !== null &&
        action.update.view.state.sessionVersion <
          state.presentation.state.sessionVersion
      ) {
        return state;
      }
      return { ...state, presentation: action.update.view };
    case "audio_playback_blocked":
      return { ...state, needsAudioUnlock: true };
    case "audio_playback_unlocked":
      return { ...state, needsAudioUnlock: false };
    case "stopped":
      return ["stopped", "failure"].includes(state.phase)
        ? state
        : { ...state, phase: "stopped", endReason: null, needsAudioUnlock: false };
    case "ended":
      return ["stopped", "failure"].includes(state.phase)
        ? state
        : {
            ...state,
            phase: "stopped",
            endReason: action.reason,
            needsAudioUnlock: false,
          };
    case "failed":
      return ["stopped", "failure"].includes(state.phase)
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

function emptyTiming(): LiveTimingSummary {
  return {
    planningDurationMs: null,
    providerResponseStartGapMs: null,
    modelTtftMs: null,
    llmTtftMs: null,
    ttsTtfbMs: null,
    endOfUtteranceDelayMs: null,
    interruptionDetectionDelayMs: null,
  };
}

function mergeTiming(
  timing: LiveTimingSummary,
  fields: ConversationDiagnosticEvent["fields"],
): LiveTimingSummary {
  const next = { ...timing };
  for (const key of Object.keys(next) as Array<keyof LiveTimingSummary>) {
    const value = fields[key];
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
      next[key] = value;
    }
  }
  return next;
}
