import { afterEach, describe, expect, it, vi } from "vitest";
import { RoomEvent, type LocalAudioTrack, type Room } from "livekit-client";

import { LiveKitProbeTransport } from "./livekitTransport";
import { CONTROL_TOPIC } from "./protocol";

class FakeRoom {
  handlers = new Map<string, (...args: unknown[]) => void>();
  startAudioError: Error | null = null;
  startAudioCalls = 0;
  unpublishCalls = 0;
  publishDataCalls = 0;
  publishedData: Uint8Array[] = [];
  disconnectCalls = 0;
  hangPublishData = false;
  localParticipant = {
    publishTrack: async () => undefined,
    publishData: async (payload: Uint8Array) => {
      this.publishDataCalls += 1;
      this.publishedData.push(payload);
      if (this.hangPublishData) await new Promise(() => undefined);
      if (this.publishDataCalls === 2) throw new Error("control channel failed");
    },
    unpublishTrack: async () => {
      this.unpublishCalls += 1;
    },
  };

  on(event: string, handler: (...args: unknown[]) => void) {
    this.handlers.set(event, handler);
    return this;
  }

  async connect() {}

  async disconnect() {
    this.disconnectCalls += 1;
  }

  async startAudio() {
    this.startAudioCalls += 1;
    if (this.startAudioError !== null) throw this.startAudioError;
  }
}

describe("LiveKit probe transport", () => {
  afterEach(() => vi.useRealTimers());

  it("exposes replay completion immediately while acknowledgement is best-effort", async () => {
    const room = new FakeRoom();
    const observed: string[] = [];
    const transport = new LiveKitProbeTransport(
      {
        onStatus: (status) => observed.push(status.type),
        onDisconnected: () => undefined,
        onAudioPlaybackBlocked: () => undefined,
      },
      { roomFactory: () => room as unknown as Room },
    );
    await transport.connect({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
      serverUrl: "wss://example.livekit.cloud",
      participantToken: "participant-token",
    });

    room.handlers.get(RoomEvent.DataReceived)?.(
      new TextEncoder().encode(
        JSON.stringify({
          version: 1,
          type: "replay_completed",
          attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
          emittedAtMs: 500,
          metrics: { frameCount: 25, audioDurationMs: 500 },
        }),
      ),
      { identity: "probe-worker-9ea3a1cb" },
      undefined,
      CONTROL_TOPIC,
    );
    await Promise.resolve();
    await Promise.resolve();

    expect(room.publishDataCalls).toBe(1);
    expect(JSON.parse(new TextDecoder().decode(room.publishedData[0]))).toMatchObject({
      type: "replay_acknowledged",
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
    });
    expect(observed).toEqual(["replay_completed"]);
  });

  it("does not hold terminal UI state behind a stalled acknowledgement", async () => {
    const room = new FakeRoom();
    room.hangPublishData = true;
    const observed: string[] = [];
    const transport = new LiveKitProbeTransport(
      {
        onStatus: (status) => observed.push(status.type),
        onDisconnected: () => undefined,
        onAudioPlaybackBlocked: () => undefined,
      },
      { roomFactory: () => room as unknown as Room },
    );
    await transport.connect({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
      serverUrl: "wss://example.livekit.cloud",
      participantToken: "participant-token",
    });

    room.handlers.get(RoomEvent.DataReceived)?.(
      new TextEncoder().encode(
        JSON.stringify({
          version: 1,
          type: "replay_completed",
          attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
          emittedAtMs: 500,
        }),
      ),
      { identity: "probe-worker-9ea3a1cb" },
      undefined,
      CONTROL_TOPIC,
    );

    expect(observed).toEqual(["replay_completed"]);
  });

  it("caps the browser connection below one billing minute", async () => {
    vi.useFakeTimers();
    const room = new FakeRoom();
    let disconnected = 0;
    const transport = new LiveKitProbeTransport(
      {
        onStatus: () => undefined,
        onDisconnected: () => {
          disconnected += 1;
        },
        onAudioPlaybackBlocked: () => undefined,
      },
      {
        roomFactory: () => room as unknown as Room,
        sessionTimeoutMs: 10,
      },
    );
    await transport.connect({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
      serverUrl: "wss://example.livekit.cloud",
      participantToken: "participant-token",
    });

    await vi.advanceTimersByTimeAsync(10);

    expect(disconnected).toBe(1);
    expect(room.disconnectCalls).toBe(1);
  });

  it("disconnects promptly and reports failure if the worker leaves pre-terminal", async () => {
    const room = new FakeRoom();
    let disconnected = 0;
    const transport = new LiveKitProbeTransport(
      {
        onStatus: () => undefined,
        onDisconnected: () => {
          disconnected += 1;
        },
        onAudioPlaybackBlocked: () => undefined,
      },
      { roomFactory: () => room as unknown as Room },
    );
    await transport.connect({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
      serverUrl: "wss://example.livekit.cloud",
      participantToken: "participant-token",
    });

    room.handlers.get(RoomEvent.ParticipantDisconnected)?.({
      identity: "probe-worker-9ea3a1cb",
    });
    await Promise.resolve();

    expect(disconnected).toBe(1);
    expect(room.disconnectCalls).toBe(1);
  });

  it("treats blocked gesture-time audio priming as an event-driven recovery", async () => {
    const room = new FakeRoom();
    room.startAudioError = new Error("playback blocked");
    const transport = new LiveKitProbeTransport(
      {
        onStatus: () => undefined,
        onDisconnected: () => undefined,
        onAudioPlaybackBlocked: () => undefined,
      },
      { roomFactory: () => room as unknown as Room },
    );

    const primeResult: unknown = transport.primeAudio();
    expect(primeResult).toBeUndefined();
    if (primeResult instanceof Promise) await primeResult.catch(() => undefined);
    expect(room.startAudioCalls).toBe(1);
  });

  it("primes browser audio directly and always stops the microphone after stop failure", async () => {
    const room = new FakeRoom();
    let microphoneStopped = false;
    const microphone = {
      stop: () => {
        microphoneStopped = true;
      },
    } as unknown as LocalAudioTrack;
    const transport = new LiveKitProbeTransport(
      {
        onStatus: () => undefined,
        onDisconnected: () => undefined,
        onAudioPlaybackBlocked: () => undefined,
      },
      {
        roomFactory: () => room as unknown as Room,
        microphoneFactory: async () => microphone,
      },
    );

    transport.primeAudio();
    await transport.connect({
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      roomName: "probe-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
      serverUrl: "wss://example.livekit.cloud",
      participantToken: "participant-token",
    });
    await transport.startCapture();

    await expect(transport.stopCapture()).rejects.toThrow("control channel failed");
    expect(room.startAudioCalls).toBe(1);
    expect(room.unpublishCalls).toBe(1);
    expect(microphoneStopped).toBe(true);
  });
});
