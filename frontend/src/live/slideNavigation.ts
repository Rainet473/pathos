import type { PlanningStage } from "./planningStatus";
import type { PresentationPhase } from "./presentationTypes";

export function adjacentSlideId(
  slides: ReadonlyArray<{ id: string }>,
  visibleSlideId: string,
  direction: number,
): string | null {
  if (direction !== -1 && direction !== 1) return null;
  const index = slides.findIndex((slide) => slide.id === visibleSlideId);
  if (index < 0) return null;
  return slides[index + direction]?.id ?? null;
}

export function canNavigateSlides(
  sessionActive: boolean,
  presentationPhase: PresentationPhase,
  planningStage: PlanningStage | null,
  activePlayoutPurpose: "narration" | "answer" | null,
): boolean {
  if (!sessionActive || planningStage !== null) return false;
  if (presentationPhase !== "answering") return true;
  return activePlayoutPurpose === "answer";
}

export function navigationConsequence(
  presentationPhase: PresentationPhase,
): string | null {
  return presentationPhase === "answering"
    ? "Browsing now stops this answer and pauses the presentation."
    : null;
}
