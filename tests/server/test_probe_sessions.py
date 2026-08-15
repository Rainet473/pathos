from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient


@dataclass
class FakeTokenIssuer:
    calls: list[dict[str, object]] = field(default_factory=list)

    def issue_join_token(self, **claims: object) -> str:
        self.calls.append(claims)
        return "signed-participant-token"


@dataclass
class FakeSessionLauncher:
    calls: list[object] = field(default_factory=list)
    failure: Exception | None = None
    closed: bool = False

    async def launch(self, session: object) -> None:
        if self.failure is not None:
            raise self.failure
        self.calls.append(session)

    async def aclose(self) -> None:
        self.closed = True


def _client(*, launcher: FakeSessionLauncher | None = None):
    from voice_presentation.server.app import create_app
    from voice_presentation.transport.bootstrap import ProbeBootstrapService

    issuer = FakeTokenIssuer()
    session_launcher = launcher or FakeSessionLauncher()
    service = ProbeBootstrapService(
        server_url="wss://example.livekit.cloud",
        token_issuer=issuer,
        session_launcher=session_launcher,
    )
    return TestClient(create_app(service)), issuer, session_launcher


def _valid_payload():
    return {
        "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        "room_name": "probe-9ea3a1cb",
        "participant_identity": "browser-9ea3a1cb",
    }


@pytest.mark.offline
def test_probe_bootstrap_starts_worker_and_returns_only_browser_connection_data():
    client, issuer, launcher = _client()

    response = client.post("/api/probe/sessions", json=_valid_payload())

    assert response.status_code == 201
    assert response.json() == {
        **_valid_payload(),
        "server_url": "wss://example.livekit.cloud",
        "participant_token": "signed-participant-token",
    }
    assert len(launcher.calls) == 1
    assert len(issuer.calls) == 2
    assert issuer.calls[0]["identity"] == "browser-9ea3a1cb"
    assert issuer.calls[0]["can_publish_sources"] == ("microphone",)
    assert issuer.calls[1]["identity"] == "probe-worker-9ea3a1cb"

    serialized = response.text.lower()
    assert "api_secret" not in serialized
    assert "api_key" not in serialized


@pytest.mark.offline
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("attempt_id", "not-a-uuid"),
        ("room_name", "../../shared-room"),
        ("room_name", "presentation-room"),
        ("room_name", "probe-different"),
        ("participant_identity", ""),
        ("participant_identity", "worker-admin"),
        ("participant_identity", "browser-different"),
    ],
)
def test_probe_bootstrap_rejects_malformed_or_overprivileged_names(field, value):
    client, issuer, launcher = _client()
    payload = _valid_payload()
    payload[field] = value

    response = client.post("/api/probe/sessions", json=payload)

    assert response.status_code == 422
    assert issuer.calls == []
    assert launcher.calls == []


@pytest.mark.offline
def test_probe_bootstrap_reports_dependency_failure_without_leaking_details():
    launcher = FakeSessionLauncher(failure=RuntimeError("secret internal failure"))
    client, _, _ = _client(launcher=launcher)

    response = client.post("/api/probe/sessions", json=_valid_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "voice transport is unavailable"}
    assert "secret internal failure" not in response.text


@pytest.mark.offline
def test_server_shutdown_closes_active_probe_sessions():
    client, _, launcher = _client()

    with client:
        assert client.get("/api/health").status_code == 200

    assert launcher.closed is True
