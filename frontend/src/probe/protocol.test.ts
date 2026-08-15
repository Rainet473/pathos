import { describe, expect, it } from "vitest";

import {
  CONTROL_TOPIC,
  createAttemptIdentifiers,
  createControlPacket,
  parseStatusPacket,
} from "./protocol";

describe("probe wire protocol", () => {
  it("derives constrained room and browser names from a UUID", () => {
    expect(createAttemptIdentifiers("9ea3a1cb-56ea-44d3-b322-d9d3134ce0db")).toEqual({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
    });
  });

  it("encodes a versioned capture control packet", () => {
    const encoded = createControlPacket(
      "capture_stopped",
      "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      123,
    );

    expect(CONTROL_TOPIC).toBe("voice-probe.control.v1");
    expect(JSON.parse(new TextDecoder().decode(encoded))).toEqual({
      version: 1,
      type: "capture_stopped",
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      emittedAtMs: 123,
    });
  });

  it("encodes replay acknowledgement as an attempt-scoped control packet", () => {
    const encoded = createControlPacket(
      "replay_acknowledged",
      "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      124,
    );

    expect(JSON.parse(new TextDecoder().decode(encoded))).toEqual({
      version: 1,
      type: "replay_acknowledged",
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      emittedAtMs: 124,
    });
  });

  it("accepts replay status and rejects malformed or unsupported packets", () => {
    const decoder = new TextEncoder();
    expect(
      parseStatusPacket(
        decoder.encode(
          JSON.stringify({
            version: 1,
            type: "replay_started",
            attemptId: "attempt-1",
            emittedAtMs: 500,
            metrics: { frameCount: 50, audioDurationMs: 1000 },
          }),
        ),
      ),
    ).toEqual({
      version: 1,
      type: "replay_started",
      attemptId: "attempt-1",
      emittedAtMs: 500,
      metrics: { frameCount: 50, audioDurationMs: 1000 },
    });

    expect(parseStatusPacket(decoder.encode("not-json"))).toBeNull();
    expect(
      parseStatusPacket(
        decoder.encode(
          JSON.stringify({
            version: 2,
            type: "replay_started",
            attemptId: "attempt-1",
            emittedAtMs: 1,
          }),
        ),
      ),
    ).toBeNull();
  });
});
