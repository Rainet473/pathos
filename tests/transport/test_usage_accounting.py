from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.offline
def test_short_attempt_rounds_each_possible_connection_to_one_minute(tmp_path):
    from voice_presentation.transport.usage import JsonlUsageLedger, UsageRecord

    path = tmp_path / "usage.jsonl"
    ledger = JsonlUsageLedger(path)
    started = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    record = UsageRecord.from_interval(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        started_at=started,
        ended_at=started + timedelta(seconds=12),
        outcome="completed",
        browser_participant_minutes_upper_bound=1,
    )

    ledger.record(record)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["durationSeconds"] == 12.0
    assert payload["participantMinutesUpperBound"] == 2
    assert set(payload) == {
        "version",
        "attemptId",
        "startedAt",
        "durationSeconds",
        "outcome",
        "workerConnectionMinutes",
        "browserParticipantMinutesUpperBound",
        "participantMinutesUpperBound",
    }


@pytest.mark.offline
def test_usage_rounding_and_summary_are_conservative(tmp_path):
    from voice_presentation.transport.usage import (
        JsonlUsageLedger,
        UsageRecord,
        summarize_usage,
    )

    path = tmp_path / "usage.jsonl"
    ledger = JsonlUsageLedger(path)
    started = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    ledger.record(
        UsageRecord.from_interval(
            attempt_id="attempt-long",
            started_at=started,
            ended_at=started + timedelta(seconds=61),
            outcome="failed",
            browser_participant_minutes_upper_bound=1,
        )
    )
    ledger.record(
        UsageRecord.from_interval(
            attempt_id="attempt-cancelled",
            started_at=started,
            ended_at=started,
            outcome="cancelled",
            browser_participant_minutes_upper_bound=1,
        )
    )

    summary = summarize_usage(path, monthly_allowance=5_000, prior_usage=100)

    assert summary.attempt_count == 2
    assert summary.local_participant_minutes_upper_bound == 5
    assert summary.remaining_if_baseline_is_current == 4_895


@pytest.mark.offline
def test_usage_record_rejects_invalid_time_or_outcome():
    from voice_presentation.transport.usage import UsageRecord

    started = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="ended_at"):
        UsageRecord.from_interval(
            attempt_id="attempt",
            started_at=started,
            ended_at=started - timedelta(seconds=1),
            outcome="completed",
            browser_participant_minutes_upper_bound=1,
        )
    with pytest.raises(ValueError, match="outcome"):
        UsageRecord.from_interval(
            attempt_id="attempt",
            started_at=started,
            ended_at=started,
            outcome="unknown",
            browser_participant_minutes_upper_bound=1,
        )


@pytest.mark.offline
def test_summary_retains_version_one_rows_from_earlier_live_attempts(tmp_path):
    from voice_presentation.transport.usage import summarize_usage

    path = tmp_path / "usage.jsonl"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "attemptId": "historical-attempt",
                "startedAt": "2026-08-15T12:00:00+00:00",
                "durationSeconds": 12.0,
                "outcome": "completed",
                "participantConnectionsUpperBound": 2,
                "participantMinutesUpperBound": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_usage(path, monthly_allowance=5_000)

    assert summary.attempt_count == 1
    assert summary.local_participant_minutes_upper_bound == 2
