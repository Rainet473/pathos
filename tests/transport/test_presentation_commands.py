from __future__ import annotations

import pytest
from pydantic import ValidationError

from voice_presentation.transport.presentation import PresentationCommand


pytestmark = pytest.mark.offline


def test_navigation_command_accepts_one_validated_camel_case_slide_id():
    command = PresentationCommand.model_validate_json(
        b'{"action":"navigate","slideId":"clutch-and-gears"}'
    )

    assert command.action == "navigate"
    assert command.slide_id == "clutch-and-gears"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"action":"navigate"}',
        b'{"action":"navigate","slideId":""}',
        b'{"action":"continue","slideId":"clutch-and-gears"}',
    ],
)
def test_navigation_command_rejects_missing_blank_or_extraneous_slide_id(payload):
    with pytest.raises(ValidationError):
        PresentationCommand.model_validate_json(payload)
