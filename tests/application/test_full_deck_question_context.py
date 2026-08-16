from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import PresentationPhase
from voice_presentation.domain.events import DomainEventType, SlideChangeReason


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIX_SLIDE_DECK = REPOSITORY_ROOT / "assets" / "motorcycle-controls" / "slide-breakdown.json"


def test_full_deck_question_slide_is_temporary_and_cursor_restores_before_resume():
    deck = JsonMaterialRepository(SIX_SLIDE_DECK).load()
    session = ApplicationPresentationSession(deck, session_id="question-context")
    narration = session.start().generation
    assert narration is not None
    original_cursor = narration.cursor
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)

    answer = session.prepare_question(
        "Does ABS increase grip? Continue after answering."
    )

    assert answer.view.state.presentation_cursor == original_cursor
    assert answer.view.state.visible_slide_id == "braking-abs"
    assert any(
        event.type is DomainEventType.SLIDE_CHANGED
        and event.slide_change_reason is SlideChangeReason.QUESTION
        for event in answer.view.events
    )
    assert answer.generation is not None
    session.playout_started(turn_id=answer.generation.turn_id)
    resumed = session.playout_finished(
        turn_id=answer.generation.turn_id,
        interrupted=False,
    )

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.presentation_cursor == original_cursor
    assert resumed.view.state.visible_slide_id == original_cursor.slide_id
    assert resumed.generation is not None
    assert resumed.generation.cursor == original_cursor
    assert any(
        event.type is DomainEventType.SLIDE_CHANGED
        and event.slide_change_reason is SlideChangeReason.RESTORE
        for event in resumed.view.events
    )


def test_manual_browse_sets_question_preference_but_full_deck_search_can_override_it():
    deck = JsonMaterialRepository(SIX_SLIDE_DECK).load()
    session = ApplicationPresentationSession(deck, session_id="manual-context")
    narration = session.start().generation
    assert narration is not None
    original_cursor = narration.cursor
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)

    browsed = session.navigate_to_slide("braking-abs")
    assert browsed.view.state.phase is PresentationPhase.WAITING
    assert browsed.view.state.presentation_cursor == original_cursor
    assert browsed.view.state.visible_slide_id == "braking-abs"

    answer = session.prepare_question("Why does a motorcycle need a clutch?")

    assert answer.view.scope_mode.value == "grounded"
    assert answer.view.state.presentation_cursor == original_cursor
    assert answer.view.state.visible_slide_id == "clutch-and-gears"
    assert answer.generation is not None
    assert "clutch provides a controllable connection" in answer.generation.instructions


def test_browsing_abandons_answer_and_continue_then_replays_preserved_narration():
    deck = JsonMaterialRepository(SIX_SLIDE_DECK).load()
    session = ApplicationPresentationSession(deck, session_id="answer-browse")
    narration = session.start().generation
    assert narration is not None
    original_cursor = narration.cursor
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)
    answer = session.prepare_question(
        "Does ABS increase grip? Continue after answering."
    )
    assert answer.generation is not None
    session.playout_started(turn_id=answer.generation.turn_id)
    session.playout_finished(turn_id=answer.generation.turn_id, interrupted=True)

    browsed = session.navigate_to_slide("power-to-wheel")

    assert browsed.view.state.phase is PresentationPhase.WAITING
    assert browsed.view.state.presentation_cursor == original_cursor
    assert browsed.view.state.visible_slide_id == "power-to-wheel"
    assert browsed.view.state.continuation_preference is None
    assert browsed.view.state.answer_return_phase is None

    late = session.playout_finished(
        turn_id=answer.generation.turn_id,
        interrupted=False,
    )
    assert late.generation is None
    assert [event.type for event in late.view.events] == [
        DomainEventType.STALE_RESPONSE_DISCARDED
    ]

    resumed = session.continue_presentation()
    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.presentation_cursor == original_cursor
    assert resumed.view.state.visible_slide_id == original_cursor.slide_id
    assert resumed.generation is not None
    assert resumed.generation.cursor == original_cursor
