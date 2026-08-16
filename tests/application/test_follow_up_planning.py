from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.follow_up_planning import (
    DeterministicPlannerHarness,
    FollowUpPlanningSession,
    PlanningProtocolError,
    RecordedPlanningSuite,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.contracts import PresentationPhase, ScopeMode
from voice_presentation.domain.controller import PresentationController
from voice_presentation.domain.provenance import GroundingSource
from voice_presentation.domain.reasoning import (
    PlanningRejectionCode,
    PlanningStatus,
    SearchMaterialInput,
    SubmitAnswerPlanInput,
)
from voice_presentation.transport.context_trace import (
    ApplicationDecisionTrace,
    FunctionCallTrace,
    FunctionResultTrace,
    ReasoningContextSnapshot,
)


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DECK_PATH = REPOSITORY_ROOT / "assets/motorcycle-controls/slide-breakdown.json"
CONTEXT_FIXTURE = (
    REPOSITORY_ROOT / "tests/fixtures/question-reasoning-turn-10.json"
)
PLANNER_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/follow-up-planner-actions.json"


def _deck():
    return JsonMaterialRepository(DECK_PATH).load()


def _context_snapshot() -> ReasoningContextSnapshot:
    return ReasoningContextSnapshot.model_validate_json(
        CONTEXT_FIXTURE.read_text(encoding="utf-8")
    )


def _suite() -> RecordedPlanningSuite:
    return RecordedPlanningSuite.model_validate_json(
        PLANNER_FIXTURE.read_text(encoding="utf-8")
    )


def _case(name: str):
    return next(case for case in _suite().cases if case.name == name)


def _conversation_plan() -> SubmitAnswerPlanInput:
    return SubmitAnswerPlanInput(
        scope=ScopeMode.GROUNDED,
        grounding_source=GroundingSource.CONVERSATION,
        answer_brief="Clarify the response described by the interrupted narration.",
        supporting_turn_ids=("narration-0002",),
        supporting_slide_ids=("control-loop",),
    )


def test_recorded_conversation_and_search_cases_complete_with_traceable_plans():
    snapshot = _context_snapshot()
    harness = DeterministicPlannerHarness(deck=_deck(), provenance=snapshot.ledger)

    conversation = harness.run(_case("conversation-citation"))
    material = harness.run(_case("material-search"))

    assert conversation.status is PlanningStatus.ACCEPTED
    assert conversation.accepted_plan is not None
    assert conversation.accepted_plan.grounding_source is GroundingSource.CONVERSATION
    assert conversation.accepted_plan.supporting_turn_ids == ("narration-0002",)
    assert [type(entry) for entry in conversation.trace] == [
        FunctionCallTrace,
        FunctionResultTrace,
        ApplicationDecisionTrace,
    ]

    assert material.status is PlanningStatus.ACCEPTED
    assert material.accepted_plan is not None
    assert material.accepted_plan.grounding_source is GroundingSource.PRESENTATION
    assert material.accepted_plan.evidence_ids == (
        "motorcycle-controls.clutch-and-gears.narration.1",
    )
    assert material.accepted_plan.focus_slide_id == "clutch-and-gears"
    searched_ids = {
        hit.evidence_id
        for result in material.search_results
        for hit in result.hits
    }
    assert set(material.accepted_plan.evidence_ids) <= searched_ids
    assert [entry.name for entry in material.trace if hasattr(entry, "name")] == [
        "search_material",
        "search_material",
        "submit_answer_plan",
        "submit_answer_plan",
    ]

    assert harness.run(_case("conversation-citation")).to_json() == (
        conversation.to_json()
    )
    assert harness.run(_case("material-search")).to_json() == material.to_json()


def test_planning_never_mutates_presentation_controller_state():
    deck = _deck()
    controller = PresentationController(deck)
    before = controller.state.model_copy(deep=True)
    harness = DeterministicPlannerHarness(
        deck=deck,
        provenance=_context_snapshot().ledger,
    )

    result = harness.run(_case("material-search"))

    assert result.accepted_plan is not None
    assert controller.state == before
    assert controller.state.phase is PresentationPhase.READY


@pytest.mark.parametrize(
    ("plan", "code"),
    [
        (
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.CONVERSATION,
                answer_brief="Cite a missing turn.",
                supporting_turn_ids=("missing-turn",),
            ),
            PlanningRejectionCode.UNKNOWN_TURN,
        ),
        (
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.PRESENTATION,
                answer_brief="Cite evidence that was never searched.",
                evidence_ids=("motorcycle-controls.clutch-and-gears.narration.1",),
                supporting_slide_ids=("clutch-and-gears",),
            ),
            PlanningRejectionCode.UNKNOWN_EVIDENCE,
        ),
        (
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.CONVERSATION,
                answer_brief="Cite an unknown slide.",
                supporting_turn_ids=("narration-0002",),
                supporting_slide_ids=("missing-slide",),
            ),
            PlanningRejectionCode.UNKNOWN_SLIDE,
        ),
        (
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.CONVERSATION,
                answer_brief="Cite a turn after the active follow-up.",
                supporting_turn_ids=("answer-0004",),
            ),
            PlanningRejectionCode.INELIGIBLE_TURN,
        ),
        (
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.CONVERSATION,
                answer_brief="Propose an unrelated focus slide.",
                supporting_turn_ids=("narration-0002",),
                supporting_slide_ids=("braking-abs",),
                focus_slide_id="braking-abs",
            ),
            PlanningRejectionCode.INCOHERENT_PLAN,
        ),
    ],
)
def test_invalid_plan_ids_reject_terminally_without_controller_side_effects(plan, code):
    deck = _deck()
    controller = PresentationController(deck)
    before = controller.state.model_copy(deep=True)
    session = FollowUpPlanningSession(
        deck=deck,
        provenance=_context_snapshot().ledger,
        context=_case("conversation-citation").context,
    )

    with pytest.raises(PlanningProtocolError) as caught:
        session.submit(
            plan,
            session_version=10,
            follow_up_turn_id="user-follow-up-0003",
        )

    assert caught.value.code is code
    assert session.snapshot.status is PlanningStatus.REJECTED
    assert session.snapshot.accepted_plan is None
    assert controller.state == before


