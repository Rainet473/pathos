from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


BACKEND = VoiceBackendIdentity(
    provider=VoiceProvider.GEMINI_LIVE,
    kind=VoiceBackendKind.REALTIME,
    model="gemini-2.5-flash-native-audio-preview-12-2025",
)


@dataclass
class FakeTokenIssuer:
    calls: list[dict[str, object]] = field(default_factory=list)

    def issue_join_token(self, **claims: object) -> str:
        self.calls.append(claims)
        return f"signed-{claims['identity']}"


@dataclass
class FakeConversationLauncher:
    identity: VoiceBackendIdentity = BACKEND
    calls: list[object] = field(default_factory=list)
    failure: Exception | None = None
    closed: bool = False

    async def launch(self, session: object) -> None:
        if self.failure is not None:
            raise self.failure
        self.calls.append(session)

    async def aclose(self) -> None:
        self.closed = True


def _client(*, launcher: FakeConversationLauncher | None = None):
    from voice_presentation.server.app import create_app
    from voice_presentation.transport.conversation import ConversationBootstrapService

    issuer = FakeTokenIssuer()
    session_launcher = launcher or FakeConversationLauncher()
    service = ConversationBootstrapService(
        server_url="wss://example.livekit.cloud",
        token_issuer=issuer,
        session_launcher=session_launcher,
        instructions="Be concise. Do not use tools.",
    )
    app = create_app(conversation_service=service)
    return TestClient(app), issuer, session_launcher


def _valid_payload() -> dict[str, str]:
    return {
        "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        "room_name": "conversation-9ea3a1cb",
        "participant_identity": "browser-9ea3a1cb",
    }


@pytest.mark.offline
def test_live_bootstrap_launches_selected_backend_and_returns_browser_credentials():
    client, issuer, launcher = _client()

    response = client.post("/api/live/sessions", json=_valid_payload())

    assert response.status_code == 201
    assert response.json() == {
        **_valid_payload(),
        "server_url": "wss://example.livekit.cloud",
        "participant_token": "signed-browser-9ea3a1cb",
        "backend": BACKEND.model_dump(mode="json"),
        "idle_timeout_seconds": 120,
        "absolute_timeout_seconds": 900,
    }
    assert len(launcher.calls) == 1
    launched = launcher.calls[0]
    assert launched.instructions == "Be concise. Do not use tools."
    assert launched.backend == BACKEND
    assert launched.idle_timeout_seconds == 120
    assert launched.absolute_timeout_seconds == 900
    assert [call["identity"] for call in issuer.calls] == [
        "browser-9ea3a1cb",
        "voice-worker-9ea3a1cb",
    ]
    assert all(call["can_publish_sources"] == ("microphone",) for call in issuer.calls)
    assert all(call["ttl_seconds"] == 900 for call in issuer.calls)
    assert "google" not in response.text.lower() or "google_api_key" not in response.text.lower()
    assert "api_key" not in response.text.lower()
    assert "api_secret" not in response.text.lower()


@pytest.mark.offline
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("attempt_id", "not-a-uuid"),
        ("room_name", "probe-9ea3a1cb"),
        ("room_name", "conversation-different"),
        ("participant_identity", "voice-worker-9ea3a1cb"),
        ("participant_identity", "browser-different"),
    ],
)
def test_live_bootstrap_rejects_invalid_or_overprivileged_names(field, value):
    client, issuer, launcher = _client()
    payload = _valid_payload()
    payload[field] = value

    response = client.post("/api/live/sessions", json=payload)

    assert response.status_code == 422
    assert issuer.calls == []
    assert launcher.calls == []


@pytest.mark.offline
def test_live_bootstrap_surfaces_provider_failure_without_leaking_details():
    launcher = FakeConversationLauncher(
        failure=RuntimeError("private-google-key provider detail")
    )
    client, _, _ = _client(launcher=launcher)

    response = client.post("/api/live/sessions", json=_valid_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "live voice provider is unavailable"}
    assert "private-google-key" not in response.text


@pytest.mark.offline
def test_server_shutdown_closes_active_live_sessions():
    client, _, launcher = _client()

    with client:
        assert client.get("/api/health").status_code == 200

    assert launcher.closed is True


@pytest.mark.offline
def test_mvp_defaults_to_the_verified_livekit_inference_pipeline(monkeypatch):
    from voice_presentation.server.app import _selected_voice_provider_name

    monkeypatch.delenv("VOICE_PROVIDER", raising=False)

    assert _selected_voice_provider_name() == "livekit_inference_pipeline"
