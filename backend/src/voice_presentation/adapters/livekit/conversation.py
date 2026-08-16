from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Protocol

from livekit import rtc

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
    GenerationDirective,
    PresentationActionResult,
)
from voice_presentation.transport.conversation import ConversationSessionSpec
from voice_presentation.transport.context_trace import (
    InferenceContextLedger,
    InferenceContextTrace,
    NullInferenceContextLedger,
)
from voice_presentation.transport.diagnostics import (
    ConversationDiagnosticEvent,
    ConversationDiagnosticLedger,
    ConversationDiagnostics,
    NullConversationDiagnosticLedger,
)
from voice_presentation.transport.lifecycle import (
    CONVERSATION_LIFECYCLE_TOPIC,
    ConversationLifecycleReason,
    ConversationLifecycleUpdate,
)
from voice_presentation.transport.usage import NullUsageLedger, UsageLedger, UsageRecord
from voice_presentation.transport.presentation import (
    PRESENTATION_COMMAND_TOPIC,
    PRESENTATION_STATE_TOPIC,
    PresentationCommand,
    PresentationStateUpdate,
)
from voice_presentation.transport.transcript import (
    CONVERSATION_TRANSCRIPT_TOPIC,
    ConversationTranscriptEntry,
    ConversationTranscriptUpdate,
)
from voice_presentation.voice.sessions import VoiceBackendIdentity, VoiceSessionFactory

logger = logging.getLogger(__name__)

CONVERSATION_DIAGNOSTICS_TOPIC = "voice-conversation.diagnostics.v1"


class ConversationSessionAlreadyActive(RuntimeError):
    """Raised when the same live attempt is launched more than once."""


class ConversationSessionLaunchError(RuntimeError):
    """Raised when a live worker cannot become ready for the browser."""


class RunnableConversationSession(Protocol):
    @property
    def usage_outcome(self) -> str: ...

    async def run(self, ready: asyncio.Event) -> None: ...


ConversationFactory = Callable[
    [ConversationSessionSpec, VoiceSessionFactory], RunnableConversationSession
]
PresentationSessionFactory = Callable[[str], ApplicationPresentationSession]
AgentConstructor = Callable[..., object]
PresentationAgentConstructor = Callable[..., object]
HttpContextFactory = Callable[[], contextlib.AbstractAsyncContextManager[object]]
PrepareUserTurn = Callable[[str], Awaitable[str]]


def _default_agent_constructor(**kwargs: Any) -> object:
    from livekit.agents import Agent

    return Agent(**kwargs)


def _default_presentation_agent_constructor(
    *,
    instructions: str,
    prepare_user_turn: PrepareUserTurn,
) -> object:
    from livekit.agents import Agent

    class ApplicationControlledPresentationAgent(Agent):
        async def on_user_turn_completed(
            self,
            turn_ctx: object,
            new_message: object,
        ) -> None:
            question = str(getattr(new_message, "text_content", "")).strip()
            answer_instructions = await prepare_user_turn(question)
            turn_ctx.add_message(role="developer", content=answer_instructions)

    return ApplicationControlledPresentationAgent(
        instructions=instructions,
        tools=[],
    )


def _default_http_context_factory() -> contextlib.AbstractAsyncContextManager[object]:
    from livekit.agents.utils import http_context

    return http_context.open()


