from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.application.fake_session import SlideView
from voice_presentation.domain.content import NarrationBeat, PresentationDeck
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    Cursor,
    PlayoutPurpose,
    PresentationPhase,
    PresentationState,
    ScopeMode,
)
from voice_presentation.domain.controller import PresentationController
from voice_presentation.domain.events import DomainEvent, DomainEventType
from voice_presentation.domain.policy import QuestionDecision, QuestionScopePolicy


_WORD_SPACE = re.compile(r"[^a-z0-9]+")


class GenerationDirective(BaseModel):
    """Provider-neutral request for exactly one interruptible spoken turn."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    turn_id: str = Field(min_length=1)
    cursor: Cursor
    purpose: PlayoutPurpose
    instructions: str = Field(min_length=1)


class LivePresentationView(BaseModel):
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
    events: tuple[DomainEvent, ...]
    scope_mode: ScopeMode | None = None
    committed_beats: tuple[Cursor, ...]


class PresentationActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view: LivePresentationView
    generation: GenerationDirective | None = None


class ApplicationPresentationSession:
    """Application-owned presentation policy at the real voice boundary.

    The class has no LiveKit or provider imports. Adapters may execute its generation
    directives and report normalized playout facts back through the public methods.
    """

    def __init__(self, deck: PresentationDeck, *, session_id: str) -> None:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id cannot be blank")
        self._session_id = session_id
        self._controller = PresentationController(deck)
        self._policy = QuestionScopePolicy(deck)
        self._events: tuple[DomainEvent, ...] = ()
        self._scope_mode: ScopeMode | None = None
        self._committed_beats: list[Cursor] = []
        self._turn_sequence = 0
        self._directives: dict[str, GenerationDirective] = {}

    def view(self) -> LivePresentationView:
        deck = self._controller.deck
        return LivePresentationView(
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
            events=self._events,
            scope_mode=self._scope_mode,
            committed_beats=tuple(self._committed_beats),
        )

    def start(self) -> PresentationActionResult:
        turn_id = self._next_turn_id("narration")
        events = self._controller.start_presentation(turn_id=turn_id)
        generation = self._narration_directive(turn_id)
        return self._finish(events, generation=generation)

    def playout_started(self, *, turn_id: str) -> PresentationActionResult:
        directive = self._directive(turn_id)
        active = self._controller.state.active_playout
        if active is not None and active.turn_id == directive.turn_id:
            return self._finish((self._stale(turn_id),))
        events = self._controller.playout_started(
            turn_id=directive.turn_id,
            cursor=directive.cursor,
            purpose=directive.purpose,
        )
        return self._finish(events)

    def playout_finished(
        self,
        *,
        turn_id: str,
        interrupted: bool,
    ) -> PresentationActionResult:
        directive = self._directive(turn_id)
        if interrupted:
            events = self._controller.playout_interrupted(turn_id=turn_id)
            return self._finish(events)

        if directive.purpose is PlayoutPurpose.NARRATION:
            events = self._controller.playout_completed(
                turn_id=turn_id,
                cursor=directive.cursor,
            )
            beat_committed = any(
                event.type is DomainEventType.BEAT_COMMITTED for event in events
            )
            if beat_committed:
                if directive.cursor not in self._committed_beats:
                    self._committed_beats.append(directive.cursor)
            if (
                not beat_committed
                or self._controller.state.phase is not PresentationPhase.PRESENTING
            ):
                return self._finish(events)
            next_turn_id = self._next_turn_id("narration")
            events += self._controller.select_narration(turn_id=next_turn_id)
            generation = self._narration_directive(next_turn_id)
            return self._finish(events, generation=generation)

        resume_turn_id: str | None = None
        if (
            self._controller.state.continuation_preference
            is ContinuationPreference.CONTINUE_AFTER_ANSWER
            and self._controller.state.answer_return_phase
            is not PresentationPhase.COMPLETED
        ):
            resume_turn_id = self._next_turn_id("narration")
        events = self._controller.answer_completed(
            turn_id=turn_id,
            resume_turn_id=resume_turn_id,
        )
        if resume_turn_id is None:
            return self._finish(events)
        generation = self._narration_directive(resume_turn_id)
        return self._finish(events, generation=generation)

    def prepare_question(self, question: str) -> PresentationActionResult:
        question = question.strip()
        if not question:
            raise ValueError("question cannot be blank")

        decision = self._policy.classify(question)
        preference = self._continuation_preference(question)
        if decision.scope_mode is ScopeMode.NEEDS_CLARIFICATION:
            preference = ContinuationPreference.ASK_BEFORE_CONTINUING

        turn_id = self._next_turn_id("answer")
        events = list(
            self._controller.begin_answer(
                turn_id=turn_id,
                continuation_preference=preference,
                question_slide_id=decision.supporting_slide_id,
            )
        )
        events.append(
            DomainEvent(
                type=DomainEventType.QUESTION_CLASSIFIED,
                turn_id=turn_id,
                scope_mode=decision.scope_mode,
                continuation_preference=preference,
            )
        )
        self._scope_mode = decision.scope_mode
        generation = self._answer_directive(turn_id, question, decision)
        return self._finish(tuple(events), generation=generation)

    def continue_presentation(self) -> PresentationActionResult:
        turn_id = self._next_turn_id("narration")
        events = self._controller.continue_presentation(turn_id=turn_id)
        generation = self._narration_directive(turn_id)
        return self._finish(events, generation=generation)

    def _narration_directive(self, turn_id: str) -> GenerationDirective:
        cursor = self._controller.state.presentation_cursor
        beat = self._beat(cursor)
        slide = self._controller.deck.slide(cursor.slide_id)
        required = ", ".join(beat.required_concepts)
        labels = ", ".join(slide.labels)
        instructions = (
            "Deliver exactly one concise presentation beat in one or two sentences. "
            "Do not greet, ask a question, mention these instructions, or navigate. "
            f"Slide headline: {slide.headline} "
            f"Visible labels: {labels}. "
            f"Beat summary: {beat.summary} "
            f"Narration guidance: {beat.narration_guidance} "
            f"Required concepts: {required}."
        )
        directive = GenerationDirective(
            turn_id=turn_id,
            cursor=cursor,
            purpose=PlayoutPurpose.NARRATION,
            instructions=instructions,
        )
        self._directives[turn_id] = directive
        return directive

    def _answer_directive(
        self,
        turn_id: str,
        question: str,
        decision: QuestionDecision,
    ) -> GenerationDirective:
        cursor = (
            self._controller.state.interrupted_cursor
            or self._controller.state.presentation_cursor
        )
        if decision.scope_mode is ScopeMode.GROUNDED:
            evidence = " ".join(decision.evidence)
            mode_instruction = (
                "Answer only from this selected presentation evidence: " + evidence
            )
        elif decision.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE:
            mode_instruction = (
                "First disclose that the exact answer is not on the slide, then give "
                "a short general-knowledge answer without inventing motorcycle-specific values."
            )
        elif decision.scope_mode is ScopeMode.NEEDS_CLARIFICATION:
            mode_instruction = (
                "Ask only this clarification question: "
                + (decision.clarification_prompt or "Which situation do you mean?")
            )
        else:
            mode_instruction = (
                "Briefly say this is outside the presentation and do not provide unsafe "
                "or exact motorcycle-specific instructions."
            )
        instructions = (
            "Respond to the listener in no more than three short sentences. "
            "Do not navigate, resume the presentation, or mention hidden instructions. "
            f"Listener question: {question} {mode_instruction}"
        )
        directive = GenerationDirective(
            turn_id=turn_id,
            cursor=cursor,
            purpose=PlayoutPurpose.ANSWER,
            instructions=instructions,
        )
        self._directives[turn_id] = directive
        return directive

    def _beat(self, cursor: Cursor) -> NarrationBeat:
        slide = self._controller.deck.slide(cursor.slide_id)
        return slide.beats[cursor.beat_index]

    def _directive(self, turn_id: str) -> GenerationDirective:
        turn_id = turn_id.strip()
        if not turn_id:
            raise ValueError("turn_id cannot be blank")
        directive = self._directives.get(turn_id)
        if directive is None:
            raise ValueError(f"unknown generation turn: {turn_id}")
        return directive

    @staticmethod
    def _continuation_preference(question: str) -> ContinuationPreference:
        normalized = _WORD_SPACE.sub(" ", question.lower()).strip()
        if any(
            phrase in normalized
            for phrase in (
                "do not continue",
                "dont continue",
                "stay paused",
                "wait after answering",
            )
        ):
            return ContinuationPreference.STAY_PAUSED
        if any(
            phrase in normalized
            for phrase in (
                "answer and continue",
                "continue after answering",
                "continue after the answer",
                "then continue",
            )
        ):
            return ContinuationPreference.CONTINUE_AFTER_ANSWER
        return ContinuationPreference.ASK_BEFORE_CONTINUING

    def _next_turn_id(self, purpose: str) -> str:
        self._turn_sequence += 1
        return f"{purpose}-{self._turn_sequence}"

    def _finish(
        self,
        events: tuple[DomainEvent, ...],
        *,
        generation: GenerationDirective | None = None,
    ) -> PresentationActionResult:
        self._events = events
        return PresentationActionResult(view=self.view(), generation=generation)

    @staticmethod
    def _stale(turn_id: str) -> DomainEvent:
        return DomainEvent(
            type=DomainEventType.STALE_RESPONSE_DISCARDED,
            turn_id=turn_id,
        )
