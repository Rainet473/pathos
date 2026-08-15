from __future__ import annotations

from importlib import import_module

import pytest


pytestmark = pytest.mark.offline


def domain_modules():
    return (
        import_module("voice_presentation.domain.content"),
        import_module("voice_presentation.domain.contracts"),
        import_module("voice_presentation.domain.controller"),
    )


def event_types(events) -> list[str]:
    return [getattr(event.type, "value", event.type) for event in events]


def started_controller(deck_payload, *, turn_id: str = "narration-1"):
    content, contracts, controller_module = domain_modules()
    controller = controller_module.PresentationController(
        content.PresentationDeck.model_validate(deck_payload)
    )
    controller.start_presentation(turn_id=turn_id)
    controller.playout_started(
        turn_id=turn_id,
        cursor=controller.state.presentation_cursor,
        purpose=contracts.PlayoutPurpose.NARRATION,
    )
    return contracts, controller_module, controller


def test_start_selects_first_beat_without_committing_it(deck_payload):
    content, contracts, controller_module = domain_modules()
    controller = controller_module.PresentationController(
        content.PresentationDeck.model_validate(deck_payload)
    )

    events = controller.start_presentation(turn_id="narration-1")

    assert controller.state.phase is contracts.PresentationPhase.PRESENTING
    assert controller.state.presentation_cursor == contracts.Cursor(
        slide_id="engine-braking", beat_index=0
    )
    assert event_types(events) == ["presentation_started", "beat_selected"]


def test_matching_playout_completion_commits_exactly_one_beat(deck_payload):
    contracts, _, controller = started_controller(deck_payload)
    active_cursor = controller.state.presentation_cursor

    events = controller.playout_completed(
        turn_id="narration-1", cursor=active_cursor
    )

    assert "beat_committed" in event_types(events)
    assert controller.state.presentation_cursor == contracts.Cursor(
        slide_id="engine-braking", beat_index=1
    )


def test_interrupted_playout_keeps_active_beat_uncommitted(deck_payload):
    contracts, _, controller = started_controller(deck_payload)
    active_cursor = controller.state.presentation_cursor

    events = controller.playout_interrupted(turn_id="narration-1")

    assert event_types(events) == ["playout_interrupted"]
    assert controller.state.presentation_cursor == active_cursor
    assert controller.state.interrupted_cursor == active_cursor
    assert controller.state.phase is contracts.PresentationPhase.INTERRUPTED


def test_duplicate_completion_cannot_advance_twice(deck_payload):
    _, _, controller = started_controller(deck_payload)
    active_cursor = controller.state.presentation_cursor
    controller.playout_completed(turn_id="narration-1", cursor=active_cursor)
    state_after_first_completion = controller.state.model_copy(deep=True)

    events = controller.playout_completed(
        turn_id="narration-1", cursor=active_cursor
    )

    assert controller.state == state_after_first_completion
    assert event_types(events) == ["stale_response_discarded"]


def test_late_completion_from_superseded_turn_is_discarded(deck_payload):
    _, _, controller = started_controller(deck_payload)
    interrupted_cursor = controller.state.presentation_cursor
    controller.playout_interrupted(turn_id="narration-1")
    controller.begin_answer(
        turn_id="answer-1",
        continuation_preference="ask_before_continuing",
    )
    state_before_late_event = controller.state.model_copy(deep=True)

    events = controller.playout_completed(
        turn_id="narration-1", cursor=interrupted_cursor
    )

    assert controller.state == state_before_late_event
    assert event_types(events) == ["stale_response_discarded"]


def test_final_beat_completion_finishes_presentation(deck_payload):
    contracts, _, controller = started_controller(deck_payload, turn_id="narration-1")

    for index, turn_id in enumerate(("narration-1", "narration-2", "narration-3", "narration-4")):
        if index:
            controller.playout_started(
                turn_id=turn_id,
                cursor=controller.state.presentation_cursor,
                purpose=contracts.PlayoutPurpose.NARRATION,
            )
        cursor = controller.state.presentation_cursor
        events = controller.playout_completed(turn_id=turn_id, cursor=cursor)

    assert controller.state.phase is contracts.PresentationPhase.COMPLETED
    assert "presentation_completed" in event_types(events)
