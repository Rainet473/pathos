from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

PROBE_SAMPLE_RATE_HZ = 48_000
PROBE_CHANNEL_COUNT = 1
MAX_FRAME_DURATION_MS = 100


class ProbePhase(StrEnum):
    IDLE = "idle"
    CAPTURING = "capturing"
    TRANSFERRING = "transferring"
    REPLAYING = "replaying"
    COMPLETE = "complete"
    FAILED = "failed"


class ProbeTransitionRejected(RuntimeError):
    """Raised when an attempt cannot safely accept a requested transition."""


class ProbeSignalType(StrEnum):
    CAPTURE_STARTED = "capture_started"
    CAPTURE_STOPPED = "capture_stopped"
    REPLAY_STARTED = "replay_started"
    REPLAY_COMPLETED = "replay_completed"
    REPLAY_ACKNOWLEDGED = "replay_acknowledged"
    FAILED = "failed"


class ProbeSignalMetrics(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    frame_count: int = Field(ge=0)
    audio_duration_ms: float = Field(ge=0)


class ProbeControlSignal(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    version: Literal[1] = 1
    type: ProbeSignalType
    attempt_id: str = Field(min_length=1, max_length=64)
    emitted_at_ms: int = Field(ge=0)
    metrics: ProbeSignalMetrics | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=200)


class AudioFrameMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempt_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=0)
    sample_rate_hz: int = Field(ge=PROBE_SAMPLE_RATE_HZ, le=PROBE_SAMPLE_RATE_HZ)
    channel_count: int = Field(ge=PROBE_CHANNEL_COUNT, le=PROBE_CHANNEL_COUNT)
    samples_per_channel: int = Field(
        ge=1,
        le=PROBE_SAMPLE_RATE_HZ * MAX_FRAME_DURATION_MS // 1_000,
    )

    @property
    def duration_ms(self) -> float:
        return self.samples_per_channel * 1_000 / self.sample_rate_hz


@dataclass(slots=True)
class ProbeMetrics:
    frame_count: int = 0
    sample_count: int = 0
    audio_duration_ms: float = 0
    capture_started_at_ms: int | None = None
    capture_stopped_at_ms: int | None = None
    replay_started_at_ms: int | None = None
    replay_completed_at_ms: int | None = None


@dataclass(slots=True)
class ProbeAttempt:
    attempt_id: str
    phase: ProbePhase = ProbePhase.IDLE
    metrics: ProbeMetrics = field(default_factory=ProbeMetrics)
    failure_reason: str | None = None
    _last_sequence: int = field(default=-1, repr=False)

    def __post_init__(self) -> None:
        if not self.attempt_id or len(self.attempt_id) > 64:
            raise ValueError("attempt_id must be between 1 and 64 characters")

    def begin_capture(self, *, at_ms: int) -> bool:
        if self.phase is not ProbePhase.IDLE:
            return False
        self._validate_timestamp(at_ms)
        self.phase = ProbePhase.CAPTURING
        self.metrics.capture_started_at_ms = at_ms
        return True

    def accept_frame(self, frame: AudioFrameMetadata, *, at_ms: int) -> bool:
        if frame.attempt_id != self.attempt_id or self.phase is not ProbePhase.CAPTURING:
            return False
        self._validate_timestamp(at_ms)
        if frame.sequence <= self._last_sequence:
            return False
        self._last_sequence = frame.sequence
        self.metrics.frame_count += 1
        self.metrics.sample_count += frame.samples_per_channel
        self.metrics.audio_duration_ms += frame.duration_ms
        return True

    def stop_capture(self, *, at_ms: int) -> bool:
        if self.phase is ProbePhase.TRANSFERRING:
            return False
        if self.phase is not ProbePhase.CAPTURING:
            return False
        self._validate_timestamp(at_ms)
        self.metrics.capture_stopped_at_ms = at_ms
        if self.metrics.frame_count == 0:
            self.fail("no audio frames were captured", at_ms=at_ms)
            raise ProbeTransitionRejected("no audio frames were captured")
        self.phase = ProbePhase.TRANSFERRING
        return True

    def begin_replay(self, *, at_ms: int) -> bool:
        if self.phase is not ProbePhase.TRANSFERRING:
            return False
        self._validate_timestamp(at_ms)
        self.phase = ProbePhase.REPLAYING
        self.metrics.replay_started_at_ms = at_ms
        return True

    def complete_replay(self, *, at_ms: int) -> bool:
        if self.phase is ProbePhase.COMPLETE:
            return False
        if self.phase is not ProbePhase.REPLAYING:
            return False
        self._validate_timestamp(at_ms)
        self.phase = ProbePhase.COMPLETE
        self.metrics.replay_completed_at_ms = at_ms
        return True

    def fail(self, reason: str, *, at_ms: int) -> bool:
        if self.phase in {ProbePhase.COMPLETE, ProbePhase.FAILED}:
            return False
        self._validate_timestamp(at_ms)
        reason = reason.strip()
        if not reason:
            raise ValueError("failure reason cannot be blank")
        self.phase = ProbePhase.FAILED
        self.failure_reason = reason
        return True

    def _validate_timestamp(self, at_ms: int) -> None:
        if at_ms < 0:
            raise ValueError("timestamps must be non-negative")
