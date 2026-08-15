import { describe, expect, it } from "vitest";

import { visualSpecForSlide } from "./slideVisuals";

const slideIds = [
  "control-loop",
  "clutch-and-gears",
  "power-to-wheel",
  "engine-braking",
  "rev-matching",
  "braking-abs",
];

describe("visualSpecForSlide", () => {
  it("selects a distinct authored diagram for every full-deck slide", () => {
    const specs = slideIds.map((slideId) => visualSpecForSlide(slideId));

    expect(specs.map((spec) => spec.id)).toEqual(slideIds);
    expect(new Set(specs.map((spec) => spec.kind)).size).toBe(slideIds.length);
    expect(specs.every((spec) => spec.nodes.length >= 3)).toBe(true);
  });

  it("uses a safe generic flow for an unknown slide", () => {
    expect(visualSpecForSlide("future-slide")).toMatchObject({
      id: "future-slide",
      kind: "generic-flow",
    });
  });
});
