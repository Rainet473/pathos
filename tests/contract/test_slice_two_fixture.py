from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SLICE_TWO_DECK = REPOSITORY_ROOT / "content" / "slice-two.json"


def test_slice_two_fixture_is_one_validated_slide_with_one_semantic_beat():
    from voice_presentation.content.repository import JsonMaterialRepository

    deck = JsonMaterialRepository(SLICE_TWO_DECK).load()

    assert deck.id == "motorcycle-controls-slice-two"
    assert len(deck.slides) == 1
    assert deck.slides[0].id == "engine-braking"
    assert [beat.id for beat in deck.slides[0].beats] == ["low-gear-effect"]
    assert deck.slides[0].deep_dive


def test_missing_slice_fixture_fails_at_the_repository_boundary(tmp_path):
    from voice_presentation.content.repository import JsonMaterialRepository

    with pytest.raises(FileNotFoundError):
        JsonMaterialRepository(tmp_path / "missing.json").load()
