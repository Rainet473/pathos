from __future__ import annotations

from livekit.agents import llm

from voice_presentation.transport.context_trace import (
    FunctionCallTrace,
    FunctionResultTrace,
    InferenceContextMessage,
    ReasoningContextSnapshot,
)


def reasoning_context_to_livekit(snapshot: ReasoningContextSnapshot) -> llm.ChatContext:
    """Format provider-neutral context with native LiveKit chat item types."""

    context = llm.ChatContext.empty()
    for item in snapshot.model_context_items():
        if isinstance(item, InferenceContextMessage):
            message_kwargs: dict[str, object] = {
                "role": item.role,
                "content": item.content,
                "interrupted": item.interrupted,
            }
            if item.provider_item_id is not None:
                message_kwargs["id"] = item.provider_item_id
            context.add_message(**message_kwargs)
        elif isinstance(item, FunctionCallTrace):
            context.insert(
                llm.FunctionCall(
                    id=f"tool-{item.call_id}",
                    call_id=item.call_id,
                    name=item.name,
                    arguments=item.arguments_json(),
                )
            )
        elif isinstance(item, FunctionResultTrace):
            context.insert(
                llm.FunctionCallOutput(
                    id=f"tool-result-{item.call_id}",
                    call_id=item.call_id,
                    name=item.name,
                    output=item.output_json(),
                    is_error=item.is_error,
                )
            )
    return context
