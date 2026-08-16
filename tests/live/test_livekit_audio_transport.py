from __future__ import annotations

import asyncio
import math
import os
from array import array
from uuid import uuid4

import pytest
from livekit import rtc


pytestmark = [pytest.mark.live, pytest.mark.integration]

SAMPLE_RATE_HZ = 48_000
CHANNEL_COUNT = 1


def test_livekit_cloud_carries_synthetic_audio_between_two_participants():
    """Opt-in infrastructure diagnostic; this is not a second product runtime."""
    if os.getenv("RUN_LIVEKIT_TESTS") != "1":
        pytest.skip("set RUN_LIVEKIT_TESTS=1 to spend LiveKit quota")
    required = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        pytest.fail(f"missing live configuration: {', '.join(missing)}")

    asyncio.run(_audio_transport_smoke())


async def _audio_transport_smoke() -> None:
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer

    prefix = str(uuid4()).split("-", maxsplit=1)[0]
    room_name = f"audio-smoke-{prefix}"
    issuer = LiveKitTokenIssuer(
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    subscriber_token = issuer.issue_join_token(
        room_name=room_name,
        identity=f"audio-subscriber-{prefix}",
        can_publish=False,
        can_subscribe=True,
        can_publish_data=False,
        can_publish_sources=(),
        ttl_seconds=120,
    )
    publisher_token = issuer.issue_join_token(
        room_name=room_name,
        identity=f"audio-publisher-{prefix}",
        can_publish=True,
        can_subscribe=False,
        can_publish_data=False,
        can_publish_sources=("microphone",),
        ttl_seconds=120,
    )

    subscriber = rtc.Room()
    publisher = rtc.Room()
    audio_seen = asyncio.Event()
    received_samples = 0
    collection_tasks: list[asyncio.Task[None]] = []

    @subscriber.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if (
            participant.identity != f"audio-publisher-{prefix}"
            or track.kind != rtc.TrackKind.KIND_AUDIO
        ):
            return

        async def collect_audio() -> None:
            nonlocal received_samples
            stream = rtc.AudioStream(
                track,
                sample_rate=SAMPLE_RATE_HZ,
                num_channels=CHANNEL_COUNT,
                frame_size_ms=20,
            )
            try:
                async for event in stream:
                    received_samples += event.frame.samples_per_channel
                    if any(event.frame.data):
                        audio_seen.set()
                        return
            finally:
                await stream.aclose()

        task = asyncio.create_task(collect_audio())
        collection_tasks.append(task)

    publication: rtc.LocalTrackPublication | None = None
    source: rtc.AudioSource | None = None
    try:
        await subscriber.connect(os.environ["LIVEKIT_URL"], subscriber_token)
        await publisher.connect(os.environ["LIVEKIT_URL"], publisher_token)

        source = rtc.AudioSource(SAMPLE_RATE_HZ, CHANNEL_COUNT)
        microphone = rtc.LocalAudioTrack.create_audio_track("synthetic-microphone", source)
        publication = await publisher.local_participant.publish_track(
            microphone,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )
        await asyncio.wait_for(publication.wait_for_subscription(), timeout=5)

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
        await asyncio.wait_for(audio_seen.wait(), timeout=5)
        assert received_samples > 0
    finally:
        if publication is not None and publisher.isconnected():
            await publisher.local_participant.unpublish_track(publication.sid)
        if source is not None:
            await source.aclose()
        if publisher.isconnected():
            await publisher.disconnect()
        if subscriber.isconnected():
            await subscriber.disconnect()
        if collection_tasks:
            await asyncio.gather(*collection_tasks, return_exceptions=True)
