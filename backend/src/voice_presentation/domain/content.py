from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator


NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class VisualAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlankString
    kind: Literal["original_svg", "generated", "external_download"]
    src: NonBlankString
    alt: NonBlankString
    source_url: HttpUrl | None = None
    author: NonBlankString | None = None
    license: NonBlankString | None = None
    changes: NonBlankString | None = None
    retrieved_on: date | None = None


class NarrationBeat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlankString
    summary: NonBlankString
    narration_guidance: NonBlankString
    required_concepts: tuple[NonBlankString, ...] = Field(min_length=1)


class DeepDive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concept: NonBlankString
    explanation: NonBlankString
    caveats: tuple[NonBlankString, ...] = ()


class PresentationSlide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlankString
    title: NonBlankString
    objective: NonBlankString
    headline: NonBlankString
    labels: tuple[NonBlankString, ...] = Field(min_length=1)
    visual_description: NonBlankString
    assets: tuple[VisualAsset, ...] = ()
    beats: tuple[NarrationBeat, ...] = Field(min_length=1)
    deep_dive: tuple[DeepDive, ...] = Field(min_length=1)
    related_terms: tuple[NonBlankString, ...] = ()

    @model_validator(mode="after")
    def beat_ids_are_unique(self) -> "PresentationSlide":
        beat_ids = [beat.id for beat in self.beats]
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError(f"duplicate beat id on slide {self.id}")
        return self


class PresentationDeck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlankString
    title: NonBlankString
    slides: tuple[PresentationSlide, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def semantic_ids_are_unique(self) -> "PresentationDeck":
        slide_ids = [slide.id for slide in self.slides]
        if len(set(slide_ids)) != len(slide_ids):
            raise ValueError("duplicate slide id")
        beat_ids = [beat.id for slide in self.slides for beat in slide.beats]
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError("duplicate beat id")
        return self

    def slide(self, slide_id: str) -> PresentationSlide:
        for slide in self.slides:
            if slide.id == slide_id:
                return slide
        raise ValueError(f"unknown slide id: {slide_id}")
