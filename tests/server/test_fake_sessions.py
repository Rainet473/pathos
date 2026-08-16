from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voice_presentation.server.app import (
    _selected_voice_session_factory,
    create_configured_app,
    create_offline_app,
)
from voice_presentation.voice.sessions import VoiceBackendKind, VoiceProvider


pytestmark = pytest.mark.offline


def create_session(client: TestClient) -> dict[str, object]:
    response = client.post("/api/fake/sessions")
    assert response.status_code == 201
    return response.json()


def act(
    client: TestClient,
    session_id: str,
    action: dict[str, object],
):
    return client.post(f"/api/fake/sessions/{session_id}/actions", json=action)


def test_offline_session_api_is_quiet_until_start_and_needs_no_credentials(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)

    with TestClient(create_offline_app()) as client:
        body = create_session(client)

    assert body["state"]["phase"] == "ready"
    assert body["state"]["activeTurnId"] is None
    assert body["transcript"] == []
    assert body["slides"][0]["id"] == "engine-braking"


def test_configured_app_does_not_expose_offline_session_harness(
    monkeypatch, tmp_path
):
    usage_log = tmp_path / "livekit-usage.jsonl"
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(usage_log))

    with TestClient(create_configured_app()) as client:
        response = client.post("/api/fake/sessions")

    assert response.status_code == 404
    assert not usage_log.exists()


def test_configured_app_reports_missing_selected_provider_key_without_fallback(
    monkeypatch, tmp_path
):
    usage_log = tmp_path / "livekit-usage.jsonl"
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(usage_log))
    monkeypatch.setenv("VOICE_PROVIDER", "gemini_live")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used-as-fallback")

    with TestClient(create_configured_app()) as client:
        response = client.post(
            "/api/live/sessions",
            json={
                "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
                "room_name": "conversation-9ea3a1cb",
                "participant_identity": "browser-9ea3a1cb",
            },
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "live voice provider is unavailable"}
    assert "openai" not in response.text.lower()
    assert not usage_log.exists()


def test_configured_app_registers_gemini_live_without_connecting_on_startup(
    monkeypatch, tmp_path
):
    usage_log = tmp_path / "livekit-usage.jsonl"
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(usage_log))
    monkeypatch.setenv("VOICE_PROVIDER", "gemini_live")
    monkeypatch.setenv("GOOGLE_API_KEY", "configured-google-key")

    with TestClient(create_configured_app()) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/live/sessions" in schema["paths"]
    assert not usage_log.exists()


def test_openai_selection_requires_its_key_and_never_falls_back_to_google(
    monkeypatch, tmp_path
):
    usage_log = tmp_path / "livekit-usage.jsonl"
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("LIVEKIT_USAGE_LOG", str(usage_log))
    monkeypatch.setenv("VOICE_PROVIDER", "openai_realtime")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "must-not-be-used-as-fallback")

    with TestClient(create_configured_app()) as client:
        response = client.post(
            "/api/live/sessions",
            json={
                "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
                "room_name": "conversation-9ea3a1cb",
                "participant_identity": "browser-9ea3a1cb",
            },
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "live voice provider is unavailable"}
    assert "google" not in response.text.lower()
    assert not usage_log.exists()


def test_provider_selector_builds_explicit_openai_and_livekit_pipeline_factories():
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


def test_api_runs_plain_question_and_direct_resume_paths_from_fresh_sessions():
    with TestClient(create_offline_app()) as client:
        plain = create_session(client)
        plain_id = plain["sessionId"]
        started = act(client, plain_id, {"type": "start"}).json()
        saved_cursor = started["state"]["presentationCursor"]
        answer = act(
            client,
            plain_id,
            {
                "type": "interrupt_and_ask",
                "question": "Why does engine braking feel stronger in a low gear?",
                "continuationPreference": "ask_before_continuing",
            },
        ).json()
        assert answer["state"]["phase"] == "answering"
        waiting = act(client, plain_id, {"type": "complete_playout"}).json()
        assert waiting["state"]["phase"] == "waiting"
        assert waiting["state"]["presentationCursor"] == saved_cursor

        direct = create_session(client)
        direct_id = direct["sessionId"]
        started = act(client, direct_id, {"type": "start"}).json()
        saved_cursor = started["state"]["presentationCursor"]
        narration_turn = started["state"]["activeTurnId"]
        act(
            client,
            direct_id,
            {
                "type": "interrupt_and_ask",
                "question": "Why does engine braking feel stronger in a low gear? Continue after answering.",
                "continuationPreference": "continue_after_answer",
            },
        )
        resumed = act(client, direct_id, {"type": "complete_playout"}).json()

    assert resumed["state"]["phase"] == "presenting"
    assert resumed["state"]["presentationCursor"] == saved_cursor
    assert resumed["state"]["activeTurnId"] != narration_turn
    assert resumed["state"]["activePlayout"]["cursor"] == saved_cursor


def test_illegal_action_is_a_visible_conflict_and_unknown_session_is_not_found():
    with TestClient(create_offline_app()) as client:
        session = create_session(client)
        illegal = act(client, session["sessionId"], {"type": "complete_playout"})
        missing = act(client, "missing-session", {"type": "start"})

    assert illegal.status_code == 409
    assert illegal.json()["detail"]
    assert missing.status_code == 404
