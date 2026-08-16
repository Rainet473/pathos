from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.offline


def test_root_frontend_mounts_only_the_live_experience():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    live_source = Path("frontend/src/live/LiveConversationApp.tsx").read_text(
        encoding="utf-8"
    )

    assert "LiveConversationApp" in app_source
    assert "FakePresentationApp" not in app_source
    assert "ProbeApp" not in app_source
    assert "Open deterministic presentation" not in live_source
