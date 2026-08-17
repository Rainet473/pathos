from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.application.follow_up_planning import (
    FollowUpPlanningSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    PresentationPhase,
    ScopeMode,
)
from voice_presentation.domain.events import DomainEventType, SlideChangeReason
from voice_presentation.domain.provenance import (
    GroundingSource,
    LogicalTurn,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
)
from voice_presentation.domain.reasoning import (
    PresentationActionKind,
    PlanningStage,
    SearchMaterialInput,
    SubmitAnswerPlanInput,
    ValidatedPresentationAction,
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


def test_validated_model_continue_action_resumes_without_creating_an_answer():
    session, _ = _interrupted_session()
    request = session.begin_follow_up(
        "Would you carry on with the presentation from there?",
        provider_item_id="provider-user-continue",
    )

    resumed = session.accept_presentation_action(
        ValidatedPresentationAction(
            action_id="presentation-action-1",
            follow_up_turn_id=request.context.follow_up_turn_id,
            session_version=request.context.session_version,
            action=PresentationActionKind.CONTINUE_PRESENTATION,
        )
    )

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.generation is not None
    assert resumed.generation.purpose.value == "narration"
    assert resumed.view.planning_stage is None
    assert session.active_planning_identity() == (
        resumed.view.state.session_version,
        "",
    )
    assert [event.type for event in resumed.view.events] == [
        DomainEventType.PRESENTATION_RESUMED,
        DomainEventType.BEAT_SELECTED,
    ]


def test_stale_model_continue_action_is_rejected_without_state_change():
    session, _ = _interrupted_session()
    request = session.begin_follow_up("Would you continue from there?")
    before = session.view()

    with pytest.raises(ValueError, match="stale presentation action"):
        session.accept_presentation_action(
            ValidatedPresentationAction(
                action_id="presentation-action-stale",
                follow_up_turn_id=request.context.follow_up_turn_id,
                session_version=request.context.session_version + 1,
                action=PresentationActionKind.CONTINUE_PRESENTATION,
            )
        )

    after = session.view()
    assert after.state == before.state
    assert after.planning_stage == before.planning_stage
    assert session.active_planning_identity() == (
        request.context.session_version,
        request.context.follow_up_turn_id,
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
    assert request.context.timeout_seconds == 30.0
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
    assert accepted.view.state.presentation_cursor.slide_id == "control-loop"
    assert accepted.view.state.visible_slide_id == hit.slide_id
    assert [event.type for event in accepted.view.events] == [
        DomainEventType.SLIDE_CHANGED,
        DomainEventType.QUESTION_CLASSIFIED,
    ]
    assert accepted.view.events[0].slide_change_reason is SlideChangeReason.QUESTION
    session.playout_started(turn_id=directive.turn_id)
    waiting = session.playout_finished(
        turn_id=directive.turn_id,
        interrupted=False,
    )
    assert waiting.view.state.phase is PresentationPhase.WAITING
    assert waiting.view.state.presentation_cursor.slide_id == "control-loop"
    assert waiting.view.state.visible_slide_id == hit.slide_id
    assert waiting.view.committed_beats == ()

    resumed = session.continue_presentation()

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.visible_slide_id == "control-loop"
    assert resumed.generation is not None
    assert resumed.generation.cursor.slide_id == "control-loop"
    assert [event.type for event in resumed.view.events] == [
        DomainEventType.SLIDE_CHANGED,
        DomainEventType.PRESENTATION_RESUMED,
        DomainEventType.BEAT_SELECTED,
    ]
    assert resumed.view.events[0].slide_change_reason is SlideChangeReason.RESTORE


def test_verified_slide_fallback_reaches_answer_as_packaged_summary_evidence():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Explain ABS, then continue your presentation.",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)
    planning = FollowUpPlanningSession(
        deck=session.deck,
        provenance=ledger,
        context=request.context,
    )
    plan = planning.submit(
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.PRESENTATION,
            answer_brief="Explain how ABS manages pressure near wheel lock.",
            supporting_slide_ids=("braking-abs",),
            focus_slide_id="braking-abs",
        ),
        session_version=request.context.session_version,
        follow_up_turn_id=request.context.follow_up_turn_id,
    )

    accepted = session.accept_answer_plan(
        plan,
        provenance=ledger,
        search_results=planning.snapshot.search_results,
    )

    directive = accepted.generation
    assert directive is not None
    assert directive.scope_mode is ScopeMode.GROUNDED
    assert directive.grounding_source is GroundingSource.PRESENTATION
    assert directive.evidence_ids == (
        "motorcycle-controls.braking-abs.summary.0",
    )
    assert "ABS manages pressure near lock" in directive.instructions
    assert accepted.view.state.visible_slide_id == "braking-abs"


def test_focused_answer_and_continue_restores_before_resuming_once():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Explain ABS, then continue your presentation.",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)
    search = MaterialSearch(session.deck).search(
        SearchMaterialInput(
            keywords=("ABS",),
            phrases=("wheel lock",),
            slide_ids=("braking-abs",),
            include_neighbors=True,
            max_results=5,
        )
    )
    hit = next(
        candidate
        for candidate in search.hits
        if candidate.evidence_id.endswith("braking-abs.narration.3")
    )
    plan = ValidatedAnswerPlan(
        plan_id="answer-plan-live-focus",
        follow_up_turn_id=request.context.follow_up_turn_id,
        session_version=request.context.session_version,
        continuation_preference=request.context.continuation_preference,
        scope=ScopeMode.GROUNDED,
        grounding_source=GroundingSource.PRESENTATION,
        answer_brief="Explain that ABS modulates pressure near wheel lock.",
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
    assert accepted.view.state.presentation_cursor.slide_id == "control-loop"
    assert accepted.view.state.visible_slide_id == "braking-abs"
    assert accepted.view.events[0].slide_change_reason is SlideChangeReason.QUESTION

    session.playout_started(turn_id=directive.turn_id)
    resumed = session.playout_finished(
        turn_id=directive.turn_id,
        interrupted=False,
    )

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.presentation_cursor.slide_id == "control-loop"
    assert resumed.view.state.visible_slide_id == "control-loop"
    assert resumed.generation is not None
    assert resumed.generation.cursor.slide_id == "control-loop"
    assert [event.type for event in resumed.view.events] == [
        DomainEventType.ANSWER_COMPLETED,
        DomainEventType.SLIDE_CHANGED,
        DomainEventType.PRESENTATION_RESUMED,
        DomainEventType.BEAT_SELECTED,
    ]
    assert resumed.view.events[1].slide_change_reason is SlideChangeReason.RESTORE
    assert resumed.view.committed_beats == ()


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


def test_recoverable_plan_failure_creates_one_disclosed_citation_free_answer():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Does engine braking damage the clutch? Then continue.",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)
    original_cursor = request.view.state.presentation_cursor
    original_visible_slide = request.view.state.visible_slide_id

    recovered = session.recover_answer_plan(
        follow_up_turn_id=request.context.follow_up_turn_id,
        reason_code="unknown_evidence",
        provenance=ledger,
    )

    directive = recovered.generation
    assert directive is not None
    assert directive.plan_id == (
        f"recovery-plan-{request.context.follow_up_turn_id}"
    )
    assert directive.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE
    assert directive.grounding_source is GroundingSource.MODEL_KNOWLEDGE
    assert directive.supporting_turn_ids == ()
    assert directive.evidence_ids == ()
    assert "presentation support could not be validated" in directive.instructions
    assert "presentation does not contain the exact answer" not in directive.instructions
    assert "Does engine braking damage the clutch?" in directive.instructions
    assert recovered.view.planning_recovery_code == "unknown_evidence"
    assert recovered.view.planning_failure_code is None
    assert recovered.view.state.presentation_cursor == original_cursor
    assert recovered.view.state.visible_slide_id == original_visible_slide
    assert [event.type for event in recovered.view.events] == [
        DomainEventType.FOLLOW_UP_PLANNING_RECOVERED,
        DomainEventType.QUESTION_CLASSIFIED,
    ]

    session.playout_started(turn_id=directive.turn_id)
    resumed = session.playout_finished(turn_id=directive.turn_id, interrupted=False)

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.generation is not None
    assert resumed.generation.cursor == original_cursor
    assert resumed.view.committed_beats == ()


@pytest.mark.parametrize(
    ("question", "expected_scope", "expected_text"),
    [
        (
            "Why does it jerk? Then continue.",
            ScopeMode.NEEDS_CLARIFICATION,
            "Which motorcycle control or situation do you mean?",
        ),
        (
            "What exact torque should I use for my axle nut? Then continue.",
            ScopeMode.OUT_OF_SCOPE,
            "presentation boundary",
        ),
    ],
)
def test_recovered_answer_preserves_clarification_and_safety_boundaries(
    question,
    expected_scope,
    expected_text,
):
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        question,
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)

    recovered = session.recover_answer_plan(
        follow_up_turn_id=request.context.follow_up_turn_id,
        reason_code="invalid_tool_arguments",
        provenance=ledger,
    )

    directive = recovered.generation
    assert directive is not None
    assert directive.scope_mode is expected_scope
    assert directive.supporting_turn_ids == ()
    assert directive.evidence_ids == ()
    assert expected_text in directive.instructions
    assert recovered.view.state.visible_slide_id == "control-loop"

    session.playout_started(turn_id=directive.turn_id)
    settled = session.playout_finished(turn_id=directive.turn_id, interrupted=False)
    if expected_scope is ScopeMode.NEEDS_CLARIFICATION:
        assert settled.view.state.phase is PresentationPhase.WAITING
        assert settled.generation is None
    else:
        assert settled.view.state.phase is PresentationPhase.PRESENTING
        assert settled.generation is not None


@pytest.mark.parametrize(
    "reason_code",
    [
        "timeout",
        "provider_error",
        "stale_context",
        "stale_session",
        "stale_follow_up",
        "cancelled",
        "missing_tool_call",
        "multiple_tool_calls",
        "unknown_tool",
    ],
)
def test_nonrecoverable_planning_failures_cannot_create_fallback_speech(reason_code):
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Does engine braking damage the clutch?",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)

    with pytest.raises(ValueError, match="not recoverable"):
        session.recover_answer_plan(
            follow_up_turn_id=request.context.follow_up_turn_id,
            reason_code=reason_code,
            provenance=ledger,
        )

    assert session.view().state.phase is PresentationPhase.INTERRUPTED
    assert session.view().state.active_turn_id is None
    assert session.view().planning_recovery_code is None


@pytest.mark.parametrize(
    ("question", "expected_hints"),
    [
        (
            "Explain ABS, then continue.",
            [("ABS", "ABS", "exact")],
        ),
        (
            "Explain A B S, then continue.",
            [("A B S", "ABS", "spaced")],
        ),
        (
            "Explain APS, then continue.",
            [("APS", "ABS", "phonetic_neighbor")],
        ),
        ("Explain AWS, then continue.", []),
    ],
)
def test_acronym_hints_are_authored_bounded_and_preserve_transcript(
    question,
    expected_hints,
):
    session, _ = _interrupted_session()

    request = session.begin_follow_up(
        question,
        provider_item_id="provider-user-follow-up",
    )

    assert request.follow_up_turn.actual_text == question
    assert [
        (hint.observed_text, hint.authored_term, hint.match_kind)
        for hint in request.context.terminology_hints
    ] == expected_hints


def test_approximate_acronym_recovery_clarifies_instead_of_silently_rewriting():
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        "Explain APS, then continue.",
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)

    recovered = session.recover_answer_plan(
        follow_up_turn_id=request.context.follow_up_turn_id,
        reason_code="unknown_evidence",
        provenance=ledger,
    )

    directive = recovered.generation
    assert directive is not None
    assert directive.scope_mode is ScopeMode.NEEDS_CLARIFICATION
    assert "Did you mean ABS" in directive.instructions
    assert "Explain APS" in directive.instructions
    session.playout_started(turn_id=directive.turn_id)
    settled = session.playout_finished(turn_id=directive.turn_id, interrupted=False)
    assert settled.view.state.phase is PresentationPhase.WAITING
    assert settled.generation is None


@pytest.mark.parametrize(
    "question",
    [
        "Explain ABS, then continue.",
        "Explain A B S, then continue.",
    ],
)
def test_exact_authored_acronym_can_use_disclosed_citation_free_recovery(question):
    session, narration_turn_id = _interrupted_session()
    request = session.begin_follow_up(
        question,
        provider_item_id="provider-user-follow-up",
    )
    ledger = _provenance(request=request, narration_turn_id=narration_turn_id)

    recovered = session.recover_answer_plan(
        follow_up_turn_id=request.context.follow_up_turn_id,
        reason_code="invalid_tool_arguments",
        provenance=ledger,
    )

    directive = recovered.generation
    assert directive is not None
    assert directive.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE
    assert directive.grounding_source is GroundingSource.MODEL_KNOWLEDGE
    assert directive.evidence_ids == ()
    assert directive.supporting_turn_ids == ()


def test_then_narration_is_explicit_application_owned_continuation():
    session, _ = _interrupted_session()

    request = session.begin_follow_up(
        "Explain what AWS is. Then narration.",
        provider_item_id="provider-user-follow-up",
    )

    assert request.context.continuation_preference is (
        ContinuationPreference.CONTINUE_AFTER_ANSWER
    )