def test_explicit_current_slide_evidence_can_ground_a_zero_search_plan():
    deck = _deck()
    supplied = MaterialSearch(deck).search(
        SearchMaterialInput(
            keywords=("engine braking", "lower gear", "engine speed"),
            phrases=("lower gear",),
            slide_ids=("engine-braking",),
            max_results=1,
        )
    ).hits[0]
    base_context = _case("conversation-citation").context
    context = base_context.model_copy(
        update={
            "current_slide_id": "engine-braking",
            "visible_slide_id": "engine-braking",
            "current_slide_evidence": (supplied,),
        }
    )
    session = FollowUpPlanningSession(
        deck=deck,
        provenance=_context_snapshot().ledger,
        context=context,
    )

    accepted = session.submit(
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.PRESENTATION,
            answer_brief="Explain why a lower gear strengthens engine braking.",
            evidence_ids=(supplied.evidence_id,),
            supporting_slide_ids=("engine-braking",),
            focus_slide_id="engine-braking",
        ),
        session_version=10,
        follow_up_turn_id="user-follow-up-0003",
    )

    assert accepted.evidence_ids == (supplied.evidence_id,)
    assert session.snapshot.search_calls == 0


def test_evidence_is_scoped_to_the_same_planning_session():
    snapshot = _context_snapshot()
    search_case = _case("material-search")
    first = FollowUpPlanningSession(
        deck=_deck(),
        provenance=snapshot.ledger,
        context=search_case.context,
    )
    search = first.search(
        SearchMaterialInput(
            keywords=("clutch", "friction zone", "partial engagement"),
            phrases=("friction zone",),
            slide_ids=("clutch-and-gears",),
        ),
        session_version=10,
        follow_up_turn_id="user-follow-up-0007",
    )
    evidence_id = search.hits[0].evidence_id

    second = FollowUpPlanningSession(
        deck=_deck(),
        provenance=snapshot.ledger,
        context=search_case.context,
    )
    with pytest.raises(PlanningProtocolError) as caught:
        second.submit(
            SubmitAnswerPlanInput(
                scope=ScopeMode.GROUNDED,
                grounding_source=GroundingSource.PRESENTATION,
                answer_brief="Attempt to reuse another planning turn's evidence.",
                evidence_ids=(evidence_id,),
                supporting_slide_ids=("clutch-and-gears",),
            ),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.UNKNOWN_EVIDENCE


def test_combined_grounding_requires_and_accepts_both_support_kinds():
    session = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=_case("conversation-citation").context,
    )
    search = session.search(
        SearchMaterialInput(
            keywords=("lower gear", "mechanical advantage", "engine speed"),
            phrases=("lower gear",),
            slide_ids=("power-to-wheel",),
            max_results=1,
        ),
        session_version=10,
        follow_up_turn_id="user-follow-up-0003",
    )
    evidence = search.hits[0]

    accepted = session.submit(
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.CONVERSATION_AND_PRESENTATION,
            answer_brief="Connect the earlier ratio reference to the deck explanation.",
            supporting_turn_ids=("narration-0002",),
            evidence_ids=(evidence.evidence_id,),
            supporting_slide_ids=(evidence.slide_id,),
            focus_slide_id=evidence.slide_id,
        ),
        session_version=10,
        follow_up_turn_id="user-follow-up-0003",
    )

    assert accepted.grounding_source is (
        GroundingSource.CONVERSATION_AND_PRESENTATION
    )
    assert accepted.supporting_turn_ids == ("narration-0002",)
    assert accepted.evidence_ids == (evidence.evidence_id,)


