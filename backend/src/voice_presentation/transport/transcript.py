from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


CONVERSATION_TRANSCRIPT_TOPIC = "voice-conversation.transcript.v1"


class ConversationTranscriptEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    role: Literal["user", "agent"]
    text: str = Field(min_length=1)
    final: bool

    @field_validator("id", "text")
    @classmethod
    def strip_non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("transcript fields cannot be blank")
        return value


class ConversationTranscriptUpdate(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    version: Literal[1] = 1
    attempt_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    emitted_at: datetime
    entry: ConversationTranscriptEntry

    @field_validator("attempt_id")
    @classmethod
    def strip_non_blank_attempt_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("attempt_id cannot be blank")
        return value

    @classmethod
    def from_entry(
        cls,
        *,
        attempt_id: str,
        sequence: int,
        entry: ConversationTranscriptEntry,
    ) -> "ConversationTranscriptUpdate":
        return cls(
            attempt_id=attempt_id,
            sequence=sequence,
            emitted_at=datetime.now(UTC),
            entry=entry,
        )

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)
