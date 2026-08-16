import { describe, expect, it } from "vitest";

import { deckSlideRenderUrl } from "./deckSlideVisual";

describe("deckSlideRenderUrl", () => {
  it("builds the safe render endpoint for the selected deck and slide", () => {
    expect(deckSlideRenderUrl("motorcycle-controls", "clutch-and-gears")).toBe(
      "/api/decks/motorcycle-controls/slides/clutch-and-gears/render",
    );
  });

  it("escapes identifiers instead of treating them as path fragments", () => {
    expect(deckSlideRenderUrl("deck id", "slide/one")).toBe(
      "/api/decks/deck%20id/slides/slide%2Fone/render",
    );
  });
});
