from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.domain.content import NarrationBeat, PresentationDeck
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    Cursor,
    PlayoutPurpose,
    PresentationState,
    ScopeMode,
)
from voice_presentation.domain.controller import PresentationController
from voice_presentation.domain.events import DomainEvent, DomainEventType
from voice_presentation.domain.policy import QuestionDecision, QuestionScopePolicy
from voice_presentation.voice.fake import DeterministicFakeVoiceRuntime
from voice_presentation.voice.runtime import PlayoutRequest, VoiceEventType


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    role: Literal["user", "agent"]
    text: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)


class SlideView(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    id: str
    title: str
    headline: str
    labels: tuple[str, ...]


class FakeSessionView(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    session_id: str
    title: str
    state: PresentationState
    slides: tuple[SlideView, ...]
    transcript: tuple[TranscriptEntry, ...]
    events: tuple[DomainEvent, ...]
    scope_mode: ScopeMode | None = None
    committed_beats: tuple[Cursor, ...]


class FakePresentationSession:
    def __init__(self, deck: PresentationDeck, *, session_id: str) -> None:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id cannot be blank")
        self._session_id = session_id
        self._controller = PresentationController(deck)
        self._policy = QuestionScopePolicy(deck)
        self._runtime = DeterministicFakeVoiceRuntime()
        self._transcript: list[TranscriptEntry] = []
        self._events: tuple[DomainEvent, ...] = ()
        self._scope_mode: ScopeMode | None = None
        self._committed_beats: list[Cursor] = []
        self._turn_sequence = 0

    @property
    def runtime(self) -> DeterministicFakeVoiceRuntime:
        return self._runtime

    def view(self) -> FakeSessionView:
        deck = self._controller.deck
        return FakeSessionView(
            session_id=self._session_id,
            title=deck.title,
            state=self._controller.state.model_copy(deep=True),
            slides=tuple(
                SlideView(
                    id=slide.id,
                    title=slide.title,
                    headline=slide.headline,
                    labels=slide.labels,
                )
                for slide in deck.slides
            ),
            transcript=tuple(self._transcript),
            events=self._events,
            scope_mode=self._scope_mode,
            committed_beats=tuple(self._committed_beats),
        )

    def start(self) -> FakeSessionView:
        turn_id = self._next_turn_id("narration")
        events = list(self._controller.start_presentation(turn_id=turn_id))
        events.extend(self._start_narration_playout(turn_id))
        return self._finish_action(events)

    def interrupt_and_answer(
        self,
        *,
        question: str,
        continuation_preference: ContinuationPreference,
    ) -> FakeSessionView:
        active = self._runtime.active_playout
        if active is None:
            raise RuntimeError("there is no active playout to interrupt")

        voice_event = self._runtime.interrupt_playout(turn_id=active.turn_id)
        if voice_event.type is not VoiceEventType.PLAYOUT_INTERRUPTED:
            raise RuntimeError("fake runtime returned an invalid interruption event")
        events = list(self._controller.playout_interrupted(turn_id=active.turn_id))

        decision = self._policy.classify(question)
        effective_preference = continuation_preference
        if decision.scope_mode is ScopeMode.NEEDS_CLARIFICATION:
            effective_preference = ContinuationPreference.ASK_BEFORE_CONTINUING
        answer_turn_id = self._next_turn_id("answer")
        events.extend(
            self._controller.begin_answer(
                turn_id=answer_turn_id,
                continuation_preference=effective_preference,
                question_slide_id=decision.supporting_slide_id,
            )
        )
        events.append(
            DomainEvent(
                type=DomainEventType.QUESTION_CLASSIFIED,
                turn_id=answer_turn_id,
                scope_mode=decision.scope_mode,
            )
        )

        self._scope_mode = decision.scope_mode
        self._transcript.append(
            TranscriptEntry(role="user", text=question.strip(), turn_id=answer_turn_id)
        )
        answer = self._scripted_answer(decision)
        cursor = (
            self._controller.state.interrupted_cursor
            or self._controller.state.presentation_cursor
        )
        request = PlayoutRequest(
            turn_id=answer_turn_id,
            cursor=cursor,
            purpose=PlayoutPurpose.ANSWER,
            text=answer,
        )
        started = self._runtime.start_playout(request)
        events.extend(
            self._controller.playout_started(
                turn_id=started.request.turn_id,
                cursor=started.request.cursor,
                purpose=started.request.purpose,
            )
        )
        self._transcript.append(
            TranscriptEntry(role="agent", text=answer, turn_id=answer_turn_id)
        )
        return self._finish_action(events)

    def complete_active_playout(self) -> FakeSessionView:
        active = self._runtime.active_playout
        if active is None:
            raise RuntimeError("there is no active playout to complete")
        completed = self._runtime.complete_playout(turn_id=active.turn_id)
        if completed.type is not VoiceEventType.PLAYOUT_COMPLETED:
            raise RuntimeError("fake runtime returned an invalid completion event")

        if active.purpose is PlayoutPurpose.NARRATION:
            events = list(
                self._controller.playout_completed(
                    turn_id=active.turn_id,
                    cursor=active.cursor,
                )
            )
            if any(event.type is DomainEventType.BEAT_COMMITTED for event in events):
                self._committed_beats.append(active.cursor)
            return self._finish_action(events)

        resume_turn_id = None
        if (
            self._controller.state.continuation_preference
            is ContinuationPreference.CONTINUE_AFTER_ANSWER
        ):
            resume_turn_id = self._next_turn_id("narration")
        events = list(
            self._controller.answer_completed(
                turn_id=active.turn_id,
                resume_turn_id=resume_turn_id,
            )
        )
        if resume_turn_id is not None:
            events.extend(self._start_narration_playout(resume_turn_id))
        return self._finish_action(events)

    def continue_presentation(self) -> FakeSessionView:
        turn_id = self._next_turn_id("narration")
        events = list(self._controller.continue_presentation(turn_id=turn_id))
        events.extend(self._start_narration_playout(turn_id))
        return self._finish_action(events)

    def _start_narration_playout(self, turn_id: str) -> tuple[DomainEvent, ...]:
        cursor = self._controller.state.presentation_cursor
        beat = self._beat(cursor)
        request = PlayoutRequest(
            turn_id=turn_id,
            cursor=cursor,
            purpose=PlayoutPurpose.NARRATION,
            text=beat.summary,
        )
        started = self._runtime.start_playout(request)
        self._transcript.append(
            TranscriptEntry(role="agent", text=request.text, turn_id=turn_id)
        )
        return self._controller.playout_started(
            turn_id=started.request.turn_id,
            cursor=started.request.cursor,
            purpose=started.request.purpose,
        )

    def _beat(self, cursor: Cursor) -> NarrationBeat:
        slide = self._controller.deck.slide(cursor.slide_id)
        return slide.beats[cursor.beat_index]

    @staticmethod
    def _scripted_answer(decision: QuestionDecision) -> str:
        if decision.scope_mode is ScopeMode.GROUNDED:
            return decision.evidence[0]
        if decision.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE:
            return (
                "The slide does not contain that exact answer. "
                "From general knowledge, it is a related drivetrain feature."
            )
        if decision.scope_mode is ScopeMode.NEEDS_CLARIFICATION:
            return decision.clarification_prompt or "Which situation do you mean?"
        return (
            "That request is outside this presentation. For exact motorcycle-specific "
            "values, use the official service manual."
        )

    def _next_turn_id(self, purpose: str) -> str:
        self._turn_sequence += 1
        return f"{purpose}-{self._turn_sequence}"

    def _finish_action(self, events: list[DomainEvent]) -> FakeSessionView:
        self._events = tuple(events)
        return self.view()
