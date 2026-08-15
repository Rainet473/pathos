from __future__ import annotations

import pytest

from voice_presentation.domain.contracts import Cursor, PlayoutPurpose
from voice_presentation.voice.fake import (
    DeterministicFakeVoiceRuntime,
    FakeRuntimeTransitionRejected,
)
from voice_presentation.voice.runtime import (
    PlayoutRequest,
    VoiceEventType,
)


pytestmark = pytest.mark.offline


def narration_request(turn_id: str = "narration-1") -> PlayoutRequest:
    return PlayoutRequest(
        turn_id=turn_id,
        cursor=Cursor(slide_id="engine-braking", beat_index=0),
        purpose=PlayoutPurpose.NARRATION,
        text="Lower gears make engine braking feel stronger because of the gear ratio.",
    )


def test_fake_runtime_is_quiet_and_advertises_only_its_real_capabilities():
    runtime = DeterministicFakeVoiceRuntime()

    assert runtime.active_playout is None
    assert runtime.event_log == ()
    assert runtime.capabilities.audio_output is False
    assert runtime.capabilities.reliable_playout_completion is True
    assert runtime.capabilities.native_barge_in is False
    assert runtime.capabilities.semantic_turn_detection is False


def test_fake_runtime_emits_explicit_started_and_completed_lifecycle():
    runtime = DeterministicFakeVoiceRuntime()
    request = narration_request()

    started = runtime.start_playout(request)
    completed = runtime.complete_playout(turn_id=request.turn_id)

    assert started.type is VoiceEventType.PLAYOUT_STARTED
    assert completed.type is VoiceEventType.PLAYOUT_COMPLETED
    assert started.request == request
    assert completed.request == request
    assert runtime.active_playout is None
    assert [event.type for event in runtime.event_log] == [
        VoiceEventType.PLAYOUT_STARTED,
        VoiceEventType.PLAYOUT_COMPLETED,
    ]


def test_fake_runtime_interruption_never_synthesizes_completion():
    runtime = DeterministicFakeVoiceRuntime()
    request = narration_request()
    runtime.start_playout(request)

    interrupted = runtime.interrupt_playout(turn_id=request.turn_id)

    assert interrupted.type is VoiceEventType.PLAYOUT_INTERRUPTED
    assert runtime.active_playout is None
    with pytest.raises(FakeRuntimeTransitionRejected):
        runtime.complete_playout(turn_id=request.turn_id)
    assert VoiceEventType.PLAYOUT_COMPLETED not in {
        event.type for event in runtime.event_log
    }


def test_fake_runtime_rejects_overlapping_or_wrong_turn_playout():
    runtime = DeterministicFakeVoiceRuntime()
    runtime.start_playout(narration_request())

    with pytest.raises(FakeRuntimeTransitionRejected):
        runtime.start_playout(narration_request(turn_id="narration-2"))
    with pytest.raises(FakeRuntimeTransitionRejected):
        runtime.complete_playout(turn_id="old-turn")

    assert runtime.active_playout == narration_request()
