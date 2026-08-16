from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class SlideView(BaseModel):
    """Provider-neutral slide metadata published to the browser."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    id: str
    title: str
    headline: str
    labels: tuple[str, ...]
    visual_description: str
