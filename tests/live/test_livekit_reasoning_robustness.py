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
from voice_presentation.domain.contracts import ScopeMode
from voice_presentation.domain.provenance import GroundingSource
from voice_presentation.domain.reasoning import (
    PlanningRejectionCode,
    PlanningStatus,
)
from voice_presentation.domain.terminology import resolve_terminology_hints
from voice_presentation.transport.context_trace import (
    ReasoningContextSnapshot,
    TurnMessageTrace,
)


pytestmark = [pytest.mark.live, pytest.mark.integration, pytest.mark.observation]

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DECK_PATH = REPOSITORY_ROOT / "assets/motorcycle-controls/slide-breakdown.json"
CONTEXT_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/question-reasoning-turn-10.json"
PLANNER_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/follow-up-planner-actions.json"


def test_livekit_gemma_handles_acronym_phrase_and_listener_correction_cases():
    """Three silent cases; hard-capped at nine inference requests and no audio."""

    if os.getenv("RUN_LIVEKIT_ROBUSTNESS_TESTS") != "1":
        pytest.skip(
            "set RUN_LIVEKIT_ROBUSTNESS_TESTS=1 to spend at most nine inference requests"
        )
    load_dotenv(REPOSITORY_ROOT / ".env")
    missing = [
        name
        for name in ("LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
        if not os.getenv(name, "").strip()
    ]
    if missing:
        pytest.fail(f"missing live configuration: {', '.join(missing)}")

    selected_case = os.getenv("LIVEKIT_ROBUSTNESS_CASE", "").strip()
    runs = asyncio.run(_run_cases(selected_case=selected_case or None))

    if selected_case:
        assert len(runs) == 1
        _assert_case(selected_case, runs[0])
        print(runs[0].sanitized_summary())
        return

    acronym, phrase, correction = runs
    _assert_case("acronym-neighbor", acronym)
    _assert_case("anti-lock-phrase-variation", phrase)
    _assert_case("listener-correction", correction)

    assert sum(len(run.requests) for run in runs) <= 9
    assert all(run.speech_requested is False for run in runs)
    for run in runs:
        print(run.sanitized_summary())


def _assert_case(name: str, run) -> None:
    if name == "acronym-neighbor":
        if run.snapshot.status is PlanningStatus.ACCEPTED:
            assert run.snapshot.accepted_plan is not None
            assert run.snapshot.accepted_plan.scope in {
                ScopeMode.GROUNDED,
                ScopeMode.NEEDS_CLARIFICATION,
            }
            assert run.snapshot.accepted_plan.scope is not ScopeMode.OUT_OF_SCOPE
        else:
            assert run.snapshot.status is PlanningStatus.REJECTED
            assert run.snapshot.rejection_code in {
                PlanningRejectionCode.UNKNOWN_TURN,
                PlanningRejectionCode.INELIGIBLE_TURN,
                PlanningRejectionCode.UNKNOWN_EVIDENCE,
                PlanningRejectionCode.UNKNOWN_SLIDE,
                PlanningRejectionCode.INCOHERENT_PLAN,
            }
            assert run.snapshot.terminology_hints
            assert run.snapshot.terminology_hints[0].authored_term == "ABS"
            assert run.snapshot.accepted_plan is None
        return
    assert run.snapshot.status is PlanningStatus.ACCEPTED
    assert run.snapshot.accepted_plan is not None
    assert run.snapshot.accepted_plan.scope is ScopeMode.GROUNDED
    assert run.snapshot.accepted_plan.grounding_source in {
        GroundingSource.PRESENTATION,
        GroundingSource.CONVERSATION_AND_PRESENTATION,
    }
    assert run.snapshot.accepted_plan.evidence_ids
    assert run.snapshot.search_calls >= 1


async def _run_cases(*, selected_case: str | None = None):
    deck = JsonMaterialRepository(DECK_PATH).load()
    suite = RecordedPlanningSuite.model_validate_json(
        PLANNER_FIXTURE.read_text(encoding="utf-8")
    )
    base_context = next(
        case.context for case in suite.cases if case.name == "conversation-citation"
    )
    cases = (
        (
            "acronym-neighbor",
            "Explain APS, then continue your presentation.",
        ),
        (
            "anti-lock-phrase-variation",
            "How can the anti-lock system preserve steering if it cannot add traction?",
        ),
        (
            "listener-correction",
            "I thought ABS creates grip, but that sounds wrong. Correct that claim, then continue.",
        ),
    )
    planner = LiveKitSilentPlanner.from_credentials(
        deck=deck,
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
        ledger=JsonlSilentPlanningLedger(
            REPOSITORY_ROOT / ".runtime/livekit-silent-planning.jsonl"
        ),
    )
    runs = []
    try:
        for name, utterance in cases:
            if selected_case is not None and name != selected_case:
                continue
            snapshot = _snapshot_with_follow_up(
                base_context.follow_up_turn_id,
                utterance,
            )
            context = base_context.model_copy(
                update={
                    "terminology_hints": resolve_terminology_hints(
                        utterance,
                        deck,
                    ),
                    "timeout_seconds": 30.0,
                }
            )
            runs.append(
                await planner.plan(
                    case_name=f"robustness:{name}",
                    snapshot=snapshot,
                    context=context,
                )
            )
    finally:
        await planner.aclose()
    if selected_case is not None and not runs:
        raise ValueError(f"unknown robustness case: {selected_case}")
    return tuple(runs)


def _snapshot_with_follow_up(
    turn_id: str,
    utterance: str,
) -> ReasoningContextSnapshot:
    snapshot = ReasoningContextSnapshot.model_validate_json(
        CONTEXT_FIXTURE.read_text(encoding="utf-8")
    )
    turn_index = next(
        index for index, turn in enumerate(snapshot.turns) if turn.turn_id == turn_id
    )
    turns = list(snapshot.turns[: turn_index + 1])
    turns[-1] = turns[-1].model_copy(update={"actual_text": utterance})
    trace = []
    for entry in snapshot.trace:
        trace.append(entry)
        if isinstance(entry, TurnMessageTrace) and entry.turn_id == turn_id:
            break
    return ReasoningContextSnapshot.model_validate(
        {
            **snapshot.model_dump(),
            "turns": tuple(turns),
            "trace": tuple(trace),
        }
    )
