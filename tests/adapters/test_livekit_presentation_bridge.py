from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import PresentationPhase
from voice_presentation.transport.presentation import (
    PRESENTATION_COMMAND_TOPIC,
    PRESENTATION_STATE_TOPIC,
    PresentationStateUpdate,
)
from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ONE_SLIDE_FIXTURE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "one-slide-presentation.json"
)
BACKEND = VoiceBackendIdentity(
    provider=VoiceProvider.LIVEKIT_INFERENCE_PIPELINE,
    kind=VoiceBackendKind.PIPELINE,
    model="deepgram/nova-3 + google/gemma-4-31b-it + inworld/inworld-tts-2",
)


class FakeVoiceSessionFactory:
    identity = BACKEND

    def __init__(self, result: object) -> None:
        self.result = result

    def build_session(self, *, instructions: str) -> object:
        assert instructions
        return self.result


class FakeSpeechHandle:
    def __init__(self, speech_id: str) -> None:
        self.id = speech_id
        self.interrupted = False
        self._done = False
        self._callbacks: list[object] = []

    def add_done_callback(self, callback) -> None:
        self._callbacks.append(callback)

    def done(self) -> bool:
        return self._done

    def interrupt(self, *, force: bool = False):
        del force
        self.finish(interrupted=True)
        return self

    def finish(self, *, interrupted: bool = False) -> None:
        self.interrupted = interrupted
        self._done = True
        for callback in tuple(self._callbacks):
            callback(self)


class FakeAgentSession:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.generated: list[dict[str, object]] = []
        self.start_calls: list[tuple[object, object]] = []
        self.close_count = 0
        self._speech_sequence = 0

    def on(self, event: str):
        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def start(self, agent: object, *, room: object) -> None:
        self.start_calls.append((agent, room))

    def generate_reply(self, **kwargs: object) -> FakeSpeechHandle:
        self.generated.append(kwargs)
        self._speech_sequence += 1
        return FakeSpeechHandle(f"speech-{self._speech_sequence}")

    async def aclose(self) -> None:
        self.close_count += 1


class FakeLocalParticipant:
    def __init__(self) -> None:
        self.publish_calls: list[tuple[str, dict[str, object]]] = []

    async def publish_data(self, payload: str, **kwargs: object) -> None:
        self.publish_calls.append((payload, kwargs))


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

    async def connect(self, _url: str, _token: str) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def isconnected(self) -> bool:
        return self.connected


@dataclass
class RecordingPresentationAgentConstructor:
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return object()


@dataclass
class RecordingContextLedger:
    records: list[object] = field(default_factory=list)

    def record(self, record: object) -> None:
        self.records.append(record)


class NullAsyncContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


def _spec():
    from voice_presentation.transport.conversation import ConversationSessionSpec

    return ConversationSessionSpec(
        attempt_id="9ea3a1cb-56ea-44d3-b322-d9d3134ce0db",
        room_name="conversation-9ea3a1cb",
        browser_identity="browser-9ea3a1cb",
        worker_identity="voice-worker-9ea3a1cb",
        server_url="wss://example.livekit.cloud",
        worker_token="worker-token",
        instructions="Follow application-selected presentation evidence.",
        backend=BACKEND,
    )


def _application_session() -> ApplicationPresentationSession:
    deck = JsonMaterialRepository(ONE_SLIDE_FIXTURE).load()
    return ApplicationPresentationSession(deck, session_id=_spec().attempt_id)


def _updates(room: FakeRoom) -> list[PresentationStateUpdate]:
    return [
        PresentationStateUpdate.model_validate_json(payload)
        for payload, kwargs in room.local_participant.publish_calls
        if kwargs.get("topic") == PRESENTATION_STATE_TOPIC
    ]


