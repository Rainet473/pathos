from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIX_SLIDE_DECK = REPOSITORY_ROOT / "content" / "motorcycle-controls.json"

EXPECTED_SLIDES = [
    "control-loop",
    "clutch-and-gears",
    "power-to-wheel",
    "engine-braking",
    "rev-matching",
    "braking-abs",
]


def test_full_fixture_contains_six_ordered_slides_and_24_unique_beats():
    from voice_presentation.content.repository import JsonMaterialRepository

    deck = JsonMaterialRepository(SIX_SLIDE_DECK).load()

    assert [slide.id for slide in deck.slides] == EXPECTED_SLIDES
    assert [len(slide.beats) for slide in deck.slides] == [4] * 6
    beat_ids = [beat.id for slide in deck.slides for beat in slide.beats]
    assert len(beat_ids) == 24
    assert len(set(beat_ids)) == 24
    assert all(slide.deep_dive for slide in deck.slides)
    assert all(slide.related_terms for slide in deck.slides)
    assert all(slide.visual_description for slide in deck.slides)


def test_deck_rejects_a_beat_id_reused_on_another_slide(deck_payload):
    from voice_presentation.domain.content import PresentationDeck

    deck_payload["slides"][1]["beats"][0]["id"] = (
        deck_payload["slides"][0]["beats"][0]["id"]
    )

    with pytest.raises(ValueError, match="duplicate beat id"):
        PresentationDeck.model_validate(deck_payload)


def test_configured_live_session_uses_the_full_deck():
    from voice_presentation.server.app import _live_presentation_session

    session = _live_presentation_session("full-deck-session")

    assert [slide.id for slide in session.view().slides] == EXPECTED_SLIDES
