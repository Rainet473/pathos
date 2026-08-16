import type {
  Cursor,
  DomainEventSnapshot,
  PresentationSnapshot,
  SlideSummary,
} from "./presentationTypes";
import type { PlanningStage } from "./planningStatus";

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
  groundingSource: string | null;
  planningStage: PlanningStage | null;
  planningFailureCode: string | null;
  planningRecoveryCode: string | null;
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
      !isNullableString(value.view.scopeMode) ||
      !isNullableString(value.view.groundingSource) ||
      !isPlanningStage(value.view.planningStage) ||
      !isNullableString(value.view.planningFailureCode) ||
      !isNullableString(value.view.planningRecoveryCode) ||
      !Array.isArray(value.view.committedBeats)
    ) {
      return null;
    }
    return value as unknown as PresentationStateUpdate;
  } catch {
    return null;
  }
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isPlanningStage(value: unknown): value is PlanningStage | null {
  return (
    value === null ||
    value === "understanding" ||
    value === "searching" ||
    value === "preparing"
  );
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
