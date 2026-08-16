from __future__ import annotations

import re
from collections.abc import Iterator

from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.reasoning import TerminologyHint


_AUTHORED_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")
_WORD_TOKEN = re.compile(r"\b[A-Za-z]{2,6}\b")
_SPACED_ACRONYM = re.compile(
    r"(?<![A-Za-z])([A-Za-z](?:[\s.-]+[A-Za-z]){1,5})(?![A-Za-z])"
)
_PHONETIC_LETTER_NEIGHBORS = frozenset(
    {
        frozenset(("B", "P")),
        frozenset(("D", "T")),
        frozenset(("F", "V")),
        frozenset(("G", "K")),
        frozenset(("M", "N")),
        frozenset(("S", "Z")),
    }
)


def resolve_terminology_hints(
    text: str,
    deck: PresentationDeck,
) -> tuple[TerminologyHint, ...]:
    """Return conservative deck-authored acronym candidates without rewriting text."""

    authored_terms = _authored_acronyms(deck)
    hints: list[TerminologyHint] = []
    occupied_spans: list[tuple[int, int]] = []

    for match in _SPACED_ACRONYM.finditer(text):
        observed = match.group(1)
        compact = re.sub(r"[\s.-]+", "", observed).upper()
        if compact not in authored_terms:
            continue
        occupied_spans.append(match.span(1))
        hints.append(
            TerminologyHint(
                observed_text=observed,
                authored_term=compact,
                match_kind="spaced",
            )
        )

    for match in _WORD_TOKEN.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end in occupied_spans):
            continue
        observed = match.group(0)
        normalized = observed.upper()
        if normalized in authored_terms:
            hints.append(
                TerminologyHint(
                    observed_text=observed,
                    authored_term=normalized,
                    match_kind="exact",
                )
            )
            continue
        candidates = tuple(
            term
            for term in authored_terms
            if _is_phonetic_neighbor(normalized, term)
        )
        if len(candidates) == 1:
            hints.append(
                TerminologyHint(
                    observed_text=observed,
                    authored_term=candidates[0],
                    match_kind="phonetic_neighbor",
                )
            )

    return tuple(hints[:4])


def _authored_acronyms(deck: PresentationDeck) -> tuple[str, ...]:
    terms = {
        match.group(0)
        for text in _iter_text(deck.model_dump(mode="json"))
        for match in _AUTHORED_ACRONYM.finditer(text)
    }
    return tuple(sorted(terms))


def _iter_text(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_text(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_text(child)


def _is_phonetic_neighbor(observed: str, authored: str) -> bool:
    if len(observed) != len(authored):
        return False
    differences = [
        (left, right)
        for left, right in zip(observed, authored, strict=True)
        if left != right
    ]
    return (
        len(differences) == 1
        and frozenset(differences[0]) in _PHONETIC_LETTER_NEIGHBORS
    )
