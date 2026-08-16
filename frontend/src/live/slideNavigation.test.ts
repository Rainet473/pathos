import { describe, expect, it } from "vitest";

import { adjacentSlideId } from "./slideNavigation";

const slides = [
  { id: "control-loop" },
  { id: "clutch-and-gears" },
  { id: "power-to-wheel" },
];

describe("manual slide navigation", () => {
  it("moves to adjacent authored slides without wrapping", () => {
    expect(adjacentSlideId(slides, "clutch-and-gears", -1)).toBe("control-loop");
    expect(adjacentSlideId(slides, "clutch-and-gears", 1)).toBe("power-to-wheel");
    expect(adjacentSlideId(slides, "control-loop", -1)).toBeNull();
    expect(adjacentSlideId(slides, "power-to-wheel", 1)).toBeNull();
  });

  it("returns null for an unknown visible slide or unsupported direction", () => {
    expect(adjacentSlideId(slides, "missing", 1)).toBeNull();
    expect(adjacentSlideId(slides, "control-loop", 0)).toBeNull();
  });
});
