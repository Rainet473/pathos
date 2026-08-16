from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def summarize_reasoning_evidence(
    diagnostics_path: str | Path,
    *,
    attempt_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Summarize app-owned reasoning and pipeline timing fields from JSONL."""

    selected_attempts = {
        attempt_id.strip() for attempt_id in attempt_ids or () if attempt_id.strip()
    }
    observed_attempts: set[str] = set()
    planning_records: list[dict[str, Any]] = []
    endpointing: list[int] = []
    callbacks: list[int] = []
    answer_llm: list[int] = []
    answer_tts: list[int] = []
    unscoped_llm: list[int] = []
    unscoped_tts: list[int] = []

    path = Path(diagnostics_path)
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid diagnostics JSON on line {line_number}"
            ) from error
        if not isinstance(row, dict) or not isinstance(row.get("fields"), dict):
            raise ValueError(f"invalid diagnostics record on line {line_number}")
        attempt_id = row.get("attemptId")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError(f"invalid attempt ID on line {line_number}")
        if selected_attempts and attempt_id not in selected_attempts:
            continue
        observed_attempts.add(attempt_id)
        fields = row["fields"]
        event_type = row.get("eventType")
        if event_type == "follow_up_planning":
            planning_records.append(fields)
        if event_type != "turn_metrics":
            continue
        _append_number(endpointing, fields.get("endOfUtteranceDelayMs"))
        _append_number(callbacks, fields.get("turnCallbackDelayMs"))
        purpose = fields.get("turnPurpose")
        if purpose == "answer":
            _append_number(answer_llm, fields.get("llmTtftMs"))
            _append_number(answer_tts, fields.get("ttsTtfbMs"))
        elif purpose is None:
            _append_number(unscoped_llm, fields.get("llmTtftMs"))
            _append_number(unscoped_tts, fields.get("ttsTtfbMs"))

    non_search = [
        record
        for record in planning_records
        if _number(record.get("planningSearchCalls")) == 0
    ]
    search = [
        record
        for record in planning_records
        if _number(record.get("planningSearchCalls")) > 0
    ]
    input_tokens = sum(
        _number(record.get("planningInputTokens")) for record in planning_records
    )
    cached_tokens = sum(
        _number(record.get("planningCachedInputTokens"))
        for record in planning_records
    )
    statuses = Counter(
        str(record.get("planningStatus", "unknown"))
        for record in planning_records
    )

    return {
        "attemptIds": sorted(observed_attempts),
        "planning": {
            "records": len(planning_records),
            "statusCounts": dict(sorted(statuses.items())),
            "cache": {
                "cachedInputTokens": cached_tokens,
                "inputTokens": input_tokens,
                "ratio": round(cached_tokens / input_tokens, 6)
                if input_tokens
                else 0.0,
                "recordsWithCachedTokens": sum(
                    _number(record.get("planningCachedInputTokens")) > 0
                    for record in planning_records
                ),
            },
            "nonSearch": _planning_group(non_search),
            "search": _planning_group(search),
        },
        "pipeline": {
            "endpointingMs": _distribution(endpointing),
            "followUpCallbackMs": _distribution(callbacks),
            "answerLlmTtftMs": _distribution(answer_llm),
            "answerTtsFirstAudioMs": _distribution(answer_tts),
            "unscopedLlmTtftMs": _distribution(unscoped_llm),
            "unscopedTtsFirstAudioMs": _distribution(unscoped_tts),
        },
    }


def _planning_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [
        record for record in records if record.get("planningStatus") == "accepted"
    ]
    return {
        "records": len(records),
        "acceptedRecords": len(accepted),
        "durationMs": _distribution(
            [
                _number(record.get("planningDurationMs"))
                for record in records
                if _is_number(record.get("planningDurationMs"))
            ]
        ),
        "acceptedDurationMs": _distribution(
            [
                _number(record.get("planningDurationMs"))
                for record in accepted
                if _is_number(record.get("planningDurationMs"))
            ]
        ),
    }


def _distribution(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {"count": 0, "min": 0, "median": 0, "p95": 0, "max": 0}
    ordered = sorted(values)
    median = statistics.median(ordered)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": round(median, 3),
        "p95": ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)],
        "max": ordered[-1],
    }


def _append_number(target: list[int], value: object) -> None:
    if _is_number(value):
        target.append(round(float(value)))


def _number(value: object) -> int:
    return round(float(value)) if _is_number(value) else 0


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize follow-up reasoning evidence from diagnostics JSONL."
    )
    parser.add_argument("diagnostics", type=Path)
    parser.add_argument("--attempt-id", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            summarize_reasoning_evidence(
                args.diagnostics,
                attempt_ids=set(args.attempt_id),
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
