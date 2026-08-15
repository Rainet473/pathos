from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


BACKEND = VoiceBackendIdentity(
    provider=VoiceProvider.GEMINI_LIVE,
    kind=VoiceBackendKind.REALTIME,
    model="gemini-2.5-flash-native-audio-preview-12-2025",
)


class FakeVoiceSessionFactory:
    identity = BACKEND

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[str] = []

    def build_session(self, *, instructions: str) -> object:
        self.calls.append(instructions)
        return self.result


class FakeAgentSession:
    def __init__(self, *, start_failure: Exception | None = None) -> None:
        self.handlers: dict[str, object] = {}
        self.start_failure = start_failure
        self.start_calls: list[tuple[object, object]] = []
        self.close_count = 0

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def start(self, agent: object, *, room: object) -> None:
        if self.start_failure is not None:
            raise self.start_failure
        self.start_calls.append((agent, room))

    async def aclose(self) -> None:
        self.close_count += 1


class FakeRoom:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.connected = False
        self.connect_calls: list[tuple[str, str]] = []
        self.disconnect_count = 0
        self.local_participant = FakeLocalParticipant()

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def connect(self, url: str, token: str) -> None:
        self.connect_calls.append((url, token))
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self.connected = False

    def isconnected(self) -> bool:
        return self.connected


class FakeLocalParticipant:
    def __init__(self) -> None:
        self.publish_calls: list[tuple[str, dict[str, object]]] = []

    async def publish_data(self, payload: str, **kwargs: object) -> None:
        self.publish_calls.append((payload, kwargs))


@dataclass
class RecordingAgentConstructor:
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return object()


@dataclass
class RecordingUsageLedger:
    records: list[object] = field(default_factory=list)

    def record(self, usage: object) -> None:
        self.records.append(usage)


@dataclass
class RecordingDiagnosticLedger:
    events: list[object] = field(default_factory=list)

    def record(self, event: object) -> None:
        self.events.append(event)


class ReadyRunner:
    def __init__(self, release: asyncio.Event) -> None:
        self.release = release

    async def run(self, ready: asyncio.Event) -> None:
        ready.set()
        await self.release.wait()


class FailingRunner:
    async def run(self, ready: asyncio.Event) -> None:
        del ready
        raise RuntimeError("provider failed")


class RecordingAsyncContext:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def __aenter__(self) -> object:
        self.events.append("http_enter")
        return object()

    async def __aexit__(self, *_args: object) -> None:
        self.events.append("http_exit")


def _spec():
    from voice_presentation.transport.conversation import ConversationSessionSpec

    return ConversationSessionSpec(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        room_name="conversation-9ea3a1cb",
        browser_identity="browser-9ea3a1cb",
        worker_identity="voice-worker-9ea3a1cb",
        server_url="wss://example.livekit.cloud",
        worker_token="worker-token",
        instructions="Speak concisely and use no tools.",
        backend=BACKEND,
    )


@pytest.mark.offline
def test_launcher_exposes_identity_rejects_duplicate_and_records_usage():
    from voice_presentation.adapters.livekit.conversation import (
        ConversationSessionAlreadyActive,
        LiveKitConversationSessionLauncher,
    )

    async def scenario() -> None:
        release = asyncio.Event()
        usage = RecordingUsageLedger()
        factory = FakeVoiceSessionFactory(object())
        launcher = LiveKitConversationSessionLauncher(
            voice_session_factory=factory,
            conversation_factory=lambda _spec, _factory: ReadyRunner(release),
            ready_timeout_seconds=0.1,
            usage_ledger=usage,
        )

        assert launcher.identity == BACKEND
        await launcher.launch(_spec())
        with pytest.raises(ConversationSessionAlreadyActive):
            await launcher.launch(_spec())

        release.set()
        await asyncio.sleep(0)
        await launcher.aclose()

        assert len(usage.records) == 1
        assert usage.records[0].attempt_id == _spec().attempt_id
        assert usage.records[0].participant_minutes_upper_bound == 2

    asyncio.run(scenario())


@pytest.mark.offline
def test_launcher_reports_provider_failure_before_ready():
    from voice_presentation.adapters.livekit.conversation import (
        ConversationSessionLaunchError,
        LiveKitConversationSessionLauncher,
    )

    async def scenario() -> None:
        launcher = LiveKitConversationSessionLauncher(
            voice_session_factory=FakeVoiceSessionFactory(object()),
            conversation_factory=lambda _spec, _factory: FailingRunner(),
            ready_timeout_seconds=0.1,
        )

        with pytest.raises(ConversationSessionLaunchError, match="before becoming ready"):
            await launcher.launch(_spec())

        await launcher.aclose()

    asyncio.run(scenario())