@pytest.mark.parametrize(
    "plan",
    [
        SubmitAnswerPlanInput(
            scope=ScopeMode.EXTENDED_KNOWLEDGE,
            grounding_source=GroundingSource.MODEL_KNOWLEDGE,
            answer_brief="Disclose the deck gap, then explain the general concept.",
            supporting_slide_ids=("clutch-and-gears",),
        ),
        SubmitAnswerPlanInput(
            scope=ScopeMode.NEEDS_CLARIFICATION,
            grounding_source=GroundingSource.NONE,
            answer_brief="Ask which jerk the listener means.",
            supporting_turn_ids=("narration-0002",),
            clarification_prompt="Do you mean clutch engagement or a downshift?",
        ),
        SubmitAnswerPlanInput(
            scope=ScopeMode.OUT_OF_SCOPE,
            grounding_source=GroundingSource.NONE,
            answer_brief="Redirect the exact repair value to the service manual.",
        ),
    ],
)
def test_non_grounded_modes_validate_without_claiming_deck_evidence(plan):
    session = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=_case("conversation-citation").context,
    )

    accepted = session.submit(
        plan,
        session_version=10,
        follow_up_turn_id="user-follow-up-0003",
    )

    assert accepted.scope is plan.scope
    assert accepted.evidence_ids == ()
    assert accepted.continuation_preference.value == "continue_after_answer"


