from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from voice_presentation.application.live_presentation import GenerationDirective
from voice_presentation.domain.contracts import PlayoutPurpose


ContextRole = Literal["system", "developer", "user", "assistant"]


class InferenceContextMessage(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    role: ContextRole
    content: str = Field(min_length=1)
    provider_item_id: str | None = None
    interrupted: bool = False


class InferenceContextRecord(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    attempt_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    captured_at: datetime
    turn_id: str = Field(min_length=1)
    purpose: PlayoutPurpose
    stable_instructions: str = Field(min_length=1)
    messages: tuple[InferenceContextMessage, ...]
    fidelity: Literal["application_livekit_chat_context"] = (
        "application_livekit_chat_context"
    )

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )


class InferenceContextLedger(Protocol):
    def record(self, record: InferenceContextRecord) -> None: ...


class NullInferenceContextLedger:
    def record(self, record: InferenceContextRecord) -> None:
        del record


class JsonlInferenceContextLedger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(self, record: InferenceContextRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(record.to_json())
            stream.write("\n")


class InferenceContextTrace:
    """Mirrors the application-visible LiveKit chat context for local inspection."""

    def __init__(
        self,
        *,
        attempt_id: str,
        stable_instructions: str,
        ledger: InferenceContextLedger | None = None,
    ) -> None:
        if not attempt_id.strip():
            raise ValueError("attempt_id must not be blank")
        if not stable_instructions.strip():
            raise ValueError("stable_instructions must not be blank")
        self._attempt_id = attempt_id
        self._stable_instructions = stable_instructions
        self._ledger = ledger or NullInferenceContextLedger()
        self._history: list[InferenceContextMessage] = []
        self._history_indexes: dict[str, int] = {}
        self._sequence = 0

    def add_history_message(
        self,
        *,
        provider_item_id: str | None,
        role: Literal["user", "assistant"],
        content: str,
        interrupted: bool = False,
    ) -> None:
        content = content.strip()
        if not content:
            return
        normalized_id = (provider_item_id or "").strip() or None
        message = InferenceContextMessage(
            role=role,
            content=content,
            provider_item_id=normalized_id,
            interrupted=interrupted,
        )
        if normalized_id is not None and normalized_id in self._history_indexes:
            self._history[self._history_indexes[normalized_id]] = message
            return
        if normalized_id is not None:
            self._history_indexes[normalized_id] = len(self._history)
        self._history.append(message)

    def record_generation(
        self,
        directive: GenerationDirective,
        *,
        current_user_message: str | None = None,
    ) -> InferenceContextRecord:
        messages = list(self._history)
        if directive.purpose is PlayoutPurpose.NARRATION:
            messages.append(
                InferenceContextMessage(
                    role="system", content=directive.instructions
                )
            )
        else:
            current_user_message = (current_user_message or "").strip()
            if not current_user_message:
                raise ValueError("answer context requires the current user message")
            messages.extend(
                (
                    InferenceContextMessage(
                        role="developer", content=directive.instructions
                    ),
                    InferenceContextMessage(
                        role="user", content=current_user_message
                    ),
                )
            )
        self._sequence += 1
        record = InferenceContextRecord(
            attempt_id=self._attempt_id,
            sequence=self._sequence,
            captured_at=datetime.now(UTC),
            turn_id=directive.turn_id,
            purpose=directive.purpose,
            stable_instructions=self._stable_instructions,
            messages=tuple(messages),
        )
        self._ledger.record(record)
        return record
