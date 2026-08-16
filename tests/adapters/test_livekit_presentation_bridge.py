from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import PlayoutPurpose, PresentationPhase
from voice_presentation.domain.provenance import GroundingSource
from voice_presentation.domain.reasoning import (
    PlanningRejectionCode,
    PlanningSnapshot,
    PlanningStage,
    PlanningStatus,
    ValidatedAnswerPlan,
)
from voice_presentation.transport.presentation import (
    PRESENTATION_COMMAND_TOPIC,
    PRESENTATION_STATE_TOPIC,
    PresentationStateUpdate,
)
from voice_presentation.transport.diagnostics import ConversationDiagnosticEvent
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


class FakeAcceptedPlanner:
    def __init__(
        self,
        expected_question: str = (
            "What response did you mean? Continue after answering."
        ),
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self.close_count = 0
        self.expected_question = expected_question

    async def plan(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        snapshot = kwargs["snapshot"]
        context = kwargs["context"]
        on_stage = kwargs["on_stage"]
        assert snapshot.turns[-1].turn_id == context.follow_up_turn_id
        assert snapshot.turns[-1].actual_text == self.expected_question
        assert snapshot.turns[-2].actual_text == (
            "Rider inputs create a response through the drivetrain and tyres..."
        )
        await on_stage(PlanningStage.SEARCHING)
        await on_stage(PlanningStage.PREPARING)
        return SimpleNamespace(
            snapshot=PlanningSnapshot(
                status=PlanningStatus.ACCEPTED,
                tool_steps=1,
                search_calls=0,
                accepted_plan=ValidatedAnswerPlan(
                    plan_id="answer-plan-live-2",
                    follow_up_turn_id=context.follow_up_turn_id,
                    session_version=context.session_version,
                    continuation_preference=context.continuation_preference,
                    scope="grounded",
                    grounding_source=GroundingSource.CONVERSATION,
                    answer_brief=(
                        "Clarify that response means the motorcycle's change after "
                        "a rider input."
                    ),
                    supporting_turn_ids=(snapshot.turns[-2].turn_id,),
                    supporting_slide_ids=("engine-braking",),
                ),
            ),
            trace=(),
            failure_code=None,
        )

    async def aclose(self) -> None:
        self.close_count += 1


class FakeRejectedPlanner:
    async def plan(self, **kwargs: object) -> object:
        del kwargs
        return SimpleNamespace(
            snapshot=PlanningSnapshot(
                status=PlanningStatus.CANCELLED,
                tool_steps=0,
                search_calls=0,
                rejection_code="cancelled",
            ),
            trace=(),
            failure_code=SimpleNamespace(value="provider_error"),
        )

    async def aclose(self) -> None:
        return None


class FakeRecoverableRejectedPlanner:
    async def plan(self, **kwargs: object) -> object:
        del kwargs
        return SimpleNamespace(
            snapshot=PlanningSnapshot(
                status=PlanningStatus.REJECTED,
                tool_steps=1,
                search_calls=1,
                rejection_code=PlanningRejectionCode.UNKNOWN_EVIDENCE,
            ),
            requests=(),
            trace=(),
            failure_code=None,
        )

    async def aclose(self) -> None:
        return None


class FakeExplodingPlanner:
    async def plan(self, **kwargs: object) -> object:
        del kwargs
        raise RuntimeError("credential-shaped provider detail must stay private")

    async def aclose(self) -> None:
        return None


class FakeBlockingPlanner:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.cancelled = False
        self.close_count = 0

    async def plan(self, **kwargs: object) -> object:
        del kwargs
        self.entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self) -> None:
        self.close_count += 1


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


def _diagnostics(room: FakeRoom) -> list[ConversationDiagnosticEvent]:
    return [
        ConversationDiagnosticEvent.model_validate(json.loads(payload))
        for payload, kwargs in room.local_participant.publish_calls
        if kwargs.get("topic") == "voice-conversation.diagnostics.v1"
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

    from voice_presentation.adapters.livekit.conversation_agent import (
        default_presentation_agent_constructor,
    )

    async def scenario() -> None:
        async def prepare_user_turn(
            question: str,
            provider_item_id: str | None,
        ) -> str:
            assert question == "Why is a low gear stronger?"
            assert provider_item_id is None or provider_item_id
            return "Use only selected evidence."

        agent = default_presentation_agent_constructor(
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
def test_default_presentation_agent_suppresses_generation_without_validated_instructions():
    from livekit.agents import llm

    from voice_presentation.adapters.livekit.conversation_agent import (
        default_presentation_agent_constructor,
    )

    async def scenario() -> None:
        calls: list[tuple[str, str | None]] = []

        async def prepare_user_turn(
            question: str,
            provider_item_id: str | None,
        ) -> str | None:
            calls.append((question, provider_item_id))
            return None

        agent = default_presentation_agent_constructor(
            instructions="Follow application evidence.",
            prepare_user_turn=prepare_user_turn,
        )
        turn_context = llm.ChatContext.empty()
        message = llm.ChatMessage(
            id="provider-user-1",
            role="user",
            content=["Why is a low gear stronger?"],
        )

        with pytest.raises(llm.StopResponse):
            await agent.on_user_turn_completed(turn_context, message)

        assert calls == [("Why is a low gear stronger?", "provider-user-1")]
        assert turn_context.messages() == []

    asyncio.run(scenario())


@pytest.mark.offline
def test_default_presentation_agent_coalesces_incomplete_continuation_fragment():
    from livekit.agents import llm

    from voice_presentation.adapters.livekit.conversation_agent import (
        default_presentation_agent_constructor,
    )

    async def scenario() -> None:
        calls: list[tuple[str, str | None]] = []

        async def prepare_user_turn(
            question: str,
            provider_item_id: str | None,
        ) -> str:
            calls.append((question, provider_item_id))
            return "Use the combined follow-up."

        agent = default_presentation_agent_constructor(
            instructions="Follow application evidence.",
            prepare_user_turn=prepare_user_turn,
            follow_up_fragment_window_seconds=0.1,
        )
        first_context = llm.ChatContext.empty()
        second_context = llm.ChatContext.empty()
        first_message = llm.ChatMessage(
            id="provider-user-1",
            role="user",
            content=["Explain what AWS is. Then"],
        )
        second_message = llm.ChatMessage(
            id="provider-user-2",
            role="user",
            content=["narration."],
        )

        first = asyncio.create_task(
            agent.on_user_turn_completed(first_context, first_message)
        )
        await asyncio.sleep(0)
        await agent.on_user_turn_completed(second_context, second_message)
        with pytest.raises(llm.StopResponse):
            await first

        assert calls == [
            ("Explain what AWS is. Then narration.", "provider-user-2")
        ]
        assert second_context.messages()[-1].text_content == (
            "Use the combined follow-up."
        )

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_streams_only_an_accepted_current_plan_and_resumes_after_playout():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        planner = FakeAcceptedPlanner()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            follow_up_planner=planner,
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
        agent_session.handlers["conversation_item_added"](
            type(
                "ConversationItem",
                (),
                {
                    "item": type(
                        "Message",
                        (),
                        {
                            "id": "provider-narration-1",
                            "role": "assistant",
                            "text_content": (
                                "Rider inputs create a response through the drivetrain "
                                "and tyres..."
                            ),
                            "interrupted": True,
                            "metrics": None,
                        },
                    )()
                },
            )()
        )
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        instructions = await prepare_user_turn(
            "What response did you mean? Continue after answering.",
            "provider-user-2",
        )

        assert instructions is not None
        assert "Rider inputs create a response" in instructions
        assert "Do not ask whether the listener is ready" in instructions
        assert len(planner.calls) == 1
        stages = [update.view.planning_stage for update in _updates(room)]
        assert PlanningStage.UNDERSTANDING in stages
        assert PlanningStage.SEARCHING in stages
        assert PlanningStage.PREPARING in stages
        assert _updates(room)[-1].view.state.phase is PresentationPhase.ANSWERING
        assert _updates(room)[-1].view.grounding_source is GroundingSource.CONVERSATION
        assert agent_constructor.calls[0].get("tools", []) == []
        await asyncio.sleep(0)
        planning_diagnostics = [
            event
            for event in _diagnostics(room)
            if event.event_type == "follow_up_planning"
        ]
        assert len(planning_diagnostics) == 1
        assert planning_diagnostics[0].fields["planningStatus"] == "accepted"
        assert "llmTtftMs" not in planning_diagnostics[0].fields

        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            type("Speech", (), {"speech_handle": answer_handle})()
        )
        agent_session.handlers["agent_state_changed"](
            type("State", (), {"old_state": "thinking", "new_state": "speaking"})()
        )
        assert len(agent_session.generated) == 1
        answer_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(agent_session.generated) == 2
        assert agent_session.generated[-1]["tool_choice"] == "none"
        assert agent_session.generated[-1]["tools"] == []
        assert _updates(room)[-1].view.state.phase is PresentationPhase.PRESENTING
        assert _updates(room)[-1].view.committed_beats == ()

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)
        assert planner.close_count == 1

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_interrupted_validated_answer_cannot_resume_or_settle_twice():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        question = "What response did you mean?"
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            follow_up_planner=FakeAcceptedPlanner(question),
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
        agent_session.handlers["conversation_item_added"](
            SimpleNamespace(
                item=SimpleNamespace(
                    id="provider-narration-1",
                    role="assistant",
                    text_content=(
                        "Rider inputs create a response through the drivetrain and tyres..."
                    ),
                    interrupted=True,
                    metrics=None,
                )
            )
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        assert await prepare_user_turn(question, "provider-user-2") is not None
        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            SimpleNamespace(speech_handle=answer_handle)
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        answer_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        update_after_interruption = _updates(room)[-1]

        answer_handle.finish(interrupted=False)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert _updates(room)[-1] == update_after_interruption
        assert (
            update_after_interruption.view.state.phase
            is PresentationPhase.INTERRUPTED
        )
        assert update_after_interruption.view.committed_beats == ()
        assert len(agent_session.generated) == 1

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_rejected_plan_stops_automatic_reply_and_publishes_failure():
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
            follow_up_planner=FakeRejectedPlanner(),
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
        instructions = await prepare_user_turn(
            "What did you mean?",
            "provider-user-2",
        )

        assert instructions is None
        assert len(agent_session.generated) == 1
        update = _updates(room)[-1]
        assert update.view.state.phase is PresentationPhase.WAITING
        assert update.view.planning_failure_code == "provider_error"
        assert update.view.state.presentation_cursor.beat_index == 0

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_recoverable_rejection_streams_one_safe_fallback_and_resumes():
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
            follow_up_planner=FakeRecoverableRejectedPlanner(),
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
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        interrupted_view = _updates(room)[-1].view
        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        instructions = await prepare_user_turn(
            "Does engine braking damage the clutch? Then continue.",
            "provider-user-2",
        )

        assert instructions is not None
        assert "presentation support could not be validated" in instructions
        assert "presentation does not contain the exact answer" not in instructions
        update = _updates(room)[-1]
        assert update.view.state.phase is PresentationPhase.ANSWERING
        assert update.view.planning_recovery_code == "unknown_evidence"
        assert update.view.planning_failure_code is None
        assert (
            update.view.state.visible_slide_id
            == interrupted_view.state.visible_slide_id
        )
        assert (
            update.view.state.presentation_cursor
            == interrupted_view.state.presentation_cursor
        )
        assert update.view.events[0].type.value == "follow_up_planning_recovered"

        answer_handle = FakeSpeechHandle("speech-answer-fallback")
        agent_session.handlers["speech_created"](
            SimpleNamespace(speech_handle=answer_handle)
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        answer_handle.finish()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(agent_session.generated) == 2
        assert _updates(room)[-1].view.state.phase is PresentationPhase.PRESENTING
        assert _updates(room)[-1].view.committed_beats == ()

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_bridge_planner_exception_is_sanitized_and_never_reaches_speech():
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
            follow_up_planner=FakeExplodingPlanner(),
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
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        instructions = await prepare_user_turn(
            "What did you mean?",
            "provider-user-2",
        )

        assert instructions is None
        assert len(agent_session.generated) == 1
        update = _updates(room)[-1]
        assert update.view.state.phase is PresentationPhase.WAITING
        assert update.view.planning_failure_code == "provider_error"
        assert "credential-shaped" not in update.model_dump_json()

        room.handlers["participant_disconnected"](browser)
        await asyncio.wait_for(task, timeout=0.1)

    asyncio.run(scenario())


@pytest.mark.offline
def test_browser_disconnect_cancels_inflight_planning_without_fallback_speech():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        planner = FakeBlockingPlanner()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=_application_session(),
            presentation_agent_constructor=agent_constructor,
            follow_up_planner=planner,
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=1,
        )
        ready = asyncio.Event()
        run_task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = type("Participant", (), {"identity": _spec().browser_identity})()
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        prepare_task = asyncio.create_task(
            prepare_user_turn(
                "How does rev matching work?",
                "provider-user-2",
            )
        )
        await asyncio.wait_for(planner.entered.wait(), timeout=0.1)

        try:
            room.handlers["participant_disconnected"](browser)
            await asyncio.wait_for(run_task, timeout=0.1)
            await asyncio.sleep(0)

            assert prepare_task.cancelled()
            assert planner.cancelled is True
            assert planner.close_count == 1
            assert len(agent_session.generated) == 1
            assert all(
                update.view.planning_recovery_code is None
                for update in _updates(room)
            )
        finally:
            if not prepare_task.done():
                prepare_task.cancel()
                await asyncio.gather(prepare_task, return_exceptions=True)

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
def test_browser_navigation_validates_then_abandons_answer_and_continue_once():
    from voice_presentation.adapters.livekit.conversation import LiveKitConversationSession

    async def scenario() -> None:
        question = "What response did you mean? Continue after answering."
        room = FakeRoom()
        agent_session = FakeAgentSession()
        agent_constructor = RecordingPresentationAgentConstructor()
        deck = JsonMaterialRepository(
            REPOSITORY_ROOT
            / "assets"
            / "motorcycle-controls"
            / "slide-breakdown.json"
        ).load()
        runner = LiveKitConversationSession(
            _spec(),
            voice_session_factory=FakeVoiceSessionFactory(agent_session),
            room=room,
            presentation_session=ApplicationPresentationSession(
                deck,
                session_id=_spec().attempt_id,
            ),
            presentation_agent_constructor=agent_constructor,
            follow_up_planner=FakeAcceptedPlanner(question),
            http_context_factory=NullAsyncContext,
            idle_timeout_seconds=1,
            absolute_timeout_seconds=2,
        )
        ready = asyncio.Event()
        task = asyncio.create_task(runner.run(ready))
        await asyncio.wait_for(ready.wait(), timeout=0.1)
        browser = SimpleNamespace(identity=_spec().browser_identity)
        room.handlers["participant_connected"](browser)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        original_cursor = _updates(room)[-1].view.state.presentation_cursor
        narration_handle = runner.active_speech_handle
        assert narration_handle is not None
        agent_session.handlers["conversation_item_added"](
            SimpleNamespace(
                item=SimpleNamespace(
                    id="provider-narration-1",
                    role="assistant",
                    text_content=(
                        "Rider inputs create a response through the drivetrain and tyres..."
                    ),
                    interrupted=True,
                    metrics=None,
                )
            )
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        narration_handle.finish(interrupted=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        prepare_user_turn = agent_constructor.calls[0]["prepare_user_turn"]
        assert await prepare_user_turn(question, "provider-user-2") is not None
        answer_handle = FakeSpeechHandle("speech-answer")
        agent_session.handlers["speech_created"](
            SimpleNamespace(speech_handle=answer_handle)
        )
        agent_session.handlers["agent_state_changed"](
            SimpleNamespace(old_state="thinking", new_state="speaking")
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        answering = _updates(room)[-1]
        assert answering.view.state.phase is PresentationPhase.ANSWERING
        assert answering.view.state.active_playout is not None
        assert (
            answering.view.state.active_playout.purpose
            is PlayoutPurpose.ANSWER
        )

        def navigate(slide_id: str) -> None:
            room.handlers["data_received"](
                SimpleNamespace(
                    data=json.dumps(
                        {"action": "navigate", "slideId": slide_id}
                    ).encode(),
                    topic=PRESENTATION_COMMAND_TOPIC,
                    participant=browser,
                )
            )

        navigate("missing-slide")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert answer_handle.interrupted is False
        assert _updates(room)[-1] == answering

        navigate(answering.view.state.visible_slide_id)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert answer_handle.interrupted is False
        assert _updates(room)[-1] == answering

        navigate("braking-abs")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        abandoned = _updates(room)[-1]
        assert answer_handle.interrupted is True
        assert abandoned.view.state.phase is PresentationPhase.WAITING
        assert abandoned.view.state.presentation_cursor == original_cursor
        assert abandoned.view.state.visible_slide_id == "braking-abs"
        assert abandoned.view.state.continuation_preference is None
        assert abandoned.view.state.answer_return_phase is None
        assert len(agent_session.generated) == 1

        answer_handle.finish(interrupted=False)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert _updates(room)[-1] == abandoned
        assert len(agent_session.generated) == 1

        room.handlers["data_received"](
            SimpleNamespace(
                data=b'{"action":"continue"}',
                topic=PRESENTATION_COMMAND_TOPIC,
                participant=browser,
            )
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        resumed = _updates(room)[-1]
        assert resumed.view.state.phase is PresentationPhase.PRESENTING
        assert resumed.view.state.visible_slide_id == original_cursor.slide_id
        assert len(agent_session.generated) == 2

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
