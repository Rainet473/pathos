from __future__ import annotations

import inspect
from pathlib import Path

import pytest


pytestmark = pytest.mark.offline


@pytest.mark.parametrize(
    "path",
    [
        "backend/src/voice_presentation/transport/bootstrap.py",
        "backend/src/voice_presentation/transport/contracts.py",
        "backend/src/voice_presentation/voice/fake.py",
        "backend/src/voice_presentation/application/fake_session.py",
        "backend/src/voice_presentation/application/fake_sessions.py",
        "backend/src/voice_presentation/adapters/livekit/probe.py",
        "frontend/src/probe",
        "frontend/src/presentation/FakePresentationApp.tsx",
        "frontend/src/presentation/api.ts",
        "content/slice-two.json",
    ],
)
def test_historical_product_module_is_absent(path):
    assert not Path(path).exists()


def test_shared_live_contracts_have_neutral_modules():
    from voice_presentation.application.views import SlideView
    from voice_presentation.transport.auth import JoinTokenIssuer

    assert SlideView.model_fields["visual_description"].is_required()
    assert inspect.isclass(JoinTokenIssuer)


def test_server_composition_accepts_only_the_live_service():
    from voice_presentation.server.app import create_app

    assert set(inspect.signature(create_app).parameters) == {"conversation_service"}
