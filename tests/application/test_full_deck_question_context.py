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
SIX_SLIDE_DECK = REPOSITORY_ROOT / "content" / "motorcycle-controls.json"


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
