from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import PresentationPhase
from voice_presentation.domain.events import DomainEventType


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIX_SLIDE_DECK = REPOSITORY_ROOT / "assets" / "motorcycle-controls" / "slide-breakdown.json"


def _deck():
    return JsonMaterialRepository(SIX_SLIDE_DECK).load()


def test_live_application_automatically_selects_all_24_narration_beats():
    session = ApplicationPresentationSession(_deck(), session_id="six-slide-live")
    result = session.start()
    generated_cursors = []

    while result.generation is not None:
        generation = result.generation
        generated_cursors.append(generation.cursor)
        session.playout_started(turn_id=generation.turn_id)
        result = session.playout_finished(
            turn_id=generation.turn_id,
            interrupted=False,
        )
        if result.generation is not None:
            assert DomainEventType.BEAT_SELECTED in {
                event.type for event in result.view.events
            }

    assert result.view.state.phase is PresentationPhase.COMPLETED
    assert result.view.committed_beats == tuple(generated_cursors)
    assert len(generated_cursors) == 24
    assert [cursor.slide_id for cursor in generated_cursors[::4]] == [
        "control-loop",
        "clutch-and-gears",
        "power-to-wheel",
        "engine-braking",
        "rev-matching",
        "braking-abs",
    ]


def test_duplicate_completion_cannot_select_a_second_successor_turn():
    session = ApplicationPresentationSession(_deck(), session_id="duplicate-live")
    first = session.start().generation
    assert first is not None
    session.playout_started(turn_id=first.turn_id)
    selected_next = session.playout_finished(
        turn_id=first.turn_id,
        interrupted=False,
    )
    state_after_first_completion = selected_next.view.state
    assert selected_next.generation is not None

    duplicate = session.playout_finished(
        turn_id=first.turn_id,
        interrupted=False,
    )

    assert duplicate.view.state == state_after_first_completion
    assert duplicate.generation is None
    assert [event.type for event in duplicate.view.events] == [
        DomainEventType.STALE_RESPONSE_DISCARDED
    ]
