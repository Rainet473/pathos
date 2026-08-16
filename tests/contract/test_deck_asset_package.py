from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from voice_presentation.content.repository import DeckPackageRepository
from voice_presentation.server.app import create_offline_app


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPOSITORY_ROOT / "assets"


def test_motorcycle_package_loads_the_normalized_six_slide_deck():
    deck = DeckPackageRepository(ASSET_ROOT, "motorcycle-controls").load()

    assert deck.id == "motorcycle-controls"
    assert len(deck.slides) == 6
    assert sum(len(slide.beats) for slide in deck.slides) == 24


def test_motorcycle_package_preserves_source_deck_and_exact_slide_renders():
    package = ASSET_ROOT / "motorcycle-controls"
    repository = DeckPackageRepository(ASSET_ROOT, "motorcycle-controls")
    deck = repository.load()

    with ZipFile(package / "deck.pptx") as source:
        for slide_number, slide in enumerate(deck.slides, start=1):
            embedded = source.read(f"ppt/media/image{slide_number}.png")
            assert repository.render_path(slide.id).read_bytes() == embedded


def test_unknown_slide_render_is_rejected_before_resolving_a_path():
    repository = DeckPackageRepository(ASSET_ROOT, "motorcycle-controls")

    with pytest.raises(ValueError, match="unknown slide id"):
        repository.render_path("../secret")


def test_offline_app_serves_a_packaged_slide_render():
    client = TestClient(create_offline_app())

    response = client.get(
        "/api/decks/motorcycle-controls/slides/control-loop/render"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    "deck_id",
    ["", "../motorcycle-controls", "motorcycle-controls/../secret", "/absolute"],
)
def test_package_repository_rejects_invalid_or_traversing_deck_ids(deck_id):
    with pytest.raises(ValueError, match="deck_id"):
        DeckPackageRepository(ASSET_ROOT, deck_id)
