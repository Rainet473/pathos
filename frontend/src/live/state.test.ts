import { describe, expect, it } from "vitest";

import { initialLiveState, reduceLiveState } from "./state";

const attempt = "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db";
const backend = {
  provider: "gemini_live" as const,
  kind: "realtime" as const,
  model: "gemini-2.5-flash-native-audio-preview-12-2025",
};

describe("live conversation state", () => {
  it("is quiet with no attempt, provider, transcript or failure on page load", () => {
    expect(initialLiveState()).toEqual({
      phase: "idle",
      attemptId: null,
      backend: null,
      transcript: [],
      presentation: null,
      failure: null,
      needsAudioUnlock: false,
      timing: {
        providerResponseStartGapMs: null,
        modelTtftMs: null,
        llmTtftMs: null,
        ttsTtfbMs: null,
        endOfUtteranceDelayMs: null,
        interruptionDetectionDelayMs: null,
      },
    });
  });

  it("keeps the newest application-owned presentation snapshot", () => {
    let state = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    state = reduceLiveState(state, { type: "connected", attemptId: attempt, backend });
    const update = presentationUpdate(4);
    state = reduceLiveState(state, {
      type: "presentation",
      attemptId: attempt,
      update,
    });
    state = reduceLiveState(state, {
      type: "presentation",
      attemptId: attempt,
      update: presentationUpdate(3),
    });

    expect(state.presentation).toEqual(update.view);
  });

  it("retains the latest normalized latency stages for the active attempt", () => {
    let state = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    state = reduceLiveState(state, { type: "connected", attemptId: attempt, backend });
    state = reduceLiveState(state, {
      type: "diagnostic",
      attemptId: attempt,
      event: {
        version: 1,
        attemptId: attempt,
        sequence: 4,
        eventType: "realtime_model_metrics",
        elapsedMs: 3200,
        fields: { providerResponseStartGapMs: 1800 },
      },
    });
    state = reduceLiveState(state, {
      type: "diagnostic",
      attemptId: attempt,
      event: {
        version: 1,
        attemptId: attempt,
        sequence: 5,
        eventType: "realtime_model_metrics",
        elapsedMs: 4100,
        fields: {
          modelTtftMs: 950,
          llmTtftMs: 420,
          ttsTtfbMs: 180,
          interruptionDetectionDelayMs: 110,
        },
      },
    });

    expect(state.timing).toEqual({
      providerResponseStartGapMs: 1800,
      modelTtftMs: 950,
      llmTtftMs: 420,
      ttsTtfbMs: 180,
      endOfUtteranceDelayMs: null,
      interruptionDetectionDelayMs: 110,
    });
  });

  it("tracks connection, provider state and an observable interruption", () => {
    let state = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    state = reduceLiveState(state, { type: "connected", attemptId: attempt, backend });
    state = reduceLiveState(state, {
      type: "agent_state",
      attemptId: attempt,
      state: "speaking",
    });
    state = reduceLiveState(state, { type: "local_speech", attemptId: attempt });

    expect(state.phase).toBe("interrupted");
    expect(state.backend).toEqual(backend);

    state = reduceLiveState(state, {
      type: "agent_state",
      attemptId: attempt,
      state: "listening",
    });
    expect(state.phase).toBe("listening");
  });

  it("ignores duplicate starts and every callback from a stale attempt", () => {
    const connecting = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    let state = reduceLiveState(connecting, {
      type: "start_requested",
      attemptId: "f19d6458-7145-4388-8337-841d27a428ec",
    });
    state = reduceLiveState(state, {
      type: "connected",
      attemptId: "old-attempt",
      backend,
    });
    state = reduceLiveState(state, {
      type: "transcript",
      attemptId: "old-attempt",
      entry: { id: "late", role: "agent", text: "late", final: true },
    });

    expect(state).toEqual(connecting);
  });

  it("deduplicates interim transcript segments and keeps the final text", () => {
    let state = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    state = reduceLiveState(state, { type: "connected", attemptId: attempt, backend });
    state = reduceLiveState(state, {
      type: "transcript",
      attemptId: attempt,
      entry: { id: "turn-1", role: "user", text: "hel", final: false },
    });
    state = reduceLiveState(state, {
      type: "transcript",
      attemptId: attempt,
      entry: { id: "turn-1", role: "user", text: "hello", final: true },
    });

    expect(state.transcript).toEqual([
      { id: "turn-1", role: "user", text: "hello", final: true },
    ]);
  });

  it("stops cleanly, preserves the first failure, and permits a fresh attempt", () => {
    let state = reduceLiveState(initialLiveState(), {
      type: "start_requested",
      attemptId: attempt,
    });
    state = reduceLiveState(state, {
      type: "failed",
      attemptId: attempt,
      reason: "Microphone permission was denied.",
    });
    state = reduceLiveState(state, {
      type: "failed",
      attemptId: attempt,
      reason: "room disconnected",
    });
    expect(state.failure).toBe("Microphone permission was denied.");

    state = reduceLiveState(state, {
      type: "start_requested",
      attemptId: "f19d6458-7145-4388-8337-841d27a428ec",
    });
    expect(state.phase).toBe("connecting");
    expect(state.failure).toBeNull();

    state = reduceLiveState(state, {
      type: "stopped",
      attemptId: "f19d6458-7145-4388-8337-841d27a428ec",
    });
    expect(state.phase).toBe("stopped");
  });
});

function presentationUpdate(sessionVersion: number) {
  return {
    attemptId: attempt,
    emittedAt: "2026-08-16T10:00:00Z",
    view: {
      sessionId: attempt,
      title: "How a Motorcycle Responds to Your Controls",
      state: {
        sessionVersion,
        phase: "presenting" as const,
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
      }],
      events: [],
      scopeMode: null,
      committedBeats: [],
    },
  };
}
