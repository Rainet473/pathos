export const CONVERSATION_LIFECYCLE_TOPIC = "voice-conversation.lifecycle.v1";

export type LiveSessionEndReason = "idle_timeout" | "absolute_timeout";

export interface ConversationLifecycleUpdate {
  version: 1;
  attemptId: string;
  reason: LiveSessionEndReason;
}

export function parseConversationLifecycleUpdate(
  payload: Uint8Array,
): ConversationLifecycleUpdate | null {
  try {
    const value = JSON.parse(new TextDecoder().decode(payload)) as Record<string, unknown>;
    if (
      value.version !== 1 ||
      typeof value.attemptId !== "string" ||
      (value.reason !== "idle_timeout" && value.reason !== "absolute_timeout")
    ) {
      return null;
    }
    return value as unknown as ConversationLifecycleUpdate;
  } catch {
    return null;
  }
}
