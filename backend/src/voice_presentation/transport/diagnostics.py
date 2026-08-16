from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


DiagnosticScalar = bool | int | float | str


class ConversationDiagnosticEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attempt_id: str = Field(alias="attemptId")
    sequence: int = Field(ge=1)
    event_type: str = Field(alias="eventType", min_length=1)
    elapsed_ms: int = Field(alias="elapsedMs", ge=0)
    fields: dict[str, DiagnosticScalar] = Field(default_factory=dict)
    version: int = 1

    def to_wire(self) -> dict[str, object]:
        return self.model_dump(mode="json", by_alias=True)

    def to_json(self) -> str:
        return json.dumps(self.to_wire(), separators=(",", ":"), sort_keys=True)


class ConversationDiagnosticLedger(Protocol):
    def record(self, event: ConversationDiagnosticEvent) -> None: ...


class NullConversationDiagnosticLedger:
    def record(self, event: ConversationDiagnosticEvent) -> None:
        del event


class JsonlConversationDiagnosticLedger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(self, event: ConversationDiagnosticEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(event.to_json())
            stream.write("\n")


class ConversationDiagnostics:
    """Normalize one attempt's safe lifecycle and provider timing evidence."""

    def __init__(
        self,
        *,
        attempt_id: str,
        ledger: ConversationDiagnosticLedger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not attempt_id.strip():
            raise ValueError("attempt_id must not be blank")
        self.attempt_id = attempt_id
        self._ledger = ledger or NullConversationDiagnosticLedger()
        self._clock = clock
        self._origin: float | None = None
        self._sequence = 0
        self._last_realtime_complete_ms: int | None = None

    def record_user_state(
        self, *, old_state: str, new_state: str
    ) -> ConversationDiagnosticEvent:
        elapsed_ms = self._elapsed_ms()
        fields: dict[str, DiagnosticScalar] = {
            "oldState": old_state,
            "newState": new_state,
        }
        return self._record("user_state_changed", elapsed_ms, fields)

    def record_agent_state(
        self, *, old_state: str, new_state: str
    ) -> ConversationDiagnosticEvent:
        elapsed_ms = self._elapsed_ms()
        fields: dict[str, DiagnosticScalar] = {
            "oldState": old_state,
            "newState": new_state,
        }
        return self._record("agent_state_changed", elapsed_ms, fields)

    def record_metrics(self, metrics: object) -> ConversationDiagnosticEvent:
        elapsed_ms = self._elapsed_ms()
        metric_type = str(getattr(metrics, "type", "unknown_metrics"))
        fields: dict[str, DiagnosticScalar]
        if metric_type == "realtime_model_metrics":
            fields = self._realtime_model_fields(metrics, elapsed_ms=elapsed_ms)
        elif metric_type == "eou_metrics":
            fields = {
                "endOfUtteranceDelayMs": _milliseconds(
                    getattr(metrics, "end_of_utterance_delay", 0)
                ),
                "transcriptionDelayMs": _milliseconds(
                    getattr(metrics, "transcription_delay", 0)
                ),
                "turnCallbackDelayMs": _milliseconds(
                    getattr(metrics, "on_user_turn_completed_delay", 0)
                ),
            }
        elif metric_type == "llm_metrics":
            fields = {
                "llmTtftMs": _milliseconds(getattr(metrics, "ttft", 0)),
                "modelDurationMs": _milliseconds(
                    getattr(metrics, "duration", 0)
                ),
                "cancelled": bool(getattr(metrics, "cancelled", False)),
                "inputTokens": int(getattr(metrics, "prompt_tokens", 0)),
                "outputTokens": int(getattr(metrics, "completion_tokens", 0)),
                "totalTokens": int(getattr(metrics, "total_tokens", 0)),
                "cachedInputTokens": int(
                    getattr(metrics, "prompt_cached_tokens", 0)
                ),
                "tokensPerSecond": float(
                    getattr(metrics, "tokens_per_second", 0)
                ),
            }
        elif metric_type == "tts_metrics":
            fields = {
                "ttsTtfbMs": _milliseconds(getattr(metrics, "ttfb", 0)),
                "modelDurationMs": _milliseconds(
                    getattr(metrics, "duration", 0)
                ),
                "audioDurationMs": _milliseconds(
                    getattr(metrics, "audio_duration", 0)
                ),
                "cancelled": bool(getattr(metrics, "cancelled", False)),
                "charactersCount": int(
                    getattr(metrics, "characters_count", 0)
                ),
                "streamed": bool(getattr(metrics, "streamed", False)),
                "connectionAcquireMs": _milliseconds(
                    getattr(metrics, "acquire_time", 0)
                ),
                "connectionReused": bool(
                    getattr(metrics, "connection_reused", False)
                ),
            }
        elif metric_type == "interruption_metrics":
            fields = {
                "interruptionDetectionDelayMs": _milliseconds(
                    getattr(metrics, "detection_delay", 0)
                ),
                "interruptionPredictionMs": _milliseconds(
                    getattr(metrics, "prediction_duration", 0)
                ),
                "interruptionDurationMs": _milliseconds(
                    getattr(metrics, "total_duration", 0)
                ),
                "numInterruptions": int(
                    getattr(metrics, "num_interruptions", 0)
                ),
                "numBackchannels": int(
                    getattr(metrics, "num_backchannels", 0)
                ),
                "numRequests": int(getattr(metrics, "num_requests", 0)),
            }
        else:
            fields = {"metricType": metric_type}
        return self._record(metric_type, elapsed_ms, fields)

    def record_turn_metrics(
        self, metrics: Mapping[str, object]
    ) -> ConversationDiagnosticEvent:
        elapsed_ms = self._elapsed_ms()
        field_names = {
            "end_of_turn_delay": "endOfUtteranceDelayMs",
            "on_user_turn_completed_delay": "turnCallbackDelayMs",
            "llm_node_ttft": "llmTtftMs",
            "tts_node_ttfb": "ttsTtfbMs",
        }
        fields: dict[str, DiagnosticScalar] = {}
        for source_name, wire_name in field_names.items():
            value = metrics.get(source_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                fields[wire_name] = _milliseconds(value)
        return self._record("turn_metrics", elapsed_ms, fields)

    def record_follow_up_planning(
        self,
        *,
        duration_seconds: float,
        provider_duration_seconds: float,
        request_count: int,
        tool_steps: int,
        search_calls: int,
        status: str,
        input_tokens: int,
        cached_input_tokens: int,
        total_tokens: int,
    ) -> ConversationDiagnosticEvent:
        """Record silent planning separately from answer LLM and TTS metrics."""

        fields: dict[str, DiagnosticScalar] = {
            "planningDurationMs": _milliseconds(duration_seconds),
            "planningProviderDurationMs": _milliseconds(
                provider_duration_seconds
            ),
            "planningRequestCount": max(0, request_count),
            "planningToolSteps": max(0, tool_steps),
            "planningSearchCalls": max(0, search_calls),
            "planningStatus": status,
            "planningInputTokens": max(0, input_tokens),
            "planningCachedInputTokens": max(0, cached_input_tokens),
            "planningTotalTokens": max(0, total_tokens),
        }
        return self._record("follow_up_planning", self._elapsed_ms(), fields)

    def _realtime_model_fields(
        self, metrics: object, *, elapsed_ms: int
    ) -> dict[str, DiagnosticScalar]:
        duration_ms = _milliseconds(getattr(metrics, "duration", 0))
        input_tokens = int(getattr(metrics, "input_tokens", 0))
        output_tokens = int(getattr(metrics, "output_tokens", 0))
        total_tokens = int(getattr(metrics, "total_tokens", 0))
        fields: dict[str, DiagnosticScalar] = {
            "modelDurationMs": duration_ms,
            "cancelled": bool(getattr(metrics, "cancelled", False)),
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": total_tokens,
            "cachedInputTokens": int(
                getattr(getattr(metrics, "input_token_details", None), "cached_tokens", 0)
            ),
            "connectionAcquireMs": _milliseconds(
                getattr(metrics, "acquire_time", 0)
            ),
            "connectionReused": bool(getattr(metrics, "connection_reused", False)),
        }
        ttft = float(getattr(metrics, "ttft", -1))
        if ttft >= 0:
            fields["modelTtftMs"] = _milliseconds(ttft)
        is_response = duration_ms > 0 or total_tokens > 0 or ttft >= 0
        if is_response:
            response_started_ms = max(0, elapsed_ms - duration_ms)
            if self._last_realtime_complete_ms is not None:
                fields["providerResponseStartGapMs"] = max(
                    0, response_started_ms - self._last_realtime_complete_ms
                )
            self._last_realtime_complete_ms = elapsed_ms
        return fields

    def _elapsed_ms(self) -> int:
        current = self._clock()
        if self._origin is None:
            self._origin = current
        return max(0, round((current - self._origin) * 1000))

    def _record(
        self,
        event_type: str,
        elapsed_ms: int,
        fields: dict[str, DiagnosticScalar],
    ) -> ConversationDiagnosticEvent:
        self._sequence += 1
        event = ConversationDiagnosticEvent(
            attempt_id=self.attempt_id,
            sequence=self._sequence,
            event_type=event_type,
            elapsed_ms=elapsed_ms,
            fields=fields,
        )
        self._ledger.record(event)
        return event


def _milliseconds(seconds: object) -> int:
    return max(0, round(float(seconds) * 1000))
