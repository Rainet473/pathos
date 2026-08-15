import { describe, expect, it } from "vitest";

import { createLiveAttemptIdentifiers } from "./protocol";

describe("live conversation protocol", () => {
  it("derives room-scoped identifiers from one UUID", () => {
    expect(
      createLiveAttemptIdentifiers("9EA3A1CB-56EA-44D3-B322-D9D3134CE0DB"),
    ).toEqual({
      attemptId: "9EA3A1CB-56EA-44D3-B322-D9D3134CE0DB",
      roomName: "conversation-9ea3a1cb",
      participantIdentity: "browser-9ea3a1cb",
    });
  });

  it("rejects malformed attempt identifiers before bootstrap", () => {
    expect(() => createLiveAttemptIdentifiers("not-a-uuid")).toThrow(/UUID/);
  });
});
