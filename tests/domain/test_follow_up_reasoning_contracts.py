from __future__ import annotations

import pytest
from pydantic import ValidationError

from voice_presentation.domain.contracts import ContinuationPreference, ScopeMode
from voice_presentation.domain.provenance import GroundingSource
from voice_presentation.domain.reasoning import (
    PlanningContext,
    SearchMaterialInput,
    SubmitAnswerPlanInput,
)


pytestmark = pytest.mark.offline


def test_planning_context_defaults_to_one_thirty_second_deadline():
    context = PlanningContext(
        follow_up_turn_id="user-follow-up-1",
        session_version=3,
        current_slide_id="clutch-and-gears",
        visible_slide_id="clutch-and-gears",
        continuation_preference=ContinuationPreference.STAY_PAUSED,
    )

    assert context.timeout_seconds == 30.0

    with pytest.raises(ValidationError):
        PlanningContext(
            follow_up_turn_id="user-follow-up-1",
            session_version=3,
            current_slide_id="clutch-and-gears",
            visible_slide_id="clutch-and-gears",
            continuation_preference=ContinuationPreference.STAY_PAUSED,
            timeout_seconds=60.1,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"keywords": []},
        {"keywords": [" "]},
        {"keywords": [str(index) for index in range(9)]},
        {"keywords": ["clutch"], "phrases": [str(index) for index in range(5)]},
        {"keywords": ["clutch"], "slideIds": [str(index) for index in range(7)]},
        {"keywords": ["clutch"], "maxResults": 0},
        {"keywords": ["clutch"], "maxResults": 6},
        {"keywords": ["x" * 513]},
    ],
)
def test_search_input_rejects_out_of_bounds_payloads(payload):
    with pytest.raises(ValidationError):
        SearchMaterialInput.model_validate(payload)


def test_search_input_accepts_the_documented_upper_bounds():
    request = SearchMaterialInput(
        keywords=tuple(f"keyword-{index}" for index in range(8)),
        phrases=tuple(f"phrase-{index}" for index in range(4)),
        slide_ids=tuple(f"slide-{index}" for index in range(6)),
        include_neighbors=True,
        max_results=5,
    )

    assert len(request.keywords) == 8
    assert len(request.phrases) == 4
    assert len(request.slide_ids) == 6
    assert request.include_neighbors is True


@pytest.mark.parametrize(
    "payload",
    [
        {
            "scope": "grounded",
            "groundingSource": "conversation",
            "answerBrief": "Explain the referenced statement.",
        },
        {
            "scope": "grounded",
            "groundingSource": "presentation",
            "answerBrief": "Explain the searched material.",
        },
        {
            "scope": "grounded",
            "groundingSource": "conversation_and_presentation",
            "answerBrief": "Connect the earlier statement to the searched material.",
        },
    ],
)
def test_plan_contract_requires_support_appropriate_to_scope_and_source(payload):
    with pytest.raises(ValidationError):
        SubmitAnswerPlanInput.model_validate(payload)


def test_plan_contract_accepts_all_coherent_scope_source_modes():
    plans = (
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.CONVERSATION,
            answer_brief="Explain the earlier use of response.",
            supporting_turn_ids=("narration-0002",),
            supporting_slide_ids=("control-loop",),
        ),
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.PRESENTATION,
            answer_brief="Explain partial plate contact and relative motion.",
            evidence_ids=("motorcycle-controls.clutch-and-gears.narration.1",),
            supporting_slide_ids=("clutch-and-gears",),
            focus_slide_id="clutch-and-gears",
        ),
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.CONVERSATION_AND_PRESENTATION,
            answer_brief="Connect the prior ratio statement to the deck explanation.",
            supporting_turn_ids=("narration-0002",),
            evidence_ids=("motorcycle-controls.power-to-wheel.deep_dive.0",),
            supporting_slide_ids=("power-to-wheel",),
        ),
        SubmitAnswerPlanInput(
            scope=ScopeMode.EXTENDED_KNOWLEDGE,
            grounding_source=GroundingSource.MODEL_KNOWLEDGE,
            answer_brief="Disclose the material gap, then explain the general concept.",
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
    )

    assert [plan.scope for plan in plans] == [
        ScopeMode.GROUNDED,
        ScopeMode.GROUNDED,
        ScopeMode.GROUNDED,
        ScopeMode.EXTENDED_KNOWLEDGE,
        ScopeMode.NEEDS_CLARIFICATION,
        ScopeMode.OUT_OF_SCOPE,
    ]
    assert all(
        "continuationPreference" not in plan.model_dump(mode="json", by_alias=True)
        for plan in plans
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "scope": "grounded",
            "groundingSource": "model_knowledge",
            "answerBrief": "Wrong source.",
            "supportingTurnIds": ["narration-0002"],
        },
        {
            "scope": "extended_knowledge",
            "groundingSource": "model_knowledge",
            "answerBrief": "Deck evidence must not be claimed as model-only support.",
            "evidenceIds": ["evidence-1"],
            "supportingSlideIds": ["clutch-and-gears"],
        },
        {
            "scope": "needs_clarification",
            "groundingSource": "none",
            "answerBrief": "Ask one question.",
            "clarificationPrompt": "Is it the clutch? Or the gearbox?",
        },
        {
            "scope": "out_of_scope",
            "groundingSource": "none",
            "answerBrief": "Decline.",
            "focusSlideId": "braking-abs",
            "supportingSlideIds": ["braking-abs"],
        },
        {
            "scope": "grounded",
            "groundingSource": "presentation",
            "answerBrief": "Explain the deck.",
            "evidenceIds": ["evidence-1"],
            "supportingSlideIds": ["clutch-and-gears"],
            "focusSlideId": "engine-braking",
        },
    ],
)
def test_plan_contract_rejects_incoherent_scope_source_or_focus(payload):
    with pytest.raises(ValidationError):
        SubmitAnswerPlanInput.model_validate(payload)


def test_answer_brief_and_clarification_are_bounded():
    with pytest.raises(ValidationError):
        SubmitAnswerPlanInput(
            scope=ScopeMode.GROUNDED,
            grounding_source=GroundingSource.CONVERSATION,
            answer_brief="word " * 81,
            supporting_turn_ids=("narration-0002",),
        )

    with pytest.raises(ValidationError):
        SubmitAnswerPlanInput(
            scope=ScopeMode.NEEDS_CLARIFICATION,
            grounding_source=GroundingSource.NONE,
            answer_brief="Ask one question.",
            clarification_prompt="x" * 180 + "?",
        )
