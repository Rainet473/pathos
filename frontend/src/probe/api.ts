import type { AttemptIdentifiers, ProbeSessionResponse } from "./protocol";

interface BootstrapWireResponse {
  attempt_id: string;
  room_name: string;
  participant_identity: string;
  server_url: string;
  participant_token: string;
}

export async function createProbeSession(
  identifiers: AttemptIdentifiers,
): Promise<ProbeSessionResponse> {
  const response = await fetch("/api/probe/sessions", {
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
        ? "The Python voice transport is unavailable. Check the backend logs."
        : `Session bootstrap failed (${response.status}).`,
    );
  }
  const value = (await response.json()) as BootstrapWireResponse;
  return {
    attemptId: value.attempt_id,
    roomName: value.room_name,
    participantIdentity: value.participant_identity,
    serverUrl: value.server_url,
    participantToken: value.participant_token,
  };
}
