"""Bounded, provider-neutral matching for application-owned voice commands."""

from __future__ import annotations

import re


_WORD_SPACE = re.compile(r"[^a-z0-9]+")
_DISCOURSE_PREFIX = (
    r"(?:(?:alright|okay|ok|please|yes|yeah|sounds good|that sounds good)\s+)*"
)
_POLITE_SUFFIX = r"(?:\s+(?:then|now|please|thanks|thank you))*"
_PRESENTATION_TARGET = r"(?:(?:the|your|our)\s+)?(?:presentation|narration)"

# The connector grammar intentionally allows at most the three useful words in
# phrases such as "continue on with the presentation". An unrestricted wildcard
# would also accept unsafe compounds such as "continue searching the presentation".
_CONTINUE_COMMAND = re.compile(
    rf"^{_DISCOURSE_PREFIX}(?:"
    rf"continue(?:\s+(?:presenting|speaking)|(?:\s+on)?(?:\s+with)?\s+{_PRESENTATION_TARGET})?"
    rf"|resume(?:\s+(?:presenting|speaking)|(?:\s+with)?\s+{_PRESENTATION_TARGET})?"
    rf"|(?:go|carry)\s+on(?:\s+with\s+{_PRESENTATION_TARGET})?"
    rf"|proceed(?:\s+with\s+{_PRESENTATION_TARGET})?"
    rf"){_POLITE_SUFFIX}$"
)


def is_spoken_continue_command(transcript: str) -> bool:
    """Return true only for a short standalone presentation-resume command."""

    normalized = _WORD_SPACE.sub(" ", transcript.lower()).strip()
    return _CONTINUE_COMMAND.fullmatch(normalized) is not None
