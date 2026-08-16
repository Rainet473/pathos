from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from voice_presentation.adapters.livekit.context_format import (
    reasoning_context_to_livekit,
)
from voice_presentation.transport.context_trace import (
    ApplicationDecisionTrace,
    FunctionCallTrace,
    FunctionResultTrace,
    ReasoningContextSnapshot,
    TurnMessageTrace,
)


pytestmark = pytest.mark.offline

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "question-reasoning-turn-10.json"
)


def _snapshot() -> ReasoningContextSnapshot:
    return ReasoningContextSnapshot.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )


def test_turn_ten_fixture_round_trips_deterministically_and_resolves_citations():
    snapshot = _snapshot()
    canonical = snapshot.to_json()

    assert ReasoningContextSnapshot.model_validate_json(canonical).to_json() == canonical
    assert len(snapshot.turns) == 10
    assert snapshot.ledger.require_turn_ids(
        ("narration-0002", "narration-0006")
    ) == (snapshot.turns[1], snapshot.turns[5])

    decisions = [
        entry
        for entry in snapshot.trace
        if isinstance(entry, ApplicationDecisionTrace)
    ]
    assert [decision.plan_id for decision in decisions] == [
        "answer-plan-0004",
        "answer-plan-0008",
    ]
    assert all(decision.accepted for decision in decisions)


def test_context_expansion_keeps_annotations_adjacent_and_messages_plain():
    items = _snapshot().model_context_items()

    first_turn_index = next(
        index
        for index, item in enumerate(items)
        if getattr(item, "content", "").startswith("Turn reference: narration-0001")
    )
    annotation = items[first_turn_index]
    message = items[first_turn_index + 1]
    assert annotation.role == "developer"
    assert message.role == "assistant"
    assert message.logical_turn_id == "narration-0001"
    assert "Turn reference:" not in message.content

    interrupted = next(
        item
        for item in items
        if getattr(item, "logical_turn_id", None) == "narration-0002"
    )
    assert interrupted.content == "Every input creates a response through the drivetrain or brakes"
    assert interrupted.interrupted is True


def test_native_tool_items_and_application_decisions_have_distinct_trace_shapes():
    snapshot = _snapshot()
    calls = [entry for entry in snapshot.trace if isinstance(entry, FunctionCallTrace)]
    results = [
        entry for entry in snapshot.trace if isinstance(entry, FunctionResultTrace)
    ]
    decisions = [
        entry
        for entry in snapshot.trace
        if isinstance(entry, ApplicationDecisionTrace)
    ]

    assert [call.name for call in calls] == [
        "submit_answer_plan",
        "search_material",
        "submit_answer_plan",
    ]
    assert [result.call_id for result in results] == [
        "call-plan-0004",
        "call-search-0007-1",
        "call-plan-0008",
    ]
    assert all(decision.reason_code == "accepted" for decision in decisions)
    assert all(decision.type == "application_decision" for decision in decisions)

    payload = json.loads(snapshot.to_json())
    assert payload["trace"][3]["type"] == "function_call"
    assert payload["trace"][4]["type"] == "function_result"
    assert payload["trace"][5]["type"] == "application_decision"


def test_unknown_decision_citation_and_out_of_order_result_are_rejected():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["trace"][5]["supportingTurnIds"] = ["provider-assistant-2"]
    with pytest.raises(ValidationError, match="unknown logical turn"):
        ReasoningContextSnapshot.model_validate(payload)

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["trace"][3], payload["trace"][4] = (
        payload["trace"][4],
        payload["trace"][3],
    )
    with pytest.raises(ValidationError, match="before its function call"):
        ReasoningContextSnapshot.model_validate(payload)


def test_installed_livekit_formatter_preserves_roles_and_native_tool_records():
    chat_context = reasoning_context_to_livekit(_snapshot())
    formatted, _ = chat_context.to_provider_format(format="openai")

    interrupted = next(
        item
        for item in chat_context.items
        if getattr(item, "id", None) == "provider-assistant-2"
    )
    assert interrupted.interrupted is True
    assert interrupted.text_content == (
        "Every input creates a response through the drivetrain or brakes"
    )

    assert [item["role"] for item in formatted[:9]] == [
        "system",
        "developer",
        "assistant",
        "developer",
        "assistant",
        "developer",
        "user",
        "assistant",
        "tool",
    ]
    assert formatted[1]["content"].startswith("Turn reference: narration-0001")
    assert formatted[2]["content"] == (
        "Motorcycle controls form a loop from rider input to tyre force and feedback."
    )
    assert formatted[7]["tool_calls"][0]["function"]["name"] == (
        "submit_answer_plan"
    )
    assert formatted[8]["tool_call_id"] == "call-plan-0004"

    plain_messages = [
        item["content"]
        for item in formatted
        if item["role"] in {"user", "assistant"} and "content" in item
    ]
    assert all("Turn reference:" not in content for content in plain_messages)
    assert all(item["role"] != "application" for item in formatted)


def test_trace_entry_types_are_discriminated():
    snapshot = _snapshot()
    assert isinstance(snapshot.trace[0], TurnMessageTrace)
    assert isinstance(snapshot.trace[3], FunctionCallTrace)
    assert isinstance(snapshot.trace[4], FunctionResultTrace)
    assert isinstance(snapshot.trace[5], ApplicationDecisionTrace)
