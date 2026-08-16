from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field, ValidationError
from livekit.agents import APIConnectOptions, llm

from voice_presentation.adapters.livekit.agents.inference_pipeline import (
    LIVEKIT_INFERENCE_LLM_MODEL,
)
from voice_presentation.adapters.livekit.context_format import (
    reasoning_items_to_livekit,
)
from voice_presentation.application.follow_up_planning import (
    FollowUpPlanningSession,
    MAX_SEARCH_CALLS,
    PlanningProtocolError,
    PlanningTraceEntry,
)
from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.reasoning import (
    PlanningContext,
    PlanningRejectionCode,
    PlanningStage,
    PlanningSnapshot,
    PlanningStatus,
    ReasoningModel,
    SearchMaterialInput,
    SubmitAnswerPlanInput,
)
from voice_presentation.transport.context_trace import (
    ApplicationDecisionTrace,
    FunctionCallTrace,
    FunctionResultTrace,
    InferenceContextMessage,
    ReasoningContextSnapshot,
    TurnMessageTrace,
)


SILENT_PLANNER_INSTRUCTIONS = """You are the silent planning phase for an application-controlled presentation. Never answer the listener in prose. Every response must contain exactly one native function call and no more than one. Supply every tool field, using empty arrays or null where appropriate. If the listener asks what wording in a retained prior turn means, submit a grounded conversation plan immediately and cite that antecedent turn; do not search for wording already present in conversation. Use search_material only when the retained conversation does not contain enough support. Never repeat the same search. After zero to two searches, terminate with submit_answer_plan. Cite only logical turn IDs from the immediately preceding developer Turn reference annotations and only evidence IDs returned by search_material or supplied in the application snapshot. Keep scope separate from grounding source. A conversation reference uses grounded plus conversation; deck material uses grounded plus presentation; mixed support uses conversation_and_presentation; related knowledge absent from the deck uses extended_knowledge plus model_knowledge; ambiguity uses needs_clarification plus none; unsupported requests use out_of_scope plus none. If focusSlideId is non-null, the identical slide ID must also appear in supportingSlideIds; use null when no visual focus is needed. The answer brief is concise factual guidance, not a scripted answer or hidden reasoning. The application alone owns navigation, continuation, speech, and state. Never include continuation permission in a plan."""

MAX_PROVIDER_REQUESTS = 3
DEFAULT_MAX_COMPLETION_TOKENS = 512


class PlannerFailureCode(StrEnum):
    STALE_CONTEXT = "stale_context"
    MISSING_TOOL_CALL = "missing_tool_call"
    MULTIPLE_TOOL_CALLS = "multiple_tool_calls"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_TOOL_ARGUMENTS = "invalid_tool_arguments"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"


class PlannerTokenUsage(ReasoningModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cached_prompt_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class PlannerRequestEvidence(ReasoningModel):
    sequence: int = Field(ge=1, le=MAX_PROVIDER_REQUESTS)
    provider_request_ids: tuple[str, ...] = ()
    normalized_roles: tuple[str, ...] = ()
    tool_names: tuple[str, ...] = ()
    provider_extra_keys: tuple[str, ...] = ()
    ttft_ms: float | None = Field(default=None, ge=0)
    duration_ms: float = Field(ge=0)
    discarded_text_characters: int = Field(ge=0)
    usage: PlannerTokenUsage | None = None


class SilentPlanningRun(ReasoningModel):
    case_name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    captured_at: datetime
    snapshot: PlanningSnapshot
    failure_code: PlannerFailureCode | None = None
    failure_detail: str | None = None
    requests: tuple[PlannerRequestEvidence, ...] = ()
    trace: tuple[PlanningTraceEntry, ...] = ()
    schema_names: tuple[Literal["search_material", "submit_answer_plan"], ...] = (
        "search_material",
        "submit_answer_plan",
    )
    speech_requested: Literal[False] = False

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )

    def sanitized_summary(self) -> dict[str, object]:
        plan = self.snapshot.accepted_plan
        return {
            "case": self.case_name,
            "status": self.snapshot.status.value,
            "failureCode": self.failure_code.value if self.failure_code else None,
            "planId": plan.plan_id if plan is not None else None,
            "supportingTurnIds": list(plan.supporting_turn_ids) if plan else [],
            "evidenceIds": list(plan.evidence_ids) if plan else [],
            "requestCount": len(self.requests),
            "toolSequence": [
                entry.name
                for entry in self.trace
                if isinstance(entry, FunctionCallTrace)
            ],
            "requests": [
                {
                    "sequence": request.sequence,
                    "providerRequestIds": list(request.provider_request_ids),
                    "roles": list(request.normalized_roles),
                    "toolNames": list(request.tool_names),
                    "ttftMs": request.ttft_ms,
                    "durationMs": request.duration_ms,
                    "discardedTextCharacters": request.discarded_text_characters,
                    "usage": (
                        request.usage.model_dump(mode="json", by_alias=True)
                        if request.usage is not None
                        else None
                    ),
                }
                for request in self.requests
            ],
            "speechRequested": False,
        }


