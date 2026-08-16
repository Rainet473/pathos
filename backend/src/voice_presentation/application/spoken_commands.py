"""Bounded, provider-neutral matching for application-owned voice commands."""

from __future__ import annotations

import re


_WORD_SPACE = re.compile(r"[^a-z0-9]+")
_DISCOURSE_PREFIXES = frozenset({"alright", "okay", "ok", "please", "yes"})
_POLITE_SUFFIXES = frozenset({"now", "please", "thanks"})
_CONTINUE_COMMANDS = frozenset(
    {
        "continue",
        "continue narration",
        "continue presentation",
        "continue presenting",
        "continue speaking",
        "continue the narration",
        "continue the presentation",
        "continue with narration",
        "continue with presentation",
        "continue with the narration",
        "continue with the presentation",
        "continue your narration",
        "continue your presentation",
        "resume",
        "resume narration",
        "resume presentation",
        "resume presenting",
        "resume the narration",
        "resume the presentation",
        "resume your narration",
        "resume your presentation",
        "go on",
        "carry on",
        "proceed",
        "proceed with narration",
        "proceed with presentation",
        "proceed with the narration",
        "proceed with the presentation",
    }
)


def is_spoken_continue_command(transcript: str) -> bool:
    """Return true only for a short standalone presentation-resume command."""

    words = _WORD_SPACE.sub(" ", transcript.lower()).strip().split()
    while words and words[0] in _DISCOURSE_PREFIXES:
        words.pop(0)
    while words and words[-1] in _POLITE_SUFFIXES:
        words.pop()
    if words[-2:] == ["thank", "you"]:
        del words[-2:]
    return " ".join(words) in _CONTINUE_COMMANDS

