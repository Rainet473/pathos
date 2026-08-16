from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    PresentationPhase,
    ScopeMode,
)
from voice_presentation.domain.events import DomainEventType
from voice_presentation.domain.provenance import (
    GroundingSource,
    LogicalTurn,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
)
from voice_presentation.domain.reasoning import (
    PlanningStage,
    SearchMaterialInput,
    ValidatedAnswerPlan,
)


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DECK_PATH = REPOSITORY_ROOT / "assets/motorcycle-controls/slide-breakdown.json"


def _session() -> ApplicationPresentationSession:
    return ApplicationPresentationSession(
        JsonMaterialRepository(DECK_PATH).load(),
        session_id="validated-answer-session",
    )


def _interrupted_session() -> tuple[ApplicationPresentationSession, str]:
    session = _session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)
    return session, narration.turn_id


def _provenance(*, request, narration_turn_id: str) -> LogicalTurnLedger:
    ledger = LogicalTurnLedger(session_version=request.context.session_version)
    ledger.register(
        LogicalTurn(
            turn_id=narration_turn_id,
            role=TurnRole.ASSISTANT,
            purpose=TurnPurpose.NARRATION,
            session_version=request.context.session_version,
            slide_id="control-loop",
            beat_index=0,
            provider_item_ids=("provider-narration",),
            actual_text=(
                "Rider inputs create a motorcycle response through the drivetrain, "
                "brakes, and tyre force."
            ),
            delivery_status=TurnDeliveryStatus.INTERRUPTED,
        )
    )
    ledger.register(request.follow_up_turn)
    return ledger


def _conversation_plan(*, request, narration_turn_id: str) -> ValidatedAnswerPlan:
    return ValidatedAnswerPlan(
        plan_id="answer-plan-live-1",
        follow_up_turn_id=request.context.follow_up_turn_id,
        session_version=request.context.session_version,
        continuation_preference=request.context.continuation_preference,
        scope=ScopeMode.GROUNDED,
        grounding_source=GroundingSource.CONVERSATION,
        answer_brief=(
            "Clarify that response means the motorcycle's change after a rider input."
        ),
        supporting_turn_ids=(narration_turn_id,),
        supporting_slide_ids=("control-loop",),
    )


def test_follow_up_planning_is_visible_and_does_not_begin_an_answer_turn():
    session, narration_turn_id = _interrupted_session()

    request = session.begin_follow_up(
        "What response did you mean? Continue after answering.",
        provider_item_id="provider-user-follow-up",
    )

    assert request.view.state.phase is PresentationPhase.INTERRUPTED
    assert request.view.state.active_turn_id is None
    assert request.view.planning_stage is PlanningStage.UNDERSTANDING
    assert request.view.scope_mode is None
    assert request.context.follow_up_turn_id == request.follow_up_turn.turn_id
    assert request.context.continuation_preference is (
        ContinuationPreference.CONTINUE_AFTER_ANSWER
    )
    assert request.follow_up_turn.interrupted_turn_id == narration_turn_id
    assert request.follow_up_turn.actual_text == (
        "What response did you mean? Continue after answering."
    )
    assert session.active_planning_identity() == (
        request.context.session_version,
        request.context.follow_up_turn_id,
    )

    searching = session.set_planning_stage(
        PlanningStage.SEARCHING,
        follow_up_turn_id=request.context.follow_up_turn_id,
    )
    preparing = session.set_planning_stage(
        PlanningStage.PREPARING,
        follow_up_turn_id=request.context.follow_up_turn_id,
    )
    assert searching.view.planning_stage is PlanningStage.SEARCHING
    assert preparing.view.planning_stage is PlanningStage.PREPARING
    assert preparing.generation is None


