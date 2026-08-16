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
  if (reasonCode === "unknown_evidence") {
    return "The presentation support changed before the answer was ready. Please ask the follow-up again.";
  }
  if (reasonCode === "invalid_tool_arguments") {
    return "I could not form a complete answer request. Please finish or rephrase the follow-up.";
  }
  if (reasonCode === "provider_error") {
    return "Answer preparation is temporarily unavailable. Please try the follow-up again.";
  }
  return "The assistant could not prepare a validated answer. You can ask the follow-up again.";
}

export function planningRecoveryMessage(reasonCode: string): string {
  if (reasonCode === "invalid_tool_arguments") {
    return "The answer plan was incomplete, so its citations and slide focus were discarded before a safe fallback answer.";
  }
  return "The presentation support could not be validated, so its citations and slide focus were discarded before a safe fallback answer.";
}
