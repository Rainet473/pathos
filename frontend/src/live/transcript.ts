import type { TranscriptEntry } from "./state";


export const CONVERSATION_TRANSCRIPT_TOPIC = "voice-conversation.transcript.v1";

export interface ConversationTranscriptUpdate {
  version: 1;
  attemptId: string;
  sequence: number;
  emittedAt: string;
  entry: TranscriptEntry;
}

export function parseConversationTranscriptUpdate(
  payload: Uint8Array,
): ConversationTranscriptUpdate | null {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder().decode(payload));
    if (!isRecord(parsed) || parsed.version !== 1) return null;
    if (typeof parsed.attemptId !== "string" || !parsed.attemptId.trim()) return null;
    if (!Number.isInteger(parsed.sequence) || Number(parsed.sequence) < 1) return null;
    if (
      typeof parsed.emittedAt !== "string" ||
      !parsed.emittedAt ||
      Number.isNaN(Date.parse(parsed.emittedAt))
    ) return null;
    if (!isTranscriptEntry(parsed.entry)) return null;
    return {
      version: 1,
      attemptId: parsed.attemptId,
      sequence: Number(parsed.sequence),
      emittedAt: parsed.emittedAt,
      entry: {
        id: parsed.entry.id,
        role: parsed.entry.role,
        text: parsed.entry.text.trim(),
        final: parsed.entry.final,
      },
    };
  } catch {
    return null;
  }
}

function isTranscriptEntry(value: unknown): value is TranscriptEntry {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    Boolean(value.id.trim()) &&
    (value.role === "user" || value.role === "agent") &&
    typeof value.text === "string" &&
    Boolean(value.text.trim()) &&
    typeof value.final === "boolean"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