def test_current_conversation_plan_creates_one_evidence_bound_answer_directive():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "What response did you mean? Continue after answering.",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)

    accepted = session.accept_answer_plan(
        _conversation_plan(request=request, narration_turn_id=narration_turn_id),
        provenance=ledger,
    )

    directive = accepted.generation
    assert directive is not None
    assert directive.plan_id == "answer-plan-live-1"
    assert directive.scope_mode is ScopeMode.GROUNDED
    assert directive.grounding_source is GroundingSource.CONVERSATION
    assert directive.supporting_turn_ids == (narration_turn_id,)
    assert directive.evidence_ids == ()
    assert "motorcycle response through the drivetrain" in directive.instructions
    assert "Clarify that response means" in directive.instructions
    assert "Do not ask whether the listener is ready" in directive.instructions
    assert accepted.view.state.phase is PresentationPhase.ANSWERING
    assert accepted.view.planning_stage is None
    assert accepted.view.grounding_source is GroundingSource.CONVERSATION
    assert any(
        event.type is DomainEventType.QUESTION_CLASSIFIED
        for event in accepted.view.events
    )

    session.playout_started(turn_id=directive.turn_id)
    resumed = session.playout_finished(
        turn_id=directive.turn_id,
        interrupted=False,
    )

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.generation is not None
    assert resumed.generation.cursor == directive.cursor
    assert resumed.view.committed_beats == ()


def test_presentation_plan_resolves_only_accepted_search_evidence_and_waits():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Why can clutch plates slip in the friction zone?",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)
    search = MaterialSearch(session.deck).search(
        SearchMaterialInput(
            keywords=("clutch", "friction zone", "partial engagement"),
            phrases=("friction zone",),
            slide_ids=("clutch-and-gears",),
            include_neighbors=True,
            max_results=1,
        )
    )
    hit = search.hits[0]
    plan = ValidatedAnswerPlan(
        plan_id="answer-plan-live-2",
        follow_up_turn_id=request.context.follow_up_turn_id,
        session_version=request.context.session_version,
        continuation_preference=request.context.continuation_preference,
        scope=ScopeMode.GROUNDED,
        grounding_source=GroundingSource.PRESENTATION,
        answer_brief="Explain partial torque transfer and relative plate motion.",
        evidence_ids=(hit.evidence_id,),
        supporting_slide_ids=(hit.slide_id,),
        focus_slide_id=hit.slide_id,
    )

    accepted = session.accept_answer_plan(
        plan,
        provenance=ledger,
        search_results=(search,),
    )

    directive = accepted.generation
    assert directive is not None
    assert hit.text in directive.instructions
    assert directive.evidence_ids == (hit.evidence_id,)
    assert accepted.view.state.visible_slide_id == "control-loop"
    session.playout_started(turn_id=directive.turn_id)
    waiting = session.playout_finished(
        turn_id=directive.turn_id,
        interrupted=False,
    )
    assert waiting.view.state.phase is PresentationPhase.WAITING
    assert waiting.view.committed_beats == ()


def test_stale_plan_and_planning_failure_never_create_answer_generation():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "What response did you mean?",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)
    stale = _conversation_plan(
        request=request,
        narration_turn_id=narration_turn_id,
    ).model_copy(update={"session_version": request.context.session_version + 1})

    with pytest.raises(ValueError, match="stale answer plan"):
        session.accept_answer_plan(stale, provenance=ledger)

    assert session.view().state.phase is PresentationPhase.INTERRUPTED
    assert session.view().state.active_turn_id is None
    failed = session.fail_answer_plan(
        follow_up_turn_id=request.context.follow_up_turn_id,
        reason_code="provider_error",
    )
    assert failed.generation is None
    assert failed.view.state.phase is PresentationPhase.WAITING
    assert failed.view.planning_stage is None
    assert failed.view.planning_failure_code == "provider_error"
    assert failed.view.committed_beats == ()
    assert [event.type for event in failed.view.events] == [
        DomainEventType.FOLLOW_UP_PLANNING_FAILED,
        DomainEventType.PRESENTATION_WAITING,
    ]

    recovered = session.continue_presentation()
    assert recovered.view.state.phase is PresentationPhase.PRESENTING
    assert recovered.view.planning_failure_code is None
    assert recovered.generation is not None


def test_then_narration_is_explicit_application_owned_continuation():
    session, _ = _interrupted_session()

    request = session.begin_follow_up(
        "Explain what AWS is. Then narration.",
        provider_item_id="provider-user-follow-up",
    )

    assert request.context.continuation_preference is (
        ContinuationPreference.CONTINUE_AFTER_ANSWER
    )
