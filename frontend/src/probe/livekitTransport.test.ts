import { describe, expect, it } from "vitest";
import type { LocalAudioTrack, Room } from "livekit-client";

import { LiveKitProbeTransport } from "./livekitTransport";

class FakeRoom {
  handlers = new Map<string, (...args: unknown[]) => void>();
  startAudioCalls = 0;
  unpublishCalls = 0;
  publishDataCalls = 0;
  localParticipant = {
    publishTrack: async () => undefined,
    publishData: async () => {
      this.publishDataCalls += 1;
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

  async disconnect() {}

  async startAudio() {
    this.startAudioCalls += 1;
  }
}

describe("LiveKit probe transport", () => {
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

    await transport.primeAudio();
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
