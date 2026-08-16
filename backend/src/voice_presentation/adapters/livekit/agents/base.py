from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from voice_presentation.voice.sessions import VoiceBackendIdentity


KeywordConstructor = Callable[..., object]


def default_agent_session_constructor(**kwargs: Any) -> object:
    """Import LiveKit lazily so deterministic tests need no provider startup."""

    from livekit.agents import AgentSession

    return AgentSession(**kwargs)


def require_text(value: str, *, name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must be configured")
    return cleaned


class AgentSessionFactoryBase(ABC):
    """Shared contract for provider-specific LiveKit session factories.

    This base deliberately owns only behavior that is identical for every
    provider: identity, nonblank application instructions, and a credential-safe
    representation. Provider options and SDK construction remain local to each
    concrete adapter.
    """

    def __init__(self, *, identity: VoiceBackendIdentity, voice: str) -> None:
        self._identity = identity
        self._display_voice = voice

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._identity

    def build_session(self, *, instructions: str) -> object:
        cleaned = instructions.strip()
        if not cleaned:
            raise ValueError("instructions must not be blank")
        return self._build_session(instructions=cleaned)

    @abstractmethod
    def _build_session(self, *, instructions: str) -> object:
        """Construct one provider-backed session from validated instructions."""

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={self.identity.provider.value!r}, "
            f"model={self.identity.model!r}, voice={self._display_voice!r})"
        )
