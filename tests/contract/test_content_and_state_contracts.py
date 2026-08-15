from __future__ import annotations

from importlib import import_module

import pytest


pytestmark = pytest.mark.offline


def content_module():
    return import_module("voice_presentation.domain.content")


def contracts_module():
    return import_module("voice_presentation.domain.contracts")


def test_valid_deck_preserves_ordered_semantic_beats(deck_payload):
    content = content_module()

    deck = content.PresentationDeck.model_validate(deck_payload)

    assert [slide.id for slide in deck.slides] == ["engine-braking", "braking-abs"]
    assert [beat.id for beat in deck.slides[0].beats] == [
        "reduced-driving-torque",
        "low-gear-effect",
    ]
    assert deck.slides[0].beats[1].required_concepts == (
        "gear ratio",
        "stronger low-gear effect",
    )


def test_deck_rejects_duplicate_slide_ids(copied_deck_payload):
    content = content_module()
    payload = copied_deck_payload()
    payload["slides"][1]["id"] = "engine-braking"

    with pytest.raises(ValueError, match="duplicate slide id"):
        content.PresentationDeck.model_validate(payload)


def test_slide_rejects_duplicate_beat_ids(copied_deck_payload):
    content = content_module()
    payload = copied_deck_payload()
    payload["slides"][0]["beats"][1]["id"] = "reduced-driving-torque"

    with pytest.raises(ValueError, match="duplicate beat id"):
        content.PresentationDeck.model_validate(payload)


def test_slide_rejects_an_empty_beat_sequence(copied_deck_payload):
    content = content_module()
    payload = copied_deck_payload()
    payload["slides"][0]["beats"] = []

    with pytest.raises(ValueError):
        content.PresentationDeck.model_validate(payload)


def test_ready_state_keeps_cursor_and_visible_slide_separate():
    contracts = contracts_module()
    cursor = contracts.Cursor(slide_id="engine-braking", beat_index=0)

    state = contracts.PresentationState(
        session_version=0,
        phase=contracts.PresentationPhase.READY,
        presentation_cursor=cursor,
        visible_slide_id="braking-abs",
    )

    assert state.presentation_cursor.slide_id == "engine-braking"
    assert state.visible_slide_id == "braking-abs"
    assert state.active_playout is None
    assert state.interrupted_cursor is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("slide_id", ""), ("beat_index", -1)],
)
def test_cursor_rejects_invalid_identity_or_position(field, value):
    contracts = contracts_module()
    payload = {"slide_id": "engine-braking", "beat_index": 0, field: value}

    with pytest.raises(ValueError):
        contracts.Cursor(**payload)


def test_contract_enums_expose_stable_wire_values():
    contracts = contracts_module()

    assert contracts.PresentationPhase.READY.value == "ready"
    assert contracts.PresentationPhase.PRESENTING.value == "presenting"
    assert contracts.ContinuationPreference.ASK_BEFORE_CONTINUING.value == "ask_before_continuing"
    assert contracts.ContinuationPreference.CONTINUE_AFTER_ANSWER.value == "continue_after_answer"
    assert contracts.ScopeMode.EXTENDED_KNOWLEDGE.value == "extended_knowledge"
