from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.domain.contracts import (
    ContinuationPreference,
    Cursor,
    PlayoutPurpose,
    ScopeMode,
)


class DomainEventType(StrEnum):
    PRESENTATION_STARTED = "presentation_started"
    BEAT_SELECTED = "beat_selected"
    PLAYOUT_STARTED = "playout_started"
    BEAT_COMMITTED = "beat_committed"
    SLIDE_CHANGED = "slide_changed"
    PLAYOUT_INTERRUPTED = "playout_interrupted"
    QUESTION_CLASSIFIED = "question_classified"
    ANSWER_COMPLETED = "answer_completed"
    PRESENTATION_WAITING = "presentation_waiting"
    PRESENTATION_RESUMED = "presentation_resumed"
    TRANSITION_REJECTED = "transition_rejected"
    STALE_RESPONSE_DISCARDED = "stale_response_discarded"
    PRESENTATION_COMPLETED = "presentation_completed"


class SlideChangeReason(StrEnum):
    PRESENTATION = "presentation"
    QUESTION = "question"
    RESTORE = "restore"
    USER = "user"


class DomainEvent(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: DomainEventType
    cursor: Cursor | None = None
    turn_id: str | None = Field(default=None, min_length=1)
    slide_id: str | None = Field(default=None, min_length=1)
    slide_change_reason: SlideChangeReason | None = None
    purpose: PlayoutPurpose | None = None
    scope_mode: ScopeMode | None = None
    continuation_preference: ContinuationPreference | None = None
    attempted_action: str | None = Field(default=None, min_length=1)
    allowed_actions: tuple[str, ...] = ()
