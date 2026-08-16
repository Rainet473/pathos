from __future__ import annotations

import pytest

from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.contracts import (
    Cursor,
    PlayoutPurpose,
    PresentationPhase,
)
from voice_presentation.domain.controller import (
    PresentationController,
    TransitionRejected,
)
from voice_presentation.domain.events import DomainEventType, SlideChangeReason


pytestmark = pytest.mark.offline


def _speaking_controller(deck_payload) -> PresentationController:
    controller = PresentationController(PresentationDeck.model_validate(deck_payload))
    cursor = controller.state.presentation_cursor
    controller.start_presentation(turn_id="narration-1")
    controller.playout_started(
        turn_id="narration-1",
        cursor=cursor,
        purpose=PlayoutPurpose.NARRATION,
    )
    return controller


def test_manual_navigation_after_interruption_waits_without_moving_cursor(deck_payload):
    controller = _speaking_controller(deck_payload)
    original_cursor = controller.state.presentation_cursor
    controller.playout_interrupted(turn_id="narration-1")

    events = controller.navigate_to_slide(slide_id="braking-abs")

    assert controller.state.phase is PresentationPhase.WAITING
    assert controller.state.presentation_cursor == original_cursor
    assert controller.state.interrupted_cursor == original_cursor
    assert controller.state.visible_slide_id == "braking-abs"
    assert controller.state.active_playout is None
    assert [event.type for event in events] == [
        DomainEventType.SLIDE_CHANGED,
        DomainEventType.PRESENTATION_WAITING,
    ]
    assert events[0].slide_change_reason is SlideChangeReason.USER


def test_repeated_manual_selection_is_idempotent_while_waiting(deck_payload):
    controller = _speaking_controller(deck_payload)
    controller.playout_interrupted(turn_id="narration-1")
    controller.navigate_to_slide(slide_id="braking-abs")
    version = controller.state.session_version

    events = controller.navigate_to_slide(slide_id="braking-abs")

    assert events == ()
    assert controller.state.session_version == version


def test_manual_navigation_rejects_unknown_slide_without_mutation(deck_payload):
    controller = _speaking_controller(deck_payload)
    controller.playout_interrupted(turn_id="narration-1")
    before = controller.state.model_copy(deep=True)

    with pytest.raises(TransitionRejected, match="unknown slide id"):
        controller.navigate_to_slide(slide_id="missing-slide")

    assert controller.state == before


def test_manual_navigation_after_completion_keeps_terminal_cursor(deck_payload):
    for slide in deck_payload["slides"]:
        slide["beats"] = [slide["beats"][0]]
    controller = _speaking_controller(deck_payload)
    first = Cursor(slide_id="engine-braking", beat_index=0)
    controller.playout_completed(turn_id="narration-1", cursor=first)
    controller.select_narration(turn_id="narration-2")
    final = Cursor(slide_id="braking-abs", beat_index=0)
    controller.playout_started(
        turn_id="narration-2",
        cursor=final,
        purpose=PlayoutPurpose.NARRATION,
    )
    controller.playout_completed(turn_id="narration-2", cursor=final)
    assert controller.state.phase is PresentationPhase.COMPLETED

    events = controller.navigate_to_slide(slide_id="engine-braking")

    assert controller.state.phase is PresentationPhase.COMPLETED
    assert controller.state.presentation_cursor == final
    assert controller.state.visible_slide_id == "engine-braking"
    assert events[0].slide_change_reason is SlideChangeReason.USER
