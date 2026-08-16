from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from voice_presentation.application.live_presentation import (
    ApplicationPresentationSession,
)
from voice_presentation.domain.content import PresentationDeck
from voice_presentation.transport.context_trace import (
    InferenceContextLedger,
    NullInferenceContextLedger,
)
from voice_presentation.transport.conversation import ConversationSessionSpec
from voice_presentation.transport.diagnostics import (
    ConversationDiagnosticLedger,
    NullConversationDiagnosticLedger,
)
from voice_presentation.transport.usage import NullUsageLedger, UsageLedger, UsageRecord
from voice_presentation.voice.sessions import VoiceBackendIdentity, VoiceSessionFactory


logger = logging.getLogger(__name__)


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
FollowUpPlannerFactory = Callable[[PresentationDeck], object]


class LiveKitConversationSessionLauncher:
    """Own background conversation tasks and exactly-once usage recording."""

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
        follow_up_planner_factory: FollowUpPlannerFactory | None = None,
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
        self._follow_up_planner_factory = follow_up_planner_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._voice_session_factory.identity

    async def launch(self, session: ConversationSessionSpec) -> None:
        from voice_presentation.adapters.livekit.conversation import (
            LiveKitConversationSession,
        )

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
            follow_up_planner = None
            if (
                presentation_session is not None
                and self._follow_up_planner_factory is not None
            ):
                follow_up_planner = self._follow_up_planner_factory(
                    presentation_session.deck
                )
            runner = LiveKitConversationSession(
                session,
                self._voice_session_factory,
                diagnostic_ledger=self._diagnostic_ledger,
                context_ledger=self._context_ledger,
                presentation_session=presentation_session,
                follow_up_planner=follow_up_planner,
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
