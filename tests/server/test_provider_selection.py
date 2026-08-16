from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voice_presentation.server.app import (
    _selected_follow_up_planner_factory,
    _selected_voice_session_factory,
    create_configured_app,
)
from voice_presentation.voice.sessions import VoiceBackendKind, VoiceProvider


pytestmark = pytest.mark.offline


def _configure_livekit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(tmp_path / "usage.jsonl"))
    monkeypatch.setenv(
        "LIVE_DIAGNOSTICS_LOG", str(tmp_path / "diagnostics.jsonl")
    )
    monkeypatch.setenv("LLM_CONTEXT_LOG", str(tmp_path / "context.jsonl"))


def _valid_live_request() -> dict[str, str]:
    return {
        "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        "room_name": "conversation-9ea3a1cb",
        "participant_identity": "browser-9ea3a1cb",
    }


def test_missing_gemini_key_does_not_fall_back_to_openai(
    monkeypatch, tmp_path
):
    _configure_livekit(monkeypatch, tmp_path)
    monkeypatch.setenv("VOICE_PROVIDER", "gemini_live")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used-as-fallback")

    with TestClient(create_configured_app()) as client:
        response = client.post("/api/live/sessions", json=_valid_live_request())

    assert response.status_code == 503
    assert response.json() == {"detail": "live voice provider is unavailable"}
    assert "openai" not in response.text.lower()
    assert not (tmp_path / "usage.jsonl").exists()


def test_configured_app_registers_gemini_without_connecting_on_startup(
    monkeypatch, tmp_path
):
    _configure_livekit(monkeypatch, tmp_path)
    monkeypatch.setenv("VOICE_PROVIDER", "gemini_live")
    monkeypatch.setenv("GOOGLE_API_KEY", "configured-google-key")

    with TestClient(create_configured_app()) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/live/sessions" in schema["paths"]
    assert not (tmp_path / "usage.jsonl").exists()


def test_missing_openai_key_does_not_fall_back_to_google(
    monkeypatch, tmp_path
):
    _configure_livekit(monkeypatch, tmp_path)
    monkeypatch.setenv("VOICE_PROVIDER", "openai_realtime")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "must-not-be-used-as-fallback")

    with TestClient(create_configured_app()) as client:
        response = client.post("/api/live/sessions", json=_valid_live_request())

    assert response.status_code == 503
    assert response.json() == {"detail": "live voice provider is unavailable"}
    assert "google" not in response.text.lower()
    assert not (tmp_path / "usage.jsonl").exists()


def test_provider_selector_builds_explicit_openai_and_pipeline_factories():
    openai = _selected_voice_session_factory(
        selected_provider="openai_realtime",
        google_api_key="must-not-be-used",
        openai_api_key="configured-openai-key",
        livekit_api_key="configured-livekit-key",
        livekit_api_secret="configured-livekit-secret",
    )
    pipeline = _selected_voice_session_factory(
        selected_provider="livekit_inference_pipeline",
        google_api_key="",
        openai_api_key="",
        livekit_api_key="configured-livekit-key",
        livekit_api_secret="configured-livekit-secret",
    )

    assert openai.identity.provider is VoiceProvider.OPENAI_REALTIME
    assert openai.identity.kind is VoiceBackendKind.REALTIME
    assert openai.identity.model == "gpt-realtime-2.1-mini"
    assert pipeline.identity.provider is VoiceProvider.LIVEKIT_INFERENCE_PIPELINE
    assert pipeline.identity.kind is VoiceBackendKind.PIPELINE
    assert pipeline.identity.model == (
        "deepgram/nova-3 + google/gemma-4-31b-it + inworld/inworld-tts-2"
    )


def test_provider_selector_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="not implemented"):
        _selected_voice_session_factory(
            selected_provider="automatic",
            google_api_key="configured-google-key",
            openai_api_key="configured-openai-key",
            livekit_api_key="configured-livekit-key",
            livekit_api_secret="configured-livekit-secret",
        )


def test_silent_follow_up_planner_is_enabled_only_for_selected_pipeline():
    ledger = object()

    pipeline = _selected_follow_up_planner_factory(
        selected_provider="livekit_inference_pipeline",
        livekit_api_key="configured-livekit-key",
        livekit_api_secret="configured-livekit-secret",
        ledger=ledger,
    )
    realtime = _selected_follow_up_planner_factory(
        selected_provider="openai_realtime",
        livekit_api_key="configured-livekit-key",
        livekit_api_secret="configured-livekit-secret",
        ledger=ledger,
    )

    assert callable(pipeline)
    assert realtime is None
