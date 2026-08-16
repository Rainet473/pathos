from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.offline


def _event(
    *,
    attempt_id: str,
    sequence: int,
    event_type: str,
    fields: dict[str, object],
) -> str:
    return json.dumps(
        {
            "attemptId": attempt_id,
            "sequence": sequence,
            "eventType": event_type,
            "elapsedMs": sequence * 100,
            "fields": fields,
            "version": 1,
        }
    )


def test_summary_separates_search_latency_cache_and_answer_pipeline_metrics(tmp_path):
    from voice_presentation.transport.reasoning_evidence import (
        summarize_reasoning_evidence,
    )

    path = tmp_path / "diagnostics.jsonl"
    rows = [
        _event(
            attempt_id="attempt-a",
            sequence=1,
            event_type="follow_up_planning",
            fields={
                "planningDurationMs": 1000,
                "planningSearchCalls": 0,
                "planningStatus": "accepted",
                "planningInputTokens": 1000,
                "planningCachedInputTokens": 400,
            },
        ),
        _event(
            attempt_id="attempt-a",
            sequence=2,
            event_type="follow_up_planning",
            fields={
                "planningDurationMs": 3000,
                "planningSearchCalls": 1,
                "planningStatus": "accepted",
                "planningInputTokens": 2000,
                "planningCachedInputTokens": 0,
            },
        ),
        _event(
            attempt_id="attempt-a",
            sequence=3,
            event_type="turn_metrics",
            fields={
                "endOfUtteranceDelayMs": 1200,
                "turnCallbackDelayMs": 1010,
            },
        ),
        _event(
            attempt_id="attempt-a",
            sequence=4,
            event_type="turn_metrics",
            fields={
                "llmTtftMs": 420,
                "ttsTtfbMs": 180,
                "turnId": "answer-3",
                "turnPurpose": "answer",
            },
        ),
        _event(
            attempt_id="attempt-b",
            sequence=1,
            event_type="follow_up_planning",
            fields={
                "planningDurationMs": 9000,
                "planningSearchCalls": 0,
                "planningStatus": "cancelled",
                "planningInputTokens": 9000,
                "planningCachedInputTokens": 8000,
            },
        ),
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    summary = summarize_reasoning_evidence(path, attempt_ids={"attempt-a"})

    assert summary["attemptIds"] == ["attempt-a"]
    assert summary["planning"]["records"] == 2
    assert summary["planning"]["statusCounts"] == {"accepted": 2}
    assert summary["planning"]["cache"] == {
        "cachedInputTokens": 400,
        "inputTokens": 3000,
        "ratio": pytest.approx(0.133333, abs=0.000001),
        "recordsWithCachedTokens": 1,
    }
    assert summary["planning"]["nonSearch"]["durationMs"] == {
        "count": 1,
        "min": 1000,
        "median": 1000,
        "p95": 1000,
        "max": 1000,
    }
    assert summary["planning"]["nonSearch"]["acceptedDurationMs"] == {
        "count": 1,
        "min": 1000,
        "median": 1000,
        "p95": 1000,
        "max": 1000,
    }
    assert summary["planning"]["search"]["durationMs"]["median"] == 3000
    assert summary["pipeline"]["endpointingMs"]["median"] == 1200
    assert summary["pipeline"]["followUpCallbackMs"]["median"] == 1010
    assert summary["pipeline"]["answerLlmTtftMs"]["median"] == 420
    assert summary["pipeline"]["answerTtsFirstAudioMs"]["median"] == 180
    assert summary["pipeline"]["unscopedLlmTtftMs"]["count"] == 0


def test_summary_rejects_malformed_jsonl_instead_of_silently_skipping_it(tmp_path):
    from voice_presentation.transport.reasoning_evidence import (
        summarize_reasoning_evidence,
    )

    path = tmp_path / "diagnostics.jsonl"
    path.write_text("{not-json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        summarize_reasoning_evidence(path)