class SilentPlanningLedger(Protocol):
    def record(self, run: SilentPlanningRun) -> None: ...


class NullSilentPlanningLedger:
    def record(self, run: SilentPlanningRun) -> None:
        del run


class JsonlSilentPlanningLedger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(self, run: SilentPlanningRun) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(run.to_json())
            stream.write("\n")


class PlanningModelClient(Protocol):
    model: str

    def chat(self, **kwargs: object) -> object: ...

    async def aclose(self) -> None: ...


class _CollectedProviderResponse(ReasoningModel):
    evidence: PlannerRequestEvidence
    tool_calls: tuple[llm.FunctionToolCall, ...]


def build_planning_tools() -> tuple[llm.RawFunctionTool, llm.RawFunctionTool]:
    async def search_material(raw_arguments: dict[str, object]) -> None:
        del raw_arguments
        raise RuntimeError("planning tools are executed by application code")

    async def submit_answer_plan(raw_arguments: dict[str, object]) -> None:
        del raw_arguments
        raise RuntimeError("planning tools are executed by application code")

    search_tool = llm.function_tool(
        search_material,
        raw_schema={
            "name": "search_material",
            "description": (
                "Search the packaged presentation for a few auditable passages. "
                "This never changes presentation state."
            ),
            "parameters": _provider_tool_parameters(SearchMaterialInput),
        },
    )
    submit_tool = llm.function_tool(
        submit_answer_plan,
        raw_schema={
            "name": "submit_answer_plan",
            "description": (
                "Submit the one terminal validated answer plan. This does not "
                "speak, navigate, or resume the presentation."
            ),
            "parameters": _provider_tool_parameters(SubmitAnswerPlanInput),
        },
    )
    assert isinstance(search_tool, llm.RawFunctionTool)
    assert isinstance(submit_tool, llm.RawFunctionTool)
    return search_tool, submit_tool


