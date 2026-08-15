import type {
  LiveAttemptIdentifiers,
  LiveSessionResponse,
  VoiceBackendIdentity,
} from "./protocol";

interface BootstrapWireResponse {
  attempt_id: string;
  room_name: string;
  participant_identity: string;
  server_url: string;
  participant_token: string;
  backend: VoiceBackendIdentity;
}

export async function createLiveSession(
  identifiers: LiveAttemptIdentifiers,
): Promise<LiveSessionResponse> {
  const response = await fetch("/api/live/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      attempt_id: identifiers.attemptId,
      room_name: identifiers.roomName,
      participant_identity: identifiers.participantIdentity,
    }),
  });
  if (!response.ok) {
    throw new Error(
      response.status === 503
        ? "The selected live voice provider is unavailable. Check the backend log."
        : `Live session bootstrap failed (${response.status}).`,
    );
  }
  const value = (await response.json()) as BootstrapWireResponse;
  return {
    attemptId: value.attempt_id,
    roomName: value.room_name,
    participantIdentity: value.participant_identity,
    serverUrl: value.server_url,
    participantToken: value.participant_token,
    backend: value.backend,
  };
}
