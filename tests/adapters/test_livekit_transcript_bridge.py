from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

import pytest

from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession
from voice_presentation.transport.conversation import ConversationSessionSpec
from voice_presentation.transport.transcript import (
    CONVERSATION_TRANSCRIPT_TOPIC,
    ConversationTranscriptUpdate,
)
from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


pytestmark = pytest.mark.offline

BACKEND = VoiceBackendIdentity(
    provider=VoiceProvider.LIVEKIT_INFERENCE_PIPELINE,
    kind=VoiceBackendKind.PIPELINE,
    model="deepgram/nova-3 + google/gemma-4-31b-it + inworld/inworld-tts-2",
)


class FakeAgentSession:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def start(self, _agent: object, *, room: object) -> None:
        del room

    async def aclose(self) -> None:
        return None


class FakeVoiceSessionFactory:
    identity = BACKEND

    def __init__(self, session: FakeAgentSession) -> None:
        self._session = session

    def build_session(self, *, instructions: str) -> FakeAgentSession:
        assert instructions
        return self._session


class FakeLocalParticipant:
    def __init__(self, *, fail_transcript: bool = False) -> None:
        self.publish_calls: list[tuple[str, dict[str, object]]] = []
        self.fail_transcript = fail_transcript

    async def publish_data(self, payload: str, **kwargs: object) -> None:
        if (
            self.fail_transcript
            and kwargs.get("topic") == CONVERSATION_TRANSCRIPT_TOPIC
        ):
            raise RuntimeError("transcript channel unavailable")
        self.publish_calls.append((payload, kwargs))


class FakeRoom:
    def __init__(self, *, fail_transcript: bool = False) -> None:
        self.handlers: dict[str, object] = {}
        self.connected = False
        self.local_participant = FakeLocalParticipant(
            fail_transcript=fail_transcript
        )

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def connect(self, _url: str, _token: str) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def isconnected(self) -> bool:
        return self.connected


class NullAsyncContext(AbstractAsyncContextManager[object]):
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


@dataclass
class Message:
    role: str
    text_content: str
    id: str | None = None


def _spec() -> ConversationSessionSpec:
    return ConversationSessionSpec(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        room_name="conversation-9ea3a1cb",
        browser_identity="browser-9ea3a1cb",
        worker_identity="voice-worker-9ea3a1cb",
        server_url="wss://example.livekit.cloud",
        worker_token="worker-token",
        instructions="Be concise.",
        backend=BACKEND,
    )


def _updates(room: FakeRoom) -> list[ConversationTranscriptUpdate]:
    return [
        ConversationTranscriptUpdate.model_validate_json(payload)
        for payload, kwargs in room.local_participant.publish_calls
        if kwargs.get("topic") == CONVERSATION_TRANSCRIPT_TOPIC
    ]


def test_agent_session_events_publish_stable_user_and_final_agent_transcript():
    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=lambda **_kwargs: object(),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        agent_session.handlers["user_input_transcribed"](
            type("Transcript", (), {"transcript": "Why does a lower", "is_final": False})()
        )
        agent_session.handlers["user_input_transcribed"](
            type(
                "Transcript",
                (),
                {"transcript": "Why does a lower gear slow more?", "is_final": True},
            )()
        )
        agent_session.handlers["conversation_item_added"](
            type(
                "ConversationItem",
                (),
                {"item": Message("assistant", "Because the ratio multiplies resistance.", "msg-7")},
            )()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        updates = _updates(room)
        assert [update.sequence for update in updates] == [1, 2, 3]
        assert updates[0].entry.id == updates[1].entry.id
        assert updates[0].entry.final is False
        assert updates[1].entry.final is True
        assert updates[2].entry.role == "agent"
        assert updates[2].entry.text == "Because the ratio multiplies resistance."
        assert updates[2].entry.final is True

        room.handlers["disconnected"]("client_initiated")
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


def test_blank_and_unsupported_transcript_events_do_not_publish():
    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=lambda **_kwargs: object(),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        agent_session.handlers["user_input_transcribed"](
            type("Transcript", (), {"transcript": "   ", "is_final": True})()
        )
        agent_session.handlers["conversation_item_added"](
            type("ConversationItem", (), {"item": Message("tool", "internal")})()
        )
        await asyncio.sleep(0)

        assert _updates(room) == []
        room.handlers["disconnected"]("client_initiated")
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


def test_closely_spaced_final_user_fragments_accumulate_into_one_entry():
    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        timestamps = iter((10.0, 10.7, 11.6, 13.2, 13.3))
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=lambda **_kwargs: object(),
            http_context_factory=NullAsyncContext,
            transcript_clock=lambda: next(timestamps),
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        handler = agent_session.handlers["user_input_transcribed"]
        handler(
            type(
                "Transcript",
                (),
                {"transcript": "How does the lower gear help exactly? Like,", "is_final": True},
            )()
        )
        handler(type("Transcript", (), {"transcript": "to", "is_final": True})())
        handler(
            type(
                "Transcript",
                (),
                {"transcript": "decrease the speed and all?", "is_final": True},
            )()
        )
        handler(
            type("Transcript", (), {"transcript": "Separate question", "is_final": True})()
        )
        agent_session.handlers["conversation_item_added"](
            type(
                "ConversationItem",
                (),
                {"item": Message("assistant", "An answer.", "msg-8")},
            )()
        )
        handler(
            type("Transcript", (), {"transcript": "After the answer", "is_final": True})()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        updates = _updates(room)
        assert [update.entry.id for update in updates[:3]] == [
            "user-1",
            "user-1",
            "user-1",
        ]
        assert updates[2].entry.text == (
            "How does the lower gear help exactly? Like, to decrease the speed and all?"
        )
        assert updates[3].entry.id == "user-2"
        assert updates[4].entry.role == "agent"
        assert updates[5].entry.id == "user-3"

        room.handlers["disconnected"]("client_initiated")
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


def test_blank_final_closes_interim_identity():
    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=lambda **_kwargs: object(),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        handler = agent_session.handlers["user_input_transcribed"]
        handler(
            type("Transcript", (), {"transcript": "unfinished", "is_final": False})()
        )
        handler(type("Transcript", (), {"transcript": " ", "is_final": True})())
        handler(
            type("Transcript", (), {"transcript": "new question", "is_final": True})()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        updates = _updates(room)
        assert [update.entry.id for update in updates] == ["user-1", "user-2"]
        room.handlers["disconnected"]("client_initiated")
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


def test_transcript_publish_failure_is_non_fatal(
    caplog: pytest.LogCaptureFixture,
):
    async def scenario() -> None:
        room = FakeRoom(fail_transcript=True)
        agent_session = FakeAgentSession()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            agent_constructor=lambda **_kwargs: object(),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        handler = agent_session.handlers["user_input_transcribed"]
        handler(
            type("Transcript", (), {"transcript": "unfinished", "is_final": False})()
        )
        handler(type("Transcript", (), {"transcript": " ", "is_final": True})())
        handler(
            type("Transcript", (), {"transcript": "new question", "is_final": True})()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert not task.done()
        assert "Could not publish conversation transcript" in caplog.text
        room.handlers["disconnected"]("client_initiated")
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())
