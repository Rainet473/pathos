from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PresentationPhase(StrEnum):
    READY = "ready"
    PRESENTING = "presenting"
    INTERRUPTED = "interrupted"
    ANSWERING = "answering"
    WAITING = "waiting"
    COMPLETED = "completed"


class ContinuationPreference(StrEnum):
    ASK_BEFORE_CONTINUING = "ask_before_continuing"
    CONTINUE_AFTER_ANSWER = "continue_after_answer"
    STAY_PAUSED = "stay_paused"


class ScopeMode(StrEnum):
    GROUNDED = "grounded"
    EXTENDED_KNOWLEDGE = "extended_knowledge"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"


class PlayoutPurpose(StrEnum):
    NARRATION = "narration"
    ANSWER = "answer"


class Cursor(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    slide_id: str = Field(min_length=1)
    beat_index: int = Field(ge=0)


class ActivePlayout(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    turn_id: str = Field(min_length=1)
    cursor: Cursor
    purpose: PlayoutPurpose


class PresentationState(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    session_version: int = Field(ge=0)
    phase: PresentationPhase
    presentation_cursor: Cursor
    visible_slide_id: str = Field(min_length=1)
    active_turn_id: str | None = Field(default=None, min_length=1)
    active_playout: ActivePlayout | None = None
    interrupted_cursor: Cursor | None = None
    continuation_preference: ContinuationPreference | None = None
