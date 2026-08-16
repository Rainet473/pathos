"""Translate one LiveKit room into application-owned presentation actions.

Launcher lifecycle and Agent construction live in adjacent modules. This bridge
keeps correlated room events, transcripts, playout, and presentation callbacks
together because they share one active-session state and cancellation boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Awaitable

from livekit import rtc

from voice_presentation.adapters.livekit.conversation_agent import (
    AgentConstructor,
    HttpContextFactory,
    PresentationAgentConstructor,
    default_agent_constructor as _default_agent_constructor,
    default_http_context_factory as _default_http_context_factory,
    default_presentation_agent_constructor as _default_presentation_agent_constructor,
)
from voice_presentation.adapters.livekit.silent_planner import LiveKitSilentPlanner
from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
    FollowUpPlanningAction,
    GenerationDirective,
    PresentationActionResult,
)
from voice_presentation.domain.reasoning import PlanningStage, PlanningStatus
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
from voice_presentation.voice.sessions import VoiceSessionFactory

logger = logging.getLogger(__name__)

CONVERSATION_DIAGNOSTICS_TOPIC = "voice-conversation.diagnostics.v1"


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
        follow_up_planner: LiveKitSilentPlanner | None = None,
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
        self._follow_up_planner = follow_up_planner
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
        self._follow_up_tasks: set[asyncio.Task[object]] = set()
        self._presentation_lock = asyncio.Lock()
        self._presentation_started = False
        self._pending_generation: GenerationDirective | None = None
        self._active_speech: _SpeechBinding | None = None
        self._settled_turns: set[str] = set()
        self._logical_assistant_turn_queue: list[str] = []

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
                    for task in tuple(self._follow_up_tasks):
                        task.cancel()
                    if self._follow_up_tasks:
                        await asyncio.gather(
                            *self._follow_up_tasks,
                            return_exceptions=True,
                        )
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
                    if self._follow_up_planner is not None:
                        with contextlib.suppress(Exception):
                            await self._follow_up_planner.aclose()
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
                directive = self._pending_generation
                binding = self._active_speech
                self._queue_diagnostic(
                    self._diagnostics.record_turn_metrics(
                        metrics,
                        turn_id=(
                            directive.turn_id
                            if directive is not None
                            else binding.turn_id
                            if binding is not None
                            else None
                        ),
                        turn_purpose=(
                            directive.purpose.value
                            if directive is not None
                            else binding.purpose
                            if binding is not None
                            else None
                        ),
                    )
                )
            role = str(getattr(item, "role", ""))
            text = str(getattr(item, "text_content", "")).strip()
            if role in {"user", "assistant"} and text:
                provider_item_id = str(getattr(item, "id", "") or "").strip()
                logical_turn_id: str | None = None
                if role == "assistant":
                    logical_turn_id = self._context_trace.logical_turn_id_for_provider(
                        provider_item_id
                    )
                    if (
                        logical_turn_id is None
                        and self._logical_assistant_turn_queue
                    ):
                        logical_turn_id = self._logical_assistant_turn_queue.pop(0)
                self._context_trace.add_history_message(
                    provider_item_id=provider_item_id,
                    role=role,
                    content=text,
                    interrupted=bool(getattr(item, "interrupted", False)),
                    logical_turn_id=logical_turn_id,
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

    async def _prepare_user_turn(
        self,
        question: str,
        provider_item_id: str | None = None,
    ) -> str | None:
        task = asyncio.current_task()
        if task is not None:
            self._follow_up_tasks.add(task)
        try:
            return await self._prepare_user_turn_impl(
                question,
                provider_item_id,
            )
        finally:
            if task is not None:
                self._follow_up_tasks.discard(task)

    async def _prepare_user_turn_impl(
        self,
        question: str,
        provider_item_id: str | None = None,
    ) -> str | None:
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

            if self._follow_up_planner is None:
                result = self._presentation_session.prepare_question(question)
                if result.generation is None:
                    raise RuntimeError(
                        "question preparation did not issue an answer turn"
                    )
                self._pending_generation = result.generation
                await self._publish_presentation(result)
                self._record_generation_context(
                    result.generation,
                    current_user_message=question,
                )
                return result.generation.instructions

            self._logical_assistant_turn_queue = [
                turn_id
                for turn_id in self._logical_assistant_turn_queue
                if turn_id not in self._settled_turns
            ]
            planning = self._presentation_session.begin_follow_up(
                question,
                provider_item_id=provider_item_id,
            )
            await self._publish_follow_up_planning(planning)
            self._context_trace.register_follow_up(planning.follow_up_turn)
            snapshot = self._context_trace.reasoning_snapshot(
                session_version=planning.context.session_version
            )

            async def on_stage(stage: PlanningStage) -> None:
                stage_result = self._presentation_session.set_planning_stage(
                    stage,
                    follow_up_turn_id=planning.context.follow_up_turn_id,
                )
                await self._publish_presentation(stage_result)

            planning_started_at = time.monotonic()
            try:
                run = await self._follow_up_planner.plan(
                    case_name=(
                        f"{self._spec.attempt_id}:"
                        f"{planning.context.follow_up_turn_id}"
                    ),
                    snapshot=snapshot,
                    context=planning.context,
                    active_identity=(
                        self._presentation_session.active_planning_identity
                    ),
                    on_stage=on_stage,
                )
            except asyncio.CancelledError:
                with contextlib.suppress(Exception):
                    await asyncio.shield(
                        self._fail_follow_up_planning(
                            planning,
                            reason_code="cancelled",
                        )
                    )
                raise
            except Exception as error:
                planning_duration = time.monotonic() - planning_started_at
                self._queue_diagnostic(
                    self._diagnostics.record_follow_up_planning(
                        duration_seconds=planning_duration,
                        provider_duration_seconds=0,
                        request_count=0,
                        tool_steps=0,
                        search_calls=0,
                        status="provider_error",
                        input_tokens=0,
                        cached_input_tokens=0,
                        total_tokens=0,
                    )
                )
                logger.warning(
                    "Silent follow-up planning failed for attempt %s (%s)",
                    self._spec.attempt_id,
                    type(error).__name__,
                )
                await self._fail_follow_up_planning(
                    planning,
                    reason_code="provider_error",
                )
                return None
            planning_duration = time.monotonic() - planning_started_at
            requests = tuple(getattr(run, "requests", ()))
            usages = tuple(
                request.usage
                for request in requests
                if getattr(request, "usage", None) is not None
            )
            self._queue_diagnostic(
                self._diagnostics.record_follow_up_planning(
                    duration_seconds=planning_duration,
                    provider_duration_seconds=(
                        sum(request.duration_ms for request in requests) / 1000
                    ),
                    request_count=len(requests),
                    tool_steps=run.snapshot.tool_steps,
                    search_calls=run.snapshot.search_calls,
                    status=run.snapshot.status.value,
                    input_tokens=sum(usage.prompt_tokens for usage in usages),
                    cached_input_tokens=sum(
                        usage.cached_prompt_tokens for usage in usages
                    ),
                    total_tokens=sum(usage.total_tokens for usage in usages),
                )
            )
            self._context_trace.record_planning_trace(run.trace)
            accepted_plan = run.snapshot.accepted_plan
            if (
                run.snapshot.status is not PlanningStatus.ACCEPTED
                or accepted_plan is None
            ):
                failure_code = (
                    run.failure_code.value
                    if run.failure_code is not None
                    else run.snapshot.rejection_code.value
                    if run.snapshot.rejection_code is not None
                    else "planning_failed"
                )
                try:
                    recovered = self._presentation_session.recover_answer_plan(
                        follow_up_turn_id=planning.context.follow_up_turn_id,
                        reason_code=failure_code,
                        provenance=snapshot.ledger,
                    )
                except ValueError:
                    await self._fail_follow_up_planning(
                        planning,
                        reason_code=failure_code,
                    )
                    return None
                if recovered.generation is None:
                    raise RuntimeError(
                        "planning recovery did not issue an answer turn"
                    )
                self._pending_generation = recovered.generation
                await self._publish_presentation(recovered)
                self._record_generation_context(
                    recovered.generation,
                    current_user_message=question,
                )
                return recovered.generation.instructions

            result = self._presentation_session.accept_answer_plan(
                accepted_plan,
                provenance=snapshot.ledger,
                search_results=run.snapshot.search_results,
            )
            if result.generation is None:
                raise RuntimeError("question preparation did not issue an answer turn")
            self._pending_generation = result.generation
            await self._publish_presentation(result)
            self._record_generation_context(
                result.generation,
                current_user_message=question,
            )
            return result.generation.instructions

    async def _publish_follow_up_planning(
        self,
        planning: FollowUpPlanningAction,
    ) -> None:
        await self._publish_presentation(
            PresentationActionResult(view=planning.view)
        )

    async def _fail_follow_up_planning(
        self,
        planning: FollowUpPlanningAction,
        *,
        reason_code: str,
    ) -> None:
        if self._presentation_session is None:
            return
        failed = self._presentation_session.fail_answer_plan(
            follow_up_turn_id=planning.context.follow_up_turn_id,
            reason_code=reason_code,
        )
        await self._publish_presentation(failed)

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
            slide_id = slide_id.strip()
            try:
                self._presentation_session.deck.slide(slide_id)
            except ValueError:
                logger.warning(
                    "Ignored navigation to an unknown slide",
                    extra={"slide_id": slide_id},
                )
                return
            if (
                self._presentation_session.view().state.visible_slide_id
                == slide_id
            ):
                return
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
        self._record_generation_context(directive)
        self._pending_generation = directive
        handle = self._agent_session.generate_reply(
            instructions=directive.instructions,
            tool_choice="none",
            tools=[],
            allow_interruptions=True,
        )
        self._bind_speech(handle, directive)
        self._pending_generation = None

    def _record_generation_context(
        self,
        directive: GenerationDirective,
        *,
        current_user_message: str | None = None,
    ) -> None:
        self._context_trace.record_generation(
            directive,
            current_user_message=current_user_message,
        )
        if directive.turn_id not in self._logical_assistant_turn_queue:
            self._logical_assistant_turn_queue.append(directive.turn_id)

    def _bind_speech(self, handle: object, directive: GenerationDirective) -> None:
        existing = self._active_speech
        if existing is not None and existing.handle is handle:
            return
        binding = _SpeechBinding(
            handle=handle,
            turn_id=directive.turn_id,
            purpose=directive.purpose.value,
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
    purpose: str
    started: bool = False
