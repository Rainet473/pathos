from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voice_presentation.server.app import create_configured_app


pytestmark = pytest.mark.offline


def test_configured_app_exposes_only_release_session_surface(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(tmp_path / "usage.jsonl"))
    monkeypatch.setenv("LIVE_DIAGNOSTICS_LOG", str(tmp_path / "diagnostics.jsonl"))
    monkeypatch.setenv("LLM_CONTEXT_LOG", str(tmp_path / "context.jsonl"))

    with TestClient(create_configured_app()) as client:
        paths = set(client.get("/openapi.json").json()["paths"])

    assert "/api/live/sessions" in paths
    assert "/api/health" in paths
    assert "/api/decks/{deck_id}/slides/{slide_id}/render" in paths
    assert "/api/fake/sessions" not in paths
    assert "/api/probe/sessions" not in paths
