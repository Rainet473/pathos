export type VoiceProvider =
  | "gemini_live"
  | "openai_realtime"
  | "livekit_inference_pipeline";
export type VoiceBackendKind = "realtime" | "pipeline";

export interface VoiceBackendIdentity {
  provider: VoiceProvider;
  kind: VoiceBackendKind;
  model: string;
}

export interface LiveAttemptIdentifiers {
  attemptId: string;
  roomName: string;
  participantIdentity: string;
}

export interface LiveSessionResponse extends LiveAttemptIdentifiers {
  serverUrl: string;
  participantToken: string;
  backend: VoiceBackendIdentity;
  idleTimeoutSeconds: number;
  absoluteTimeoutSeconds: number;
}

export function createLiveAttemptIdentifiers(
  attemptId: string,
): LiveAttemptIdentifiers {
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(attemptId)) {
    throw new Error("attempt identifier must be a UUID");
  }
  const prefix = attemptId.split("-", 1)[0].toLowerCase();
  return {
    attemptId,
    roomName: `conversation-${prefix}`,
    participantIdentity: `browser-${prefix}`,
  };
}
