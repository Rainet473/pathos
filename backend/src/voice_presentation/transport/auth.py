from __future__ import annotations

from typing import Protocol


class JoinTokenIssuer(Protocol):
    """Issue a least-privilege token for one LiveKit room participant."""

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
    ) -> str: ...
