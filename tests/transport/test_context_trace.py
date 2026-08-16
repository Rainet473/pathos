from __future__ import annotations

import json

import pytest

from voice_presentation.application.live_presentation import GenerationDirective
from voice_presentation.domain.contracts import Cursor, PlayoutPurpose
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
