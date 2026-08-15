from __future__ import annotations

from datetime import timedelta

from livekit import api


class LiveKitTokenIssuer:
    def __init__(self, *, api_key: str, api_secret: str) -> None:
        if not api_key.strip() or not api_secret.strip():
            raise ValueError("LiveKit credentials cannot be blank")
        self._api_key = api_key
        self._api_secret = api_secret

    def issue_join_token(
        self,
        *,
        room_name: str,
        identity: str,
        can_publish: bool,
        can_subscribe: bool,
        can_publish_data: bool,
        can_publish_sources: tuple[str, ...],
        ttl_seconds: int,
    ) -> str:
        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(identity)
            .with_name(identity)
            .with_ttl(timedelta(seconds=ttl_seconds))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=can_publish,
                    can_subscribe=can_subscribe,
                    can_publish_data=can_publish_data,
                    can_publish_sources=list(can_publish_sources),
                )
            )
        )
        return token.to_jwt()
