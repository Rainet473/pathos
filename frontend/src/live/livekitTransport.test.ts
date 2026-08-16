import { afterEach, describe, expect, it, vi } from "vitest";
import { RoomEvent, Track } from "livekit-client";

import { LiveKitConversationTransport } from "./livekitTransport";
import { CONVERSATION_DIAGNOSTICS_TOPIC } from "./diagnostics";
import { PRESENTATION_STATE_TOPIC } from "./presentation";
import type { LiveSessionResponse } from "./protocol";
import { CONVERSATION_TRANSCRIPT_TOPIC } from "./transcript";

class FakeMicrophone {
  stopped = false;
  stop() {
    this.stopped = true;
  }
}

class FakeAudioTrack {
  kind = Track.Kind.Audio;
  element = {
    autoplay: false,
    dataset: {} as Record<string, string>,
    style: { display: "" },
    removed: false,
    remove() {
      this.removed = true;
    },
  };
  attach() {
    return this.element;
  }
}

class FakeRoom {
  handlers = new Map<string, (...args: any[]) => void>();
  connectCalls: unknown[][] = [];
  disconnectCount = 0;
  startAudioCount = 0;
  localParticipant = {
    identity: "browser-9ea3a1cb",
    publishCalls: [] as unknown[][],
    unpublishCalls: [] as unknown[][],
    publishTrack: async (...args: unknown[]) => {
      this.localParticipant.publishCalls.push(args);
    },
    publishData: async (...args: unknown[]) => {
      this.localParticipant.publishCalls.push(args);
    },
    unpublishTrack: async (...args: unknown[]) => {
      this.localParticipant.unpublishCalls.push(args);
    },
  };

  on(event: string, handler: (...args: any[]) => void) {
    this.handlers.set(event, handler);
    return this;
  }

  async connect(...args: unknown[]) {
    this.connectCalls.push(args);
  }

  async disconnect() {
    this.disconnectCount += 1;
  }

  async startAudio() {
    this.startAudioCount += 1;
  }
}

const session: LiveSessionResponse = {
  attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
  roomName: "conversation-9ea3a1cb",
  participantIdentity: "browser-9ea3a1cb",
  serverUrl: "wss://example.livekit.cloud",
  participantToken: "participant-token",
  idleTimeoutSeconds: 120,
  absoluteTimeoutSeconds: 900,
  backend: {
    provider: "gemini_live",
    kind: "realtime",
    model: "gemini-2.5-flash-native-audio-preview-12-2025",
  },
};

function setup() {
  const room = new FakeRoom();
  const microphone = new FakeMicrophone();
  const events: Array<[string, unknown]> = [];
  const appended: object[] = [];
  const transport = new LiveKitConversationTransport(
    {
      onConnected: (backend) => events.push(["connected", backend]),
      onAgentState: (state) => events.push(["state", state]),
      onLocalSpeechWhileAgentSpeaking: () => events.push(["interrupted", null]),
      onTranscript: (entry) => events.push(["transcript", entry]),
      onDiagnostic: (event) => events.push(["diagnostic", event]),
      onPresentation: (event) => events.push(["presentation", event]),
      onEnded: (reason) => events.push(["ended", reason]),
      onDisconnected: () => events.push(["disconnected", null]),
      onAudioPlaybackBlocked: () => events.push(["blocked", null]),
    },
    {
      roomFactory: () => room as never,
      microphoneFactory: async () => microphone as never,
      audioElementHost: { append: (element) => appended.push(element) },
    },
  );
  return { room, microphone, events, transport, appended };
}

