from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.domain.contracts import Cursor, PlayoutPurpose


class VoiceCapabilities(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    native_barge_in: bool
    semantic_turn_detection: bool
    streaming_tool_calls: bool
    audio_output: bool
    transcript_timing: bool
    reliable_playout_completion: bool


class PlayoutRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    turn_id: str = Field(min_length=1)
    cursor: Cursor
    purpose: PlayoutPurpose
    text: str = Field(min_length=1)


class VoiceEventType(StrEnum):
    PLAYOUT_STARTED = "playout_started"
    PLAYOUT_COMPLETED = "playout_completed"
    PLAYOUT_INTERRUPTED = "playout_interrupted"


class VoiceEvent(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: VoiceEventType
    request: PlayoutRequest
    sequence: int = Field(ge=1)


class VoiceRuntime(Protocol):
    @property
    def capabilities(self) -> VoiceCapabilities: ...

    @property
    def active_playout(self) -> PlayoutRequest | None: ...

    def start_playout(self, request: PlayoutRequest) -> VoiceEvent: ...

    def complete_playout(self, *, turn_id: str) -> VoiceEvent: ...

    def interrupt_playout(self, *, turn_id: str) -> VoiceEvent: ...
