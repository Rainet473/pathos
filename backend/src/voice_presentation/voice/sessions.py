from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class VoiceProvider(StrEnum):
    GEMINI_LIVE = "gemini_live"
    OPENAI_REALTIME = "openai_realtime"
    LIVEKIT_INFERENCE_PIPELINE = "livekit_inference_pipeline"


class VoiceBackendKind(StrEnum):
    REALTIME = "realtime"
    PIPELINE = "pipeline"


class VoiceBackendIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: VoiceProvider
    kind: VoiceBackendKind
    model: str = Field(min_length=1)


class VoiceSessionFactory(Protocol):
    @property
    def identity(self) -> VoiceBackendIdentity: ...

    def build_session(self, *, instructions: str) -> object: ...
