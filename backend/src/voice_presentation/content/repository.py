from __future__ import annotations

import json
from pathlib import Path
import re

from voice_presentation.domain.content import PresentationDeck


class JsonMaterialRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> PresentationDeck:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return PresentationDeck.model_validate(payload)


_DECK_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class DeckPackageRepository:
    """Loads the normalized runtime manifest from one portable deck package."""

    def __init__(self, asset_root: str | Path, deck_id: str) -> None:
        normalized = deck_id.strip()
        if not _DECK_ID.fullmatch(normalized):
            raise ValueError("deck_id must contain lowercase letters, digits, or hyphens")
        self._package_path = Path(asset_root) / normalized

    def load(self) -> PresentationDeck:
        return JsonMaterialRepository(
            self._package_path / "slide-breakdown.json"
        ).load()

    def render_path(self, slide_id: str) -> Path:
        slide = self.load().slide(slide_id)
        if not _DECK_ID.fullmatch(slide.id):
            raise ValueError(f"slide id cannot resolve an asset path: {slide.id}")
        path = self._package_path / "renders" / f"{slide.id}.png"
        if not path.is_file():
            raise FileNotFoundError(f"slide render is missing: {slide.id}")
        return path
