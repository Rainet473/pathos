from __future__ import annotations

import json
from pathlib import Path

from voice_presentation.domain.content import PresentationDeck


class JsonMaterialRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> PresentationDeck:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return PresentationDeck.model_validate(payload)
