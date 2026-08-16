from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.application.fake_session import FakePresentationSession
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import (
    ContinuationPreference,
    PresentationPhase,
)


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SLICE_TWO_DECK = REPOSITORY_ROOT / "content" / "slice-two.json"
SIX_SLIDE_DECK = REPOSITORY_ROOT / "assets" / "motorcycle-controls" / "slide-breakdown.json"


def new_session() -> FakePresentationSession:
    deck = JsonMaterialRepository(SLICE_TWO_DECK).load()
    return FakePresentationSession(deck, session_id="offline-session")


def test_plain_question_path_ends_waiting_with_the_beat_uncommitted():
    session = new_session()
    initial = session.view()

    assert initial.state.phase is PresentationPhase.READY
    assert initial.state.active_turn_id is None
    assert initial.transcript == ()

    presenting = session.start()
    interrupted_cursor = presenting.state.presentation_cursor
    narration_turn = presenting.state.active_turn_id
    assert presenting.state.phase is PresentationPhase.PRESENTING
    assert presenting.state.active_playout is not None

    answering = session.interrupt_and_answer(
        question="Why does engine braking feel stronger in a low gear?",
        continuation_preference=ContinuationPreference.ASK_BEFORE_CONTINUING,
    )
    assert answering.state.phase is PresentationPhase.ANSWERING
    assert answering.state.presentation_cursor == interrupted_cursor
    assert answering.state.active_turn_id != narration_turn
    assert answering.scope_mode.value == "grounded"

    waiting = session.complete_active_playout()

    assert waiting.state.phase is PresentationPhase.WAITING
    assert waiting.state.presentation_cursor == interrupted_cursor
    assert waiting.state.interrupted_cursor == interrupted_cursor
    assert waiting.state.active_playout is None
    assert [entry.role for entry in waiting.transcript] == ["agent", "user", "agent"]


def test_explicit_answer_and_continue_replays_the_same_beat_then_commits_once():
    session = new_session()
    first_narration = session.start()
    saved_cursor = first_narration.state.presentation_cursor
    first_turn = first_narration.state.active_turn_id
    session.interrupt_and_answer(
        question="Why does engine braking feel stronger in a low gear? Continue after answering.",
        continuation_preference=ContinuationPreference.CONTINUE_AFTER_ANSWER,
    )

    resumed = session.complete_active_playout()

    assert resumed.state.phase is PresentationPhase.PRESENTING
    assert resumed.state.presentation_cursor == saved_cursor
    assert resumed.state.visible_slide_id == saved_cursor.slide_id
    assert resumed.state.active_turn_id not in {None, first_turn}
    assert resumed.state.active_playout is not None
    assert resumed.state.active_playout.cursor == saved_cursor

    completed = session.complete_active_playout()
    state_after_completion = completed.state.model_copy(deep=True)

    assert completed.state.phase is PresentationPhase.COMPLETED
    assert completed.committed_beats == (saved_cursor,)
    with pytest.raises(RuntimeError):
        session.complete_active_playout()
    assert session.view().state == state_after_completion


def test_waiting_session_resumes_only_after_explicit_continue():
    session = new_session()
    session.start()
    saved_cursor = session.view().state.presentation_cursor
    session.interrupt_and_answer(
        question="Why does engine braking feel stronger in a low gear?",
        continuation_preference=ContinuationPreference.STAY_PAUSED,
    )
    session.complete_active_playout()

    resumed = session.continue_presentation()

    assert resumed.state.phase is PresentationPhase.PRESENTING
    assert resumed.state.presentation_cursor == saved_cursor
    assert resumed.state.active_playout is not None


def test_fresh_sessions_produce_the_same_script_and_transition_shape():
    snapshots = []
    for _ in range(2):
        session = new_session()
        session.start()
        session.interrupt_and_answer(
            question="Why does engine braking feel stronger in a low gear?",
            continuation_preference=ContinuationPreference.ASK_BEFORE_CONTINUING,
        )
        snapshots.append(session.complete_active_playout())

    assert [entry.text for entry in snapshots[0].transcript] == [
        entry.text for entry in snapshots[1].transcript
    ]
    assert snapshots[0].state.phase == snapshots[1].state.phase
    assert snapshots[0].state.presentation_cursor == snapshots[1].state.presentation_cursor


def test_clarification_stays_waiting_even_when_continue_was_requested():
    session = new_session()
    session.start()
    session.interrupt_and_answer(
        question="Why does it jerk? Continue after answering.",
        continuation_preference=ContinuationPreference.CONTINUE_AFTER_ANSWER,
    )

    waiting_for_clarification = session.complete_active_playout()

    assert waiting_for_clarification.scope_mode.value == "needs_clarification"
    assert waiting_for_clarification.state.phase is PresentationPhase.WAITING
    assert waiting_for_clarification.state.active_playout is None


def test_manual_browse_interrupts_fake_narration_and_resume_restores_cursor():
    deck = JsonMaterialRepository(SIX_SLIDE_DECK).load()
    session = FakePresentationSession(deck, session_id="manual-browse")
    presenting = session.start()
    cursor = presenting.state.presentation_cursor

    browsed = session.navigate_to_slide("braking-abs")

    assert browsed.state.phase is PresentationPhase.WAITING
    assert browsed.state.presentation_cursor == cursor
    assert browsed.state.interrupted_cursor == cursor
    assert browsed.state.visible_slide_id == "braking-abs"
    assert browsed.committed_beats == ()

    resumed = session.continue_presentation()

    assert resumed.state.phase is PresentationPhase.PRESENTING
    assert resumed.state.presentation_cursor == cursor
    assert resumed.state.visible_slide_id == cursor.slide_id
    assert resumed.state.active_playout is not None
    assert resumed.state.active_playout.cursor == cursor
