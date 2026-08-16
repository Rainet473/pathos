from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


CONVERSATION_LIFECYCLE_TOPIC = "voice-conversation.lifecycle.v1"


class ConversationLifecycleReason(StrEnum):
    IDLE_TIMEOUT = "idle_timeout"
    ABSOLUTE_TIMEOUT = "absolute_timeout"


class ConversationLifecycleUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    attempt_id: str = Field(alias="attemptId", min_length=1)
    reason: ConversationLifecycleReason
    version: int = 1

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )
