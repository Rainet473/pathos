from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from voice_presentation.adapters.livekit.silent_planner import (
    JsonlSilentPlanningLedger,
    LiveKitSilentPlanner,
)
from voice_presentation.application.follow_up_planning import RecordedPlanningSuite
from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.provenance import GroundingSource
from voice_presentation.domain.reasoning import PlanningContext, PlanningStatus
from voice_presentation.transport.context_trace import (
    ReasoningContextSnapshot,
    TurnMessageTrace,
)


pytestmark = [pytest.mark.live, pytest.mark.integration, pytest.mark.observation]

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DECK_PATH = REPOSITORY_ROOT / "assets/motorcycle-controls/slide-breakdown.json"
CONTEXT_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/question-reasoning-turn-10.json"
PLANNER_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/follow-up-planner-actions.json"


def test_livekit_inference_gemma_emits_bounded_native_plans_for_both_cases():
    """Expected three or four, hard-capped at five; no audio dependencies."""
    if os.getenv("RUN_LIVEKIT_PLANNER_TESTS") != "1":
        pytest.skip(
            "set RUN_LIVEKIT_PLANNER_TESTS=1 to spend at most five inference requests"
        )
    load_dotenv(REPOSITORY_ROOT / ".env")
    required = ("LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        pytest.fail(f"missing live configuration: {', '.join(missing)}")

    runs = asyncio.run(_run_live_cases())

    assert len(runs) == 2, (
        "material case was not run because conversation planning failed its "
        "two-request correction gate"
    )
    conversation, material = runs
    assert conversation.snapshot.status is PlanningStatus.ACCEPTED
    assert conversation.snapshot.accepted_plan is not None
    assert conversation.snapshot.accepted_plan.grounding_source is (
        GroundingSource.CONVERSATION
    )
    assert "narration-0002" in conversation.snapshot.accepted_plan.supporting_turn_ids
    assert 1 <= len(conversation.requests) <= 2

    assert material.snapshot.status is PlanningStatus.ACCEPTED
    assert material.snapshot.accepted_plan is not None
    assert material.snapshot.accepted_plan.grounding_source in (
        GroundingSource.PRESENTATION,
        GroundingSource.CONVERSATION_AND_PRESENTATION,
    )
    assert material.snapshot.search_calls == 1
    assert material.snapshot.accepted_plan.evidence_ids
    assert len(material.requests) == 2

    assert 3 <= sum(len(run.requests) for run in runs) <= 5
    assert all(run.speech_requested is False for run in runs)
    assert all(request.usage is not None for run in runs for request in run.requests)
    assert all(
        request.usage.total_tokens > 0
        for run in runs
        for request in run.requests
        if request.usage is not None
    )
    for run in runs:
        print(run.sanitized_summary())


async def _run_live_cases():
    deck = JsonMaterialRepository(DECK_PATH).load()
    suite = RecordedPlanningSuite.model_validate_json(
        PLANNER_FIXTURE.read_text(encoding="utf-8")
    )
    ledger = JsonlSilentPlanningLedger(
        REPOSITORY_ROOT / ".runtime/livekit-silent-planning.jsonl"
    )
    planner = LiveKitSilentPlanner.from_credentials(
        deck=deck,
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
        ledger=ledger,
        max_completion_tokens=512,
    )
    runs = []
    try:
        for case_index, case in enumerate(suite.cases):
            context = PlanningContext.model_validate(
                {
                    **case.context.model_dump(),
                    "timeout_seconds": 30.0,
                }
            )
            run = await planner.plan(
                case_name=case.name,
                snapshot=_snapshot_through(context.follow_up_turn_id),
                context=context,
            )
            runs.append(run)
            if case_index == 0 and (
                run.snapshot.status is not PlanningStatus.ACCEPTED
                or len(run.requests) > 2
            ):
                break
    finally:
        await planner.aclose()
    return tuple(runs)


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
