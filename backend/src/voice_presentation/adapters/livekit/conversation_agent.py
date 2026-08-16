from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Awaitable


AgentConstructor = Callable[..., object]
PresentationAgentConstructor = Callable[..., object]
HttpContextFactory = Callable[[], contextlib.AbstractAsyncContextManager[object]]
PrepareUserTurn = Callable[[str, str | None], Awaitable[str | None]]


def default_agent_constructor(**kwargs: Any) -> object:
    from livekit.agents import Agent

    return Agent(**kwargs)


def default_presentation_agent_constructor(
    *,
    instructions: str,
    prepare_user_turn: PrepareUserTurn,
    follow_up_fragment_window_seconds: float = 1.5,
) -> object:
    """Build the thin LiveKit hook that adds app-selected answer evidence."""

    from livekit.agents import Agent

    if follow_up_fragment_window_seconds <= 0:
        raise ValueError("follow-up fragment window must be positive")

    class ApplicationControlledPresentationAgent(Agent):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._pending_follow_up_fragment: _PendingFollowUpFragment | None = None

        async def on_user_turn_completed(
            self,
            turn_ctx: object,
            new_message: object,
        ) -> None:
            question = str(getattr(new_message, "text_content", "")).strip()
            provider_item_id = str(getattr(new_message, "id", "") or "").strip()
            loop = asyncio.get_running_loop()
            now = loop.time()
            pending = self._pending_follow_up_fragment
            if pending is not None and pending.expires_at >= now:
                self._pending_follow_up_fragment = None
                pending.consumed = True
                pending.release.set()
                question = _join_follow_up_fragments(pending.text, question)
            elif pending is not None:
                self._pending_follow_up_fragment = None
                pending.release.set()

            if _has_incomplete_continuation_tail(question):
                pending = _PendingFollowUpFragment(
                    text=question,
                    expires_at=now + follow_up_fragment_window_seconds,
                    release=asyncio.Event(),
                )
                self._pending_follow_up_fragment = pending
                try:
                    async with asyncio.timeout(follow_up_fragment_window_seconds):
                        await pending.release.wait()
                except TimeoutError:
                    if self._pending_follow_up_fragment is pending:
                        self._pending_follow_up_fragment = None
                except asyncio.CancelledError:
                    raise
                if pending.consumed:
                    from livekit.agents import llm

                    raise llm.StopResponse()

            answer_instructions = await prepare_user_turn(
                question,
                provider_item_id or None,
            )
            if answer_instructions is None:
                from livekit.agents import llm

                raise llm.StopResponse()
            turn_ctx.add_message(role="developer", content=answer_instructions)

    return ApplicationControlledPresentationAgent(
        instructions=instructions,
        tools=[],
    )


@dataclass(slots=True)
class _PendingFollowUpFragment:
    text: str
    expires_at: float
    release: asyncio.Event
    consumed: bool = False


_FOLLOW_UP_WORDS = re.compile(r"[^a-z0-9]+")


def _has_incomplete_continuation_tail(text: str) -> bool:
    normalized = _FOLLOW_UP_WORDS.sub(" ", text.lower()).strip()
    return normalized.endswith((" and", " and then", " then"))


def _join_follow_up_fragments(first: str, second: str) -> str:
    return " ".join(part.strip() for part in (first, second) if part.strip())


def default_http_context_factory() -> contextlib.AbstractAsyncContextManager[object]:
    from livekit.agents.utils import http_context

    return http_context.open()
