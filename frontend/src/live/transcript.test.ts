import { describe, expect, it } from "vitest";

import {
  CONVERSATION_TRANSCRIPT_TOPIC,
  parseConversationTranscriptUpdate,
} from "./transcript";


describe("conversation transcript wire contract", () => {
  it("accepts one provider-neutral transcript update", () => {
    const payload = new TextEncoder().encode(JSON.stringify({
      version: 1,
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      sequence: 2,
      emittedAt: "2026-08-16T08:30:00Z",
      entry: {
        id: "user-1",
        role: "user",
        text: "Why does a lower gear slow more?",
        final: true,
      },
    }));

    expect(CONVERSATION_TRANSCRIPT_TOPIC).toBe("voice-conversation.transcript.v1");
    expect(parseConversationTranscriptUpdate(payload)).toEqual({
      version: 1,
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      sequence: 2,
      emittedAt: "2026-08-16T08:30:00Z",
      entry: {
        id: "user-1",
        role: "user",
        text: "Why does a lower gear slow more?",
        final: true,
      },
    });
  });

  it.each([
    { version: 2 },
    { attemptId: "" },
    { sequence: 0 },
    { emittedAt: "not-a-date" },
    { entry: { id: "", role: "user", text: "hello", final: true } },
    { entry: { id: "user-1", role: "tool", text: "hello", final: true } },
    { entry: { id: "user-1", role: "user", text: "  ", final: true } },
  ])("rejects malformed update %#", (override) => {
    const valid = {
      version: 1,
      attemptId: "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
      sequence: 1,
      emittedAt: "2026-08-16T08:30:00Z",
      entry: { id: "user-1", role: "user", text: "hello", final: true },
    };
    const payload = {
      ...valid,
      ...override,
      entry: "entry" in override ? override.entry : valid.entry,
    };

    expect(
      parseConversationTranscriptUpdate(
        new TextEncoder().encode(JSON.stringify(payload)),
      ),
    ).toBeNull();
  });
});
