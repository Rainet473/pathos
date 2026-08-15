from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from voice_presentation.application.live_presentation import LivePresentationView


PRESENTATION_STATE_TOPIC = "voice-presentation.state.v1"
PRESENTATION_COMMAND_TOPIC = "voice-presentation.command.v1"


class PresentationStateUpdate(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    attempt_id: str
    emitted_at: datetime
    view: LivePresentationView

    @classmethod
    def from_view(
        cls,
        *,
        attempt_id: str,
        view: LivePresentationView,
    ) -> "PresentationStateUpdate":
        return cls(
            attempt_id=attempt_id,
            emitted_at=datetime.now(UTC),
            view=view,
        )

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


class PresentationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["continue"]
