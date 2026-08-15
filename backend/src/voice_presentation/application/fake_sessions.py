from __future__ import annotations

import asyncio
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from voice_presentation.application.fake_session import (
    FakePresentationSession,
    FakeSessionView,
)
from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.contracts import ContinuationPreference


class FakeSessionNotFound(LookupError):
    """Raised when an offline action names a session that does not exist."""


class FakeActionType(StrEnum):
    START = "start"
    INTERRUPT_AND_ASK = "interrupt_and_ask"
    COMPLETE_PLAYOUT = "complete_playout"
    CONTINUE = "continue"


class FakeActionRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    type: FakeActionType
    question: str | None = None
    continuation_preference: ContinuationPreference | None = None

    @model_validator(mode="after")
    def question_fields_match_action(self) -> "FakeActionRequest":
        if self.type is FakeActionType.INTERRUPT_AND_ASK:
            if self.question is None or not self.question.strip():
                raise ValueError("interrupt_and_ask requires a non-blank question")
            if self.continuation_preference is None:
                raise ValueError("interrupt_and_ask requires continuationPreference")
        elif self.question is not None or self.continuation_preference is not None:
            raise ValueError("question fields are only valid for interrupt_and_ask")
        return self


class FakeSessionStore:
    def __init__(self, deck: PresentationDeck) -> None:
        self._deck = deck
        self._sessions: dict[str, FakePresentationSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> FakeSessionView:
        async with self._lock:
            session_id = str(uuid4())
            session = FakePresentationSession(self._deck, session_id=session_id)
            self._sessions[session_id] = session
            return session.view()

    async def act(
        self, session_id: str, action: FakeActionRequest
    ) -> FakeSessionView:
        async with self._lock:
            try:
                session = self._sessions[session_id]
            except KeyError as error:
                raise FakeSessionNotFound(session_id) from error

            if action.type is FakeActionType.START:
                return session.start()
            if action.type is FakeActionType.COMPLETE_PLAYOUT:
                return session.complete_active_playout()
            if action.type is FakeActionType.CONTINUE:
                return session.continue_presentation()
            assert action.question is not None
            assert action.continuation_preference is not None
            return session.interrupt_and_answer(
                question=action.question,
                continuation_preference=action.continuation_preference,
            )
