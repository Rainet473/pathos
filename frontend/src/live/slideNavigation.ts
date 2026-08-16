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
