from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from livekit import rtc

from voice_presentation.transport.bootstrap import ProbeSessionSpec
from voice_presentation.transport.contracts import (
    AudioFrameMetadata,
    ProbeAttempt,
    ProbeControlSignal,
    ProbePhase,
    ProbeSignalMetrics,
    ProbeSignalType,
    ProbeTransitionRejected,
)
from voice_presentation.transport.usage import NullUsageLedger, UsageLedger, UsageRecord

logger = logging.getLogger(__name__)

CONTROL_TOPIC = "voice-probe.control.v1"
SAMPLE_RATE_HZ = 48_000
CHANNEL_COUNT = 1
FRAME_SIZE_MS = 20
MAX_CLIP_DURATION_MS = 5_000
CAPTURE_DRAIN_SECONDS = 0.25
CAPTURE_STOP_SIGNAL_TIMEOUT_SECONDS = 1
REPLAY_ACK_TIMEOUT_SECONDS = 2


class ProbeSessionAlreadyActive(RuntimeError):
    """Raised when the same attempt is launched more than once."""


class ProbeSessionLaunchError(RuntimeError):
    """Raised when a worker cannot become ready for the browser."""


class RunnableProbeSession(Protocol):
    async def run(self, ready: asyncio.Event) -> None: ...


SessionFactory = Callable[[ProbeSessionSpec], RunnableProbeSession]


class AudioStreamLike(Protocol):
    def __aiter__(self): ...

    async def aclose(self) -> None: ...


AudioStreamFactory = Callable[..., AudioStreamLike]


