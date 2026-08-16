import { describe, expect, it } from "vitest";

import {
  advanceAnswerPath,
  answerPathNodes,
  emptyAnswerPath,
} from "./planningPath";

describe("observable answer pathway", () => {
  it("records a searched answer node by node", () => {
    let path = emptyAnswerPath();

    path = advanceAnswerPath(path, "understanding", "interrupted");
    expect(answerPathNodes(path).map((node) => node.status)).toEqual([
      "active",
      "pending",
      "pending",
      "pending",
    ]);

    path = advanceAnswerPath(path, "searching", "interrupted");
    path = advanceAnswerPath(path, "preparing", "interrupted");
    path = advanceAnswerPath(path, null, "answering");

    expect(answerPathNodes(path).map((node) => node.status)).toEqual([
      "complete",
      "complete",
      "complete",
      "active",
    ]);
  });

  it("marks optional search as skipped when the planner answers directly", () => {
    let path = advanceAnswerPath(
      emptyAnswerPath(),
      "understanding",
      "interrupted",
    );
    path = advanceAnswerPath(path, "preparing", "interrupted");
    path = advanceAnswerPath(path, null, "answering");

    expect(answerPathNodes(path).map((node) => node.status)).toEqual([
      "complete",
      "skipped",
      "complete",
      "active",
    ]);
  });

  it("deduplicates stages, resets for a new follow-up, and clears after answer", () => {
    let path = advanceAnswerPath(
      emptyAnswerPath(),
      "understanding",
      "interrupted",
    );
    path = advanceAnswerPath(path, "searching", "interrupted");
    path = advanceAnswerPath(path, "searching", "interrupted");
    expect(path.visited).toEqual(["understanding", "searching"]);

    path = advanceAnswerPath(path, "understanding", "waiting");
    expect(path).toEqual({
      activeStep: "understanding",
      visited: ["understanding"],
    });

    expect(advanceAnswerPath(path, null, "waiting")).toEqual(emptyAnswerPath());
  });
});

