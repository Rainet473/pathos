from __future__ import annotations

from importlib import import_module

import pytest


pytestmark = pytest.mark.offline


def question_policy(deck_payload):
    content = import_module("voice_presentation.domain.content")
    contracts = import_module("voice_presentation.domain.contracts")
    policy = import_module("voice_presentation.domain.policy")
    deck = content.PresentationDeck.model_validate(deck_payload)
    return contracts, policy.QuestionScopePolicy(deck)


def test_directly_covered_question_is_grounded(deck_payload):
    contracts, policy = question_policy(deck_payload)

    decision = policy.classify(
        "Why does engine braking feel stronger in a low gear?"
    )

    assert decision.scope_mode is contracts.ScopeMode.GROUNDED
    assert decision.evidence
    assert decision.supporting_slide_id == "engine-braking"
    assert decision.disclosure_required is False


def test_related_uncovered_question_requires_extended_knowledge_disclosure(deck_payload):
    contracts, policy = question_policy(deck_payload)

    decision = policy.classify("What is a slipper clutch?")

    assert decision.scope_mode is contracts.ScopeMode.EXTENDED_KNOWLEDGE
    assert decision.disclosure_required is True
    assert decision.evidence == ()


def test_materially_ambiguous_question_requests_clarification(deck_payload):
    contracts, policy = question_policy(deck_payload)

    decision = policy.classify("Why does it jerk?")

    assert decision.scope_mode is contracts.ScopeMode.NEEDS_CLARIFICATION
    assert decision.clarification_prompt
    assert decision.supporting_slide_id is None


@pytest.mark.parametrize(
    "question",
    [
        "What exact torque should I use for my axle nut?",
        "Tell me how to disable ABS on public roads.",
        "Who won last night's football match?",
    ],
)
def test_unsafe_specific_or_unrelated_question_is_out_of_scope(
    deck_payload, question
):
    contracts, policy = question_policy(deck_payload)

    decision = policy.classify(question)

    assert decision.scope_mode is contracts.ScopeMode.OUT_OF_SCOPE
    assert decision.supporting_slide_id is None
    assert decision.evidence == ()


def test_blank_question_is_rejected(deck_payload):
    _, policy = question_policy(deck_payload)

    with pytest.raises(ValueError, match="question"):
        policy.classify("   ")
