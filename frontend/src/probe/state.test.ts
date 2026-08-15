import { describe, expect, it } from "vitest";

import { initialProbeState, reduceProbeState } from "./state";

const currentAttempt = "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db";

describe("probe state", () => {
  it("is quiet and disconnected until an explicit start request", () => {
    const state = initialProbeState();

    expect(state).toEqual({
      phase: "idle",
      attemptId: null,
      metrics: null,
      failure: null,
      needsAudioUnlock: false,
    });
  });

  it("moves one attempt through capture, transfer, replay and completion", () => {
    let state = initialProbeState();
    state = reduceProbeState(state, {
      type: "start_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "capture_started",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "stop_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "replay_started",
      attemptId: currentAttempt,
      metrics: { frameCount: 150, audioDurationMs: 3000 },
    });
    state = reduceProbeState(state, {
      type: "replay_completed",
      attemptId: currentAttempt,
      metrics: { frameCount: 150, audioDurationMs: 3000 },
    });

    expect(state.phase).toBe("complete");
    expect(state.metrics).toEqual({ frameCount: 150, audioDurationMs: 3000 });
  });

  it("ignores duplicate stop and late events from an old attempt", () => {
    let state = reduceProbeState(initialProbeState(), {
      type: "start_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "capture_started",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "stop_requested",
      attemptId: currentAttempt,
    });
    const afterFirstStop = state;

    state = reduceProbeState(state, {
      type: "stop_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "replay_completed",
      attemptId: "old-attempt",
      metrics: { frameCount: 99, audioDurationMs: 999 },
    });

    expect(state).toEqual(afterFirstStop);
  });

  it("shows disconnect failure and allows a fresh attempt", () => {
    let state = reduceProbeState(initialProbeState(), {
      type: "start_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "failed",
      attemptId: currentAttempt,
      reason: "room disconnected",
    });

    expect(state.phase).toBe("failure");
    expect(state.failure).toBe("room disconnected");

    state = reduceProbeState(state, {
      type: "start_requested",
      attemptId: "f19d6458-7145-4388-8337-841d27a428ec",
    });
    expect(state.phase).toBe("connecting");
    expect(state.failure).toBeNull();
  });

  it("does not replace the first actionable failure with cleanup noise", () => {
    let state = reduceProbeState(initialProbeState(), {
      type: "start_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "failed",
      attemptId: currentAttempt,
      reason: "Microphone permission was denied.",
    });

    state = reduceProbeState(state, {
      type: "failed",
      attemptId: currentAttempt,
      reason: "LiveKit room disconnected.",
    });

    expect(state.failure).toBe("Microphone permission was denied.");
  });

  it("exposes blocked autoplay without falsely completing replay", () => {
    let state = reduceProbeState(initialProbeState(), {
      type: "start_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "capture_started",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "stop_requested",
      attemptId: currentAttempt,
    });
    state = reduceProbeState(state, {
      type: "replay_started",
      attemptId: currentAttempt,
      metrics: { frameCount: 50, audioDurationMs: 1000 },
    });
    state = reduceProbeState(state, {
      type: "audio_playback_blocked",
      attemptId: currentAttempt,
    });

    expect(state.phase).toBe("replaying");
    expect(state.needsAudioUnlock).toBe(true);
  });
});
