from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.offline


class SequenceClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class RecordingLedger:
    def __init__(self) -> None:
        self.events: list[object] = []

    def record(self, event: object) -> None:
        self.events.append(event)


def test_lifecycle_diagnostics_record_raw_states_without_inventing_latency():
    from voice_presentation.transport.diagnostics import ConversationDiagnostics

    ledger = RecordingLedger()
    diagnostics = ConversationDiagnostics(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        ledger=ledger,
        clock=SequenceClock(10.0, 10.4, 10.6, 11.9, 12.0, 12.32),
    )

    diagnostics.record_user_state(old_state="listening", new_state="speaking")
    diagnostics.record_user_state(old_state="speaking", new_state="listening")
    diagnostics.record_agent_state(old_state="listening", new_state="thinking")
    speaking = diagnostics.record_agent_state(
        old_state="thinking", new_state="speaking"
    )
    diagnostics.record_user_state(old_state="listening", new_state="speaking")
    interrupted = diagnostics.record_agent_state(
        old_state="speaking", new_state="listening"
    )

    assert [event.sequence for event in ledger.events] == [1, 2, 3, 4, 5, 6]
    assert speaking.fields == {"oldState": "thinking", "newState": "speaking"}
    assert interrupted.fields == {"oldState": "speaking", "newState": "listening"}
    assert all(event.attempt_id == diagnostics.attempt_id for event in ledger.events)


def test_provider_metrics_are_normalized_without_transcript_or_credentials():
    from voice_presentation.transport.diagnostics import ConversationDiagnostics

    ledger = RecordingLedger()
    diagnostics = ConversationDiagnostics(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        ledger=ledger,
        clock=SequenceClock(20.0, 20.1),
    )
    realtime = SimpleNamespace(
        type="realtime_model_metrics",
        ttft=1.234,
        duration=2.5,
        cancelled=False,
        input_tokens=42,
        output_tokens=11,
        total_tokens=53,
        acquire_time=0.07,
        connection_reused=True,
        input_token_details=SimpleNamespace(cached_tokens=9),
    )
    endpointing = SimpleNamespace(
        type="eou_metrics",
        end_of_utterance_delay=4.8,
        transcription_delay=0.3,
        on_user_turn_completed_delay=0.02,
    )

    realtime_event = diagnostics.record_metrics(realtime)
    endpointing_event = diagnostics.record_metrics(endpointing)

    assert realtime_event.fields == {
        "modelTtftMs": 1234,
        "modelDurationMs": 2500,
        "cancelled": False,
        "inputTokens": 42,
        "outputTokens": 11,
        "totalTokens": 53,
        "cachedInputTokens": 9,
        "connectionAcquireMs": 70,
        "connectionReused": True,
    }
    assert endpointing_event.fields == {
        "endOfUtteranceDelayMs": 4800,
        "transcriptionDelayMs": 300,
        "turnCallbackDelayMs": 20,
    }
    assert "transcript" not in realtime_event.to_json().lower()
    assert "key" not in realtime_event.to_json().lower()


def test_consecutive_response_metrics_derive_only_the_response_start_gap():
    from voice_presentation.transport.diagnostics import ConversationDiagnostics

    diagnostics = ConversationDiagnostics(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        clock=SequenceClock(10.0, 10.4, 20.0, 30.0),
    )
    diagnostics.record_user_state(old_state="listening", new_state="speaking")

    empty_connection_metric = SimpleNamespace(
        type="realtime_model_metrics",
        ttft=-1,
        duration=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
    )
    first_response = SimpleNamespace(
        type="realtime_model_metrics",
        ttft=1.2,
        duration=2.0,
        input_tokens=20,
        output_tokens=10,
        total_tokens=30,
    )
    second_response = SimpleNamespace(
        type="realtime_model_metrics",
        ttft=0.8,
        duration=3.0,
        input_tokens=25,
        output_tokens=12,
        total_tokens=37,
    )

    diagnostics.record_metrics(empty_connection_metric)
    first = diagnostics.record_metrics(first_response)
    second = diagnostics.record_metrics(second_response)

    assert "providerResponseStartGapMs" not in first.fields
    assert second.fields["providerResponseStartGapMs"] == 7000


def test_pipeline_metrics_keep_endpoint_llm_tts_and_interruption_stages_distinct():
    from voice_presentation.transport.diagnostics import ConversationDiagnostics

    diagnostics = ConversationDiagnostics(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        clock=SequenceClock(10.0, 10.1, 10.2, 10.3),
    )
    endpoint = diagnostics.record_metrics(
        SimpleNamespace(
            type="eou_metrics",
            end_of_utterance_delay=0.65,
            transcription_delay=0.2,
            on_user_turn_completed_delay=0.03,
        )
    )
    llm = diagnostics.record_metrics(
        SimpleNamespace(
            type="llm_metrics",
            ttft=0.42,
            duration=1.5,
            cancelled=False,
            prompt_tokens=80,
            completion_tokens=18,
            total_tokens=98,
            prompt_cached_tokens=12,
            tokens_per_second=36.0,
        )
    )
    tts = diagnostics.record_metrics(
        SimpleNamespace(
            type="tts_metrics",
            ttfb=0.18,
            duration=1.2,
            audio_duration=2.4,
            cancelled=False,
            characters_count=72,
            streamed=True,
            acquire_time=0.04,
            connection_reused=True,
        )
    )
    interruption = diagnostics.record_metrics(
        SimpleNamespace(
            type="interruption_metrics",
            detection_delay=0.11,
            prediction_duration=0.05,
            total_duration=0.16,
            num_interruptions=1,
            num_backchannels=0,
            num_requests=1,
        )
    )

    assert endpoint.fields["endOfUtteranceDelayMs"] == 650
    assert llm.fields == {
        "llmTtftMs": 420,
        "modelDurationMs": 1500,
        "cancelled": False,
        "inputTokens": 80,
        "outputTokens": 18,
        "totalTokens": 98,
        "cachedInputTokens": 12,
        "tokensPerSecond": 36.0,
    }
    assert tts.fields == {
        "ttsTtfbMs": 180,
        "modelDurationMs": 1200,
        "audioDurationMs": 2400,
        "cancelled": False,
        "charactersCount": 72,
        "streamed": True,
        "connectionAcquireMs": 40,
        "connectionReused": True,
    }
    assert interruption.fields == {
        "interruptionDetectionDelayMs": 110,
        "interruptionPredictionMs": 50,
        "interruptionDurationMs": 160,
        "numInterruptions": 1,
        "numBackchannels": 0,
        "numRequests": 1,
    }


def test_jsonl_diagnostic_ledger_is_append_only_and_attempt_scoped(tmp_path):
    from voice_presentation.transport.diagnostics import (
        ConversationDiagnosticEvent,
        JsonlConversationDiagnosticLedger,
    )

    path = tmp_path / "conversation-diagnostics.jsonl"
    ledger = JsonlConversationDiagnosticLedger(path)
    event = ConversationDiagnosticEvent(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        sequence=1,
        event_type="agent_state_changed",
        elapsed_ms=125,
        fields={"oldState": "thinking", "newState": "speaking"},
    )

    ledger.record(event)
    ledger.record(event.model_copy(update={"sequence": 2, "elapsed_ms": 250}))

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[0] == {
        "attemptId": event.attempt_id,
        "sequence": 1,
        "eventType": "agent_state_changed",
        "elapsedMs": 125,
        "fields": {"oldState": "thinking", "newState": "speaking"},
        "version": 1,
    }
