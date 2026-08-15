from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    PlayoutPurpose,
    PresentationPhase,
)
from voice_presentation.domain.events import DomainEventType


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SLICE_TWO_DECK = REPOSITORY_ROOT / "content" / "slice-two.json"


def new_session() -> ApplicationPresentationSession:
    deck = JsonMaterialRepository(SLICE_TWO_DECK).load()
    return ApplicationPresentationSession(deck, session_id="live-session")


def event_types(result) -> list[DomainEventType]:
    return [event.type for event in result.view.events]


def test_start_selects_one_bounded_narration_without_committing_it():
    session = new_session()

    result = session.start()

    assert result.view.state.phase is PresentationPhase.PRESENTING
    assert result.view.state.active_playout is None
    assert result.generation is not None
    assert result.generation.purpose is PlayoutPurpose.NARRATION
    assert result.generation.cursor == result.view.state.presentation_cursor
    assert "Low gears make engine braking feel stronger" in result.generation.instructions
    assert "closed throttle" in result.generation.instructions
    assert result.view.committed_beats == ()


def test_interrupted_grounded_question_waits_and_preserves_the_uncommitted_beat():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)

    interrupted = session.playout_finished(
        turn_id=narration.turn_id,
        interrupted=True,
    )

    assert interrupted.view.state.phase is PresentationPhase.INTERRUPTED
    assert interrupted.view.committed_beats == ()
    saved_cursor = interrupted.view.state.presentation_cursor

    answer = session.prepare_question(
        "Why does engine braking feel stronger in a low gear?"
    )

    assert answer.view.state.phase is PresentationPhase.ANSWERING
    assert answer.view.state.presentation_cursor == saved_cursor
    assert answer.view.state.continuation_preference is (
        ContinuationPreference.ASK_BEFORE_CONTINUING
    )
    assert answer.generation is not None
    assert answer.generation.purpose is PlayoutPurpose.ANSWER
    assert "lower gear makes the engine turn faster" in answer.generation.instructions
    assert DomainEventType.QUESTION_CLASSIFIED in event_types(answer)

    session.playout_started(turn_id=answer.generation.turn_id)
    waiting = session.playout_finished(
        turn_id=answer.generation.turn_id,
        interrupted=False,
    )

    assert waiting.view.state.phase is PresentationPhase.WAITING
    assert waiting.view.state.presentation_cursor == saved_cursor
    assert waiting.view.committed_beats == ()
    assert waiting.generation is None


def test_explicit_answer_and_continue_replays_the_same_beat_with_a_new_turn():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)
    saved_cursor = session.view().state.presentation_cursor

    answer = session.prepare_question(
        "Why does engine braking feel stronger in a low gear? Continue after answering."
    )

    assert answer.view.state.continuation_preference is (
        ContinuationPreference.CONTINUE_AFTER_ANSWER
    )
    assert answer.generation is not None
    session.playout_started(turn_id=answer.generation.turn_id)
    resumed = session.playout_finished(
        turn_id=answer.generation.turn_id,
        interrupted=False,
    )

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.presentation_cursor == saved_cursor
    assert resumed.generation is not None
    assert resumed.generation.purpose is PlayoutPurpose.NARRATION
    assert resumed.generation.cursor == saved_cursor
    assert resumed.generation.turn_id not in {
        narration.turn_id,
        answer.generation.turn_id,
    }


def test_explicit_continue_from_waiting_replays_the_saved_beat():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)
    saved_cursor = session.view().state.presentation_cursor
    answer = session.prepare_question(
        "Why does engine braking feel stronger in a low gear?"
    )
    assert answer.generation is not None
    session.playout_started(turn_id=answer.generation.turn_id)
    session.playout_finished(
        turn_id=answer.generation.turn_id,
        interrupted=False,
    )

    resumed = session.continue_presentation()

    assert resumed.view.state.phase is PresentationPhase.PRESENTING
    assert resumed.view.state.presentation_cursor == saved_cursor
    assert resumed.generation is not None
    assert resumed.generation.cursor == saved_cursor


def test_late_completion_for_an_interrupted_turn_is_stale_and_cannot_commit():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)
    interrupted = session.playout_finished(
        turn_id=narration.turn_id,
        interrupted=True,
    )
    state_after_interruption = interrupted.view.state

    late = session.playout_finished(
        turn_id=narration.turn_id,
        interrupted=False,
    )

    assert late.view.state == state_after_interruption
    assert late.view.committed_beats == ()
    assert event_types(late) == [DomainEventType.STALE_RESPONSE_DISCARDED]


def test_blank_question_is_rejected_before_state_mutation():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)
    session.playout_finished(turn_id=narration.turn_id, interrupted=True)
    state_before = session.view().state

    with pytest.raises(ValueError, match="question cannot be blank"):
        session.prepare_question("   ")

    assert session.view().state == state_before


def test_full_narration_playout_commits_once_and_completes_the_fixture():
    session = new_session()
    narration = session.start().generation
    assert narration is not None
    session.playout_started(turn_id=narration.turn_id)

    completed = session.playout_finished(
        turn_id=narration.turn_id,
        interrupted=False,
    )

    assert completed.view.state.phase is PresentationPhase.COMPLETED
    assert completed.view.committed_beats == (narration.cursor,)
    assert event_types(completed) == [
        DomainEventType.BEAT_COMMITTED,
        DomainEventType.PRESENTATION_COMPLETED,
    ]

    duplicate = session.playout_finished(
        turn_id=narration.turn_id,
        interrupted=False,
    )
    assert duplicate.view.committed_beats == (narration.cursor,)
    assert event_types(duplicate) == [DomainEventType.STALE_RESPONSE_DISCARDED]
