from __future__ import annotations

import json

import pytest

from voice_presentation.application.live_presentation import GenerationDirective
from voice_presentation.domain.contracts import Cursor, PlayoutPurpose
from voice_presentation.domain.provenance import (
    LogicalTurn,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
)
from voice_presentation.transport.context_trace import (
    InferenceContextTrace,
    JsonlInferenceContextLedger,
)


pytestmark = pytest.mark.offline


class RecordingLedger:
    def __init__(self) -> None:
        self.records = []

    def record(self, record) -> None:
        self.records.append(record)


def _directive(purpose: PlayoutPurpose, instructions: str) -> GenerationDirective:
    return GenerationDirective(
        turn_id=f"{purpose.value}-7",
        cursor=Cursor(slide_id="engine-braking", beat_index=1),
        purpose=purpose,
        instructions=instructions,
    )


def test_context_trace_records_exact_role_order_for_narration_and_answer():
    ledger = RecordingLedger()
    trace = InferenceContextTrace(
        attempt_id="attempt-1",
        stable_instructions="Stable application prompt.",
        ledger=ledger,
    )
    trace.add_history_message(
        provider_item_id="assistant-interrupted",
        role="assistant",
        content="The clutch transfers...",
        interrupted=True,
    )

    trace.record_generation(
        _directive(PlayoutPurpose.NARRATION, "Narrate beat two exactly."),
    )
    trace.record_generation(
        _directive(PlayoutPurpose.ANSWER, "Answer from selected evidence."),
        current_user_message="Why does a lower gear raise RPM?",
    )

    narration, answer = ledger.records
    assert narration.stable_instructions == "Stable application prompt."
    assert [(item.role, item.content) for item in narration.messages] == [
        ("assistant", "The clutch transfers..."),
        ("system", "Narrate beat two exactly."),
    ]
    assert narration.messages[0].interrupted is True
    assert [(item.role, item.content) for item in answer.messages] == [
        ("assistant", "The clutch transfers..."),
        ("developer", "Answer from selected evidence."),
        ("user", "Why does a lower gear raise RPM?"),
    ]


def test_context_trace_deduplicates_provider_items_and_jsonl_is_readable(tmp_path):
    path = tmp_path / "context.jsonl"
    trace = InferenceContextTrace(
        attempt_id="attempt-2",
        stable_instructions="Stable prompt.",
        ledger=JsonlInferenceContextLedger(path),
    )
    trace.add_history_message(
        provider_item_id="user-1", role="user", content="First version"
    )
    trace.add_history_message(
        provider_item_id="user-1", role="user", content="Final version"
    )
    trace.record_generation(
        _directive(PlayoutPurpose.NARRATION, "Narrate now."),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["attemptId"] == "attempt-2"
    assert payload["fidelity"] == "application_livekit_chat_context"
    assert [item["content"] for item in payload["messages"]] == [
        "Final version",
        "Narrate now.",
    ]


def test_context_trace_builds_reasoning_snapshot_from_actual_retained_turn_text():
    trace = InferenceContextTrace(
        attempt_id="attempt-3",
        stable_instructions="Stable prompt.",
    )
    trace.record_generation(
        _directive(PlayoutPurpose.NARRATION, "Narrate the clutch beat."),
    )
    trace.add_history_message(
        provider_item_id="assistant-1",
        role="assistant",
        content="The clutch transfers engine torque to the gearbox.",
        interrupted=True,
        logical_turn_id="narration-7",
    )
    trace.register_follow_up(
        LogicalTurn(
            turn_id="follow-up-8",
            role=TurnRole.USER,
            purpose=TurnPurpose.USER_FOLLOW_UP,
            session_version=3,
            visible_slide_id="engine-braking",
            interrupted_turn_id="narration-7",
            provider_item_ids=("user-1",),
            actual_text="What does that mean?",
            delivery_status=TurnDeliveryStatus.COMPLETED,
        )
    )

    snapshot = trace.reasoning_snapshot(session_version=3)

    assert [turn.turn_id for turn in snapshot.turns] == [
        "narration-7",
        "follow-up-8",
    ]
    assert snapshot.turns[1].interrupted_turn_id == "narration-7"
    assert trace.logical_turn_id_for_provider("assistant-1") == "narration-7"
    assert trace.logical_turn_id_for_provider("user-1") == "follow-up-8"
    messages = snapshot.model_context_items()
    assert [item.content for item in messages if hasattr(item, "content")] == [
        "Stable prompt.",
        "Turn reference: narration-7; purpose=narration; "
        "slide=engine-braking; beat=2.",
        "The clutch transfers engine torque to the gearbox.",
        "Turn reference: follow-up-8; purpose=user_follow_up; "
        "visible_slide=engine-braking; interrupted_turn=narration-7.",
        "What does that mean?",
    ]


def test_context_trace_does_not_invent_missing_interrupted_narration():
    trace = InferenceContextTrace(
        attempt_id="attempt-4",
        stable_instructions="Stable prompt.",
    )
    trace.record_generation(
        _directive(PlayoutPurpose.NARRATION, "Narrate the clutch beat."),
    )
    trace.register_follow_up(
        LogicalTurn(
            turn_id="follow-up-8",
            role=TurnRole.USER,
            purpose=TurnPurpose.USER_FOLLOW_UP,
            session_version=4,
            interrupted_turn_id="narration-7",
            actual_text="Could you explain that?",
            delivery_status=TurnDeliveryStatus.COMPLETED,
        )
    )

    snapshot = trace.reasoning_snapshot(session_version=4)

    assert [turn.turn_id for turn in snapshot.turns] == ["follow-up-8"]
    assert snapshot.turns[0].interrupted_turn_id is None
    assert "narration-7" not in snapshot.to_json()