class LiveKitProbeSessionLauncher:
    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        ready_timeout_seconds: float = 8,
        usage_ledger: UsageLedger | None = None,
    ) -> None:
        if ready_timeout_seconds <= 0:
            raise ValueError("ready timeout must be positive")
        self._session_factory = session_factory or LiveKitRecordReplaySession
        self._ready_timeout_seconds = ready_timeout_seconds
        self._usage_ledger = usage_ledger or NullUsageLedger()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def launch(self, session: ProbeSessionSpec) -> None:
        self._discard_finished()
        existing = self._tasks.get(session.attempt_id)
        if existing is not None and not existing.done():
            raise ProbeSessionAlreadyActive(f"attempt {session.attempt_id} is already active")

        ready = asyncio.Event()
        runner = self._session_factory(session)
        task = asyncio.create_task(
            self._run_and_record(session, runner, ready),
            name=f"probe-{session.attempt_id}",
        )
        self._tasks[session.attempt_id] = task
        task.add_done_callback(
            lambda finished, attempt_id=session.attempt_id: self._on_session_finished(
                attempt_id,
                finished,
            )
        )
        ready_waiter = asyncio.create_task(ready.wait())

        done, _ = await asyncio.wait(
            {task, ready_waiter},
            timeout=self._ready_timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if ready_waiter in done and ready.is_set():
            return

        ready_waiter.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ready_waiter

        if task in done:
            error = task.exception()
            raise ProbeSessionLaunchError("probe worker failed before becoming ready") from error

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._tasks.pop(session.attempt_id, None)
        raise ProbeSessionLaunchError("probe worker did not become ready in time")

    async def _run_and_record(
        self,
        session: ProbeSessionSpec,
        runner: RunnableProbeSession,
        ready: asyncio.Event,
    ) -> None:
        started_at = datetime.now(UTC)
        started_monotonic = time.monotonic()
        outcome = "completed"
        try:
            await runner.run(ready)
            outcome = getattr(runner, "usage_outcome", "completed")
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            raise
        finally:
            record = UsageRecord.from_duration(
                attempt_id=session.attempt_id,
                started_at=started_at,
                duration_seconds=max(0, time.monotonic() - started_monotonic),
                outcome=outcome,
                browser_participant_minutes_upper_bound=1,
            )
            try:
                self._usage_ledger.record(record)
            except Exception:
                logger.exception("Could not append the local LiveKit usage ledger")

    async def aclose(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def _discard_finished(self) -> None:
        for attempt_id, task in list(self._tasks.items()):
            if task.done():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    task.result()
                self._tasks.pop(attempt_id, None)

    def _on_session_finished(self, attempt_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(attempt_id) is task:
            self._tasks.pop(attempt_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Transport probe session failed", exc_info=error)


class LiveKitRecordReplaySession:
    def __init__(
        self,
        spec: ProbeSessionSpec,
        *,
        room: rtc.Room | None = None,
        session_timeout_seconds: float = 60,
        audio_stream_factory: AudioStreamFactory | None = None,
        capture_drain_seconds: float = CAPTURE_DRAIN_SECONDS,
        capture_stop_signal_timeout_seconds: float = CAPTURE_STOP_SIGNAL_TIMEOUT_SECONDS,
        replay_ack_timeout_seconds: float = REPLAY_ACK_TIMEOUT_SECONDS,
    ) -> None:
        if session_timeout_seconds <= 0:
            raise ValueError("session timeout must be positive")
        if capture_drain_seconds <= 0:
            raise ValueError("capture drain must be positive")
        if capture_stop_signal_timeout_seconds <= 0:
            raise ValueError("capture stop-signal timeout must be positive")
        if replay_ack_timeout_seconds <= 0:
            raise ValueError("replay acknowledgement timeout must be positive")
        self._spec = spec
        self._room = room or rtc.Room()
        self._session_timeout_seconds = session_timeout_seconds
        self._audio_stream_factory = audio_stream_factory or rtc.AudioStream
        self._capture_drain_seconds = capture_drain_seconds
        self._capture_stop_signal_timeout_seconds = capture_stop_signal_timeout_seconds
        self._replay_ack_timeout_seconds = replay_ack_timeout_seconds
        self._attempt = ProbeAttempt(attempt_id=spec.attempt_id)
        self._finished = asyncio.Event()
        self._capture_stopped = asyncio.Event()
        self._replay_acknowledged = asyncio.Event()
        self._clock_started = time.monotonic()
        self._capture_task: asyncio.Task[None] | None = None

    @property
    def usage_outcome(self) -> str:
        if self._attempt.phase is ProbePhase.FAILED:
            return "failed"
        return "completed"

    async def run(self, ready: asyncio.Event) -> None:
        self._register_room_events()
        try:
            await self._room.connect(self._spec.server_url, self._spec.worker_token)
            ready.set()
            try:
                await asyncio.wait_for(
                    self._finished.wait(),
                    timeout=self._session_timeout_seconds,
                )
            except TimeoutError:
                await self._fail("probe attempt timed out")
        finally:
            if self._capture_task is not None and not self._capture_task.done():
                self._capture_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._capture_task
            if self._room.isconnected():
                await self._room.disconnect()

    def _register_room_events(self) -> None:
        @self._room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            _publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            if (
                participant.identity != self._spec.browser_identity
                or track.kind != rtc.TrackKind.KIND_AUDIO
                or self._capture_task is not None
            ):
                return
            self._capture_task = asyncio.create_task(self._capture_and_replay(track))

        @self._room.on("data_received")
        def on_data_received(packet: rtc.DataPacket) -> None:
            if packet.topic != CONTROL_TOPIC or packet.participant is None:
                return
            if packet.participant.identity != self._spec.browser_identity:
                return
            asyncio.create_task(self._observe_control_packet(packet.data))

        @self._room.on("disconnected")
        def on_disconnected(_reason: object) -> None:
            if not self._finished.is_set():
                self._attempt.fail("room disconnected", at_ms=self._elapsed_ms())
                self._finished.set()

        @self._room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            if (
                participant.identity == self._spec.browser_identity
                and not self._finished.is_set()
            ):
                asyncio.create_task(self._fail("browser participant disconnected"))

    async def _observe_control_packet(self, payload: bytes) -> None:
        try:
            signal = ProbeControlSignal.model_validate_json(payload)
        except ValueError:
            logger.warning("Ignoring malformed transport probe control packet")
            return
        if signal.attempt_id != self._spec.attempt_id:
            return
        if signal.type is ProbeSignalType.CAPTURE_STARTED:
            self._attempt.begin_capture(at_ms=self._elapsed_ms())
        elif signal.type is ProbeSignalType.CAPTURE_STOPPED:
            self._capture_stopped.set()
        elif signal.type is ProbeSignalType.REPLAY_ACKNOWLEDGED:
            self._replay_acknowledged.set()

    async def _capture_and_replay(self, track: rtc.Track) -> None:
        frames: list[rtc.AudioFrame] = []
        stream = self._audio_stream_factory(
            track,
            sample_rate=SAMPLE_RATE_HZ,
            num_channels=CHANNEL_COUNT,
            frame_size_ms=FRAME_SIZE_MS,
        )
        self._attempt.begin_capture(at_ms=self._elapsed_ms())
        stop_waiter = asyncio.create_task(self._capture_stopped.wait())
        drain_deadline: float | None = None
        try:
            iterator = stream.__aiter__()
            while True:
                if stop_waiter.done():
                    if drain_deadline is None:
                        drain_deadline = (
                            asyncio.get_running_loop().time() + self._capture_drain_seconds
                        )
                    remaining_drain = drain_deadline - asyncio.get_running_loop().time()
                    if remaining_drain <= 0:
                        break
                    try:
                        event = await asyncio.wait_for(
                            anext(iterator),
                            timeout=remaining_drain,
                        )
                    except (TimeoutError, StopAsyncIteration):
                        break
                else:
                    frame_waiter = asyncio.create_task(anext(iterator))
                    done, _ = await asyncio.wait(
                        {frame_waiter, stop_waiter},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if frame_waiter in done:
                        try:
                            event = frame_waiter.result()
                        except StopAsyncIteration:
                            break
                    else:
                        frame_waiter.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await frame_waiter
                        continue
                frame = event.frame
                metadata = AudioFrameMetadata(
                    attempt_id=self._spec.attempt_id,
                    sequence=len(frames),
                    sample_rate_hz=frame.sample_rate,
                    channel_count=frame.num_channels,
                    samples_per_channel=frame.samples_per_channel,
                )
                if not self._attempt.accept_frame(metadata, at_ms=self._elapsed_ms()):
                    continue
                frames.append(
                    rtc.AudioFrame(
                        data=bytes(frame.data),
                        sample_rate=frame.sample_rate,
                        num_channels=frame.num_channels,
                        samples_per_channel=frame.samples_per_channel,
                    )
                )
                if self._attempt.metrics.audio_duration_ms > MAX_CLIP_DURATION_MS:
                    await self._fail("capture exceeded the five-second limit")
                    return
            if not self._capture_stopped.is_set():
                try:
                    await asyncio.wait_for(
                        self._capture_stopped.wait(),
                        timeout=self._capture_stop_signal_timeout_seconds,
                    )
                except TimeoutError:
                    await self._fail("capture_stopped signal was not received")
                    return
        except Exception as error:
            await self._fail(f"audio capture failed: {type(error).__name__}")
            return
        finally:
            stop_waiter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stop_waiter
            await stream.aclose()

        try:
            self._attempt.stop_capture(at_ms=self._elapsed_ms())
        except ProbeTransitionRejected as error:
            await self._fail(str(error))
            return
        await self._replay(frames)

    async def _replay(self, frames: list[rtc.AudioFrame]) -> None:
        if not self._attempt.begin_replay(at_ms=self._elapsed_ms()):
            await self._fail("replay could not start")
            return

        source = rtc.AudioSource(SAMPLE_RATE_HZ, CHANNEL_COUNT)
        track = rtc.LocalAudioTrack.create_audio_track("transport-probe-replay", source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        try:
            publication = await self._room.local_participant.publish_track(track, options)
            await asyncio.wait_for(publication.wait_for_subscription(), timeout=5)
            await self._send_status(ProbeSignalType.REPLAY_STARTED)
            for frame in frames:
                await source.capture_frame(frame)
            await source.wait_for_playout()
            self._attempt.complete_replay(at_ms=self._elapsed_ms())
            await self._send_status(ProbeSignalType.REPLAY_COMPLETED)
            await self._wait_for_replay_acknowledgement()
        except Exception as error:
            await self._fail(f"audio replay failed: {type(error).__name__}")
            return
        finally:
            await source.aclose()
        self._finished.set()

    async def _wait_for_replay_acknowledgement(self) -> None:
        try:
            await asyncio.wait_for(
                self._replay_acknowledged.wait(),
                timeout=self._replay_ack_timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Replay completion was not acknowledged for attempt %s",
                self._spec.attempt_id,
            )

    async def _fail(self, reason: str) -> None:
        self._attempt.fail(reason, at_ms=self._elapsed_ms())
        if self._room.isconnected():
            with contextlib.suppress(Exception):
                await self._send_status(ProbeSignalType.FAILED, reason=reason)
        self._finished.set()

    async def _send_status(self, signal_type: ProbeSignalType, *, reason: str | None = None) -> None:
        metrics = ProbeSignalMetrics(
            frame_count=self._attempt.metrics.frame_count,
            audio_duration_ms=round(self._attempt.metrics.audio_duration_ms, 1),
        )
        signal = ProbeControlSignal(
            type=signal_type,
            attempt_id=self._spec.attempt_id,
            emitted_at_ms=self._elapsed_ms(),
            metrics=metrics,
            reason=reason,
        )
        await self._room.local_participant.publish_data(
            signal.model_dump_json(by_alias=True, exclude_none=True),
            reliable=True,
            destination_identities=[self._spec.browser_identity],
            topic=CONTROL_TOPIC,
        )

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._clock_started) * 1_000)
