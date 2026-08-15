from __future__ import annotations

from collections.abc import Iterable

from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.contracts import (
    ActivePlayout,
    ContinuationPreference,
    Cursor,
    PlayoutPurpose,
    PresentationPhase,
    PresentationState,
)
from voice_presentation.domain.events import (
    DomainEvent,
    DomainEventType,
    SlideChangeReason,
)


class TransitionRejected(RuntimeError):
    """Raised before mutation when an action is illegal for the current state."""


class PresentationController:
    def __init__(self, deck: PresentationDeck) -> None:
        self._deck = deck
        first_cursor = Cursor(slide_id=deck.slides[0].id, beat_index=0)
        self.state = PresentationState(
            session_version=0,
            phase=PresentationPhase.READY,
            presentation_cursor=first_cursor,
            visible_slide_id=first_cursor.slide_id,
        )

    @property
    def deck(self) -> PresentationDeck:
        return self._deck

    def start_presentation(self, *, turn_id: str) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        self._require_phase("start_presentation", PresentationPhase.READY)
        self.state.phase = PresentationPhase.PRESENTING
        self.state.active_turn_id = turn_id
        self._advance_version()
        cursor = self.state.presentation_cursor
        return (
            DomainEvent(type=DomainEventType.PRESENTATION_STARTED, cursor=cursor),
            DomainEvent(
                type=DomainEventType.BEAT_SELECTED,
                cursor=cursor,
                turn_id=turn_id,
            ),
        )

    def playout_started(
        self,
        *,
        turn_id: str,
        cursor: Cursor,
        purpose: PlayoutPurpose,
    ) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        purpose = PlayoutPurpose(purpose)
        self._validate_cursor(cursor)
        if self.state.active_playout is not None:
            self._reject("playout_started", ("playout_completed", "playout_interrupted"))

        if purpose is PlayoutPurpose.NARRATION:
            self._require_phase("playout_started", PresentationPhase.PRESENTING)
            if cursor != self.state.presentation_cursor:
                self._reject("playout_started", ("current_presentation_cursor",))
            if self.state.active_turn_id is None:
                self.state.active_turn_id = turn_id
            elif self.state.active_turn_id != turn_id:
                self._reject("playout_started", (self.state.active_turn_id,))
        else:
            self._require_phase("playout_started", PresentationPhase.ANSWERING)
            if self.state.active_turn_id != turn_id:
                self._reject("playout_started", (self.state.active_turn_id or "answer_turn",))
            if cursor != (self.state.interrupted_cursor or self.state.presentation_cursor):
                self._reject("playout_started", ("saved_presentation_cursor",))

        self.state.active_playout = ActivePlayout(
            turn_id=turn_id,
            cursor=cursor,
            purpose=purpose,
        )
        self._advance_version()
        return (
            DomainEvent(
                type=DomainEventType.PLAYOUT_STARTED,
                cursor=cursor,
                turn_id=turn_id,
                purpose=purpose,
            ),
        )

    def select_narration(self, *, turn_id: str) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        self._require_phase("select_narration", PresentationPhase.PRESENTING)
        if (
            self.state.active_playout is not None
            or self.state.active_turn_id is not None
        ):
            self._reject("select_narration", ("no_active_turn",))
        self.state.active_turn_id = turn_id
        self._advance_version()
        return (
            DomainEvent(
                type=DomainEventType.BEAT_SELECTED,
                cursor=self.state.presentation_cursor,
                turn_id=turn_id,
            ),
        )

    def playout_completed(
        self, *, turn_id: str, cursor: Cursor
    ) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        active = self.state.active_playout
        if (
            active is None
            or active.purpose is not PlayoutPurpose.NARRATION
            or active.turn_id != turn_id
            or active.cursor != cursor
            or cursor != self.state.presentation_cursor
        ):
            return self._stale(turn_id)

        next_cursor = self._next_cursor(cursor)
        self.state.active_playout = None
        self.state.active_turn_id = None
        self.state.interrupted_cursor = None
        events: list[DomainEvent] = [
            DomainEvent(
                type=DomainEventType.BEAT_COMMITTED,
                cursor=cursor,
                turn_id=turn_id,
            )
        ]

        if next_cursor is None:
            self.state.phase = PresentationPhase.COMPLETED
            events.append(DomainEvent(type=DomainEventType.PRESENTATION_COMPLETED))
        else:
            self.state.presentation_cursor = next_cursor
            if next_cursor.slide_id != cursor.slide_id:
                self.state.visible_slide_id = next_cursor.slide_id
                events.append(
                    DomainEvent(
                        type=DomainEventType.SLIDE_CHANGED,
                        slide_id=next_cursor.slide_id,
                        slide_change_reason=SlideChangeReason.PRESENTATION,
                    )
                )

        self._advance_version()
        return tuple(events)

    def playout_interrupted(self, *, turn_id: str) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        active = self.state.active_playout
        if active is None or active.turn_id != turn_id:
            return self._stale(turn_id)

        if active.purpose is PlayoutPurpose.NARRATION:
            self.state.interrupted_cursor = active.cursor
        self.state.phase = PresentationPhase.INTERRUPTED
        self.state.active_playout = None
        self.state.active_turn_id = None
        self._advance_version()
        return (
            DomainEvent(
                type=DomainEventType.PLAYOUT_INTERRUPTED,
                cursor=active.cursor,
                turn_id=turn_id,
                purpose=active.purpose,
            ),
        )

    def begin_answer(
        self,
        *,
        turn_id: str,
        continuation_preference: ContinuationPreference,
        question_slide_id: str | None = None,
    ) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        self._require_phase(
            "begin_answer",
            PresentationPhase.INTERRUPTED,
            PresentationPhase.WAITING,
            PresentationPhase.COMPLETED,
        )
        continuation_preference = ContinuationPreference(continuation_preference)
        if question_slide_id is not None:
            try:
                self._deck.slide(question_slide_id)
            except ValueError as error:
                raise TransitionRejected(str(error)) from error

        if self.state.answer_return_phase is None:
            self.state.answer_return_phase = self.state.phase
        self.state.phase = PresentationPhase.ANSWERING
        self.state.active_turn_id = turn_id
        self.state.continuation_preference = continuation_preference
        events: list[DomainEvent] = []
        if (
            question_slide_id is not None
            and question_slide_id != self.state.visible_slide_id
        ):
            self.state.visible_slide_id = question_slide_id
            events.append(
                DomainEvent(
                    type=DomainEventType.SLIDE_CHANGED,
                    slide_id=question_slide_id,
                    slide_change_reason=SlideChangeReason.QUESTION,
                )
            )
        self._advance_version()
        return tuple(events)

    def answer_completed(
        self, *, turn_id: str, resume_turn_id: str | None = None
    ) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        active = self.state.active_playout
        if (
            active is None
            or active.purpose is not PlayoutPurpose.ANSWER
            or active.turn_id != turn_id
        ):
            return self._stale(turn_id)

        preference = self.state.continuation_preference
        returns_to_completed = (
            self.state.answer_return_phase is PresentationPhase.COMPLETED
        )
        normalized_resume_turn_id: str | None = None
        if (
            preference is ContinuationPreference.CONTINUE_AFTER_ANSWER
            and not returns_to_completed
        ):
            if resume_turn_id is None:
                raise TransitionRejected(
                    "answer_completed requires resume_turn_id when continuation is authorized"
                )
            normalized_resume_turn_id = self._turn_id(resume_turn_id)

        events: list[DomainEvent] = [
            DomainEvent(
                type=DomainEventType.ANSWER_COMPLETED,
                turn_id=turn_id,
                continuation_preference=preference,
            )
        ]
        self.state.active_playout = None
        self.state.active_turn_id = None

        if returns_to_completed:
            self.state.phase = PresentationPhase.COMPLETED
            self.state.continuation_preference = None
            self.state.answer_return_phase = None
        elif preference is ContinuationPreference.CONTINUE_AFTER_ANSWER:
            assert normalized_resume_turn_id is not None
            resume_cursor = self.state.interrupted_cursor or self.state.presentation_cursor
            events.extend(self._restore_slide_events(resume_cursor))
            self.state.phase = PresentationPhase.PRESENTING
            self.state.active_turn_id = normalized_resume_turn_id
            self.state.continuation_preference = None
            self.state.answer_return_phase = None
            events.extend(
                (
                    DomainEvent(
                        type=DomainEventType.PRESENTATION_RESUMED,
                        cursor=resume_cursor,
                    ),
                    DomainEvent(
                        type=DomainEventType.BEAT_SELECTED,
                        cursor=resume_cursor,
                        turn_id=normalized_resume_turn_id,
                    ),
                )
            )
        else:
            self.state.phase = PresentationPhase.WAITING
            self.state.answer_return_phase = None
            events.append(DomainEvent(type=DomainEventType.PRESENTATION_WAITING))

        self._advance_version()
        return tuple(events)

    def continue_presentation(self, *, turn_id: str) -> tuple[DomainEvent, ...]:
        turn_id = self._turn_id(turn_id)
        self._require_phase("continue_presentation", PresentationPhase.WAITING)
        cursor = self.state.interrupted_cursor or self.state.presentation_cursor
        events = self._restore_slide_events(cursor)
        self.state.phase = PresentationPhase.PRESENTING
        self.state.active_turn_id = turn_id
        self.state.continuation_preference = None
        events.extend(
            (
                DomainEvent(type=DomainEventType.PRESENTATION_RESUMED, cursor=cursor),
                DomainEvent(
                    type=DomainEventType.BEAT_SELECTED,
                    cursor=cursor,
                    turn_id=turn_id,
                ),
            )
        )
        self._advance_version()
        return tuple(events)

    def _restore_slide_events(self, cursor: Cursor) -> list[DomainEvent]:
        if self.state.visible_slide_id == cursor.slide_id:
            return []
        self.state.visible_slide_id = cursor.slide_id
        return [
            DomainEvent(
                type=DomainEventType.SLIDE_CHANGED,
                slide_id=cursor.slide_id,
                slide_change_reason=SlideChangeReason.RESTORE,
            )
        ]

    def _next_cursor(self, cursor: Cursor) -> Cursor | None:
        for slide_index, slide in enumerate(self._deck.slides):
            if slide.id != cursor.slide_id:
                continue
            if cursor.beat_index + 1 < len(slide.beats):
                return Cursor(slide_id=slide.id, beat_index=cursor.beat_index + 1)
            if slide_index + 1 < len(self._deck.slides):
                return Cursor(slide_id=self._deck.slides[slide_index + 1].id, beat_index=0)
            return None
        raise TransitionRejected(f"unknown cursor slide: {cursor.slide_id}")

    def _validate_cursor(self, cursor: Cursor) -> None:
        try:
            slide = self._deck.slide(cursor.slide_id)
        except ValueError as error:
            raise TransitionRejected(str(error)) from error
        if cursor.beat_index >= len(slide.beats):
            raise TransitionRejected(f"unknown beat index: {cursor.beat_index}")

    def _require_phase(
        self, action: str, *allowed_phases: PresentationPhase
    ) -> None:
        if self.state.phase not in allowed_phases:
            self._reject(action, (phase.value for phase in allowed_phases))

    @staticmethod
    def _turn_id(turn_id: str) -> str:
        turn_id = turn_id.strip()
        if not turn_id:
            raise TransitionRejected("turn_id cannot be blank")
        return turn_id

    def _reject(self, action: str, allowed: Iterable[str]) -> None:
        allowed_text = ", ".join(str(item) for item in allowed)
        raise TransitionRejected(
            f"{action} is not allowed while phase={self.state.phase.value}; expected {allowed_text}"
        )

    @staticmethod
    def _stale(turn_id: str) -> tuple[DomainEvent, ...]:
        return (
            DomainEvent(
                type=DomainEventType.STALE_RESPONSE_DISCARDED,
                turn_id=turn_id,
            ),
        )

    def _advance_version(self) -> None:
        self.state.session_version += 1
