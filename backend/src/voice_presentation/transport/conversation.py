from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from voice_presentation.transport.auth import JoinTokenIssuer
from voice_presentation.voice.sessions import VoiceBackendIdentity

DEFAULT_CONVERSATION_IDLE_TIMEOUT_SECONDS = 120
DEFAULT_CONVERSATION_ABSOLUTE_TIMEOUT_SECONDS = 900


class ConversationSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    room_name: str = Field(pattern=r"^conversation-[a-z0-9][a-z0-9-]{0,39}$")
    participant_identity: str = Field(pattern=r"^browser-[a-z0-9][a-z0-9-]{0,47}$")

    @model_validator(mode="after")
    def names_match_attempt(self) -> "ConversationSessionRequest":
        prefix = str(self.attempt_id).split("-", maxsplit=1)[0]
        if self.room_name != f"conversation-{prefix}":
            raise ValueError("room_name must match the attempt identifier")
        if self.participant_identity != f"browser-{prefix}":
            raise ValueError("participant_identity must match the attempt identifier")
        return self


class ConversationSessionResponse(BaseModel):
    attempt_id: UUID
    room_name: str
    participant_identity: str
    server_url: str
    participant_token: str
    backend: VoiceBackendIdentity
    idle_timeout_seconds: int
    absolute_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ConversationSessionSpec:
    attempt_id: str
    room_name: str
    browser_identity: str
    worker_identity: str
    server_url: str
    worker_token: str
    instructions: str
    backend: VoiceBackendIdentity
    idle_timeout_seconds: int = DEFAULT_CONVERSATION_IDLE_TIMEOUT_SECONDS
    absolute_timeout_seconds: int = DEFAULT_CONVERSATION_ABSOLUTE_TIMEOUT_SECONDS


class ConversationSessionLauncher(Protocol):
    @property
    def identity(self) -> VoiceBackendIdentity: ...

    async def launch(self, session: ConversationSessionSpec) -> None: ...


class ConversationService(Protocol):
    async def create_session(
        self, request: ConversationSessionRequest
    ) -> ConversationSessionResponse: ...

    async def aclose(self) -> None: ...


class ConversationProviderUnavailable(RuntimeError):
    """Raised when the explicitly selected provider cannot be constructed."""


class UnavailableConversationService:
    def __init__(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("unavailable-provider reason must not be blank")
        self._reason = reason

    async def create_session(
        self, request: ConversationSessionRequest
    ) -> ConversationSessionResponse:
        del request
        raise ConversationProviderUnavailable(self._reason)

    async def aclose(self) -> None:
        return None


class ConversationBootstrapService:
    def __init__(
        self,
        *,
        server_url: str,
        token_issuer: JoinTokenIssuer,
        session_launcher: ConversationSessionLauncher,
        instructions: str,
        token_ttl_seconds: int = DEFAULT_CONVERSATION_ABSOLUTE_TIMEOUT_SECONDS,
        idle_timeout_seconds: int = DEFAULT_CONVERSATION_IDLE_TIMEOUT_SECONDS,
        absolute_timeout_seconds: int = DEFAULT_CONVERSATION_ABSOLUTE_TIMEOUT_SECONDS,
    ) -> None:
        if not server_url.startswith(("ws://", "wss://")):
            raise ValueError("LiveKit server URL must use ws:// or wss://")
        if not instructions.strip():
            raise ValueError("instructions must not be blank")
        if not 60 <= token_ttl_seconds <= 900:
            raise ValueError("conversation token TTL must be between 60 and 900 seconds")
        if idle_timeout_seconds <= 0:
            raise ValueError("conversation idle timeout must be positive")
        if not 0 < absolute_timeout_seconds <= 900:
            raise ValueError(
                "conversation absolute timeout must be at most fifteen minutes"
            )
        if idle_timeout_seconds >= absolute_timeout_seconds:
            raise ValueError(
                "conversation idle timeout must be shorter than the absolute timeout"
            )
        if token_ttl_seconds < absolute_timeout_seconds:
            raise ValueError(
                "conversation token TTL must cover the absolute timeout"
            )
        self._server_url = server_url
        self._token_issuer = token_issuer
        self._session_launcher = session_launcher
        self._instructions = instructions
        self._token_ttl_seconds = token_ttl_seconds
        self._idle_timeout_seconds = idle_timeout_seconds
        self._absolute_timeout_seconds = absolute_timeout_seconds

    async def create_session(
        self, request: ConversationSessionRequest
    ) -> ConversationSessionResponse:
        suffix = request.room_name.removeprefix("conversation-")
        worker_identity = f"voice-worker-{suffix}"
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
        session = ConversationSessionSpec(
            attempt_id=str(request.attempt_id),
            room_name=request.room_name,
            browser_identity=request.participant_identity,
            worker_identity=worker_identity,
            server_url=self._server_url,
            worker_token=worker_token,
            instructions=self._instructions,
            backend=self._session_launcher.identity,
            idle_timeout_seconds=self._idle_timeout_seconds,
            absolute_timeout_seconds=self._absolute_timeout_seconds,
        )
        await self._session_launcher.launch(session)
        return ConversationSessionResponse(
            attempt_id=request.attempt_id,
            room_name=request.room_name,
            participant_identity=request.participant_identity,
            server_url=self._server_url,
            participant_token=participant_token,
            backend=self._session_launcher.identity,
            idle_timeout_seconds=self._idle_timeout_seconds,
            absolute_timeout_seconds=self._absolute_timeout_seconds,
        )

    async def aclose(self) -> None:
        close = getattr(self._session_launcher, "aclose", None)
        if close is not None:
            await close()
