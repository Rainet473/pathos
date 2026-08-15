from __future__ import annotations

import asyncio
import json
import math
import os
from array import array
from pathlib import Path
from uuid import uuid4

import pytest
from livekit import rtc


pytestmark = [pytest.mark.live, pytest.mark.integration]


def test_livekit_cloud_round_trip_with_synthetic_audio():
    if os.getenv("RUN_LIVEKIT_TESTS") != "1":
        pytest.skip("set RUN_LIVEKIT_TESTS=1 to spend LiveKit quota")
    required = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        pytest.fail(f"missing live configuration: {', '.join(missing)}")

    asyncio.run(_round_trip())


async def _round_trip() -> None:
    from voice_presentation.adapters.livekit.probe import (
        CHANNEL_COUNT,
        CONTROL_TOPIC,
        SAMPLE_RATE_HZ,
        LiveKitProbeSessionLauncher,
    )
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer
    from voice_presentation.transport.bootstrap import (
        ProbeBootstrapService,
        ProbeSessionRequest,
    )
    from voice_presentation.transport.contracts import (
        ProbeControlSignal,
        ProbeSignalType,
    )
    from voice_presentation.transport.usage import JsonlUsageLedger

    attempt_id = uuid4()
    prefix = str(attempt_id).split("-", maxsplit=1)[0]
    usage_path = Path(os.getenv("LIVEKIT_USAGE_LOG", ".runtime/livekit-usage.jsonl"))
    launcher = LiveKitProbeSessionLauncher(
        usage_ledger=JsonlUsageLedger(usage_path),
        ready_timeout_seconds=10,
    )
    service = ProbeBootstrapService(
        server_url=os.environ["LIVEKIT_URL"],
        token_issuer=LiveKitTokenIssuer(
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        ),
        session_launcher=launcher,
    )
    room = rtc.Room()
    replay_completed = asyncio.Event()
    replay_audio_seen = asyncio.Event()
    worker_disconnected = asyncio.Event()
    replay_samples = 0
    replay_track_count = 0
    failures: list[str] = []
    statuses: list[str] = []
    collection_tasks: set[asyncio.Task[None]] = set()
    control_tasks: set[asyncio.Task[None]] = set()

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        if participant.identity.startswith("probe-worker-"):
            worker_disconnected.set()

    @room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        if packet.topic != CONTROL_TOPIC or packet.participant is None:
            return
        if not packet.participant.identity.startswith("probe-worker-"):
            return
        try:
            signal = ProbeControlSignal.model_validate_json(packet.data)
        except ValueError:
            return
        if signal.attempt_id != str(attempt_id):
            return
        statuses.append(signal.type.value)
        if signal.type is ProbeSignalType.FAILED:
            failures.append(signal.reason or "worker failed without a reason")
            replay_completed.set()
        elif signal.type is ProbeSignalType.REPLAY_COMPLETED:
            async def acknowledge_completion() -> None:
                await _send_control(
                    room,
                    ProbeSignalType.REPLAY_ACKNOWLEDGED,
                    str(attempt_id),
                )
                replay_completed.set()

            task = asyncio.create_task(acknowledge_completion())
            control_tasks.add(task)
            task.add_done_callback(control_tasks.discard)

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        nonlocal replay_track_count
        if (
            not participant.identity.startswith("probe-worker-")
            or track.kind != rtc.TrackKind.KIND_AUDIO
        ):
            return
        replay_track_count += 1

        async def collect_replay() -> None:
            nonlocal replay_samples
            stream = rtc.AudioStream(
                track,
                sample_rate=SAMPLE_RATE_HZ,
                num_channels=CHANNEL_COUNT,
                frame_size_ms=20,
            )
            try:
                async for event in stream:
                    replay_samples += event.frame.samples_per_channel
                    if any(event.frame.data):
                        replay_audio_seen.set()
            finally:
                await stream.aclose()

        task = asyncio.create_task(collect_replay())
        collection_tasks.add(task)
        task.add_done_callback(collection_tasks.discard)

    publication: rtc.LocalTrackPublication | None = None
    source: rtc.AudioSource | None = None
    try:
        response = await service.create_session(
            ProbeSessionRequest(
                attempt_id=attempt_id,
                room_name=f"probe-{prefix}",
                participant_identity=f"browser-{prefix}",
            )
        )
        await room.connect(response.server_url, response.participant_token)

        source = rtc.AudioSource(SAMPLE_RATE_HZ, CHANNEL_COUNT)
        microphone = rtc.LocalAudioTrack.create_audio_track("synthetic-microphone", source)
        publication = await room.local_participant.publish_track(
            microphone,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )
        await asyncio.wait_for(publication.wait_for_subscription(), timeout=5)
        await _send_control(room, ProbeSignalType.CAPTURE_STARTED, str(attempt_id))

        samples_per_frame = SAMPLE_RATE_HZ // 50
        for frame_index in range(25):
            offset = frame_index * samples_per_frame
            samples = array(
                "h",
                (
                    int(6_000 * math.sin(2 * math.pi * 440 * (offset + index) / SAMPLE_RATE_HZ))
                    for index in range(samples_per_frame)
                ),
            )
            await source.capture_frame(
                rtc.AudioFrame(
                    data=samples.tobytes(),
                    sample_rate=SAMPLE_RATE_HZ,
                    num_channels=CHANNEL_COUNT,
                    samples_per_channel=samples_per_frame,
                )
            )
        await source.wait_for_playout()
        await _send_control(room, ProbeSignalType.CAPTURE_STOPPED, str(attempt_id))
        await room.local_participant.unpublish_track(publication.sid)
        publication = None

        try:
            await asyncio.wait_for(replay_completed.wait(), timeout=20)
        except TimeoutError:
            pytest.fail(
                "replay did not complete; "
                f"statuses={statuses}, replay_samples={replay_samples}"
            )
        await asyncio.wait_for(replay_audio_seen.wait(), timeout=5)
        await asyncio.wait_for(worker_disconnected.wait(), timeout=5)
        usage_row = await _wait_for_usage_row(usage_path, str(attempt_id))

        assert failures == []
        assert replay_samples > 0
        assert replay_track_count == 1
        assert statuses.count("replay_started") == 1
        assert statuses.count("replay_completed") == 1
        assert statuses.index("replay_started") < statuses.index("replay_completed")
        assert usage_row["version"] == 2
        assert usage_row["outcome"] == "completed"
        assert usage_row["participantMinutesUpperBound"] == 2
    finally:
        if publication is not None and room.isconnected():
            await room.local_participant.unpublish_track(publication.sid)
        if source is not None:
            await source.aclose()
        if room.isconnected():
            await room.disconnect()
        await service.aclose()
        if collection_tasks:
            await asyncio.gather(*collection_tasks, return_exceptions=True)
        if control_tasks:
            await asyncio.gather(*control_tasks, return_exceptions=True)


async def _send_control(
    room: rtc.Room,
    signal_type: object,
    attempt_id: str,
) -> None:
    from voice_presentation.adapters.livekit.probe import CONTROL_TOPIC
    from voice_presentation.transport.contracts import (
        ProbeControlSignal,
        ProbeSignalType,
    )

    signal = ProbeControlSignal(
        type=signal_type if isinstance(signal_type, ProbeSignalType) else ProbeSignalType(signal_type),
        attempt_id=attempt_id,
        emitted_at_ms=0,
    )
    await room.local_participant.publish_data(
        signal.model_dump_json(by_alias=True, exclude_none=True),
        reliable=True,
        topic=CONTROL_TOPIC,
    )


async def _wait_for_usage_row(path: Path, attempt_id: str) -> dict[str, object]:
    for _ in range(50):
        if path.exists():
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            matches = [row for row in rows if row.get("attemptId") == attempt_id]
            if len(matches) == 1:
                return matches[0]
        await asyncio.sleep(0.02)
    pytest.fail("live attempt did not append exactly one usage row")
