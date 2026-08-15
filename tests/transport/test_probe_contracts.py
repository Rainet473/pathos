from __future__ import annotations

import pytest


def _contracts():
    from voice_presentation.transport.contracts import (
        AudioFrameMetadata,
        ProbeAttempt,
        ProbePhase,
        ProbeTransitionRejected,
    )

    return AudioFrameMetadata, ProbeAttempt, ProbePhase, ProbeTransitionRejected


def _frame(attempt_id: str = "attempt-1", *, sequence: int = 0):
    AudioFrameMetadata, _, _, _ = _contracts()
    return AudioFrameMetadata(
        attempt_id=attempt_id,
        sequence=sequence,
        sample_rate_hz=48_000,
        channel_count=1,
        samples_per_channel=480,
    )


@pytest.mark.offline
def test_audio_frame_metadata_accepts_10ms_48khz_mono_frame():
    frame = _frame()

    assert frame.duration_ms == 10


@pytest.mark.offline
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("attempt_id", ""),
        ("sequence", -1),
        ("sample_rate_hz", 44_100),
        ("channel_count", 2),
        ("samples_per_channel", 0),
        ("samples_per_channel", 4_801),
    ],
)
def test_audio_frame_metadata_rejects_unsupported_or_empty_input(field, value):
    payload = {
        "attempt_id": "attempt-1",
        "sequence": 0,
        "sample_rate_hz": 48_000,
        "channel_count": 1,
        "samples_per_channel": 480,
    }
    payload[field] = value
    AudioFrameMetadata, _, _, _ = _contracts()

    with pytest.raises(ValueError):
        AudioFrameMetadata(**payload)


@pytest.mark.offline
def test_attempt_stops_and_completes_replay_at_most_once():
    _, ProbeAttempt, ProbePhase, _ = _contracts()
    attempt = ProbeAttempt(attempt_id="attempt-1")

    attempt.begin_capture(at_ms=10)
    assert attempt.accept_frame(_frame(), at_ms=20) is True
    assert attempt.stop_capture(at_ms=30) is True
    assert attempt.stop_capture(at_ms=31) is False
    assert attempt.begin_replay(at_ms=40) is True
    assert attempt.complete_replay(at_ms=50) is True
    assert attempt.complete_replay(at_ms=51) is False

    assert attempt.phase is ProbePhase.COMPLETE
    assert attempt.metrics.frame_count == 1
    assert attempt.metrics.sample_count == 480
    assert attempt.metrics.audio_duration_ms == 10


@pytest.mark.offline
def test_stale_frame_cannot_mutate_current_attempt():
    _, ProbeAttempt, ProbePhase, _ = _contracts()
    attempt = ProbeAttempt(attempt_id="attempt-current")
    attempt.begin_capture(at_ms=10)

    assert attempt.accept_frame(_frame("attempt-old"), at_ms=20) is False
    assert attempt.phase is ProbePhase.CAPTURING
    assert attempt.metrics.frame_count == 0


@pytest.mark.offline
def test_empty_capture_fails_without_replay():
    _, ProbeAttempt, ProbePhase, ProbeTransitionRejected = _contracts()
    attempt = ProbeAttempt(attempt_id="attempt-1")
    attempt.begin_capture(at_ms=10)

    with pytest.raises(ProbeTransitionRejected, match="no audio frames"):
        attempt.stop_capture(at_ms=20)

    assert attempt.phase is ProbePhase.FAILED
    assert attempt.begin_replay(at_ms=30) is False


@pytest.mark.offline
def test_disconnect_is_visible_and_same_attempt_cannot_restart():
    _, ProbeAttempt, ProbePhase, _ = _contracts()
    attempt = ProbeAttempt(attempt_id="attempt-1")
    attempt.begin_capture(at_ms=10)
    attempt.fail("room disconnected", at_ms=20)

    assert attempt.phase is ProbePhase.FAILED
    assert attempt.failure_reason == "room disconnected"
    assert attempt.begin_capture(at_ms=30) is False


@pytest.mark.offline
def test_control_signal_has_a_versioned_camel_case_wire_shape():
    from voice_presentation.transport.contracts import ProbeControlSignal, ProbeSignalType

    signal = ProbeControlSignal.model_validate_json(
        """{
          "version": 1,
          "type": "capture_stopped",
          "attemptId": "attempt-1",
          "emittedAtMs": 1234
        }"""
    )

    assert signal.type is ProbeSignalType.CAPTURE_STOPPED
    assert signal.attempt_id == "attempt-1"
    assert signal.model_dump(mode="json", by_alias=True, exclude_none=True) == {
        "version": 1,
        "type": "capture_stopped",
        "attemptId": "attempt-1",
        "emittedAtMs": 1234,
    }


@pytest.mark.offline
@pytest.mark.parametrize(
    "payload",
    [
        '{"version": 2, "type": "capture_started", "attemptId": "attempt-1", "emittedAtMs": 1}',
        '{"version": 1, "type": "unknown", "attemptId": "attempt-1", "emittedAtMs": 1}',
        '{"version": 1, "type": "capture_started", "attemptId": "", "emittedAtMs": 1}',
        '{"version": 1, "type": "capture_started", "attemptId": "attempt-1", "emittedAtMs": -1}',
    ],
)
def test_control_signal_rejects_unsupported_or_malformed_payload(payload):
    from voice_presentation.transport.contracts import ProbeControlSignal

    with pytest.raises(ValueError):
        ProbeControlSignal.model_validate_json(payload)