class LiveKitSilentPlanner:
    """Bounded text-only LiveKit planner with application-owned tool execution."""

    def __init__(
        self,
        *,
        deck: PresentationDeck,
        model_client: PlanningModelClient,
        ledger: SilentPlanningLedger | None = None,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not 1 <= max_completion_tokens <= 2048:
            raise ValueError("max_completion_tokens must be between 1 and 2048")
        self._deck = deck
        self._model_client = model_client
        self._ledger = ledger or NullSilentPlanningLedger()
        self._max_completion_tokens = max_completion_tokens
        self._clock = clock
        self._tools = build_planning_tools()

    @classmethod
    def from_credentials(
        cls,
        *,
        deck: PresentationDeck,
        api_key: str,
        api_secret: str,
        ledger: SilentPlanningLedger | None = None,
        model: str = LIVEKIT_INFERENCE_LLM_MODEL,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    ) -> "LiveKitSilentPlanner":
        from livekit.agents import inference

        model_client = inference.LLM(
            model=model,
            api_key=api_key,
            api_secret=api_secret,
        )
        return cls(
            deck=deck,
            model_client=model_client,
            ledger=ledger,
            max_completion_tokens=max_completion_tokens,
        )

    async def aclose(self) -> None:
        await self._model_client.aclose()

    async def plan(
        self,
        *,
        case_name: str,
        snapshot: ReasoningContextSnapshot,
        context: PlanningContext,
        active_identity: Callable[[], tuple[int, str]] | None = None,
        on_stage: Callable[[PlanningStage], Awaitable[None]] | None = None,
    ) -> SilentPlanningRun:
        session = FollowUpPlanningSession(
            deck=self._deck,
            provenance=snapshot.ledger,
            context=context,
            search=MaterialSearch(self._deck),
            active_identity=active_identity,
        )
        requests: list[PlannerRequestEvidence] = []
        trace: list[PlanningTraceEntry] = []
        schema_corrections = 0
        forced_tool_name: str | None = None

        if not _snapshot_ends_at_follow_up(snapshot, context.follow_up_turn_id):
            session.cancel(PlanningRejectionCode.CANCELLED)
            return self._finish(
                case_name=case_name,
                session=session,
                requests=requests,
                trace=trace,
                failure_code=PlannerFailureCode.STALE_CONTEXT,
            )

        chat_context = _planning_chat_context(
            snapshot=snapshot,
            context=context,
            deck=self._deck,
        )
        try:
            async with asyncio.timeout(context.timeout_seconds):
                if on_stage is not None:
                    await on_stage(PlanningStage.UNDERSTANDING)
                for sequence in range(1, MAX_PROVIDER_REQUESTS + 1):
                    search_available = (
                        session.snapshot.search_calls < MAX_SEARCH_CALLS
                    )
                    if forced_tool_name is not None:
                        request_tools = tuple(
                            tool
                            for tool in self._tools
                            if tool.info.name == forced_tool_name
                        )
                        tool_choice: object = {
                            "type": "function",
                            "function": {"name": forced_tool_name},
                        }
                        forced_tool_name = None
                    else:
                        request_tools = (
                            self._tools if search_available else (self._tools[1],)
                        )
                        tool_choice = (
                            "required"
                            if search_available
                            else {
                                "type": "function",
                                "function": {"name": "submit_answer_plan"},
                            }
                        )
                    response = await self._request(
                        sequence=sequence,
                        chat_context=chat_context,
                        timeout_seconds=context.timeout_seconds,
                        tools=request_tools,
                        tool_choice=tool_choice,
                    )
                    requests.append(response.evidence)
                    if not response.tool_calls:
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.MISSING_TOOL_CALL,
                        )
                    if len(response.tool_calls) != 1:
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.MULTIPLE_TOOL_CALLS,
                        )

                    tool_call = response.tool_calls[0]
                    if tool_call.name not in {
                        "search_material",
                        "submit_answer_plan",
                    }:
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.UNKNOWN_TOOL,
                        )
                    invalid_detail: str | None = None
                    try:
                        raw_arguments = json.loads(tool_call.arguments)
                        if not isinstance(raw_arguments, dict):
                            invalid_detail = "not_object"
                            raise ValueError
                        if tool_call.name == "search_material":
                            parsed = SearchMaterialInput.model_validate(raw_arguments)
                        else:
                            parsed = SubmitAnswerPlanInput.model_validate(raw_arguments)
                    except json.JSONDecodeError:
                        invalid_detail = "json_decode"
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.INVALID_TOOL_ARGUMENTS,
                            failure_detail=invalid_detail,
                        )
                    except ValidationError as error:
                        invalid_detail = _sanitized_validation_detail(error)
                        if (
                            schema_corrections == 0
                            and sequence < MAX_PROVIDER_REQUESTS
                        ):
                            schema_corrections += 1
                            forced_tool_name = tool_call.name
                            correction_output = {
                                "accepted": False,
                                "reasonCode": invalid_detail,
                                "applicationInstruction": (
                                    "Correct the tool arguments once using this "
                                    "validation result."
                                ),
                            }
                            chat_context.insert(
                                (
                                    llm.FunctionCall(
                                        call_id=tool_call.call_id,
                                        name=tool_call.name,
                                        arguments=json.dumps(
                                            raw_arguments,
                                            separators=(",", ":"),
                                            sort_keys=True,
                                        ),
                                        extra=tool_call.extra or {},
                                    ),
                                    llm.FunctionCallOutput(
                                        call_id=tool_call.call_id,
                                        name=tool_call.name,
                                        output=json.dumps(
                                            correction_output,
                                            separators=(",", ":"),
                                            sort_keys=True,
                                        ),
                                        is_error=True,
                                    ),
                                )
                            )
                            continue
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.INVALID_TOOL_ARGUMENTS,
                            failure_detail=invalid_detail,
                        )
                    except ValueError:
                        session.cancel(PlanningRejectionCode.CANCELLED)
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                            failure_code=PlannerFailureCode.INVALID_TOOL_ARGUMENTS,
                            failure_detail=invalid_detail or "value_error",
                        )

                    call_trace = FunctionCallTrace(
                        call_id=tool_call.call_id,
                        name=tool_call.name,
                        arguments=parsed.model_dump(mode="json", by_alias=True),
                    )
                    trace.append(call_trace)
                    try:
                        if isinstance(parsed, SearchMaterialInput):
                            if on_stage is not None:
                                await on_stage(PlanningStage.SEARCHING)
                            result = session.search(
                                parsed,
                                session_version=context.session_version,
                                follow_up_turn_id=context.follow_up_turn_id,
                            )
                            output = result.model_dump(mode="json", by_alias=True)
                            remaining_search_calls = (
                                MAX_SEARCH_CALLS - session.snapshot.search_calls
                            )
                            provider_output = {
                                **output,
                                "remainingSearchCalls": remaining_search_calls,
                                "applicationInstruction": (
                                    "Search succeeded. Do not repeat this query. "
                                    "Call submit_answer_plan now if these hits are "
                                    "sufficient; only a materially different query "
                                    "may use the remaining search allowance."
                                    if remaining_search_calls
                                    else "Search succeeded. Do not repeat this query. "
                                    "The search allowance is exhausted; call "
                                    "submit_answer_plan now."
                                ),
                            }
                            trace.append(
                                FunctionResultTrace(
                                    call_id=tool_call.call_id,
                                    name=tool_call.name,
                                    output=provider_output,
                                    is_error=False,
                                )
                            )
                            chat_context.insert(
                                (
                                    llm.FunctionCall(
                                        call_id=tool_call.call_id,
                                        name=tool_call.name,
                                        arguments=call_trace.arguments_json(),
                                        extra=tool_call.extra or {},
                                    ),
                                    llm.FunctionCallOutput(
                                        call_id=tool_call.call_id,
                                        name=tool_call.name,
                                        output=json.dumps(
                                            provider_output,
                                            separators=(",", ":"),
                                            sort_keys=True,
                                        ),
                                        is_error=False,
                                    ),
                                )
                            )
                            continue

                        if on_stage is not None:
                            await on_stage(PlanningStage.PREPARING)
                        plan = session.submit(
                            parsed,
                            session_version=context.session_version,
                            follow_up_turn_id=context.follow_up_turn_id,
                        )
                        trace.extend(
                            (
                                FunctionResultTrace(
                                    call_id=tool_call.call_id,
                                    name=tool_call.name,
                                    output={
                                        "accepted": True,
                                        "planId": plan.plan_id,
                                    },
                                    is_error=False,
                                ),
                                ApplicationDecisionTrace(
                                    decision_id=f"decision-{case_name}",
                                    source_call_id=tool_call.call_id,
                                    plan_id=plan.plan_id,
                                    accepted=True,
                                    reason_code="accepted",
                                    supporting_turn_ids=plan.supporting_turn_ids,
                                ),
                            )
                        )
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                        )
                    except PlanningProtocolError as error:
                        trace.extend(
                            (
                                FunctionResultTrace(
                                    call_id=tool_call.call_id,
                                    name=tool_call.name,
                                    output={
                                        "accepted": False,
                                        "reasonCode": error.code.value,
                                    },
                                    is_error=True,
                                ),
                                ApplicationDecisionTrace(
                                    decision_id=f"decision-{case_name}",
                                    source_call_id=tool_call.call_id,
                                    plan_id=f"rejected-plan-{case_name}",
                                    accepted=False,
                                    reason_code=error.code.value,
                                    supporting_turn_ids=(
                                        parsed.supporting_turn_ids
                                        if isinstance(parsed, SubmitAnswerPlanInput)
                                        else ()
                                    ),
                                ),
                            )
                        )
                        return self._finish(
                            case_name=case_name,
                            session=session,
                            requests=requests,
                            trace=trace,
                        )

                session.finish()
        except TimeoutError:
            session.cancel(PlanningRejectionCode.TIMEOUT)
            return self._finish(
                case_name=case_name,
                session=session,
                requests=requests,
                trace=trace,
                failure_code=PlannerFailureCode.TIMEOUT,
            )
        except asyncio.CancelledError:
            session.cancel(PlanningRejectionCode.CANCELLED)
            raise
        except PlanningProtocolError:
            return self._finish(
                case_name=case_name,
                session=session,
                requests=requests,
                trace=trace,
            )
        except Exception as error:
            session.cancel(PlanningRejectionCode.CANCELLED)
            return self._finish(
                case_name=case_name,
                session=session,
                requests=requests,
                trace=trace,
                failure_code=PlannerFailureCode.PROVIDER_ERROR,
                failure_detail=type(error).__name__,
            )

        return self._finish(
            case_name=case_name,
            session=session,
            requests=requests,
            trace=trace,
        )

    async def _request(
        self,
        *,
        sequence: int,
        chat_context: llm.ChatContext,
        timeout_seconds: float,
        tools: tuple[llm.RawFunctionTool, ...],
        tool_choice: object,
    ) -> _CollectedProviderResponse:
        normalized_context, _ = chat_context.to_provider_format(format="openai")
        normalized_roles = tuple(
            str(message.get("role", message.get("type", "unknown")))
            for message in normalized_context
        )
        started_at = self._clock()
        first_event_at: float | None = None
        provider_request_ids: list[str] = []
        tool_calls: list[llm.FunctionToolCall] = []
        discarded_text_characters = 0
        usage: PlannerTokenUsage | None = None

        stream = self._model_client.chat(
            chat_ctx=chat_context,
            tools=list(tools),
            conn_options=APIConnectOptions(
                max_retry=0,
                timeout=timeout_seconds,
            ),
            parallel_tool_calls=False,
            tool_choice=tool_choice,
            extra_kwargs={
                "max_completion_tokens": self._max_completion_tokens,
            },
        )
        async with stream:
            async for chunk in stream:
                if first_event_at is None:
                    first_event_at = self._clock()
                if chunk.id and chunk.id not in provider_request_ids:
                    provider_request_ids.append(chunk.id)
                if chunk.delta is not None:
                    if chunk.delta.content:
                        discarded_text_characters += len(chunk.delta.content)
                    tool_calls.extend(chunk.delta.tool_calls)
                if chunk.usage is not None:
                    usage = PlannerTokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        cached_prompt_tokens=chunk.usage.prompt_cached_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )
        finished_at = self._clock()
        extra_keys = tuple(
            sorted(
                {
                    key
                    for tool_call in tool_calls
                    for key in (tool_call.extra or {})
                }
            )
        )
        return _CollectedProviderResponse(
            evidence=PlannerRequestEvidence(
                sequence=sequence,
                provider_request_ids=tuple(provider_request_ids),
                normalized_roles=normalized_roles,
                tool_names=tuple(tool_call.name for tool_call in tool_calls),
                provider_extra_keys=extra_keys,
                ttft_ms=(
                    (first_event_at - started_at) * 1000
                    if first_event_at is not None
                    else None
                ),
                duration_ms=(finished_at - started_at) * 1000,
                discarded_text_characters=discarded_text_characters,
                usage=usage,
            ),
            tool_calls=tuple(tool_calls),
        )

    def _finish(
        self,
        *,
        case_name: str,
        session: FollowUpPlanningSession,
        requests: list[PlannerRequestEvidence],
        trace: list[PlanningTraceEntry],
        failure_code: PlannerFailureCode | None = None,
        failure_detail: str | None = None,
    ) -> SilentPlanningRun:
        run = SilentPlanningRun(
            case_name=case_name,
            model=self._model_client.model,
            captured_at=datetime.now(UTC),
            snapshot=session.snapshot,
            failure_code=failure_code,
            failure_detail=failure_detail,
            requests=tuple(requests),
            trace=tuple(trace),
        )
        self._ledger.record(run)
        return run


