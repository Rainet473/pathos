from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, cast

UsageOutcome = Literal["completed", "failed", "cancelled"]
VALID_OUTCOMES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class UsageRecord:
    attempt_id: str
    started_at: datetime
    duration_seconds: float
    outcome: UsageOutcome
    worker_connection_minutes: int
    browser_participant_minutes_upper_bound: int
    participant_minutes_upper_bound: int
    version: int = 2

    @classmethod
    def from_interval(
        cls,
        *,
        attempt_id: str,
        started_at: datetime,
        ended_at: datetime,
        outcome: str,
        browser_participant_minutes_upper_bound: int,
    ) -> "UsageRecord":
        if ended_at < started_at:
            raise ValueError("ended_at must not precede started_at")
        return cls.from_duration(
            attempt_id=attempt_id,
            started_at=started_at,
            duration_seconds=(ended_at - started_at).total_seconds(),
            outcome=outcome,
            browser_participant_minutes_upper_bound=browser_participant_minutes_upper_bound,
        )

    @classmethod
    def from_duration(
        cls,
        *,
        attempt_id: str,
        started_at: datetime,
        duration_seconds: float,
        outcome: str,
        browser_participant_minutes_upper_bound: int,
    ) -> "UsageRecord":
        if not attempt_id:
            raise ValueError("attempt_id must not be empty")
        if started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if duration_seconds < 0 or not math.isfinite(duration_seconds):
            raise ValueError("duration_seconds must be finite and non-negative")
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
        if browser_participant_minutes_upper_bound <= 0:
            raise ValueError("browser participant-minute upper bound must be positive")
        worker_minutes = max(1, math.ceil(duration_seconds / 60))
        return cls(
            attempt_id=attempt_id,
            started_at=started_at,
            duration_seconds=round(duration_seconds, 3),
            outcome=cast(UsageOutcome, outcome),
            worker_connection_minutes=worker_minutes,
            browser_participant_minutes_upper_bound=browser_participant_minutes_upper_bound,
            participant_minutes_upper_bound=(
                worker_minutes + browser_participant_minutes_upper_bound
            ),
        )

    def to_wire(self) -> dict[str, object]:
        return {
            "version": self.version,
            "attemptId": self.attempt_id,
            "startedAt": self.started_at.isoformat(),
            "durationSeconds": self.duration_seconds,
            "outcome": self.outcome,
            "workerConnectionMinutes": self.worker_connection_minutes,
            "browserParticipantMinutesUpperBound": self.browser_participant_minutes_upper_bound,
            "participantMinutesUpperBound": self.participant_minutes_upper_bound,
        }


class UsageLedger(Protocol):
    def record(self, usage: UsageRecord) -> None: ...


class NullUsageLedger:
    def record(self, usage: UsageRecord) -> None:
        del usage


class JsonlUsageLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, usage: UsageRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(usage.to_wire(), separators=(",", ":"), sort_keys=True))
            stream.write("\n")


@dataclass(frozen=True, slots=True)
class UsageSummary:
    attempt_count: int
    local_participant_minutes_upper_bound: int
    monthly_allowance: int
    prior_usage: int
    remaining_if_baseline_is_current: int


def summarize_usage(
    path: str | Path,
    *,
    monthly_allowance: int,
    prior_usage: int = 0,
) -> UsageSummary:
    if monthly_allowance < 0 or prior_usage < 0:
        raise ValueError("allowance and prior usage must be non-negative")
    records = _read_rows(Path(path))
    local_upper_bound = sum(_validated_minutes(row) for row in records)
    return UsageSummary(
        attempt_count=len(records),
        local_participant_minutes_upper_bound=local_upper_bound,
        monthly_allowance=monthly_allowance,
        prior_usage=prior_usage,
        remaining_if_baseline_is_current=max(
            0,
            monthly_allowance - prior_usage - local_upper_bound,
        ),
    )


def _read_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"malformed usage row {line_number}") from error
            if not isinstance(row, dict):
                raise ValueError(f"usage row {line_number} must be an object")
            rows.append(row)
    return rows


def _validated_minutes(row: dict[str, object]) -> int:
    version = row.get("version")
    value = row.get("participantMinutesUpperBound")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("invalid participant-minute value")
    if version == 1:
        return value
    if version != 2:
        raise ValueError("unsupported usage record version")
    worker = row.get("workerConnectionMinutes")
    browser = row.get("browserParticipantMinutesUpperBound")
    if (
        not isinstance(worker, int)
        or isinstance(worker, bool)
        or worker <= 0
        or not isinstance(browser, int)
        or isinstance(browser, bool)
        or browser <= 0
        or worker + browser != value
    ):
        raise ValueError("invalid per-participant minute values")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize local LiveKit session usage")
    parser.add_argument("path", nargs="?", default=".runtime/livekit-usage.jsonl")
    parser.add_argument("--allowance", type=int, required=True)
    parser.add_argument("--prior-usage", type=int, default=0)
    arguments = parser.parse_args()
    summary = summarize_usage(
        arguments.path,
        monthly_allowance=arguments.allowance,
        prior_usage=arguments.prior_usage,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
