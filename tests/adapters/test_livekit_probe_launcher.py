from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from livekit import rtc


@dataclass
class ReadySession:
    release: asyncio.Event

    async def run(self, ready: asyncio.Event) -> None:
        ready.set()
        await self.release.wait()


class FailingSession:
    async def run(self, ready: asyncio.Event) -> None:
        raise RuntimeError("connection failed")


class HandledFailureSession:
    usage_outcome = "failed"

    async def run(self, ready: asyncio.Event) -> None:
        ready.set()


class RecordingUsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    def record(self, usage: object) -> None:
        self.records.append(usage)


class FakeLocalParticipant:
    def __init__(self) -> None:
        self.packets: list[str] = []

    async def publish_data(self, payload: str, **_: object) -> None:
        self.packets.append(payload)


class FakeRoom:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.connected = False
        self.local_participant = FakeLocalParticipant()

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def connect(self, *_: object) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def isconnected(self) -> bool:
        return self.connected


class OneFrameThenBlockingStream:
    def __init__(self) -> None:
        self.frame_yielded = asyncio.Event()
        self.closed = False
        self._yielded = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._yielded:
            self._yielded = True
            self.frame_yielded.set()
            return type(
                "AudioEvent",
                (),
                {
                    "frame": rtc.AudioFrame(
                        data=b"\x01\x00" * 960,
                        sample_rate=48_000,
                        num_channels=1,
                        samples_per_channel=960,
                    )
                },
            )()
        await asyncio.Event().wait()
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True


class OneFrameThenEndStream(OneFrameThenBlockingStream):
    async def __anext__(self):
        if not self._yielded:
            return await super().__anext__()
        raise StopAsyncIteration


class ContinuousFrameStream:
    def __init__(self) -> None:
        self.frame_yielded = asyncio.Event()
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0.001)
        self.frame_yielded.set()
        return type(
            "AudioEvent",
            (),
            {
                "frame": rtc.AudioFrame(
                    data=b"\x01\x00" * 960,
                    sample_rate=48_000,
                    num_channels=1,
                    samples_per_channel=960,
                )
            },
        )()

    async def aclose(self) -> None:
        self.closed = True


def _spec():
    from voice_presentation.transport.bootstrap import ProbeSessionSpec

    return ProbeSessionSpec(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        room_name="probe-9ea3a1cb",
        browser_identity="browser-9ea3a1cb",
        worker_identity="probe-worker-9ea3a1cb",
        server_url="wss://example.livekit.cloud",
        worker_token="worker-token",
    )


@pytest.mark.offline
def test_launcher_waits_until_worker_is_ready_and_rejects_duplicate_attempt():
    from voice_presentation.adapters.livekit.probe import (
        LiveKitProbeSessionLauncher,
        ProbeSessionAlreadyActive,
    )

    async def scenario() -> None:
        release = asyncio.Event()
        usage = RecordingUsageLedger()
        launcher = LiveKitProbeSessionLauncher(
            session_factory=lambda _: ReadySession(release),
            ready_timeout_seconds=0.1,
            usage_ledger=usage,
        )
        await launcher.launch(_spec())

        with pytest.raises(ProbeSessionAlreadyActive):
            await launcher.launch(_spec())

        release.set()
        await asyncio.sleep(0)
        await launcher.aclose()

        assert len(usage.records) == 1
        assert usage.records[0].attempt_id == _spec().attempt_id
        assert usage.records[0].outcome == "completed"
        assert usage.records[0].participant_minutes_upper_bound == 2

    asyncio.run(scenario())


@pytest.mark.offline
def test_launcher_surfaces_worker_failure_before_reporting_ready():
    from voice_presentation.adapters.livekit.probe import (
        LiveKitProbeSessionLauncher,
        ProbeSessionLaunchError,
    )

    async def scenario() -> None:
        launcher = LiveKitProbeSessionLauncher(
            session_factory=lambda _: FailingSession(),
            ready_timeout_seconds=0.1,
        )

        with pytest.raises(ProbeSessionLaunchError, match="before becoming ready"):
            await launcher.launch(_spec())

        await launcher.aclose()

    asyncio.run(scenario())


@pytest.mark.offline
def test_launcher_records_a_handled_worker_failure_as_failed():
    from voice_presentation.adapters.livekit.probe import LiveKitProbeSessionLauncher

    async def scenario() -> None:
        usage = RecordingUsageLedger()
        launcher = LiveKitProbeSessionLauncher(
            session_factory=lambda _: HandledFailureSession(),
            ready_timeout_seconds=0.1,
            usage_ledger=usage,
        )

        await launcher.launch(_spec())
        await asyncio.sleep(0)
        await launcher.aclose()

        assert len(usage.records) == 1
        assert usage.records[0].outcome == "failed"

    asyncio.run(scenario())


