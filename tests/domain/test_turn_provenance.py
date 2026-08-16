from __future__ import annotations

import pytest

from voice_presentation.domain.provenance import (
    GroundingSource,
    LogicalTurn,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
    format_turn_reference,
)


pytestmark = pytest.mark.offline


def _pending_narration() -> LogicalTurn:
    return LogicalTurn(
        turn_id="narration-0002",
        role=TurnRole.ASSISTANT,
        purpose=TurnPurpose.NARRATION,
        session_version=2,
        slide_id="control-loop",
        beat_index=1,
        delivery_status=TurnDeliveryStatus.PENDING,
    )


def test_interrupted_turn_retains_only_runtime_supplied_actual_text():
    ledger = LogicalTurnLedger(session_version=2)
    ledger.register(_pending_narration())

    delivered = ledger.record_actual_text(
        turn_id="narration-0002",
        provider_item_id="provider-assistant-2",
        actual_text="Every input changes the motorcycle through",
        interrupted=True,
        session_version=2,
    )

    assert delivered.delivery_status is TurnDeliveryStatus.INTERRUPTED
    assert delivered.actual_text == "Every input changes the motorcycle through"
    assert delivered.provider_item_ids == ("provider-assistant-2",)
    assert ledger.resolve_provider_item("provider-assistant-2") == delivered

    refined = ledger.record_actual_text(
        turn_id="narration-0002",
        provider_item_id="provider-assistant-2b",
        actual_text="Every input changes the motorcycle through the drivetrain",
        interrupted=True,
        session_version=2,
    )
    assert refined.delivery_status is TurnDeliveryStatus.INTERRUPTED
    assert refined.actual_text == (
        "Every input changes the motorcycle through the drivetrain"
    )
    assert refined.provider_item_ids == (
        "provider-assistant-2",
        "provider-assistant-2b",
    )

    with pytest.raises(ValueError, match="terminal interrupted turn"):
        ledger.record_actual_text(
            turn_id="narration-0002",
            provider_item_id="provider-assistant-2",
            actual_text=(
                "Every input changes the motorcycle through forces at the road."
            ),
            interrupted=False,
            session_version=2,
        )


def test_turn_and_provider_registration_are_idempotent_but_conflicts_fail():
    ledger = LogicalTurnLedger(session_version=4)
    user_turn = LogicalTurn(
        turn_id="user-follow-up-0003",
        role=TurnRole.USER,
        purpose=TurnPurpose.USER_FOLLOW_UP,
        session_version=4,
        visible_slide_id="control-loop",
        interrupted_turn_id="narration-0002",
        provider_item_ids=("provider-user-3",),
        actual_text="What kind of response do you mean?",
        delivery_status=TurnDeliveryStatus.COMPLETED,
    )

    assert ledger.register(user_turn) == user_turn
    assert ledger.register(user_turn) == user_turn
    assert ledger.resolve("user-follow-up-0003") == user_turn
    assert ledger.resolve_provider_item("provider-user-3") == user_turn

    conflicting = user_turn.model_copy(
        update={"actual_text": "What response?"}
    )
    with pytest.raises(ValueError, match="conflicting logical turn"):
        ledger.register(conflicting)

    with pytest.raises(ValueError, match="already belongs"):
        ledger.register(
            LogicalTurn(
                turn_id="user-follow-up-0004",
                role=TurnRole.USER,
                purpose=TurnPurpose.USER_FOLLOW_UP,
                session_version=4,
                provider_item_ids=("provider-user-3",),
                actual_text="Another follow-up",
                delivery_status=TurnDeliveryStatus.COMPLETED,
            )
        )


def test_citations_resolve_only_through_the_application_ledger():
    ledger = LogicalTurnLedger(session_version=7)
    narration = _pending_narration().model_copy(
        update={"session_version": 7}
    )
    ledger.register(narration)

    assert ledger.require_turn_ids(("narration-0002",)) == (narration,)
    with pytest.raises(ValueError, match="unknown logical turn"):
        ledger.require_turn_ids(("provider-assistant-2",))
    with pytest.raises(ValueError, match="session version"):
        ledger.record_actual_text(
            turn_id="narration-0002",
            provider_item_id="provider-assistant-2",
            actual_text="Partial text",
            interrupted=True,
            session_version=6,
        )


def test_turn_reference_is_compact_deterministic_metadata():
    turn = LogicalTurn(
        turn_id="answer-0008",
        role=TurnRole.ASSISTANT,
        purpose=TurnPurpose.ANSWER,
        session_version=8,
        provider_item_ids=("provider-answer-8",),
        actual_text="Partial contact transfers some torque while slip remains.",
        delivery_status=TurnDeliveryStatus.COMPLETED,
        plan_id="answer-plan-0008",
        scope_mode="grounded",
        grounding_source=GroundingSource.PRESENTATION,
    )

    assert format_turn_reference(turn) == (
        "Turn reference: answer-0008; purpose=answer; plan=answer-plan-0008; "
        "scope=grounded; source=presentation."
    )
    assert "Turn reference:" not in turn.actual_text


@pytest.mark.parametrize(
    ("role", "purpose"),
    [
        (TurnRole.USER, TurnPurpose.NARRATION),
        (TurnRole.USER, TurnPurpose.ANSWER),
        (TurnRole.ASSISTANT, TurnPurpose.USER_FOLLOW_UP),
    ],
)
def test_role_and_purpose_must_be_coherent(role: TurnRole, purpose: TurnPurpose):
    with pytest.raises(ValueError, match="role and purpose"):
        LogicalTurn(
            turn_id="invalid-0001",
            role=role,
            purpose=purpose,
            session_version=1,
            actual_text="Text",
            delivery_status=TurnDeliveryStatus.COMPLETED,
        )
