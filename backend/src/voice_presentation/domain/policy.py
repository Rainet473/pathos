from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.contracts import ScopeMode


_WORD = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "does",
    "feel",
    "in",
    "is",
    "it",
    "of",
    "the",
    "this",
    "to",
    "what",
    "why",
}
_TERM_ALIASES = {
    "abruptly": "abrupt",
    "brakes": "brake",
    "braking": "brake",
    "decelerate": "deceleration",
    "decelerates": "deceleration",
    "decrease": "deceleration",
    "decreases": "deceleration",
    "decreasing": "deceleration",
    "gears": "gear",
    "matched": "match",
    "matches": "match",
    "matching": "match",
    "quickly": "abrupt",
    "rapid": "abrupt",
    "released": "release",
    "releasing": "release",
    "revs": "engine_speed",
    "rpm": "engine_speed",
    "rpms": "engine_speed",
    "slow": "deceleration",
    "slowing": "deceleration",
    "slows": "deceleration",
    "stronger": "strong",
    "tyres": "tyre",
    "wheels": "wheel",
}


class QuestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_mode: ScopeMode
    evidence: tuple[str, ...] = ()
    supporting_slide_id: str | None = None
    disclosure_required: bool = False
    clarification_prompt: str | None = None


class QuestionScopePolicy:
    def __init__(self, deck: PresentationDeck) -> None:
        self._deck = deck

    def classify(self, question: str) -> QuestionDecision:
        question = question.strip()
        if not question:
            raise ValueError("question cannot be blank")

        normalized = " ".join(_WORD.findall(question.lower()))
        ambiguous_phrases = (
            "why does it jerk",
            "should i use it every time",
            "does this work automatically",
        )
        if any(normalized.startswith(phrase) for phrase in ambiguous_phrases):
            return QuestionDecision(
                scope_mode=ScopeMode.NEEDS_CLARIFICATION,
                clarification_prompt="Which motorcycle control or situation do you mean?",
            )

        if self._is_unsafe_specific_or_unrelated(normalized):
            return QuestionDecision(scope_mode=ScopeMode.OUT_OF_SCOPE)

        for slide in self._deck.slides:
            if any(term.lower() in normalized for term in slide.related_terms):
                return QuestionDecision(
                    scope_mode=ScopeMode.EXTENDED_KNOWLEDGE,
                    supporting_slide_id=slide.id,
                    disclosure_required=True,
                )

        question_terms = self._terms(normalized)
        best_slide_id: str | None = None
        best_evidence: tuple[str, ...] = ()
        best_score = 0
        best_overlap = 0
        for slide in self._deck.slides:
            for deep_dive in slide.deep_dive:
                concept_terms = self._terms(deep_dive.concept)
                detail_terms = self._terms(
                    " ".join((deep_dive.explanation, *deep_dive.caveats))
                )
                score = 3 * len(question_terms & concept_terms) + len(
                    question_terms & detail_terms
                )
                overlap = len(question_terms & (concept_terms | detail_terms))
                if (score, overlap) > (best_score, best_overlap):
                    best_score = score
                    best_overlap = overlap
                    best_slide_id = slide.id
                    best_evidence = (deep_dive.explanation, *deep_dive.caveats)

        if best_score >= 3 and best_overlap >= 2:
            return QuestionDecision(
                scope_mode=ScopeMode.GROUNDED,
                evidence=best_evidence,
                supporting_slide_id=best_slide_id,
            )

        return QuestionDecision(scope_mode=ScopeMode.OUT_OF_SCOPE)

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {
            _TERM_ALIASES.get(word, word)
            for word in _WORD.findall(text.lower())
            if word not in _STOP_WORDS
        }

    @staticmethod
    def _is_unsafe_specific_or_unrelated(normalized: str) -> bool:
        blocked_phrases = (
            "exact torque",
            "axle nut",
            "disable abs",
            "public roads",
            "legal speed limit",
            "football match",
            "won last night",
        )
        return any(phrase in normalized for phrase in blocked_phrases)
