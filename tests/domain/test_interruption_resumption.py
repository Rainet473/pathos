from __future__ import annotations

from importlib import import_module

import pytest


pytestmark = pytest.mark.offline


def create_interrupted_controller(deck_payload):
    content = import_module("voice_presentation.domain.content")
    contracts = import_module("voice_presentation.domain.contracts")
    controller_module = import_module("voice_presentation.domain.controller")
    controller = controller_module.PresentationController(
        content.PresentationDeck.model_validate(deck_payload)
    )
    controller.start_presentation(turn_id="narration-1")
    controller.playout_started(
        turn_id="narration-1",
        cursor=controller.state.presentation_cursor,
        purpose=contracts.PlayoutPurpose.NARRATION,
    )
    controller.playout_interrupted(turn_id="narration-1")
    return contracts, controller_module, controller


def event_types(events) -> list[str]:
    return [getattr(event.type, "value", event.type) for event in events]


def test_plain_question_waits_and_preserves_interrupted_cursor(deck_payload):
    contracts, _, controller = create_interrupted_controller(deck_payload)
    saved_cursor = controller.state.interrupted_cursor
    controller.begin_answer(
        turn_id="answer-1",
        continuation_preference=contracts.ContinuationPreference.ASK_BEFORE_CONTINUING,
        question_slide_id="braking-abs",
    )
    controller.playout_started(
        turn_id="answer-1",
        cursor=saved_cursor,
        purpose=contracts.PlayoutPurpose.ANSWER,
    )

    events = controller.answer_completed(turn_id="answer-1")

    assert controller.state.phase is contracts.PresentationPhase.WAITING
    assert controller.state.presentation_cursor == saved_cursor
    assert controller.state.interrupted_cursor == saved_cursor
    assert controller.state.visible_slide_id == "braking-abs"
    assert event_types(events) == ["answer_completed", "presentation_waiting"]


def test_answer_and_continue_restores_slide_and_replays_same_beat(deck_payload):
    contracts, _, controller = create_interrupted_controller(deck_payload)
    saved_cursor = controller.state.interrupted_cursor
    controller.begin_answer(
        turn_id="answer-1",
        continuation_preference=contracts.ContinuationPreference.CONTINUE_AFTER_ANSWER,
        question_slide_id="braking-abs",
    )
    controller.playout_started(
        turn_id="answer-1",
        cursor=saved_cursor,
        purpose=contracts.PlayoutPurpose.ANSWER,
    )

    events = controller.answer_completed(
        turn_id="answer-1", resume_turn_id="narration-2"
    )

    assert controller.state.phase is contracts.PresentationPhase.PRESENTING
    assert controller.state.presentation_cursor == saved_cursor
    assert controller.state.visible_slide_id == saved_cursor.slide_id
    assert controller.state.active_turn_id == "narration-2"
    assert "presentation_resumed" in event_types(events)
    assert "beat_selected" in event_types(events)


def test_explicit_continue_from_waiting_restores_original_slide(deck_payload):
    contracts, _, controller = create_interrupted_controller(deck_payload)
    saved_cursor = controller.state.interrupted_cursor
    controller.begin_answer(
        turn_id="answer-1",
        continuation_preference=contracts.ContinuationPreference.STAY_PAUSED,
        question_slide_id="braking-abs",
    )
    controller.playout_started(
        turn_id="answer-1",
        cursor=saved_cursor,
        purpose=contracts.PlayoutPurpose.ANSWER,
    )
    controller.answer_completed(turn_id="answer-1")

    events = controller.continue_presentation(turn_id="narration-2")

    assert controller.state.phase is contracts.PresentationPhase.PRESENTING
    assert controller.state.presentation_cursor == saved_cursor
    assert controller.state.visible_slide_id == saved_cursor.slide_id
    assert controller.state.active_turn_id == "narration-2"
    assert "presentation_resumed" in event_types(events)


def test_interruption_during_answer_keeps_original_resume_cursor(deck_payload):
    contracts, _, controller = create_interrupted_controller(deck_payload)
    saved_cursor = controller.state.interrupted_cursor
    controller.begin_answer(
        turn_id="answer-1",
        continuation_preference=contracts.ContinuationPreference.ASK_BEFORE_CONTINUING,
    )
    controller.playout_started(
        turn_id="answer-1",
        cursor=saved_cursor,
        purpose=contracts.PlayoutPurpose.ANSWER,
    )

    controller.playout_interrupted(turn_id="answer-1")

    assert controller.state.interrupted_cursor == saved_cursor
    assert controller.state.presentation_cursor == saved_cursor


def test_invalid_question_slide_is_rejected_without_mutation(deck_payload):
    contracts, controller_module, controller = create_interrupted_controller(deck_payload)
    state_before = controller.state.model_copy(deep=True)

    with pytest.raises(controller_module.TransitionRejected):
        controller.begin_answer(
            turn_id="answer-1",
            continuation_preference=contracts.ContinuationPreference.ASK_BEFORE_CONTINUING,
            question_slide_id="not-a-slide",
        )

    assert controller.state == state_before


def test_continue_before_start_is_rejected(deck_payload):
    content = import_module("voice_presentation.domain.content")
    controller_module = import_module("voice_presentation.domain.controller")
    controller = controller_module.PresentationController(
        content.PresentationDeck.model_validate(deck_payload)
    )

    with pytest.raises(controller_module.TransitionRejected):
        controller.continue_presentation(turn_id="narration-1")
