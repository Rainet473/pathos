export type PlanningStage = "understanding" | "searching" | "preparing";

export function planningStatusLabel(stage: PlanningStage): string {
  return {
    understanding: "Understanding your follow-up",
    searching: "Searching the presentation",
    preparing: "Preparing an answer",
  }[stage];
}

export function planningStatusDescription(stage: PlanningStage): string {
  return {
    understanding: "Your completed follow-up is being matched to the current conversation.",
    searching: "Relevant presentation material is being checked before an answer begins.",
    preparing: "The validated support is being prepared for the spoken answer.",
  }[stage];
}

export function planningFailureMessage(reasonCode: string): string {
  if (reasonCode === "timeout") {
    return "Answer preparation timed out. You can ask the follow-up again.";
  }
  return "The assistant could not prepare a validated answer. You can ask the follow-up again.";
}
