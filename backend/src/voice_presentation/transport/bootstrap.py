from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProbeSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    room_name: str = Field(pattern=r"^probe-[a-z0-9][a-z0-9-]{0,47}$")
    participant_identity: str = Field(pattern=r"^browser-[a-z0-9][a-z0-9-]{0,47}$")

    @model_validator(mode="after")
    def names_match_attempt(self) -> "ProbeSessionRequest":
        prefix = str(self.attempt_id).split("-", maxsplit=1)[0]
        if self.room_name != f"probe-{prefix}":
            raise ValueError("room_name must match the attempt identifier")
        if self.participant_identity != f"browser-{prefix}":
            raise ValueError("participant_identity must match the attempt identifier")
        return self


class ProbeSessionResponse(BaseModel):
    attempt_id: UUID
    room_name: str
    participant_identity: str
    server_url: str
    participant_token: str


@dataclass(frozen=True, slots=True)
class ProbeSessionSpec:
    attempt_id: str
    room_name: str
    browser_identity: str
    worker_identity: str
    server_url: str
    worker_token: str


class JoinTokenIssuer(Protocol):
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


class ProbeSessionLauncher(Protocol):
    async def launch(self, session: ProbeSessionSpec) -> None: ...


class ProbeBootstrapService:
    def __init__(
        self,
        *,
        server_url: str,
        token_issuer: JoinTokenIssuer,
        session_launcher: ProbeSessionLauncher,
        token_ttl_seconds: int = 600,
    ) -> None:
        if not server_url.startswith(("ws://", "wss://")):
            raise ValueError("LiveKit server URL must use ws:// or wss://")
        if not 60 <= token_ttl_seconds <= 900:
            raise ValueError("probe token TTL must be between 60 and 900 seconds")
        self._server_url = server_url
        self._token_issuer = token_issuer
        self._session_launcher = session_launcher
        self._token_ttl_seconds = token_ttl_seconds

    async def create_session(self, request: ProbeSessionRequest) -> ProbeSessionResponse:
        suffix = request.room_name.removeprefix("probe-")
        worker_identity = f"probe-worker-{suffix}"
        common_claims = {
            "room_name": request.room_name,
            "can_publish": True,
            "can_subscribe": True,
            "can_publish_data": True,
            "can_publish_sources": ("microphone",),
            "ttl_seconds": self._token_ttl_seconds,
        }
        participant_token = self._token_issuer.issue_join_token(
            identity=request.participant_identity,
            **common_claims,
        )
        worker_token = self._token_issuer.issue_join_token(
            identity=worker_identity,
            **common_claims,
        )
        session = ProbeSessionSpec(
            attempt_id=str(request.attempt_id),
            room_name=request.room_name,
            browser_identity=request.participant_identity,
            worker_identity=worker_identity,
            server_url=self._server_url,
            worker_token=worker_token,
        )
        await self._session_launcher.launch(session)
        return ProbeSessionResponse(
            attempt_id=request.attempt_id,
            room_name=request.room_name,
            participant_identity=request.participant_identity,
            server_url=self._server_url,
            participant_token=participant_token,
        )

    async def aclose(self) -> None:
        close = getattr(self._session_launcher, "aclose", None)
        if close is not None:
            await close()
