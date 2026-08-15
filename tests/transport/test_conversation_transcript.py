from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from voice_presentation.transport.transcript import (
    CONVERSATION_TRANSCRIPT_TOPIC,
    ConversationTranscriptEntry,
    ConversationTranscriptUpdate,
)


pytestmark = pytest.mark.offline


def test_transcript_update_has_provider_neutral_camel_case_wire_shape():
    update = ConversationTranscriptUpdate(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        sequence=3,
        emitted_at=datetime(2026, 8, 16, 8, 30, tzinfo=UTC),
        entry=ConversationTranscriptEntry(
            id="user-2",
            role="user",
            text="Why does a lower gear slow the bike more?",
            final=True,
        ),
    )

    assert CONVERSATION_TRANSCRIPT_TOPIC == "voice-conversation.transcript.v1"
    assert update.model_dump(mode="json", by_alias=True) == {
        "version": 1,
        "attemptId": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        "sequence": 3,
        "emittedAt": "2026-08-16T08:30:00Z",
        "entry": {
            "id": "user-2",
            "role": "user",
            "text": "Why does a lower gear slow the bike more?",
            "final": True,
        },
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("attempt_id", ""),
        ("sequence", 0),
        ("entry", {"id": "", "role": "user", "text": "hello", "final": True}),
        ("entry", {"id": "user-1", "role": "tool", "text": "hello", "final": True}),
        ("entry", {"id": "user-1", "role": "user", "text": "   ", "final": True}),
    ],
)
def test_transcript_update_rejects_invalid_identity_sequence_role_and_text(
    field: str,
    value: object,
):
    payload: dict[str, object] = {
        "attempt_id": "9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        "sequence": 1,
        "emitted_at": datetime.now(UTC),
        "entry": {
            "id": "user-1",
            "role": "user",
            "text": "hello",
            "final": True,
        },
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ConversationTranscriptUpdate.model_validate(payload)
