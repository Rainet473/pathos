export type PresentationPhase =
  | "ready"
  | "presenting"
  | "interrupted"
  | "answering"
  | "waiting"
  | "completed";

export type ContinuationPreference =
  | "ask_before_continuing"
  | "continue_after_answer"
  | "stay_paused";

export interface Cursor {
  slideId: string;
  beatIndex: number;
}

export interface ActivePlayout {
  turnId: string;
  cursor: Cursor;
  purpose: "narration" | "answer";
}

export interface PresentationSnapshot {
  sessionVersion: number;
  phase: PresentationPhase;
  presentationCursor: Cursor;
  visibleSlideId: string;
  activeTurnId: string | null;
  activePlayout: ActivePlayout | null;
  interruptedCursor: Cursor | null;
  continuationPreference: ContinuationPreference | null;
}

export interface SlideSummary {
  id: string;
  title: string;
  headline: string;
  labels: string[];
}

export interface TranscriptEntry {
  role: "user" | "agent";
  text: string;
  turnId: string;
}

export interface DomainEventSnapshot {
  type: string;
  cursor?: Cursor | null;
  turnId?: string | null;
  slideId?: string | null;
  slideChangeReason?: string | null;
  purpose?: string | null;
  scopeMode?: string | null;
  continuationPreference?: ContinuationPreference | null;
}

export interface FakeSessionSnapshot {
  sessionId: string;
  title?: string;
  state: PresentationSnapshot;
  slides: SlideSummary[];
  transcript: TranscriptEntry[];
  events: DomainEventSnapshot[];
  scopeMode: string | null;
  committedBeats: Cursor[];
}

export interface PresentationUiState {
  snapshot: FakeSessionSnapshot | null;
  failure: string | null;
  actionInFlight: boolean;
}

export function initialPresentationUiState(): PresentationUiState {
  return {
    snapshot: null,
    failure: null,
    actionInFlight: false,
  };
}

export function beginPresentationAction(state: PresentationUiState): PresentationUiState {
  return { ...state, actionInFlight: true, failure: null };
}

export function failPresentationAction(
  state: PresentationUiState,
  failure: string,
): PresentationUiState {
  return { ...state, actionInFlight: false, failure };
}

export function applySessionSnapshot(
  state: PresentationUiState,
  snapshot: FakeSessionSnapshot,
): PresentationUiState {
  const current = state.snapshot;
  if (
    current !== null &&
    current.sessionId === snapshot.sessionId &&
    snapshot.state.sessionVersion < current.state.sessionVersion
  ) {
    return state;
  }
  return {
    snapshot,
    failure: null,
    actionInFlight: false,
  };
}
