from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from livekit.agents import llm

from voice_presentation.adapters.livekit.silent_planner import (
    LiveKitSilentPlanner,
    PlannerFailureCode,
    build_planning_tools,
)
from voice_presentation.application.follow_up_planning import RecordedPlanningSuite
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import PresentationPhase
from voice_presentation.domain.controller import PresentationController
from voice_presentation.domain.reasoning import PlanningRejectionCode, PlanningStatus
from voice_presentation.transport.context_trace import (
    ApplicationDecisionTrace,
    FunctionCallTrace,
    FunctionResultTrace,
    ReasoningContextSnapshot,
    TurnMessageTrace,
)


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DECK_PATH = REPOSITORY_ROOT / "assets/motorcycle-controls/slide-breakdown.json"
CONTEXT_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/question-reasoning-turn-10.json"
PLANNER_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/follow-up-planner-actions.json"


class FakeStream:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._chunks)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeLLM:
    model = "google/gemma-4-31b-it"
    provider = "livekit"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.closed = False

    def chat(self, **kwargs):
        context, _ = kwargs["chat_ctx"].to_provider_format(format="openai")
        self.calls.append(
            {
                **kwargs,
                "provider_messages": context,
                "tool_names": tuple(tool.info.name for tool in kwargs["tools"]),
            }
        )
        if not self._responses:
            raise AssertionError("unexpected provider request")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeStream(response)

    async def aclose(self):
        self.closed = True


def _deck():
    return JsonMaterialRepository(DECK_PATH).load()


def _suite() -> RecordedPlanningSuite:
    return RecordedPlanningSuite.model_validate_json(
        PLANNER_FIXTURE.read_text(encoding="utf-8")
    )


def _case(name: str):
    return next(case for case in _suite().cases if case.name == name)


def _snapshot_through(turn_id: str) -> ReasoningContextSnapshot:
    snapshot = ReasoningContextSnapshot.model_validate_json(
        CONTEXT_FIXTURE.read_text(encoding="utf-8")
    )
    turn_index = next(
        index for index, turn in enumerate(snapshot.turns) if turn.turn_id == turn_id
    )
    trace = []
    for entry in snapshot.trace:
        trace.append(entry)
        if isinstance(entry, TurnMessageTrace) and entry.turn_id == turn_id:
            break
    return ReasoningContextSnapshot.model_validate(
        {
            **snapshot.model_dump(),
            "turns": snapshot.turns[: turn_index + 1],
            "trace": tuple(trace),
        }
    )


def _usage(*, prompt: int, completion: int, cached: int = 0):
    return llm.CompletionUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        prompt_cached_tokens=cached,
        total_tokens=prompt + completion,
    )


def _response(
    request_id: str,
    *,
    tool_calls=(),
    text: str | None = None,
    usage=None,
):
    chunks = [
        llm.ChatChunk(
            id=request_id,
            delta=llm.ChoiceDelta(
                role="assistant",
                content=text,
                tool_calls=list(tool_calls),
            ),
        )
    ]
    if usage is not None:
        chunks.append(llm.ChatChunk(id=request_id, usage=usage))
    return chunks


def _tool_call(name: str, arguments: dict | str, *, call_id: str):
    return llm.FunctionToolCall(
        name=name,
        arguments=(
            arguments
            if isinstance(arguments, str)
            else json.dumps(arguments, separators=(",", ":"), sort_keys=True)
        ),
        call_id=call_id,
    )


def test_planning_tools_expose_only_bounded_camel_case_slice_two_schemas():
    tools = build_planning_tools()
    schemas = llm.ToolContext(tools).parse_function_tools("openai", strict=True)

    assert [schema["function"]["name"] for schema in schemas] == [
        "search_material",
        "submit_answer_plan",
    ]
    search = schemas[0]["function"]["parameters"]
    submit = schemas[1]["function"]["parameters"]
    assert search["additionalProperties"] is False
    assert search["properties"]["keywords"]["maxItems"] == 8
    assert search["properties"]["maxResults"]["maximum"] == 5
    assert "slideIds" in search["properties"]
    assert set(search["required"]) == set(search["properties"])
    assert submit["additionalProperties"] is False
    assert "groundingSource" in submit["properties"]
    assert "answerBrief" in submit["properties"]
    assert "continuationPreference" not in submit["properties"]
    assert set(submit["required"]) == set(submit["properties"])


