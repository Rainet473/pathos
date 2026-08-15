from __future__ import annotations

from voice_presentation.voice.runtime import (
    PlayoutRequest,
    VoiceCapabilities,
    VoiceEvent,
    VoiceEventType,
)


class FakeRuntimeTransitionRejected(RuntimeError):
    """Raised when the deterministic fake receives an illegal lifecycle action."""


class DeterministicFakeVoiceRuntime:
    capabilities = VoiceCapabilities(
        native_barge_in=False,
        semantic_turn_detection=False,
        streaming_tool_calls=False,
        audio_output=False,
        transcript_timing=False,
        reliable_playout_completion=True,
    )

    def __init__(self) -> None:
        self._active_playout: PlayoutRequest | None = None
        self._event_log: list[VoiceEvent] = []

    @property
    def active_playout(self) -> PlayoutRequest | None:
        return self._active_playout

    @property
    def event_log(self) -> tuple[VoiceEvent, ...]:
        return tuple(self._event_log)

    def start_playout(self, request: PlayoutRequest) -> VoiceEvent:
        if self._active_playout is not None:
            raise FakeRuntimeTransitionRejected(
                f"turn {self._active_playout.turn_id} is already playing"
            )
        self._active_playout = request
        return self._record(VoiceEventType.PLAYOUT_STARTED, request)

    def complete_playout(self, *, turn_id: str) -> VoiceEvent:
        request = self._matching_active(turn_id)
        self._active_playout = None
        return self._record(VoiceEventType.PLAYOUT_COMPLETED, request)

    def interrupt_playout(self, *, turn_id: str) -> VoiceEvent:
        request = self._matching_active(turn_id)
        self._active_playout = None
        return self._record(VoiceEventType.PLAYOUT_INTERRUPTED, request)

    def _matching_active(self, turn_id: str) -> PlayoutRequest:
        turn_id = turn_id.strip()
        active = self._active_playout
        if not turn_id or active is None or active.turn_id != turn_id:
            raise FakeRuntimeTransitionRejected(
                f"turn {turn_id or '<blank>'} is not the active playout"
            )
        return active

    def _record(
        self, event_type: VoiceEventType, request: PlayoutRequest
    ) -> VoiceEvent:
        event = VoiceEvent(
            type=event_type,
            request=request,
            sequence=len(self._event_log) + 1,
        )
        self._event_log.append(event)
        return event