def test_stale_session_and_follow_up_cancel_before_any_tool_step():
    context = _case("conversation-citation").context
    request = SearchMaterialInput(keywords=("clutch",))

    stale_version = FollowUpPlanningSession(
        deck=_deck(), provenance=_context_snapshot().ledger, context=context
    )
    with pytest.raises(PlanningProtocolError) as caught:
        stale_version.search(
            request,
            session_version=9,
            follow_up_turn_id="user-follow-up-0003",
        )
    assert caught.value.code is PlanningRejectionCode.STALE_SESSION
    assert stale_version.snapshot.status is PlanningStatus.CANCELLED
    assert stale_version.snapshot.tool_steps == 0

    stale_turn = FollowUpPlanningSession(
        deck=_deck(), provenance=_context_snapshot().ledger, context=context
    )
    with pytest.raises(PlanningProtocolError) as caught:
        stale_turn.search(
            request,
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.STALE_FOLLOW_UP
    assert stale_turn.snapshot.status is PlanningStatus.CANCELLED


def test_cancellation_after_search_blocks_terminal_plan_and_is_idempotent():
    context = _case("material-search").context
    session = FollowUpPlanningSession(
        deck=_deck(), provenance=_context_snapshot().ledger, context=context
    )
    session.search(
        SearchMaterialInput(keywords=("clutch", "friction zone")),
        session_version=10,
        follow_up_turn_id="user-follow-up-0007",
    )

    cancelled = session.cancel(PlanningRejectionCode.CANCELLED)
    assert session.cancel(PlanningRejectionCode.CANCELLED) == cancelled
    with pytest.raises(PlanningProtocolError) as caught:
        session.submit(
            _conversation_plan(),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.CANCELLED
    assert session.snapshot.accepted_plan is None


def test_timeout_before_and_during_search_is_controlled():
    now = [100.0]
    context = _case("material-search").context
    before = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=context,
        clock=lambda: now[0],
    )
    now[0] = 111.0
    with pytest.raises(PlanningProtocolError) as caught:
        before.search(
            SearchMaterialInput(keywords=("clutch",)),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.TIMEOUT
    assert before.snapshot.status is PlanningStatus.CANCELLED

    now[0] = 200.0

    class SlowSearch:
        def __init__(self):
            self._search = MaterialSearch(_deck())

        def search(self, request, *, preferred_slide_id=None):
            result = self._search.search(
                request, preferred_slide_id=preferred_slide_id
            )
            now[0] = 211.0
            return result

    during = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=context,
        search=SlowSearch(),
        clock=lambda: now[0],
    )
    with pytest.raises(PlanningProtocolError) as caught:
        during.search(
            SearchMaterialInput(keywords=("clutch",)),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.TIMEOUT
    assert during.snapshot.search_results == ()


def test_cancellation_and_stale_identity_during_search_discard_the_result():
    context = _case("material-search").context
    holder = {}

    class CancellingSearch:
        def search(self, request, *, preferred_slide_id=None):
            result = MaterialSearch(_deck()).search(
                request, preferred_slide_id=preferred_slide_id
            )
            holder["session"].cancel()
            return result

    cancelling = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=context,
        search=CancellingSearch(),
    )
    holder["session"] = cancelling
    with pytest.raises(PlanningProtocolError) as caught:
        cancelling.search(
            SearchMaterialInput(keywords=("clutch",)),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.CANCELLED
    assert cancelling.snapshot.search_results == ()

    active_identity = [10, "user-follow-up-0007"]

    class StaleSearch:
        def search(self, request, *, preferred_slide_id=None):
            result = MaterialSearch(_deck()).search(
                request, preferred_slide_id=preferred_slide_id
            )
            active_identity[0] = 11
            return result

    stale = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=context,
        search=StaleSearch(),
        active_identity=lambda: (active_identity[0], active_identity[1]),
    )
    with pytest.raises(PlanningProtocolError) as caught:
        stale.search(
            SearchMaterialInput(keywords=("clutch",)),
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.STALE_SESSION
    assert stale.snapshot.search_results == ()


def test_search_and_terminal_step_limits_and_duplicate_terminal_are_bounded():
    context = _case("material-search").context
    session = FollowUpPlanningSession(
        deck=_deck(), provenance=_context_snapshot().ledger, context=context
    )
    request = SearchMaterialInput(keywords=("clutch",))
    for _ in range(2):
        session.search(
            request,
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    with pytest.raises(PlanningProtocolError) as caught:
        session.search(
            request,
            session_version=10,
            follow_up_turn_id="user-follow-up-0007",
        )
    assert caught.value.code is PlanningRejectionCode.SEARCH_LIMIT
    assert session.snapshot.accepted_plan is None

    accepted_session = FollowUpPlanningSession(
        deck=_deck(),
        provenance=_context_snapshot().ledger,
        context=_case("conversation-citation").context,
    )
    accepted = accepted_session.submit(
        _conversation_plan(),
        session_version=10,
        follow_up_turn_id="user-follow-up-0003",
    )
    with pytest.raises(PlanningProtocolError) as caught:
        accepted_session.submit(
            _conversation_plan(),
            session_version=10,
            follow_up_turn_id="user-follow-up-0003",
        )
    assert caught.value.code is PlanningRejectionCode.DUPLICATE_TERMINAL
    assert accepted_session.snapshot.accepted_plan == accepted
    assert accepted_session.snapshot.status is PlanningStatus.ACCEPTED


def test_harness_rejects_missing_terminal_and_records_rejected_plan_decision():
    harness = DeterministicPlannerHarness(
        deck=_deck(), provenance=_context_snapshot().ledger
    )
    material_case = _case("material-search")
    missing_terminal = material_case.model_copy(
        update={
            "name": "missing-terminal",
            "actions": (material_case.actions[0],),
        }
    )

    missing = harness.run(missing_terminal)

    assert missing.status is PlanningStatus.REJECTED
    assert missing.rejection_code is PlanningRejectionCode.MISSING_TERMINAL
    assert missing.accepted_plan is None
    assert [type(entry) for entry in missing.trace] == [
        FunctionCallTrace,
        FunctionResultTrace,
        ApplicationDecisionTrace,
    ]
    missing_decision = missing.trace[-1]
    assert isinstance(missing_decision, ApplicationDecisionTrace)
    assert missing_decision.accepted is False
    assert missing_decision.reason_code == "missing_terminal"

    invalid_plan = SubmitAnswerPlanInput(
        scope=ScopeMode.GROUNDED,
        grounding_source=GroundingSource.PRESENTATION,
        answer_brief="Cite evidence that was not searched in this planning turn.",
        evidence_ids=("motorcycle-controls.clutch-and-gears.narration.1",),
        supporting_slide_ids=("clutch-and-gears",),
    )
    rejected_action = material_case.actions[1].model_copy(
        update={"input": invalid_plan}
    )
    rejected_case = material_case.model_copy(
        update={
            "name": "rejected-plan",
            "actions": (rejected_action,),
        }
    )

    rejected = harness.run(rejected_case)

    assert rejected.status is PlanningStatus.REJECTED
    assert rejected.rejection_code is PlanningRejectionCode.UNKNOWN_EVIDENCE
    assert [type(entry) for entry in rejected.trace] == [
        FunctionCallTrace,
        FunctionResultTrace,
        ApplicationDecisionTrace,
    ]
    decision = rejected.trace[-1]
    assert isinstance(decision, ApplicationDecisionTrace)
    assert decision.accepted is False
    assert decision.reason_code == "unknown_evidence"
