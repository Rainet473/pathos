from __future__ import annotations

import pytest

from voice_presentation.application.spoken_commands import (
    is_spoken_continue_command,
)


pytestmark = pytest.mark.offline


@pytest.mark.parametrize(
    "transcript",
    (
        "Continue.",
        "Please continue the presentation.",
        "Continue with presentation",
        "Okay, continue your narration please.",
        "Resume narration.",
        "Please resume the presentation now.",
        "Go on.",
        "Alright, carry on.",
        "Okay. Carry on with the presentation then.",
        "Okay. Sounds good. Yeah. Carry on with the presentation.",
        "Okay. Continue on with the presentation.",
        "Yeah, continue on with your narration please.",
    ),
)
def test_bounded_spoken_continue_variants_match(transcript: str):
    assert is_spoken_continue_command(transcript) is True


@pytest.mark.parametrize(
    "transcript",
    (
        "",
        "Do not continue.",
        "Don't continue the presentation.",
        "Explain ABS, then continue the presentation.",
        "Can you continue after explaining engine braking?",
        "When should I continue braking?",
        "What does resume mean?",
        "Continue searching the deck.",
        "Continue searching through the presentation.",
        "Continue only after I ask another question.",
        "What does continue with the presentation mean?",
    ),
)
def test_negative_compound_and_unrelated_phrases_do_not_match(transcript: str):
    assert is_spoken_continue_command(transcript) is False
