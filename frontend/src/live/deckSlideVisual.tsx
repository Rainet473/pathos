import { useState } from "react";

import type { SlideSummary } from "./presentationTypes";
import { SlideVisual } from "./slideVisuals";

export function deckSlideRenderUrl(deckId: string, slideId: string): string {
  return `/api/decks/${encodeURIComponent(deckId)}/slides/${encodeURIComponent(slideId)}/render`;
}

interface DeckSlideVisualProps {
  deckId: string;
  slide: SlideSummary;
}

export function DeckSlideVisual({ deckId, slide }: DeckSlideVisualProps) {
  const [renderFailed, setRenderFailed] = useState(false);

  if (renderFailed) {
    return (
      <div className="deck-slide-fallback">
        <h1>{slide.title}</h1>
        <p className="slide-headline">{slide.headline}</p>
        <SlideVisual slideId={slide.id} description={slide.visualDescription} />
        <ul className="slide-labels">
          {slide.labels.map((label) => <li key={label}>{label}</li>)}
        </ul>
      </div>
    );
  }

  return (
    <figure className="deck-slide-render">
      <img
        src={deckSlideRenderUrl(deckId, slide.id)}
        alt={`${slide.title}. ${slide.visualDescription}`}
        onError={() => setRenderFailed(true)}
      />
    </figure>
  );
}