describe("LiveKit conversation transport", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does nothing on construction and starts room plus microphone only on connect", async () => {
    const { room, microphone, events, transport } = setup();
    expect(room.connectCalls).toEqual([]);
    expect(room.localParticipant.publishCalls).toEqual([]);

    transport.primeAudio();
    await transport.connect(session);

    expect(room.startAudioCount).toBe(1);
    expect(room.connectCalls).toEqual([
      [session.serverUrl, session.participantToken, { autoSubscribe: true }],
    ]);
    expect(room.localParticipant.publishCalls[0][0]).toBe(microphone);
    expect(events[0]).toEqual(["connected", session.backend]);

    await transport.disconnect();
  });

  it("normalizes agent state, interruption and transcript events", async () => {
    const { room, events, transport } = setup();
    await transport.connect(session);
    const worker = {
      identity: "voice-worker-9ea3a1cb",
      attributes: { "lk.agent.state": "speaking" },
    };

    room.handlers.get(RoomEvent.ParticipantAttributesChanged)?.(
      { "lk.agent.state": "speaking" },
      worker,
    );
    room.handlers.get(RoomEvent.ActiveSpeakersChanged)?.([
      { identity: session.participantIdentity },
    ]);
    room.handlers.get(RoomEvent.DataReceived)?.(
      new TextEncoder().encode(JSON.stringify({
        version: 1,
        attemptId: session.attemptId,
        sequence: 3,
        eventType: "realtime_model_metrics",
        elapsedMs: 2500,
        fields: { modelTtftMs: 1200 },
      })),
      worker,
      undefined,
      CONVERSATION_DIAGNOSTICS_TOPIC,
    );
    const presentation = presentationUpdate();
    room.handlers.get(RoomEvent.DataReceived)?.(
      new TextEncoder().encode(JSON.stringify(presentation)),
      worker,
      undefined,
      PRESENTATION_STATE_TOPIC,
    );

    expect(events).toContainEqual(["state", "speaking"]);
    expect(events).toContainEqual(["interrupted", null]);
    expect(events).toContainEqual([
      "diagnostic",
      {
        version: 1,
        attemptId: session.attemptId,
        sequence: 3,
        eventType: "realtime_model_metrics",
        elapsedMs: 2500,
        fields: { modelTtftMs: 1200 },
      },
    ]);
    expect(events).toContainEqual(["presentation", presentation]);

    await transport.disconnect();
  });

  it("accepts only newer current-attempt transcript packets from the worker", async () => {
    const { room, events, transport } = setup();
    await transport.connect(session);
    const worker = { identity: "voice-worker-9ea3a1cb" };
    const stranger = { identity: "other-participant" };
    const packet = (sequence: number, attemptId = session.attemptId) =>
      new TextEncoder().encode(JSON.stringify({
        version: 1,
        attemptId,
        sequence,
        emittedAt: "2026-08-16T08:30:00Z",
        entry: {
          id: "user-1",
          role: "user",
          text: sequence === 2 ? "final question" : "late partial",
          final: sequence === 2,
        },
      }));

    room.handlers.get(RoomEvent.DataReceived)?.(
      packet(2), worker, undefined, CONVERSATION_TRANSCRIPT_TOPIC,
    );
    room.handlers.get(RoomEvent.DataReceived)?.(
      packet(1), worker, undefined, CONVERSATION_TRANSCRIPT_TOPIC,
    );
    room.handlers.get(RoomEvent.DataReceived)?.(
      packet(3, "other-attempt"), worker, undefined, CONVERSATION_TRANSCRIPT_TOPIC,
    );
    room.handlers.get(RoomEvent.DataReceived)?.(
      packet(4), stranger, undefined, CONVERSATION_TRANSCRIPT_TOPIC,
    );

    expect(events.filter(([type]) => type === "transcript")).toEqual([
      [
        "transcript",
        { id: "user-1", role: "user", text: "final question", final: true },
      ],
    ]);
    await transport.disconnect();
  });

  it("sends an explicit continue command only after connection", async () => {
    const { room, transport } = setup();

    await expect(transport.continuePresentation()).rejects.toThrow("not connected");
    await transport.connect(session);
    await transport.continuePresentation();

    const call = room.localParticipant.publishCalls.at(-1) as unknown[];
    expect(new TextDecoder().decode(call[0] as Uint8Array)).toBe(
      JSON.stringify({ action: "continue" }),
    );
    expect(call[1]).toEqual({ reliable: true, topic: "voice-presentation.command.v1" });
    await transport.disconnect();
  });

  it("sends a validated manual slide navigation command only after connection", async () => {
    const { room, transport } = setup();

    await expect(transport.navigateToSlide("clutch-and-gears")).rejects.toThrow("not connected");
    await transport.connect(session);
    await transport.navigateToSlide("clutch-and-gears");

    const call = room.localParticipant.publishCalls.at(-1) as unknown[];
    expect(new TextDecoder().decode(call[0] as Uint8Array)).toBe(
      JSON.stringify({ action: "navigate", slideId: "clutch-and-gears" }),
    );
    expect(call[1]).toEqual({ reliable: true, topic: "voice-presentation.command.v1" });
    await transport.disconnect();
  });

  it("attaches remote audio and releases microphone, audio and room exactly once", async () => {
    const { room, microphone, transport, appended } = setup();
    const audio = new FakeAudioTrack();
    await transport.connect(session);

    room.handlers.get(RoomEvent.TrackSubscribed)?.(
      audio,
      {},
      { identity: "voice-worker-9ea3a1cb" },
    );
    expect(appended).toEqual([audio.element]);

    await transport.disconnect();
    await transport.disconnect();

    expect(microphone.stopped).toBe(true);
    expect(audio.element.removed).toBe(true);
    expect(room.disconnectCount).toBe(1);
  });

  it("ends normally after inactivity and meaningful activity resets only the idle deadline", async () => {
    vi.useFakeTimers();
    const { room, events, transport } = setup();
    await transport.connect({
      ...session,
      idleTimeoutSeconds: 0.05,
      absoluteTimeoutSeconds: 0.2,
    });

    await vi.advanceTimersByTimeAsync(40);
    room.handlers.get(RoomEvent.ParticipantAttributesChanged)?.(
      { "lk.agent.state": "thinking" },
      { identity: "voice-worker-9ea3a1cb" },
    );
    await vi.advanceTimersByTimeAsync(40);
    expect(events.some(([type]) => type === "ended")).toBe(false);

    await vi.advanceTimersByTimeAsync(11);
    expect(events).toContainEqual(["ended", "idle_timeout"]);
    expect(events.some(([type]) => type === "disconnected")).toBe(false);
    expect(room.disconnectCount).toBe(1);
  });

  it("does not extend the absolute fifteen-minute safety ceiling", async () => {
    vi.useFakeTimers();
    const { room, events, transport } = setup();
    await transport.connect({
      ...session,
      idleTimeoutSeconds: 0.08,
      absoluteTimeoutSeconds: 0.1,
    });

    await vi.advanceTimersByTimeAsync(60);
    room.handlers.get(RoomEvent.ParticipantAttributesChanged)?.(
      { "lk.agent.state": "speaking" },
      { identity: "voice-worker-9ea3a1cb" },
    );
    await vi.advanceTimersByTimeAsync(41);

    expect(events).toContainEqual(["ended", "absolute_timeout"]);
    expect(events.some(([type]) => type === "disconnected")).toBe(false);
  });

  it("accepts a backend graceful-end reason without reporting a disconnect failure", async () => {
    const { room, events, transport } = setup();
    await transport.connect(session);
    room.handlers.get(RoomEvent.DataReceived)?.(
      new TextEncoder().encode(JSON.stringify({
        version: 1,
        attemptId: session.attemptId,
        reason: "idle_timeout",
      })),
      { identity: "voice-worker-9ea3a1cb" },
      undefined,
      "voice-conversation.lifecycle.v1",
    );

    await Promise.resolve();
    expect(events).toContainEqual(["ended", "idle_timeout"]);
    expect(events.some(([type]) => type === "disconnected")).toBe(false);
  });

  it("still reports an unexpected worker departure as a failure", async () => {
    const { room, events, transport } = setup();
    await transport.connect(session);

    room.handlers.get(RoomEvent.ParticipantDisconnected)?.({
      identity: "voice-worker-9ea3a1cb",
    });
    await Promise.resolve();

    expect(events).toContainEqual(["disconnected", null]);
    expect(events.some(([type]) => type === "ended")).toBe(false);
  });
});

function presentationUpdate() {
  return {
    attemptId: session.attemptId,
    emittedAt: "2026-08-16T10:00:00Z",
    view: {
      sessionId: session.attemptId,
      deckId: "motorcycle-controls",
      title: "How a Motorcycle Responds to Your Controls",
      state: {
        sessionVersion: 2,
        phase: "presenting",
        presentationCursor: { slideId: "engine-braking", beatIndex: 0 },
        visibleSlideId: "engine-braking",
        activeTurnId: "narration-1",
        activePlayout: null,
        interruptedCursor: null,
        continuationPreference: null,
      },
      slides: [{
        id: "engine-braking",
        title: "Engine Braking",
        headline: "Low gears make engine braking feel stronger.",
        labels: ["closed throttle", "drivetrain resistance", "gear ratio"],
        visualDescription: "The rear wheel drives a resisting engine through the selected ratio.",
      }],
      events: [],
      scopeMode: null,
      groundingSource: null,
      planningStage: null,
      planningFailureCode: null,
      committedBeats: [],
    },
  };
}
