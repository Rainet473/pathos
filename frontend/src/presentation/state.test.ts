import { describe, expect, it } from "vitest";

import {
  applySessionSnapshot,
  initialPresentationUiState,
  type FakeSessionSnapshot,
} from "./state";


function snapshot(sessionVersion: number, sessionId = "session-1"): FakeSessionSnapshot {
  return {
    sessionId,
    state: {
      sessionVersion,
      phase: "presenting",
      presentationCursor: { slideId: "engine-braking", beatIndex: 0 },
      visibleSlideId: "engine-braking",
      activeTurnId: `narration-${sessionVersion}`,
      activePlayout: {
        turnId: `narration-${sessionVersion}`,
        cursor: { slideId: "engine-braking", beatIndex: 0 },
        purpose: "narration",
      },
      interruptedCursor: null,
      continuationPreference: null,
    },
    slides: [
      {
        id: "engine-braking",
        title: "Engine Braking",
        headline: "Low gears make the effect feel stronger.",
        labels: ["closed throttle", "gear ratio"],
        visualDescription: "The rear wheel drives a resisting engine through the selected ratio.",
      },
    ],
    transcript: [],
    events: [],
    scopeMode: null,
    committedBeats: [],
  };
}


describe("presentation UI state", () => {
  it("starts quiet without an assumed session or active turn", () => {
    expect(initialPresentationUiState()).toEqual({
      snapshot: null,
      failure: null,
      actionInFlight: false,
    });
  });

  it("accepts a fresh session and newer versions", () => {
    let state = applySessionSnapshot(initialPresentationUiState(), snapshot(0));
    state = applySessionSnapshot(state, snapshot(3));

    expect(state.snapshot?.state.sessionVersion).toBe(3);
    expect(state.snapshot?.state.activeTurnId).toBe("narration-3");
  });

  it("does not let an older response overwrite a newer visible snapshot", () => {
    const current = applySessionSnapshot(initialPresentationUiState(), snapshot(4));

    const afterLateResponse = applySessionSnapshot(current, snapshot(2));

    expect(afterLateResponse).toBe(current);
  });

  it("allows a version-zero snapshot from an explicitly new session", () => {
    const current = applySessionSnapshot(initialPresentationUiState(), snapshot(4));

    const reset = applySessionSnapshot(current, snapshot(0, "session-2"));

    expect(reset.snapshot?.sessionId).toBe("session-2");
    expect(reset.snapshot?.state.sessionVersion).toBe(0);
  });
});
