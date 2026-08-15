from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest


@dataclass
class ReadySession:
    release: asyncio.Event

    async def run(self, ready: asyncio.Event) -> None:
        ready.set()
        await self.release.wait()


class FailingSession:
    async def run(self, ready: asyncio.Event) -> None:
        raise RuntimeError("connection failed")


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
        launcher = LiveKitProbeSessionLauncher(
            session_factory=lambda _: ReadySession(release),
            ready_timeout_seconds=0.1,
        )
        await launcher.launch(_spec())

        with pytest.raises(ProbeSessionAlreadyActive):
            await launcher.launch(_spec())

        release.set()
        await launcher.aclose()

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