def _snapshot_ends_at_follow_up(
    snapshot: ReasoningContextSnapshot,
    follow_up_turn_id: str,
) -> bool:
    if not snapshot.turns or snapshot.turns[-1].turn_id != follow_up_turn_id:
        return False
    turn_entries = (
        entry for entry in snapshot.trace if isinstance(entry, TurnMessageTrace)
    )
    last_turn = None
    for last_turn in turn_entries:
        pass
    return last_turn is not None and last_turn.turn_id == follow_up_turn_id


def _planning_chat_context(
    *,
    snapshot: ReasoningContextSnapshot,
    context: PlanningContext,
    deck: PresentationDeck,
) -> llm.ChatContext:
    planner_snapshot = snapshot.model_copy(
        update={"stable_instructions": SILENT_PLANNER_INSTRUCTIONS}
    )
    application_message = InferenceContextMessage(
        role="developer",
        content=_application_snapshot_text(context=context, deck=deck),
    )
    items = list(planner_snapshot.model_context_items())
    follow_up_index = next(
        (
            index
            for index, item in enumerate(items)
            if isinstance(item, InferenceContextMessage)
            and item.logical_turn_id == context.follow_up_turn_id
        ),
        None,
    )
    if follow_up_index is None or follow_up_index == 0:
        raise ValueError("active follow-up message is missing from model context")
    annotation = items[follow_up_index - 1]
    if not (
        isinstance(annotation, InferenceContextMessage)
        and annotation.role == "developer"
        and annotation.content.startswith(
            f"Turn reference: {context.follow_up_turn_id};"
        )
    ):
        raise ValueError("active follow-up Turn reference is not immediately adjacent")
    items.insert(follow_up_index - 1, application_message)
    return reasoning_items_to_livekit(items)


