from __future__ import annotations

from datetime import datetime, timezone

import jwt
import pytest


@pytest.mark.offline
def test_livekit_token_is_short_lived_and_room_scoped():
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer

    issuer = LiveKitTokenIssuer(
        api_key="dev-key",
        api_secret="development-secret-that-is-long-enough",
    )
    encoded = issuer.issue_join_token(
        room_name="probe-9ea3a1cb",
        identity="browser-9ea3a1cb",
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        can_publish_sources=("microphone",),
        ttl_seconds=600,
    )

    claims = jwt.decode(encoded, options={"verify_signature": False})
    assert claims["iss"] == "dev-key"
    assert claims["sub"] == "browser-9ea3a1cb"
    assert claims["video"] == {
        "roomJoin": True,
        "room": "probe-9ea3a1cb",
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": True,
        "canPublishSources": ["microphone"],
    }
    lifetime_seconds = claims["exp"] - int(datetime.now(timezone.utc).timestamp())
    assert 590 <= lifetime_seconds <= 600


@pytest.mark.offline
@pytest.mark.parametrize("api_key,api_secret", [("", "secret"), ("key", "")])
def test_livekit_token_issuer_rejects_missing_credentials(api_key, api_secret):
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer

    with pytest.raises(ValueError, match="credentials"):
        LiveKitTokenIssuer(api_key=api_key, api_secret=api_secret)
