from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from voice_presentation.domain.content import PresentationDeck, PresentationSlide
from voice_presentation.domain.reasoning import (
    MaterialHit,
    MaterialSection,
    SearchMaterialInput,
    SearchMaterialResult,
)


_WORD = re.compile(r"[a-z0-9]+")
_TERM_ALIASES = {
    "brakes": "brake",
    "braking": "brake",
    "gears": "gear",
    "matched": "match",
    "matches": "match",
    "matching": "match",
    "plates": "plate",
    "revs": "engine_speed",
    "rpm": "engine_speed",
    "rpms": "engine_speed",
    "tyres": "tyre",
    "wheels": "wheel",
}
_SECTION_ORDER = {
    MaterialSection.SUMMARY: 0,
    MaterialSection.NARRATION: 1,
    MaterialSection.DEEP_DIVE: 2,
}


@dataclass(frozen=True)
class _MaterialSegment:
    evidence_id: str
    slide_id: str
    slide_number: int
    section: MaterialSection
    segment_index: int
    text: str
    search_text: str


@dataclass(frozen=True)
class _ScoredSegment:
    segment: _MaterialSegment
    score: int
    matched_on: tuple[str, ...]


class MaterialSearch:
    """Bounded deterministic retrieval over one validated presentation deck."""

    def __init__(
        self,
        deck: PresentationDeck,
        *,
        max_serialized_bytes: int = 8192,
    ) -> None:
        if max_serialized_bytes < 256:
            raise ValueError("max_serialized_bytes must be at least 256")
        self._deck = deck
        self._max_serialized_bytes = max_serialized_bytes
        self._segments = self._build_segments(deck)
        self._segment_lookup = {
            (segment.slide_id, segment.section, segment.segment_index): segment
            for segment in self._segments
        }

    def search(
        self,
        request: SearchMaterialInput,
        *,
        preferred_slide_id: str | None = None,
    ) -> SearchMaterialResult:
        if preferred_slide_id is not None:
            self._deck.slide(preferred_slide_id)
        allowed_slide_ids = set(request.slide_ids)
        for slide_id in allowed_slide_ids:
            self._deck.slide(slide_id)

        normalized_keywords = tuple(
            normalized
            for keyword in request.keywords
            if (normalized := _normalize_phrase(keyword))
        )
        normalized_phrases = tuple(
            normalized
            for phrase in request.phrases
            if (normalized := _normalize_phrase(phrase))
        )
        query_tokens = {
            token
            for value in (*normalized_keywords, *normalized_phrases)
            for token in value.split()
        }

        scored: list[_ScoredSegment] = []
        for segment in self._segments:
            if allowed_slide_ids and segment.slide_id not in allowed_slide_ids:
                continue
            matched_phrases = tuple(
                phrase
                for phrase in normalized_phrases
                if _contains_phrase(segment.search_text, phrase)
            )
            matched_keywords = tuple(
                keyword
                for keyword in normalized_keywords
                if _contains_phrase(segment.search_text, keyword)
            )
            segment_tokens = set(segment.search_text.split())
            token_overlap = tuple(sorted(query_tokens & segment_tokens))
            if not matched_phrases and not matched_keywords and not token_overlap:
                continue

            matched_on = tuple(
                dict.fromkeys((*matched_phrases, *matched_keywords, *token_overlap))
            )
            score = (
                100 * len(matched_phrases)
                + 20 * len(matched_keywords)
                + 3 * len(token_overlap)
                + (1 if segment.slide_id == preferred_slide_id else 0)
            )
            scored.append(
                _ScoredSegment(
                    segment=segment,
                    score=score,
                    matched_on=matched_on,
                )
            )

        scored.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.segment.slide_number,
                _SECTION_ORDER[candidate.segment.section],
                candidate.segment.segment_index,
            )
        )
        query_id = self._query_id(
            request,
            normalized_keywords=normalized_keywords,
            normalized_phrases=normalized_phrases,
            preferred_slide_id=preferred_slide_id,
        )

        selected: list[MaterialHit] = []
        truncated = False
        for candidate in scored[: request.max_results]:
            hit = self._hit(candidate, include_neighbors=request.include_neighbors)
            trial = SearchMaterialResult(
                query_id=query_id,
                hits=(*selected, hit),
                truncated=False,
            )
            if len(trial.to_json().encode("utf-8")) > self._max_serialized_bytes:
                truncated = True
                break
            selected.append(hit)

        return SearchMaterialResult(
            query_id=query_id,
            hits=tuple(selected),
            truncated=truncated,
        )

    def _hit(
        self,
        candidate: _ScoredSegment,
        *,
        include_neighbors: bool,
    ) -> MaterialHit:
        segment = candidate.segment
        previous: str | None = None
        next_text: str | None = None
        if include_neighbors:
            previous_segment = self._segment_lookup.get(
                (segment.slide_id, segment.section, segment.segment_index - 1)
            )
            next_segment = self._segment_lookup.get(
                (segment.slide_id, segment.section, segment.segment_index + 1)
            )
            previous = previous_segment.text if previous_segment is not None else None
            next_text = next_segment.text if next_segment is not None else None
        return MaterialHit(
            evidence_id=segment.evidence_id,
            slide_id=segment.slide_id,
            slide_number=segment.slide_number,
            section=segment.section,
            segment_index=segment.segment_index,
            text=segment.text,
            previous=previous,
            next=next_text,
            matched_on=candidate.matched_on,
        )

    def _query_id(
        self,
        request: SearchMaterialInput,
        *,
        normalized_keywords: tuple[str, ...],
        normalized_phrases: tuple[str, ...],
        preferred_slide_id: str | None,
    ) -> str:
        payload = {
            "deck_id": self._deck.id,
            "include_neighbors": request.include_neighbors,
            "keywords": normalized_keywords,
            "max_results": request.max_results,
            "phrases": normalized_phrases,
            "preferred_slide_id": preferred_slide_id,
            "slide_ids": request.slide_ids,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(encoded).hexdigest()[:16]
        return f"material-query-{digest}"

    @staticmethod
    def _build_segments(deck: PresentationDeck) -> tuple[_MaterialSegment, ...]:
        segments: list[_MaterialSegment] = []
        for slide_number, slide in enumerate(deck.slides, start=1):
            metadata = _slide_metadata(slide)
            summary = " ".join((slide.title, slide.objective, slide.headline))
            segments.append(
                _segment(
                    deck_id=deck.id,
                    slide_id=slide.id,
                    slide_number=slide_number,
                    section=MaterialSection.SUMMARY,
                    segment_index=0,
                    text=summary,
                    metadata=metadata,
                )
            )
            for segment_index, beat in enumerate(slide.beats):
                text = " ".join(
                    (
                        beat.summary,
                        beat.narration_guidance,
                        "Key concepts: " + ", ".join(beat.required_concepts) + ".",
                    )
                )
                segments.append(
                    _segment(
                        deck_id=deck.id,
                        slide_id=slide.id,
                        slide_number=slide_number,
                        section=MaterialSection.NARRATION,
                        segment_index=segment_index,
                        text=text,
                        metadata=metadata,
                    )
                )
            for segment_index, deep_dive in enumerate(slide.deep_dive):
                caveats = (
                    " Caveats: " + " ".join(deep_dive.caveats)
                    if deep_dive.caveats
                    else ""
                )
                text = f"{deep_dive.concept}. {deep_dive.explanation}{caveats}"
                segments.append(
                    _segment(
                        deck_id=deck.id,
                        slide_id=slide.id,
                        slide_number=slide_number,
                        section=MaterialSection.DEEP_DIVE,
                        segment_index=segment_index,
                        text=text,
                        metadata=metadata,
                    )
                )
        return tuple(segments)


def _segment(
    *,
    deck_id: str,
    slide_id: str,
    slide_number: int,
    section: MaterialSection,
    segment_index: int,
    text: str,
    metadata: str,
) -> _MaterialSegment:
    return _MaterialSegment(
        evidence_id=f"{deck_id}.{slide_id}.{section.value}.{segment_index}",
        slide_id=slide_id,
        slide_number=slide_number,
        section=section,
        segment_index=segment_index,
        text=text,
        search_text=_normalize_phrase(f"{text} {metadata}"),
    )


def _slide_metadata(slide: PresentationSlide) -> str:
    return " ".join(
        (
            slide.title,
            slide.headline,
            *slide.labels,
            *slide.related_terms,
        )
    )


def _normalize_phrase(text: str) -> str:
    return " ".join(
        _TERM_ALIASES.get(word, word) for word in _WORD.findall(text.lower())
    )


def _contains_phrase(search_text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {search_text} "