def test_conversation_reference_uses_one_native_terminal_call_and_discards_text():
    case = _case("conversation-citation")
    proposal = case.actions[0].input.model_dump(mode="json", by_alias=True)
    preamble = "I will cite the interrupted turn."
    model = FakeLLM(
        [
            _response(
                "provider-conversation",
                tool_calls=(
                    _tool_call(
                        "submit_answer_plan",
                        proposal,
                        call_id="provider-call-submit",
                    ),
                ),
                text=preamble,
                usage=_usage(prompt=620, completion=42, cached=100),
            )
        ]
    )
    deck = _deck()
    controller = PresentationController(deck)
    before = controller.state.model_copy(deep=True)
    planner = LiveKitSilentPlanner(deck=deck, model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name=case.name,
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.snapshot.status is PlanningStatus.ACCEPTED
    assert run.snapshot.accepted_plan is not None
    assert run.snapshot.accepted_plan.supporting_turn_ids == ("narration-0002",)
    assert run.failure_code is None
    assert run.speech_requested is False
    assert len(run.requests) == 1
    assert run.requests[0].discarded_text_characters == len(preamble)
    assert run.requests[0].usage is not None
    assert run.requests[0].usage.cached_prompt_tokens == 100
    assert run.requests[0].provider_request_ids == ("provider-conversation",)
    assert [type(entry) for entry in run.trace] == [
        FunctionCallTrace,
        FunctionResultTrace,
        ApplicationDecisionTrace,
    ]
    assert model.calls[0]["tool_names"] == (
        "search_material",
        "submit_answer_plan",
    )
    assert model.calls[0]["tool_choice"] == "required"
    assert model.calls[0]["parallel_tool_calls"] is False
    assert model.calls[0]["conn_options"].max_retry == 0
    provider_messages = model.calls[0]["provider_messages"]
    assert [message["role"] for message in provider_messages[-2:]] == [
        "developer",
        "user",
    ]
    assert provider_messages[-2]["content"].startswith(
        "Turn reference: user-follow-up-0003;"
    )
    assert provider_messages[-1]["content"] == (
        "What kind of response do you mean? Please continue after the answer."
    )
    assert "<" not in provider_messages[-1]["content"]
    assert controller.state == before
    assert controller.state.phase is PresentationPhase.READY


def test_material_question_round_trips_native_search_output_before_terminal_plan():
    case = _case("material-search")
    search_input = case.actions[0].input.model_dump(mode="json", by_alias=True)
    proposal = case.actions[1].input.model_dump(mode="json", by_alias=True)
    model = FakeLLM(
        [
            _response(
                "provider-search",
                tool_calls=(
                    _tool_call(
                        "search_material",
                        search_input,
                        call_id="provider-call-search",
                    ),
                ),
                usage=_usage(prompt=1100, completion=55),
            ),
            _response(
                "provider-submit",
                tool_calls=(
                    _tool_call(
                        "submit_answer_plan",
                        proposal,
                        call_id="provider-call-submit",
                    ),
                ),
                usage=_usage(prompt=1500, completion=70, cached=900),
            ),
        ]
    )
    deck = _deck()
    controller = PresentationController(deck)
    before = controller.state.model_copy(deep=True)
    planner = LiveKitSilentPlanner(deck=deck, model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name=case.name,
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.snapshot.status is PlanningStatus.ACCEPTED
    assert run.snapshot.accepted_plan is not None
    assert run.snapshot.accepted_plan.evidence_ids == (
        "motorcycle-controls.clutch-and-gears.narration.1",
    )
    assert run.snapshot.search_calls == 1
    assert len(run.requests) == 2
    assert [entry.name for entry in run.trace if hasattr(entry, "name")] == [
        "search_material",
        "search_material",
        "submit_answer_plan",
        "submit_answer_plan",
    ]
    assert len(
        [entry for entry in run.trace if isinstance(entry, ApplicationDecisionTrace)]
    ) == 1
    second_messages = model.calls[1]["provider_messages"]
    assert [message["role"] for message in second_messages[-2:]] == [
        "assistant",
        "tool",
    ]
    tool_output = json.loads(second_messages[-1]["content"])
    assert tool_output["hits"][0]["evidenceId"] == (
        "motorcycle-controls.clutch-and-gears.narration.1"
    )
    assert tool_output["applicationInstruction"].startswith(
        "Search succeeded. Do not repeat"
    )
    assert tool_output["remainingSearchCalls"] == 1
    assert controller.state == before


def test_search_tool_is_removed_after_the_second_allowed_search():
    case = _case("material-search")
    search_input = case.actions[0].input.model_dump(mode="json", by_alias=True)
    proposal = case.actions[1].input.model_dump(mode="json", by_alias=True)
    model = FakeLLM(
        [
            _response(
                "search-one",
                tool_calls=(
                    _tool_call("search_material", search_input, call_id="search-one"),
                ),
            ),
            _response(
                "search-two",
                tool_calls=(
                    _tool_call("search_material", search_input, call_id="search-two"),
                ),
            ),
            _response(
                "terminal",
                tool_calls=(
                    _tool_call("submit_answer_plan", proposal, call_id="terminal"),
                ),
            ),
        ]
    )
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name="two-searches",
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.snapshot.status is PlanningStatus.ACCEPTED
    assert len(run.requests) == 3
    assert model.calls[2]["tool_names"] == ("submit_answer_plan",)
    assert model.calls[2]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_answer_plan"},
    }


@pytest.mark.parametrize(
    ("response", "failure_code"),
    [
        (
            _response("text-only", text="Here is the answer directly."),
            PlannerFailureCode.MISSING_TOOL_CALL,
        ),
        (
            _response(
                "parallel",
                tool_calls=(
                    _tool_call("search_material", {"keywords": ["clutch"]}, call_id="one"),
                    _tool_call("search_material", {"keywords": ["gear"]}, call_id="two"),
                ),
            ),
            PlannerFailureCode.MULTIPLE_TOOL_CALLS,
        ),
        (
            _response(
                "unknown",
                tool_calls=(
                    _tool_call("navigate_slide", {"slideId": "braking-abs"}, call_id="one"),
                ),
            ),
            PlannerFailureCode.UNKNOWN_TOOL,
        ),
        (
            _response(
                "malformed",
                tool_calls=(
                    _tool_call("search_material", "{not-json", call_id="one"),
                ),
            ),
            PlannerFailureCode.INVALID_TOOL_ARGUMENTS,
        ),
    ],
)
def test_provider_protocol_bypass_attempts_fail_closed(response, failure_code):
    case = _case("conversation-citation")
    model = FakeLLM([response])
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name=f"failure-{failure_code.value}",
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.snapshot.status is PlanningStatus.CANCELLED
    assert run.snapshot.accepted_plan is None
    assert run.failure_code is failure_code
    assert run.speech_requested is False
    if failure_code is PlannerFailureCode.INVALID_TOOL_ARGUMENTS:
        assert run.failure_detail == "json_decode"


def test_valid_but_untrusted_terminal_arguments_are_rejected_by_application():
    case = _case("conversation-citation")
    invalid = {
        "scope": "grounded",
        "groundingSource": "presentation",
        "answerBrief": "Claim deck support that was not searched.",
        "evidenceIds": ["motorcycle-controls.clutch-and-gears.narration.1"],
        "supportingSlideIds": ["clutch-and-gears"],
    }
    model = FakeLLM(
        [
            _response(
                "invalid-plan",
                tool_calls=(
                    _tool_call(
                        "submit_answer_plan",
                        invalid,
                        call_id="provider-call-invalid-submit",
                    ),
                ),
            )
        ]
    )
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name="invalid-plan",
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.failure_code is None
    assert run.snapshot.status is PlanningStatus.REJECTED
    assert run.snapshot.rejection_code is PlanningRejectionCode.UNKNOWN_EVIDENCE
    assert run.snapshot.accepted_plan is None
    decision = run.trace[-1]
    assert isinstance(decision, ApplicationDecisionTrace)
    assert decision.accepted is False
    assert decision.reason_code == "unknown_evidence"


def test_one_parseable_schema_failure_can_self_correct_through_native_tool_output():
    case = _case("conversation-citation")
    incoherent = {
        "scope": "grounded",
        "groundingSource": "conversation_and_presentation",
        "answerBrief": "Clarify the earlier use of response.",
        "supportingTurnIds": ["narration-0002"],
        "evidenceIds": [],
        "supportingSlideIds": ["control-loop"],
        "focusSlideId": None,
        "clarificationPrompt": None,
    }
    corrected = case.actions[0].input.model_dump(mode="json", by_alias=True)
    model = FakeLLM(
        [
            _response(
                "invalid-schema",
                tool_calls=(
                    _tool_call(
                        "submit_answer_plan",
                        incoherent,
                        call_id="invalid-schema",
                    ),
                ),
            ),
            _response(
                "corrected-schema",
                tool_calls=(
                    _tool_call(
                        "submit_answer_plan",
                        corrected,
                        call_id="corrected-schema",
                    ),
                ),
            ),
        ]
    )
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name="schema-correction",
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.snapshot.status is PlanningStatus.ACCEPTED
    assert len(run.requests) == 2
    correction_context = model.calls[1]["provider_messages"]
    assert [message["role"] for message in correction_context[-2:]] == [
        "assistant",
        "tool",
    ]
    correction = json.loads(correction_context[-1]["content"])
    assert correction == {
        "accepted": False,
        "applicationInstruction": (
            "Correct the tool arguments once using this validation result."
        ),
        "reasonCode": (
            "validation:root:value_error:combined grounding requires both "
            "turns and deck evidence"
        ),
    }


def test_context_containing_turns_after_active_follow_up_never_calls_provider():
    case = _case("conversation-citation")
    model = FakeLLM([])
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)
    full_snapshot = ReasoningContextSnapshot.model_validate_json(
        CONTEXT_FIXTURE.read_text(encoding="utf-8")
    )

    run = asyncio.run(
        planner.plan(
            case_name="stale-context",
            snapshot=full_snapshot,
            context=case.context,
        )
    )

    assert run.failure_code is PlannerFailureCode.STALE_CONTEXT
    assert run.snapshot.status is PlanningStatus.CANCELLED
    assert run.requests == ()
    assert model.calls == []


def test_provider_exception_is_sanitized_and_does_not_escape_to_answering():
    case = _case("conversation-citation")
    model = FakeLLM([RuntimeError("private provider detail")])
    planner = LiveKitSilentPlanner(deck=_deck(), model_client=model)

    run = asyncio.run(
        planner.plan(
            case_name="provider-error",
            snapshot=_snapshot_through(case.context.follow_up_turn_id),
            context=case.context,
        )
    )

    assert run.failure_code is PlannerFailureCode.PROVIDER_ERROR
    assert run.failure_detail == "RuntimeError"
    assert "private provider detail" not in run.to_json()
    assert run.snapshot.accepted_plan is None
