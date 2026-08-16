from __future__ import annotations

import contextlib
from collections.abc import Callable
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
) -> object:
    """Build the thin LiveKit hook that adds app-selected answer evidence."""

    from livekit.agents import Agent

    class ApplicationControlledPresentationAgent(Agent):
        async def on_user_turn_completed(
            self,
            turn_ctx: object,
            new_message: object,
        ) -> None:
            question = str(getattr(new_message, "text_content", "")).strip()
            provider_item_id = str(getattr(new_message, "id", "") or "").strip()
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


def default_http_context_factory() -> contextlib.AbstractAsyncContextManager[object]:
    from livekit.agents.utils import http_context

    return http_context.open()