@pytest.mark.offline
def test_ready_worker_times_out_and_disconnects_when_browser_never_publishes():
    from voice_presentation.adapters.livekit.probe import LiveKitRecordReplaySession

    async def scenario() -> None:
        room = FakeRoom()
        session = LiveKitRecordReplaySession(
            _spec(),
            room=room,
            session_timeout_seconds=0.01,
        )
        ready = asyncio.Event()

        await session.run(ready)

        assert ready.is_set()
        assert room.connected is False
        assert len(room.local_participant.packets) == 1
        assert "probe attempt timed out" in room.local_participant.packets[0]

    asyncio.run(scenario())


@pytest.mark.offline
def test_explicit_capture_stopped_signal_ends_stream_and_starts_replay():
    from voice_presentation.adapters.livekit.probe import LiveKitRecordReplaySession
    from voice_presentation.transport.contracts import (
        ProbeControlSignal,
        ProbeSignalType,
    )

    async def scenario() -> None:
        stream = OneFrameThenBlockingStream()
        session = LiveKitRecordReplaySession(
            _spec(),
            room=FakeRoom(),
            audio_stream_factory=lambda *_args, **_kwargs: stream,
            capture_drain_seconds=0.01,
        )
        replay = AsyncMock()
        session._replay = replay
        capture = asyncio.create_task(session._capture_and_replay(object()))
        await stream.frame_yielded.wait()

        await session._observe_control_packet(
            ProbeControlSignal(
                type=ProbeSignalType.CAPTURE_STOPPED,
                attempt_id=_spec().attempt_id,
                emitted_at_ms=1,
            ).model_dump_json().encode()
        )
        await asyncio.wait_for(capture, timeout=0.05)

        assert stream.closed is True
        replay.assert_awaited_once()
        assert len(replay.await_args.args[0]) == 1

    asyncio.run(scenario())


@pytest.mark.offline
def test_media_end_of_stream_cannot_authorize_replay_without_stop_signal():
    from voice_presentation.adapters.livekit.probe import LiveKitRecordReplaySession
    from voice_presentation.transport.contracts import ProbePhase

    async def scenario() -> None:
        stream = OneFrameThenEndStream()
        session = LiveKitRecordReplaySession(
            _spec(),
            room=FakeRoom(),
            audio_stream_factory=lambda *_args, **_kwargs: stream,
            capture_stop_signal_timeout_seconds=0.01,
        )
        replay = AsyncMock()
        session._replay = replay

        await session._capture_and_replay(object())

        replay.assert_not_awaited()
        assert session._attempt.phase is ProbePhase.FAILED

    asyncio.run(scenario())


@pytest.mark.offline
def test_capture_drain_uses_one_global_deadline_while_frames_continue():
    from voice_presentation.adapters.livekit.probe import LiveKitRecordReplaySession
    from voice_presentation.transport.contracts import (
        ProbeControlSignal,
        ProbeSignalType,
    )

    async def scenario() -> None:
        stream = ContinuousFrameStream()
        session = LiveKitRecordReplaySession(
            _spec(),
            room=FakeRoom(),
            audio_stream_factory=lambda *_args, **_kwargs: stream,
            capture_drain_seconds=0.01,
        )
        replay = AsyncMock()
        session._replay = replay
        capture = asyncio.create_task(session._capture_and_replay(object()))
        await stream.frame_yielded.wait()
        await session._observe_control_packet(
            ProbeControlSignal(
                type=ProbeSignalType.CAPTURE_STOPPED,
                attempt_id=_spec().attempt_id,
                emitted_at_ms=1,
            ).model_dump_json().encode()
        )

        await asyncio.wait_for(capture, timeout=0.05)

        assert stream.closed is True
        replay.assert_awaited_once()

    asyncio.run(scenario())


@pytest.mark.offline
def test_worker_waits_for_replay_acknowledgement_before_finishing():
    from voice_presentation.adapters.livekit.probe import LiveKitRecordReplaySession
    from voice_presentation.transport.contracts import (
        ProbeControlSignal,
        ProbeSignalType,
    )

    async def scenario() -> None:
        session = LiveKitRecordReplaySession(
            _spec(),
            room=FakeRoom(),
            replay_ack_timeout_seconds=0.05,
        )
        acknowledgement = asyncio.create_task(session._wait_for_replay_acknowledgement())
        await asyncio.sleep(0)
        assert acknowledgement.done() is False

        await session._observe_control_packet(
            ProbeControlSignal(
                type=ProbeSignalType.REPLAY_ACKNOWLEDGED,
                attempt_id=_spec().attempt_id,
                emitted_at_ms=2,
            ).model_dump_json().encode()
        )
        await acknowledgement

    asyncio.run(scenario())