@pytest.mark.offline
def test_conversation_session_connects_starts_and_closes_on_browser_departure():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        factory = FakeVoiceSessionFactory(agent_session)
        agent_constructor = RecordingAgentConstructor()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=factory,
            room=room,
            agent_constructor=agent_constructor,
            session_timeout_seconds=1,
        )
        ready = asyncio.Event()

        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        assert room.connect_calls == [(_spec().server_url, _spec().worker_token)]
        assert factory.calls == [_spec().instructions]
        assert agent_constructor.calls == [
            {"instructions": _spec().instructions, "tools": []}
        ]
        assert agent_session.start_calls[0][1] is room

        participant = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_disconnected"](participant)
        await asyncio.wait_for(task, timeout=0.1)

        assert agent_session.close_count == 1
        assert room.disconnect_count == 1

    asyncio.run(scenario())


@pytest.mark.offline
def test_conversation_session_owns_http_context_for_full_provider_lifecycle():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        events: list[str] = []
        room = FakeRoom()

        class OrderingAgentSession(FakeAgentSession):
            async def start(self, agent: object, *, room: object) -> None:
                events.append("agent_start")
                await super().start(agent, room=room)

            async def aclose(self) -> None:
                events.append("agent_close")
                await super().aclose()

        agent_session = OrderingAgentSession()

        class OrderingFactory(FakeVoiceSessionFactory):
            def build_session(self, *, instructions: str) -> object:
                events.append("provider_build")
                return super().build_session(instructions=instructions)

        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=OrderingFactory(agent_session),
            room=room,
            agent_constructor=RecordingAgentConstructor(),
            http_context_factory=lambda: RecordingAsyncContext(events),
            session_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        participant = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_disconnected"](participant)
        await asyncio.wait_for(task, timeout=0.1)

        assert events == [
            "http_enter",
            "provider_build",
            "agent_start",
            "agent_close",
            "http_exit",
        ]

    asyncio.run(scenario())


@pytest.mark.offline
def test_conversation_session_provider_error_is_failed_and_releases_resources():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=RecordingAgentConstructor(),
            session_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        agent_session.handlers["error"](object())
        await asyncio.wait_for(task, timeout=0.1)

        assert runner.usage_outcome == "failed"
        assert agent_session.close_count == 1
        assert room.disconnect_count == 1

    asyncio.run(scenario())


@pytest.mark.offline
def test_conversation_session_start_failure_closes_room_once():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession(start_failure=RuntimeError("model rejected"))
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=RecordingAgentConstructor(),
        )

        with pytest.raises(RuntimeError, match="model rejected"):
            await runner.run(asyncio.Event())

        assert runner.usage_outcome == "failed"
        assert agent_session.close_count == 1
        assert room.disconnect_count == 1

    asyncio.run(scenario())


@pytest.mark.offline
def test_conversation_session_records_and_publishes_safe_timing_events():
    from types import SimpleNamespace

    from voice_presentation.adapters.livekit.conversation import (
        CONVERSATION_DIAGNOSTICS_TOPIC,
        LiveKitConversationSession,
    )

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        diagnostics = RecordingDiagnosticLedger()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=RecordingAgentConstructor(),
            diagnostic_ledger=diagnostics,
            session_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        agent_session.handlers["user_state_changed"](
            SimpleNamespace(old_state="speaking", new_state="listening")
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        agent_session.handlers["metrics_collected"](
            SimpleNamespace(
                metrics=SimpleNamespace(
                    type="realtime_model_metrics",
                    ttft=1.5,
                    duration=2.0,
                    cancelled=False,
                    input_tokens=5,
                    output_tokens=4,
                    total_tokens=9,
                    acquire_time=0.1,
                    connection_reused=True,
                    input_token_details=SimpleNamespace(cached_tokens=0),
                )
            )
        )
        await asyncio.sleep(0)

        participant = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_disconnected"](participant)
        await asyncio.wait_for(task, timeout=0.1)

        assert [event.event_type for event in diagnostics.events] == [
            "user_state_changed",
            "agent_state_changed",
            "realtime_model_metrics",
        ]
        assert diagnostics.events[1].fields == {
            "oldState": "thinking",
            "newState": "speaking",
        }
        assert diagnostics.events[2].fields["modelTtftMs"] == 1500
        assert len(room.local_participant.publish_calls) == 3
        assert all(
            call[1]
            == {
                "reliable": True,
                "destination_identities": [_spec().browser_identity],
                "topic": CONVERSATION_DIAGNOSTICS_TOPIC,
            }
            for call in room.local_participant.publish_calls
        )
        assert all("transcript" not in call[0].lower() for call in room.local_participant.publish_calls)

    asyncio.run(scenario())
