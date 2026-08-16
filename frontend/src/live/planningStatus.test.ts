import { describe, expect, it } from "vitest";

import {
  planningFailureMessage,
  planningStatusDescription,
  planningStatusLabel,
} from "./planningStatus";

describe("follow-up planning status", () => {
  it("uses observable status language without exposing reasoning prose", () => {
    expect(planningStatusLabel("understanding")).toBe(
      "Understanding your follow-up",
    );
    expect(planningStatusLabel("searching")).toBe(
      "Searching the presentation",
    );
    expect(planningStatusLabel("preparing")).toBe("Preparing an answer");
    expect(planningStatusDescription("searching")).toContain(
      "presentation material",
    );
    expect(planningStatusDescription("searching").toLowerCase()).not.toContain(
      "reasoning",
    );
  });

  it("turns sanitized failure codes into retryable listener guidance", () => {
    expect(planningFailureMessage("timeout")).toContain("timed out");
    expect(planningFailureMessage("unknown_evidence")).toContain(
      "presentation support changed",
    );
    expect(planningFailureMessage("invalid_tool_arguments")).toContain(
      "finish or rephrase",
    );
    expect(planningFailureMessage("provider_error")).toContain(
      "temporarily unavailable",
    );
    expect(planningFailureMessage("unknown_failure")).toContain("could not prepare");
  });
});