class LiveKitConversationSessionLauncher:
    def __init__(
        self,
        *,
        voice_session_factory: VoiceSessionFactory,
        conversation_factory: ConversationFactory | None = None,
        ready_timeout_seconds: float = 12,
        usage_ledger: UsageLedger | None = None,
        diagnostic_ledger: ConversationDiagnosticLedger | None = None,
        context_ledger: InferenceContextLedger | None = None,
        presentation_session_factory: PresentationSessionFactory | None = None,
    ) -> None:
        if ready_timeout_seconds <= 0:
            raise ValueError("ready timeout must be positive")
        self._voice_session_factory = voice_session_factory
        self._conversation_factory = conversation_factory
        self._ready_timeout_seconds = ready_timeout_seconds
        self._usage_ledger = usage_ledger or NullUsageLedger()
        self._diagnostic_ledger = (
            diagnostic_ledger or NullConversationDiagnosticLedger()
        )
        self._context_ledger = context_ledger or NullInferenceContextLedger()
        self._presentation_session_factory = presentation_session_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._voice_session_factory.identity

    async def launch(self, session: ConversationSessionSpec) -> None:
        self._discard_finished()
        existing = self._tasks.get(session.attempt_id)
        if existing is not None and not existing.done():
            raise ConversationSessionAlreadyActive(
                f"attempt {session.attempt_id} is already active"
            )

        ready = asyncio.Event()
        if self._conversation_factory is None:
            presentation_session = None
            if self._presentation_session_factory is not None:
                presentation_session = self._presentation_session_factory(
                    session.attempt_id
                )
            runner = LiveKitConversationSession(
                session,
                self._voice_session_factory,
                diagnostic_ledger=self._diagnostic_ledger,
                context_ledger=self._context_ledger,
                presentation_session=presentation_session,
            )
        else:
            runner = self._conversation_factory(session, self._voice_session_factory)
        task = asyncio.create_task(
            self._run_and_record(session, runner, ready),
            name=f"conversation-{session.attempt_id}",
        )
        self._tasks[session.attempt_id] = task
        task.add_done_callback(
            lambda finished, attempt_id=session.attempt_id: self._on_session_finished(
                attempt_id, finished
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
            raise ConversationSessionLaunchError(
                "live worker failed before becoming ready"
            ) from error

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._tasks.pop(session.attempt_id, None)
        raise ConversationSessionLaunchError(
            "live worker did not become ready in time"
        )

    async def _run_and_record(
        self,
        session: ConversationSessionSpec,
        runner: RunnableConversationSession,
        ready: asyncio.Event,
    ) -> None:
        started_at = datetime.now(UTC)
        started_monotonic = time.monotonic()
        outcome = "completed"
        try:
            await runner.run(ready)
            outcome = runner.usage_outcome
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

    def _on_session_finished(
        self, attempt_id: str, task: asyncio.Task[None]
    ) -> None:
        if self._tasks.get(attempt_id) is task:
            self._tasks.pop(attempt_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Live conversation session failed", exc_info=error)


class LiveKitConversationSession:
    def __init__(
        self,
        spec: ConversationSessionSpec,
        voice_session_factory: VoiceSessionFactory,
        *,
        room: rtc.Room | None = None,
        agent_constructor: AgentConstructor = _default_agent_constructor,
        presentation_session: ApplicationPresentationSession | None = None,
        presentation_agent_constructor: PresentationAgentConstructor = (
            _default_presentation_agent_constructor
        ),
        http_context_factory: HttpContextFactory = _default_http_context_factory,
        diagnostic_ledger: ConversationDiagnosticLedger | None = None,
        context_ledger: InferenceContextLedger | None = None,
        transcript_clock: Callable[[], float] = time.monotonic,
        transcript_merge_window_seconds: float = 1.5,
        idle_timeout_seconds: float | None = None,
        absolute_timeout_seconds: float | None = None,
    ) -> None:
        idle_timeout_seconds = (
            spec.idle_timeout_seconds
            if idle_timeout_seconds is None
            else idle_timeout_seconds
        )
        absolute_timeout_seconds = (
            spec.absolute_timeout_seconds
            if absolute_timeout_seconds is None
            else absolute_timeout_seconds
        )
        if idle_timeout_seconds <= 0:
            raise ValueError("idle timeout must be positive")
        if absolute_timeout_seconds <= 0:
            raise ValueError("absolute timeout must be positive")
        if transcript_merge_window_seconds <= 0:
            raise ValueError("transcript merge window must be positive")
        self._spec = spec
        self._voice_session_factory = voice_session_factory
        self._room = room or rtc.Room()
        self._agent_constructor = agent_constructor
        self._presentation_session = presentation_session
        self._presentation_agent_constructor = presentation_agent_constructor
        self._http_context_factory = http_context_factory
        self._idle_timeout_seconds = idle_timeout_seconds
        self._absolute_timeout_seconds = absolute_timeout_seconds
        self._finished = asyncio.Event()
        self._activity: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._termination_reason: str | None = None
        self._agent_session: object | None = None
        self._usage_outcome = "completed"
        self._diagnostics = ConversationDiagnostics(
            attempt_id=spec.attempt_id,
            ledger=diagnostic_ledger,
        )
        self._context_trace = InferenceContextTrace(
            attempt_id=spec.attempt_id,
            stable_instructions=spec.instructions,
            ledger=context_ledger,
        )
        self._transcript_clock = transcript_clock
        self._transcript_merge_window_seconds = transcript_merge_window_seconds
        self._diagnostic_tasks: set[asyncio.Task[None]] = set()
        self._transcript_tasks: set[asyncio.Task[None]] = set()
        self._transcript_tail: asyncio.Task[None] | None = None
        self._transcript_sequence = 0
        self._user_transcript_sequence = 0
        self._agent_transcript_sequence = 0
        self._active_user_transcript_id: str | None = None
        self._active_user_transcript_prefix = ""
        self._last_final_user_transcript_id: str | None = None
        self._last_final_user_transcript_text = ""
        self._last_final_user_transcript_at: float | None = None
        self._presentation_tasks: set[asyncio.Task[None]] = set()
        self._presentation_lock = asyncio.Lock()
        self._presentation_started = False
        self._pending_generation: GenerationDirective | None = None
        self._active_speech: _SpeechBinding | None = None
        self._settled_turns: set[str] = set()

    @property
    def usage_outcome(self) -> str:
        return self._usage_outcome

    @property
    def termination_reason(self) -> str | None:
        return self._termination_reason

    @property
    def active_speech_handle(self) -> object | None:
        if self._active_speech is None:
            return None
        return self._active_speech.handle

    async def run(self, ready: asyncio.Event) -> None:
        self._register_room_events()
        try:
            async with self._http_context_factory():
                try:
                    await self._room.connect(
                        self._spec.server_url, self._spec.worker_token
                    )
                    self._agent_session = self._voice_session_factory.build_session(
                        instructions=self._spec.instructions
                    )
                    self._register_agent_events(self._agent_session)
                    if self._presentation_session is None:
                        agent = self._agent_constructor(
                            instructions=self._spec.instructions,
                            tools=[],
                        )
                    else:
                        agent = self._presentation_agent_constructor(
                            instructions=self._spec.instructions,
                            prepare_user_turn=self._prepare_user_turn,
                        )
                    await self._agent_session.start(agent, room=self._room)
                    ready.set()
                    terminal_reason = await self._wait_for_session_end()
                    if terminal_reason in {
                        ConversationLifecycleReason.IDLE_TIMEOUT.value,
                        ConversationLifecycleReason.ABSOLUTE_TIMEOUT.value,
                    }:
                        await self._publish_lifecycle(
                            ConversationLifecycleReason(terminal_reason)
                        )
                finally:
                    if self._presentation_tasks:
                        await asyncio.gather(
                            *self._presentation_tasks,
                            return_exceptions=True,
                        )
                    if self._diagnostic_tasks:
                        await asyncio.gather(
                            *self._diagnostic_tasks, return_exceptions=True
                        )
                    if self._transcript_tasks:
                        await asyncio.gather(
                            *self._transcript_tasks, return_exceptions=True
                        )
                    if self._agent_session is not None:
                        with contextlib.suppress(Exception):
                            await self._agent_session.aclose()
                    if self._room.isconnected():
                        with contextlib.suppress(Exception):
                            await self._room.disconnect()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._usage_outcome = "failed"
            raise

    def _register_room_events(self) -> None:
        @self._room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            if participant.identity == self._spec.browser_identity:
                self._touch_activity()
            if (
                self._presentation_session is not None
                and participant.identity == self._spec.browser_identity
            ):
                self._queue_presentation(self._start_presentation())

        @self._room.on("data_received")
        def on_data_received(packet: rtc.DataPacket) -> None:
            participant = packet.participant
            if (
                self._presentation_session is None
                or packet.topic != PRESENTATION_COMMAND_TOPIC
                or participant is None
                or participant.identity != self._spec.browser_identity
            ):
                return
            try:
                command = PresentationCommand.model_validate_json(packet.data)
            except Exception:
                logger.warning("Ignored malformed presentation command")
                return
            if command.action == "continue":
                self._touch_activity()
                self._queue_presentation(self._continue_presentation())
            elif command.action == "navigate":
                assert command.slide_id is not None
                self._touch_activity()
                self._queue_presentation(
                    self._navigate_presentation(command.slide_id)
                )

        @self._room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            if participant.identity == self._spec.browser_identity:
                self._termination_reason = "browser_disconnected"
                self._finished.set()

        @self._room.on("disconnected")
        def on_disconnected(_reason: object) -> None:
            if not self._finished.is_set():
                self._usage_outcome = "failed"
                self._termination_reason = "unexpected_disconnect"
                self._finished.set()

    def _register_agent_events(self, agent_session: object) -> None:
        @agent_session.on("user_input_transcribed")
        def on_user_input_transcribed(event: object) -> None:
            text = str(getattr(event, "transcript", "")).strip()
            is_final = bool(getattr(event, "is_final", False))
            if not text:
                if is_final:
                    self._close_user_transcript_group()
                return
            self._touch_activity()
            now = self._transcript_clock()
            if self._active_user_transcript_id is None:
                can_merge = (
                    self._last_final_user_transcript_id is not None
                    and self._last_final_user_transcript_at is not None
                    and now - self._last_final_user_transcript_at
                    <= self._transcript_merge_window_seconds
                )
                if can_merge:
                    self._active_user_transcript_id = (
                        self._last_final_user_transcript_id
                    )
                    self._active_user_transcript_prefix = (
                        self._last_final_user_transcript_text
                    )
                else:
                    self._user_transcript_sequence += 1
                    self._active_user_transcript_id = (
                        f"user-{self._user_transcript_sequence}"
                    )
                    self._active_user_transcript_prefix = ""
            accumulated_text = " ".join(
                part
                for part in (self._active_user_transcript_prefix, text)
                if part
            )
            entry = ConversationTranscriptEntry(
                id=self._active_user_transcript_id,
                role="user",
                text=accumulated_text,
                final=is_final,
            )
            self._queue_transcript(entry)
            if is_final:
                self._last_final_user_transcript_id = entry.id
                self._last_final_user_transcript_text = entry.text
                self._last_final_user_transcript_at = now
                self._active_user_transcript_id = None
                self._active_user_transcript_prefix = ""

        @agent_session.on("conversation_item_added")
        def on_conversation_item_added(event: object) -> None:
            item = getattr(event, "item", None)
            if item is None:
                return
            self._touch_activity()
            metrics = getattr(item, "metrics", None)
            supported_metric_names = {
                "end_of_turn_delay",
                "on_user_turn_completed_delay",
                "llm_node_ttft",
                "tts_node_ttfb",
            }
            if isinstance(metrics, Mapping) and any(
                name in metrics for name in supported_metric_names
            ):
                self._queue_diagnostic(
                    self._diagnostics.record_turn_metrics(metrics)
                )
            role = str(getattr(item, "role", ""))
            text = str(getattr(item, "text_content", "")).strip()
            if role in {"user", "assistant"} and text:
                self._context_trace.add_history_message(
                    provider_item_id=str(getattr(item, "id", "") or ""),
                    role=role,
                    content=text,
                    interrupted=bool(getattr(item, "interrupted", False)),
                )
            if role != "assistant":
                return
            if not text:
                return
            self._close_user_transcript_group()
            provider_id = str(getattr(item, "id", "") or "").strip()
            if provider_id:
                entry_id = f"agent-{provider_id}"
            else:
                self._agent_transcript_sequence += 1
                entry_id = f"agent-{self._agent_transcript_sequence}"
            self._queue_transcript(
                ConversationTranscriptEntry(
                    id=entry_id,
                    role="agent",
                    text=text,
                    final=True,
                )
            )

        @agent_session.on("user_state_changed")
        def on_user_state_changed(event: object) -> None:
            self._touch_activity()
            diagnostic = self._diagnostics.record_user_state(
                old_state=str(getattr(event, "old_state")),
                new_state=str(getattr(event, "new_state")),
            )
            self._queue_diagnostic(diagnostic)

        @agent_session.on("agent_state_changed")
        def on_agent_state_changed(event: object) -> None:
            self._touch_activity()
            diagnostic = self._diagnostics.record_agent_state(
                old_state=str(getattr(event, "old_state")),
                new_state=str(getattr(event, "new_state")),
            )
            self._queue_diagnostic(diagnostic)
            if (
                self._presentation_session is not None
                and str(getattr(event, "new_state")) == "speaking"
            ):
                self._queue_presentation(self._mark_playout_started())

        @agent_session.on("speech_created")
        def on_speech_created(event: object) -> None:
            self._touch_activity()
            if self._presentation_session is None:
                return
            directive = self._pending_generation
            if directive is None:
                return
            self._bind_speech(getattr(event, "speech_handle"), directive)
            self._pending_generation = None

        @agent_session.on("error")
        def on_error(_event: object) -> None:
            self._usage_outcome = "failed"
            self._termination_reason = "provider_error"
            self._finished.set()

    def _touch_activity(self) -> None:
        if self._activity.empty():
            self._activity.put_nowait(None)

    async def _wait_for_session_end(self) -> str:
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        idle_deadline = started_at + self._idle_timeout_seconds
        absolute_deadline = started_at + self._absolute_timeout_seconds

        while not self._finished.is_set():
            now = loop.time()
            deadline = min(idle_deadline, absolute_deadline)
            remaining = deadline - now
            if remaining <= 0:
                reason = (
                    ConversationLifecycleReason.ABSOLUTE_TIMEOUT.value
                    if absolute_deadline <= idle_deadline
                    else ConversationLifecycleReason.IDLE_TIMEOUT.value
                )
                self._termination_reason = reason
                return reason

            finished_waiter = asyncio.create_task(self._finished.wait())
            activity_waiter = asyncio.create_task(self._activity.get())
            done, pending = await asyncio.wait(
                {finished_waiter, activity_waiter},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for waiter in pending:
                waiter.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            if finished_waiter in done and self._finished.is_set():
                return self._termination_reason or "stopped"
            if activity_waiter in done:
                idle_deadline = loop.time() + self._idle_timeout_seconds

        return self._termination_reason or "stopped"

    def _close_user_transcript_group(self) -> None:
        self._active_user_transcript_id = None
        self._active_user_transcript_prefix = ""
        self._last_final_user_transcript_id = None
        self._last_final_user_transcript_text = ""
        self._last_final_user_transcript_at = None

    def _queue_diagnostic(self, event: ConversationDiagnosticEvent) -> None:
        task = asyncio.create_task(self._publish_diagnostic(event))
        self._diagnostic_tasks.add(task)
        task.add_done_callback(self._diagnostic_tasks.discard)

    def _queue_transcript(self, entry: ConversationTranscriptEntry) -> None:
        self._transcript_sequence += 1
        update = ConversationTranscriptUpdate.from_entry(
            attempt_id=self._spec.attempt_id,
            sequence=self._transcript_sequence,
            entry=entry,
        )
        previous = self._transcript_tail

        async def publish_after_previous() -> None:
            if previous is not None:
                await asyncio.gather(previous, return_exceptions=True)
            await self._publish_transcript(update)

        task = asyncio.create_task(publish_after_previous())
        self._transcript_tail = task
        self._transcript_tasks.add(task)
        task.add_done_callback(self._transcript_tasks.discard)

    def _queue_presentation(self, awaitable: Awaitable[None]) -> None:
        task = asyncio.create_task(awaitable)
        self._presentation_tasks.add(task)
        task.add_done_callback(self._presentation_tasks.discard)

    async def _start_presentation(self) -> None:
        if self._presentation_session is None or self._presentation_started:
            return
        async with self._presentation_lock:
            if self._presentation_started:
                return
            self._presentation_started = True
            result = self._presentation_session.start()
            await self._publish_presentation(result)
            if result.generation is not None:
                self._execute_generation(result.generation)

    async def _prepare_user_turn(self, question: str) -> str:
        if self._presentation_session is None:
            raise RuntimeError("presentation session is not configured")
        async with self._presentation_lock:
            binding = self._active_speech
            if (
                binding is not None
                and binding.turn_id not in self._settled_turns
                and bool(getattr(binding.handle, "interrupted", False))
            ):
                if not binding.started:
                    started = self._presentation_session.playout_started(
                        turn_id=binding.turn_id
                    )
                    binding.started = True
                    await self._publish_presentation(started)
                await self._settle_binding_locked(binding, interrupted=True)

            result = self._presentation_session.prepare_question(question)
            if result.generation is None:
                raise RuntimeError("question preparation did not issue an answer turn")
            self._pending_generation = result.generation
            await self._publish_presentation(result)
            self._context_trace.record_generation(
                result.generation,
                current_user_message=question,
            )
            return result.generation.instructions

    async def _mark_playout_started(self) -> None:
        if self._presentation_session is None:
            return
        async with self._presentation_lock:
            binding = self._active_speech
            if (
                binding is None
                or binding.started
                or binding.turn_id in self._settled_turns
            ):
                return
            result = self._presentation_session.playout_started(
                turn_id=binding.turn_id
            )
            binding.started = True
            await self._publish_presentation(result)

    async def _continue_presentation(self) -> None:
        if self._presentation_session is None:
            return
        async with self._presentation_lock:
            result = self._presentation_session.continue_presentation()
            await self._publish_presentation(result)
            if result.generation is not None:
                self._execute_generation(result.generation)

    async def _navigate_presentation(self, slide_id: str) -> None:
        if self._presentation_session is None:
            return
        async with self._presentation_lock:
            binding = self._active_speech
            if binding is not None and binding.turn_id not in self._settled_turns:
                binding.handle.interrupt()
                if not binding.started:
                    started = self._presentation_session.playout_started(
                        turn_id=binding.turn_id
                    )
                    binding.started = True
                    await self._publish_presentation(started)
                await self._settle_binding_locked(binding, interrupted=True)
            result = self._presentation_session.navigate_to_slide(slide_id)
            await self._publish_presentation(result)

    async def _speech_done(self, binding: "_SpeechBinding") -> None:
        if self._presentation_session is None:
            return
        async with self._presentation_lock:
            if binding.turn_id in self._settled_turns:
                return
            interrupted = bool(getattr(binding.handle, "interrupted", False))
            if not binding.started:
                if interrupted:
                    started = self._presentation_session.playout_started(
                        turn_id=binding.turn_id
                    )
                    binding.started = True
                    await self._publish_presentation(started)
                else:
                    logger.warning(
                        "Speech completed without a speaking lifecycle event",
                        extra={"turn_id": binding.turn_id},
                    )
                    return
            await self._settle_binding_locked(binding, interrupted=interrupted)

    async def _settle_binding_locked(
        self,
        binding: "_SpeechBinding",
        *,
        interrupted: bool,
    ) -> None:
        if self._presentation_session is None:
            return
        if binding.turn_id in self._settled_turns:
            return
        self._settled_turns.add(binding.turn_id)
        result = self._presentation_session.playout_finished(
            turn_id=binding.turn_id,
            interrupted=interrupted,
        )
        if self._active_speech is binding:
            self._active_speech = None
        await self._publish_presentation(result)
        if result.generation is not None:
            self._execute_generation(result.generation)

    def _execute_generation(self, directive: GenerationDirective) -> None:
        if self._agent_session is None:
            raise RuntimeError("agent session is not started")
        self._context_trace.record_generation(directive)
        self._pending_generation = directive
        handle = self._agent_session.generate_reply(
            instructions=directive.instructions,
            tool_choice="none",
            tools=[],
            allow_interruptions=True,
        )
        self._bind_speech(handle, directive)
        self._pending_generation = None

    def _bind_speech(self, handle: object, directive: GenerationDirective) -> None:
        existing = self._active_speech
        if existing is not None and existing.handle is handle:
            return
        binding = _SpeechBinding(
            handle=handle,
            turn_id=directive.turn_id,
        )
        self._active_speech = binding
        handle.add_done_callback(
            lambda _finished, binding=binding: self._queue_presentation(
                self._speech_done(binding)
            )
        )

    async def _publish_presentation(
        self,
        result: PresentationActionResult,
    ) -> None:
        self._touch_activity()
        update = PresentationStateUpdate.from_view(
            attempt_id=self._spec.attempt_id,
            view=result.view,
        )
        try:
            await self._room.local_participant.publish_data(
                update.to_json(),
                reliable=True,
                destination_identities=[self._spec.browser_identity],
                topic=PRESENTATION_STATE_TOPIC,
            )
        except Exception:
            logger.warning(
                "Could not publish presentation state",
                exc_info=True,
            )

    async def _publish_lifecycle(
        self,
        reason: ConversationLifecycleReason,
    ) -> None:
        update = ConversationLifecycleUpdate(
            attempt_id=self._spec.attempt_id,
            reason=reason,
        )
        try:
            await self._room.local_participant.publish_data(
                update.to_json(),
                reliable=True,
                destination_identities=[self._spec.browser_identity],
                topic=CONVERSATION_LIFECYCLE_TOPIC,
            )
        except Exception:
            logger.warning(
                "Could not publish conversation lifecycle event",
                exc_info=True,
            )

    async def _publish_diagnostic(self, event: ConversationDiagnosticEvent) -> None:
        try:
            await self._room.local_participant.publish_data(
                event.to_json(),
                reliable=True,
                destination_identities=[self._spec.browser_identity],
                topic=CONVERSATION_DIAGNOSTICS_TOPIC,
            )
        except Exception:
            logger.warning(
                "Could not publish conversation diagnostic event",
                exc_info=True,
            )

    async def _publish_transcript(
        self,
        update: ConversationTranscriptUpdate,
    ) -> None:
        try:
            await self._room.local_participant.publish_data(
                update.to_json(),
                reliable=True,
                destination_identities=[self._spec.browser_identity],
                topic=CONVERSATION_TRANSCRIPT_TOPIC,
            )
        except Exception:
            logger.warning(
                "Could not publish conversation transcript",
                exc_info=True,
            )


@dataclass(slots=True)
class _SpeechBinding:
    handle: object
    turn_id: str
    started: bool = False
