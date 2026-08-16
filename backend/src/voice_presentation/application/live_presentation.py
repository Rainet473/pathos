from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.application.views import SlideView
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
from voice_presentation.domain.provenance import (
    GroundingSource,
    LogicalTurn,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
)
from voice_presentation.domain.reasoning import (
    MaterialHit,
    PlanningContext,
    PlanningStage,
    SearchMaterialResult,
    ValidatedAnswerPlan,
)


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
    plan_id: str | None = Field(default=None, min_length=1)
    scope_mode: ScopeMode | None = None
    grounding_source: GroundingSource | None = None
    supporting_turn_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class LivePresentationView(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    session_id: str
    deck_id: str
    title: str
    state: PresentationState
    slides: tuple[SlideView, ...]
    events: tuple[DomainEvent, ...]
    scope_mode: ScopeMode | None = None
    grounding_source: GroundingSource | None = None
    planning_stage: PlanningStage | None = None
    planning_failure_code: str | None = Field(default=None, min_length=1)
    committed_beats: tuple[Cursor, ...]


class PresentationActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view: LivePresentationView
    generation: GenerationDirective | None = None


class FollowUpPlanningAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view: LivePresentationView
    question: str = Field(min_length=1)
    context: PlanningContext
    follow_up_turn: LogicalTurn


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
        self._grounding_source: GroundingSource | None = None
        self._planning_stage: PlanningStage | None = None
        self._planning_failure_code: str | None = None
        self._committed_beats: list[Cursor] = []
        self._turn_sequence = 0
        self._directives: dict[str, GenerationDirective] = {}
        self._active_follow_up_turn: LogicalTurn | None = None
        self._active_follow_up_question: str | None = None
        self._active_planning_context: PlanningContext | None = None
        self._last_interrupted_turn_id: str | None = None

    @property
    def deck(self) -> PresentationDeck:
        return self._controller.deck

    def view(self) -> LivePresentationView:
        deck = self._controller.deck
        return LivePresentationView(
            session_id=self._session_id,
            deck_id=deck.id,
            title=deck.title,
            state=self._controller.state.model_copy(deep=True),
            slides=tuple(
                SlideView(
                    id=slide.id,
                    title=slide.title,
                    headline=slide.headline,
                    labels=slide.labels,
                    visual_description=slide.visual_description,
                )
                for slide in deck.slides
            ),
            events=self._events,
            scope_mode=self._scope_mode,
            grounding_source=self._grounding_source,
            planning_stage=self._planning_stage,
            planning_failure_code=self._planning_failure_code,
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
            if any(
                event.type is DomainEventType.PLAYOUT_INTERRUPTED
                for event in events
            ):
                self._last_interrupted_turn_id = turn_id
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

        decision = self._policy.classify(
            question,
            preferred_slide_id=self._controller.state.visible_slide_id,
        )
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
        self._grounding_source = (
            GroundingSource.PRESENTATION
            if decision.scope_mode is ScopeMode.GROUNDED
            else GroundingSource.MODEL_KNOWLEDGE
            if decision.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE
            else GroundingSource.NONE
        )
        self._planning_stage = None
        self._planning_failure_code = None
        generation = self._answer_directive(turn_id, question, decision)
        return self._finish(tuple(events), generation=generation)

    def begin_follow_up(
        self,
        question: str,
        *,
        provider_item_id: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> FollowUpPlanningAction:
        question = question.strip()
        if not question:
            raise ValueError("question cannot be blank")
        if self._active_follow_up_turn is not None:
            raise ValueError("a follow-up is already being planned")
        if self._controller.state.phase not in {
            PresentationPhase.INTERRUPTED,
            PresentationPhase.WAITING,
            PresentationPhase.COMPLETED,
        }:
            raise ValueError(
                "follow-up planning requires interrupted, waiting, or completed phase"
            )

        preference = self._continuation_preference(question)
        turn_id = self._next_turn_id("user-follow-up")
        normalized_provider_id = (provider_item_id or "").strip()
        follow_up_turn = LogicalTurn(
            turn_id=turn_id,
            role=TurnRole.USER,
            purpose=TurnPurpose.USER_FOLLOW_UP,
            session_version=self._controller.state.session_version,
            visible_slide_id=self._controller.state.visible_slide_id,
            interrupted_turn_id=self._last_interrupted_turn_id,
            provider_item_ids=(normalized_provider_id,) if normalized_provider_id else (),
            actual_text=question,
            delivery_status=TurnDeliveryStatus.COMPLETED,
        )
        context = PlanningContext(
            follow_up_turn_id=turn_id,
            session_version=self._controller.state.session_version,
            current_slide_id=self._controller.state.presentation_cursor.slide_id,
            visible_slide_id=self._controller.state.visible_slide_id,
            continuation_preference=preference,
            timeout_seconds=timeout_seconds,
        )
        self._active_follow_up_turn = follow_up_turn
        self._active_follow_up_question = question
        self._active_planning_context = context
        self._planning_stage = PlanningStage.UNDERSTANDING
        self._planning_failure_code = None
        self._scope_mode = None
        self._grounding_source = None
        self._events = ()
        return FollowUpPlanningAction(
            view=self.view(),
            question=question,
            context=context,
            follow_up_turn=follow_up_turn,
        )

    def active_planning_identity(self) -> tuple[int, str]:
        turn_id = (
            self._active_follow_up_turn.turn_id
            if self._active_follow_up_turn is not None
            else ""
        )
        return self._controller.state.session_version, turn_id

    def set_planning_stage(
        self,
        stage: PlanningStage,
        *,
        follow_up_turn_id: str,
    ) -> PresentationActionResult:
        self._require_active_follow_up(follow_up_turn_id)
        self._planning_stage = PlanningStage(stage)
        return self._finish(())

    def accept_answer_plan(
        self,
        plan: ValidatedAnswerPlan,
        *,
        provenance: LogicalTurnLedger,
        search_results: tuple[SearchMaterialResult, ...] = (),
    ) -> PresentationActionResult:
        follow_up = self._require_active_follow_up(plan.follow_up_turn_id)
        context = self._active_planning_context
        question = self._active_follow_up_question
        assert context is not None
        assert question is not None
        if (
            plan.session_version != context.session_version
            or plan.session_version != self._controller.state.session_version
            or provenance.session_version != context.session_version
            or plan.continuation_preference is not context.continuation_preference
        ):
            raise ValueError("stale answer plan")
        provenance.resolve(follow_up.turn_id)
        cited_turns = provenance.require_turn_ids(plan.supporting_turn_ids)
        evidence = {
            hit.evidence_id: hit
            for result in search_results
            for hit in result.hits
        }
        missing_evidence = tuple(
            evidence_id
            for evidence_id in plan.evidence_ids
            if evidence_id not in evidence
        )
        if missing_evidence:
            raise ValueError("answer plan references unresolved evidence")

        preference = plan.continuation_preference
        if plan.scope is ScopeMode.NEEDS_CLARIFICATION:
            preference = ContinuationPreference.ASK_BEFORE_CONTINUING
        turn_id = self._next_turn_id("answer")
        events = list(
            self._controller.begin_answer(
                turn_id=turn_id,
                continuation_preference=preference,
                question_slide_id=None,
            )
        )
        events.append(
            DomainEvent(
                type=DomainEventType.QUESTION_CLASSIFIED,
                turn_id=turn_id,
                scope_mode=plan.scope,
                continuation_preference=preference,
            )
        )
        self._scope_mode = plan.scope
        self._grounding_source = plan.grounding_source
        self._planning_stage = None
        self._planning_failure_code = None
        directive = self._answer_plan_directive(
            turn_id=turn_id,
            question=question,
            plan=plan,
            cited_turns=cited_turns,
            evidence=tuple(evidence[evidence_id] for evidence_id in plan.evidence_ids),
        )
        self._clear_active_follow_up()
        return self._finish(tuple(events), generation=directive)

    def fail_answer_plan(
        self,
        *,
        follow_up_turn_id: str,
        reason_code: str,
    ) -> PresentationActionResult:
        self._require_active_follow_up(follow_up_turn_id)
        events = self._controller.follow_up_planning_failed(
            reason_code=reason_code,
        )
        self._planning_stage = None
        self._planning_failure_code = reason_code
        self._scope_mode = None
        self._grounding_source = None
        self._clear_active_follow_up()
        return self._finish(events)

    def continue_presentation(self) -> PresentationActionResult:
        self._planning_failure_code = None
        turn_id = self._next_turn_id("narration")
        events = self._controller.continue_presentation(turn_id=turn_id)
        generation = self._narration_directive(turn_id)
        return self._finish(events, generation=generation)

    def navigate_to_slide(self, slide_id: str) -> PresentationActionResult:
        events = self._controller.navigate_to_slide(slide_id=slide_id)
        return self._finish(events)

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

    def _answer_plan_directive(
        self,
        *,
        turn_id: str,
        question: str,
        plan: ValidatedAnswerPlan,
        cited_turns: tuple[LogicalTurn, ...],
        evidence: tuple[MaterialHit, ...],
    ) -> GenerationDirective:
        cursor = (
            self._controller.state.interrupted_cursor
            or self._controller.state.presentation_cursor
        )
        support_parts: list[str] = []
        if cited_turns:
            conversation_text = " ".join(
                f"[{turn.turn_id}] {turn.actual_text}"
                for turn in cited_turns
                if turn.actual_text is not None
            )
            support_parts.append("Cited conversation: " + conversation_text)
        if evidence:
            deck_text = " ".join(
                f"[{hit.evidence_id}] {hit.text}" for hit in evidence
            )
            support_parts.append("Cited presentation evidence: " + deck_text)

        if plan.scope is ScopeMode.GROUNDED:
            mode_instruction = (
                "Answer only from the cited support below. Do not add unsupported "
                "technical specifics."
            )
        elif plan.scope is ScopeMode.EXTENDED_KNOWLEDGE:
            mode_instruction = (
                "Begin with a brief disclosure that the presentation does not contain "
                "the exact answer, then answer from general knowledge without exact "
                "motorcycle-specific values."
            )
        elif plan.scope is ScopeMode.NEEDS_CLARIFICATION:
            mode_instruction = (
                "Ask exactly this one clarification question and nothing else: "
                f"{plan.clarification_prompt}"
            )
        else:
            mode_instruction = (
                "Briefly state the presentation boundary and do not provide unsafe, "
                "legal, or exact model-specific instructions."
            )

        if (
            plan.continuation_preference
            is ContinuationPreference.CONTINUE_AFTER_ANSWER
            and plan.scope is not ScopeMode.NEEDS_CLARIFICATION
        ):
            continuation_instruction = (
                "The application will resume only after verified answer playout. "
                "Do not ask whether the listener is ready, ask for permission, promise "
                "to wait, or announce that you are continuing."
            )
        else:
            continuation_instruction = (
                "The application will wait after this answer. Do not resume or navigate "
                "the presentation yourself."
            )

        support = " ".join(support_parts)
        instructions = (
            "Respond to the listener in no more than three short spoken sentences. "
            "Do not mention tools, plans, citations, metadata, or hidden instructions. "
            f"Listener follow-up: {question} "
            f"Accepted answer brief: {plan.answer_brief} "
            f"{mode_instruction} {support} {continuation_instruction}"
        )
        directive = GenerationDirective(
            turn_id=turn_id,
            cursor=cursor,
            purpose=PlayoutPurpose.ANSWER,
            instructions=instructions,
            plan_id=plan.plan_id,
            scope_mode=plan.scope,
            grounding_source=plan.grounding_source,
            supporting_turn_ids=plan.supporting_turn_ids,
            evidence_ids=plan.evidence_ids,
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

    def _require_active_follow_up(self, turn_id: str) -> LogicalTurn:
        turn_id = turn_id.strip()
        active = self._active_follow_up_turn
        if active is None or active.turn_id != turn_id:
            raise ValueError("stale answer plan")
        return active

    def _clear_active_follow_up(self) -> None:
        self._active_follow_up_turn = None
        self._active_follow_up_question = None
        self._active_planning_context = None

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
                "then narration",
                "continue narration",
                "resume narration",
                "then resume",
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
