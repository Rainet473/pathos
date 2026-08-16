import type { PlanningStage } from "./planningStatus";
import type { PresentationPhase } from "./presentationTypes";

export type AnswerPathStep = PlanningStage | "answering";
export type AnswerPathStatus = "complete" | "active" | "skipped" | "pending";

export interface AnswerPathState {
  activeStep: AnswerPathStep | null;
  visited: AnswerPathStep[];
}

export interface AnswerPathNode {
  step: AnswerPathStep;
  status: AnswerPathStatus;
}

const ANSWER_PATH_STEPS: AnswerPathStep[] = [
  "understanding",
  "searching",
  "preparing",
  "answering",
];

export function emptyAnswerPath(): AnswerPathState {
  return { activeStep: null, visited: [] };
}

export function advanceAnswerPath(
  current: AnswerPathState,
  planningStage: PlanningStage | null,
  phase: PresentationPhase,
): AnswerPathState {
  if (planningStage === "understanding") {
    return { activeStep: planningStage, visited: [planningStage] };
  }
  if (planningStage !== null) {
    return visit(current, planningStage);
  }
  if (phase === "answering") {
    return visit(current, "answering");
  }
  return emptyAnswerPath();
}

export function answerPathNodes(path: AnswerPathState): AnswerPathNode[] {
  const farthestVisited = Math.max(
    -1,
    ...path.visited.map((step) => ANSWER_PATH_STEPS.indexOf(step)),
  );
  return ANSWER_PATH_STEPS.map((step, index) => {
    if (step === path.activeStep) return { step, status: "active" };
    if (path.visited.includes(step)) return { step, status: "complete" };
    if (index < farthestVisited) return { step, status: "skipped" };
    return { step, status: "pending" };
  });
}

function visit(
  current: AnswerPathState,
  step: AnswerPathStep,
): AnswerPathState {
  return {
    activeStep: step,
    visited: current.visited.includes(step)
      ? current.visited
      : [...current.visited, step],
  };
}

