export const CONVERSATION_DIAGNOSTICS_TOPIC = "voice-conversation.diagnostics.v1";

export type DiagnosticScalar = boolean | number | string;

export interface ConversationDiagnosticEvent {
  version: 1;
  attemptId: string;
  sequence: number;
  eventType: string;
  elapsedMs: number;
  fields: Record<string, DiagnosticScalar>;
}

export function parseConversationDiagnosticEvent(
  payload: Uint8Array,
): ConversationDiagnosticEvent | null {
  let candidate: unknown;
  try {
    candidate = JSON.parse(new TextDecoder().decode(payload));
  } catch {
    return null;
  }
  if (!isRecord(candidate) || candidate.version !== 1) return null;
  if (typeof candidate.attemptId !== "string" || !candidate.attemptId) return null;
  if (!Number.isInteger(candidate.sequence) || Number(candidate.sequence) < 1) return null;
  if (typeof candidate.eventType !== "string" || !candidate.eventType) return null;
  if (!isFiniteNonNegativeNumber(candidate.elapsedMs)) return null;
  if (!isRecord(candidate.fields)) return null;
  if (!Object.values(candidate.fields).every(isDiagnosticScalar)) return null;
  return candidate as unknown as ConversationDiagnosticEvent;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDiagnosticScalar(value: unknown): value is DiagnosticScalar {
  return (
    typeof value === "boolean" ||
    typeof value === "string" ||
    isFiniteNonNegativeNumber(value)
  );
}

function isFiniteNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
