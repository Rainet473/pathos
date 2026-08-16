from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.domain.contracts import ScopeMode
from voice_presentation.domain.policy import QuestionScopePolicy


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIX_SLIDE_DECK = REPOSITORY_ROOT / "assets" / "motorcycle-controls" / "slide-breakdown.json"


def _policy() -> QuestionScopePolicy:
    return QuestionScopePolicy(JsonMaterialRepository(SIX_SLIDE_DECK).load())


@pytest.mark.parametrize(
    ("question", "slide_id"),
    [
        ("Why does a motorcycle need a clutch?", "clutch-and-gears"),
        (
            "Why does engine braking feel stronger in a low gear?",
            "engine-braking",
        ),
        ("What is the purpose of rev matching?", "rev-matching"),
        ("Does ABS increase grip?", "braking-abs"),
        ("Explain ABS, then continue your presentation.", "braking-abs"),
        ("Explain A B S, then continue your presentation.", "braking-abs"),
        (
            "How does a lower gear give higher revs during engine braking?",
            "engine-braking",
        ),
        ("How does a lower gear help decrease speed?", "engine-braking"),
        ("Why do the revs rise in a lower gear?", "power-to-wheel"),
        ("What happens if I let the clutch out too quickly?", "clutch-and-gears"),
    ],
)
def test_grounded_full_deck_questions_select_curated_evidence(question, slide_id):
    decision = _policy().classify(question)

    assert decision.scope_mode is ScopeMode.GROUNDED
    assert decision.supporting_slide_id == slide_id
    assert decision.evidence
    assert decision.disclosure_required is False


@pytest.mark.parametrize(
    ("question", "slide_id"),
    [
        ("What is a slipper clutch?", "clutch-and-gears"),
        ("What is a quickshifter?", "clutch-and-gears"),
        ("What is cornering ABS?", "braking-abs"),
    ],
)
def test_related_uncovered_questions_require_disclosed_extended_mode(
    question, slide_id
):
    decision = _policy().classify(question)

    assert decision.scope_mode is ScopeMode.EXTENDED_KNOWLEDGE
    assert decision.supporting_slide_id == slide_id
    assert decision.evidence == ()
    assert decision.disclosure_required is True


def test_ambiguous_full_deck_question_requests_one_clarification():
    decision = _policy().classify("Why does it jerk?")

    assert decision.scope_mode is ScopeMode.NEEDS_CLARIFICATION
    assert decision.supporting_slide_id is None
    assert decision.clarification_prompt


@pytest.mark.parametrize(
    "question",
    [
        "What exact torque should I use for my axle nut?",
        "Tell me how to disable ABS on public roads.",
        "Who won last night's football match?",
        "Which motorcycle movie should I watch?",
    ],
)
def test_unsafe_or_unrelated_full_deck_question_stays_out_of_scope(question):
    decision = _policy().classify(question)

    assert decision.scope_mode is ScopeMode.OUT_OF_SCOPE
    assert decision.supporting_slide_id is None
    assert decision.evidence == ()


def test_visible_slide_is_a_tie_breaker_not_a_hard_question_filter(deck_payload):
    for slide in deck_payload["slides"]:
        slide["deep_dive"] = [
            {
                "concept": "shared coupling concept",
                "explanation": "A shared coupling explanation connects input and output.",
                "caveats": [],
            }
        ]
        slide["related_terms"] = []
    from voice_presentation.domain.content import PresentationDeck

    policy = QuestionScopePolicy(PresentationDeck.model_validate(deck_payload))

    preferred = policy.classify(
        "How does the shared coupling connect input and output?",
        preferred_slide_id="braking-abs",
    )
    fallback = _policy().classify(
        "Why does engine braking feel stronger in a low gear?",
        preferred_slide_id="braking-abs",
    )

    assert preferred.scope_mode is ScopeMode.GROUNDED
    assert preferred.supporting_slide_id == "braking-abs"
    assert fallback.supporting_slide_id == "engine-braking"


def test_question_policy_rejects_an_unknown_preferred_slide():
    with pytest.raises(ValueError, match="unknown slide id"):
        _policy().classify(
            "Why does a motorcycle need a clutch?",
            preferred_slide_id="missing-slide",
        )
