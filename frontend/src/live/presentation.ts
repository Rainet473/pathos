import type {
  Cursor,
  DomainEventSnapshot,
  PresentationSnapshot,
  SlideSummary,
} from "../presentation/state";

export const PRESENTATION_STATE_TOPIC = "voice-presentation.state.v1";
export const PRESENTATION_COMMAND_TOPIC = "voice-presentation.command.v1";

export interface LivePresentationView {
  sessionId: string;
  deckId: string;
  title: string;
  state: PresentationSnapshot;
  slides: SlideSummary[];
  events: DomainEventSnapshot[];
  scopeMode: string | null;
  committedBeats: Cursor[];
}

export interface PresentationStateUpdate {
  attemptId: string;
  emittedAt: string;
  view: LivePresentationView;
}

export function parsePresentationStateUpdate(
  payload: Uint8Array,
): PresentationStateUpdate | null {
  try {
    const value = JSON.parse(new TextDecoder().decode(payload)) as unknown;
    if (!isRecord(value) || !isRecord(value.view) || !isRecord(value.view.state)) {
      return null;
    }
    const state = value.view.state;
    if (
      typeof value.attemptId !== "string" ||
      typeof value.emittedAt !== "string" ||
      typeof value.view.sessionId !== "string" ||
      typeof value.view.deckId !== "string" ||
      typeof value.view.title !== "string" ||
      typeof state.sessionVersion !== "number" ||
      typeof state.phase !== "string" ||
      typeof state.visibleSlideId !== "string" ||
      !isRecord(state.presentationCursor) ||
      !Array.isArray(value.view.slides) ||
      !Array.isArray(value.view.events) ||
      !Array.isArray(value.view.committedBeats)
    ) {
      return null;
    }
    return value as unknown as PresentationStateUpdate;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