@pytest.mark.offline
def test_bridge_runs_one_grounded_interruption_and_waits_after_answer():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)

        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(agent_session.generated) == 1
        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        assert "Low gears make engine braking feel stronger" in str(
            agent_session.generated[0]["instructions"]
        )

        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        answer_instructions = await prepare_user_turn(
            "Why does engine braking feel stronger in a low gear?"
        )
        assert "lower gear makes the engine turn faster" in answer_instructions

        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            type("Speech", (), {"speech_handle": answer_handle})()
        )
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        answer_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        updates = _updates(room)
        assert updates[-1].view.state.phase is PresentationPhase.WAITING
        assert updates[-1].view.committed_beats == ()
        assert any(
            event.type.value == "playout_interrupted"
            for update in updates
            for event in update.view.events
        )

        room.handlers["data_received"](
            type(
                "Packet",
                (),
                {
                    "data": b'{"action":"continue"}',
                    "topic": PRESENTATION_COMMAND_TOPIC,
                    "participant": browser,
                },
            )()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert len(agent_session.generated) == 2
        assert _updates(room)[-1].view.state.phase is PresentationPhase.PRESENTING

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_records_narration_history_and_current_answer_context():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        context_ledger = RecordingContextLedger()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            http_context_factory=NullAsyncContext,
            context_ledger=context_ledger,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(context_ledger.records) == 1
        narration = context_ledger.records[0]
        assert narration.stable_instructions == _spec().instructions
        assert narration.messages[-1].role == "system"

        agent_session.handlers["conversation_item_added"](
            type(
                "ConversationItem",
                (),
                {
                    "item": type(
                        "Message",
                        (),
                        {
                            "id": "assistant-1",
                            "role": "assistant",
                            "text_content": "The interrupted opening...",
                            "interrupted": True,
                            "metrics": None,
                        },
                    )()
                },
            )()
        )
        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        await prepare_user_turn(
            "Why does engine braking feel stronger in a low gear?"
        )

        answer = context_ledger.records[-1]
        assert [message.role for message in answer.messages[-3:]] == [
            "assistant",
            "developer",
            "user",
        ]
        assert answer.messages[-3].interrupted is True

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_default_presentation_agent_injects_application_evidence_for_the_turn():
    from livekit.agents import llm

    from voice_presentation.adapters.livekit.conversation import (
        _default_presentation_agent_constructor,
    )

    async def scenario() -> None:
        async def prepare_user_turn(question: str) -> str:
            assert question == "Why is a low gear stronger?"
            return "Use only selected evidence."

        agent = _default_presentation_agent_constructor(
            instructions="Follow application evidence.",
            prepare_user_turn=prepare_user_turn,
        )
        turn_context = llm.ChatContext.empty()
        message = llm.ChatMessage(
            role="user",
            content=["Why is a low gear stronger?"],
        )

        await agent.on_user_turn_completed(turn_context, message)

        assert turn_context.messages()[-1].role == "developer"
        assert turn_context.messages()[-1].text_content == "Use only selected evidence."

    asyncio.run(scenario())


@pytest.mark.offline
def test_browser_navigation_interrupts_narration_and_preserves_semantic_cursor():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        deck = JsonMaterialRepository(
            REPOSITORY_ROOT
            / "assets"
            / "motorcycle-controls"
            / "slide-breakdown.json"
        ).load()
        presentation = ApplicationPresentationSession(
            deck, session_id=_spec().attempt_id
        )
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=presentation,
            presentation_agent_constructor=RecordingPresentationAgentConstructor(),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=2,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        original_cursor = _updates(room)[-1].view.state.presentation_cursor
        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )

        room.handlers["data_received"](
            type(
                "Packet",
                (),
                {
                    "data": b'{"action":"navigate","slideId":"braking-abs"}',
                    "topic": PRESENTATION_COMMAND_TOPIC,
                    "participant": browser,
                },
            )()
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        update = _updates(room)[-1]
        assert narration_handle.interrupted is True
        assert update.view.state.phase is PresentationPhase.WAITING
        assert update.view.state.presentation_cursor == original_cursor
        assert update.view.state.interrupted_cursor == original_cursor
        assert update.view.state.visible_slide_id == "braking-abs"
        assert update.view.committed_beats == ()

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_answer_and_continue_schedules_same_beat_with_new_turn():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        await prepare_user_turn(
            "Why does engine braking feel stronger in a low gear? Continue after answering."
        )
        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            type("Speech", (), {"speech_handle": answer_handle})()
        )
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        answer_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(agent_session.generated) == 2
        updates = _updates(room)
        assert updates[-1].view.state.phase is PresentationPhase.PRESENTING
        assert updates[-1].view.state.presentation_cursor.beat_index == 0
        assert updates[-1].view.committed_beats == ()

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_answers_question_received_just_after_presentation_completion():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        narration_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert _updates(room)[-1].view.state.phase is PresentationPhase.COMPLETED

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        answer_instructions = await prepare_user_turn(
            "How does the lower gear help decrease speed?"
        )
        assert "Listener question: How does the lower gear help decrease speed?" in (
            answer_instructions
        )

        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            type("Speech", (), {"speech_handle": answer_handle})()
        )
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        answer_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        updates = _updates(room)
        assert updates[-1].view.state.phase is PresentationPhase.COMPLETED
        assert len(updates[-1].view.committed_beats) == 1
        assert [event.type.value for event in updates[-1].view.events] == [
            "answer_completed"
        ]

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())