def _application_snapshot_text(
    *,
    context: PlanningContext,
    deck: PresentationDeck,
) -> str:
    current_slide = deck.slide(context.current_slide_id)
    slides = ", ".join(f"{slide.id}: {slide.title}" for slide in deck.slides)
    evidence = "none"
    if context.current_slide_evidence:
        evidence = " | ".join(
            f"{hit.evidence_id}: {hit.text}" for hit in context.current_slide_evidence
        )
    return (
        "Authoritative application planning snapshot: "
        f"sessionVersion={context.session_version}; "
        f"activeFollowUpTurnId={context.follow_up_turn_id}; "
        f"currentSlideId={context.current_slide_id}; "
        f"visibleSlideId={context.visible_slide_id}; "
        f"currentSlideTitle={current_slide.title}; "
        f"currentSlideHeadline={current_slide.headline}; "
        f"availableSlides=[{slides}]; "
        f"currentSlideEvidence=[{evidence}]. "
        "Continuation permission is application-owned and is not a plan field."
    )


def _sanitized_validation_detail(error: ValidationError) -> str:
    details = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "root"
        message = str(item["msg"]).replace("Value error, ", "")
        details.append(f"{location}:{item['type']}:{message}")
    return "validation:" + ",".join(details)


def _provider_tool_parameters(model: type[ReasoningModel]) -> dict[str, Any]:
    schema = model.model_json_schema(by_alias=True)
    properties = schema.get("properties", {})
    schema["required"] = list(properties)
    for property_schema in properties.values():
        if isinstance(property_schema, dict):
            property_schema.pop("default", None)
    return schema
