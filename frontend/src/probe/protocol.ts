export const CONTROL_TOPIC = "voice-probe.control.v1";

export type ProbeControlType =
  | "capture_started"
  | "capture_stopped"
  | "replay_acknowledged";
export type ProbeStatusType = "replay_started" | "replay_completed" | "failed";

export interface AttemptIdentifiers {
  attemptId: string;
  roomName: string;
  participantIdentity: string;
}

export interface ProbeStatusPacket {
  version: 1;
  type: ProbeStatusType;
  attemptId: string;
  emittedAtMs: number;
  metrics?: {
    frameCount: number;
    audioDurationMs: number;
  };
  reason?: string;
}

export interface ProbeSessionResponse extends AttemptIdentifiers {
  serverUrl: string;
  participantToken: string;
}

export function createAttemptIdentifiers(attemptId: string): AttemptIdentifiers {
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(attemptId)) {
    throw new Error("attempt identifier must be a UUID");
  }
  const prefix = attemptId.split("-", 1)[0].toLowerCase();
  return {
    attemptId,
    roomName: `probe-${prefix}`,
    participantIdentity: `browser-${prefix}`,
  };
}

export function createControlPacket(
  type: ProbeControlType,
  attemptId: string,
  emittedAtMs: number,
): Uint8Array<ArrayBuffer> {
  return new TextEncoder().encode(
    JSON.stringify({
      version: 1,
      type,
      attemptId,
      emittedAtMs: Math.max(0, Math.round(emittedAtMs)),
    }),
  );
}

export function parseStatusPacket(payload: Uint8Array): ProbeStatusPacket | null {
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder().decode(payload));
  } catch {
    return null;
  }
  if (!isRecord(value)) return null;
  if (value.version !== 1) return null;
  if (!isStatusType(value.type)) return null;
  if (typeof value.attemptId !== "string" || value.attemptId.length === 0) return null;
  if (!isNonNegativeNumber(value.emittedAtMs)) return null;
  if (value.reason !== undefined && typeof value.reason !== "string") return null;
  if (value.metrics !== undefined && !isMetrics(value.metrics)) return null;
  return value as unknown as ProbeStatusPacket;
}

function isStatusType(value: unknown): value is ProbeStatusType {
  return value === "replay_started" || value === "replay_completed" || value === "failed";
}

function isMetrics(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonNegativeNumber(value.frameCount) &&
    isNonNegativeNumber(value.audioDurationMs)
  );
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
