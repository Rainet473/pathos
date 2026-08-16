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
    expect(planningFailureMessage("provider_error")).toContain("could not prepare");
    expect(planningFailureMessage("unknown_failure")).toContain("could not prepare");
  });
});
