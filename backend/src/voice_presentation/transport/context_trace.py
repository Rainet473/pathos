from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from pydantic.alias_generators import to_camel

from voice_presentation.application.live_presentation import GenerationDirective
from voice_presentation.domain.contracts import PlayoutPurpose
from voice_presentation.domain.provenance import (
    LogicalTurn,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    format_turn_reference,
)


ContextRole = Literal["system", "developer", "user", "assistant"]


class InferenceContextMessage(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: Literal["message"] = "message"
    role: ContextRole
    content: str = Field(min_length=1)
    provider_item_id: str | None = None
    interrupted: bool = False
    logical_turn_id: str | None = Field(default=None, min_length=1)


class TurnMessageTrace(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: Literal["turn_message"] = "turn_message"
    turn_id: str = Field(min_length=1)


class FunctionCallTrace(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: Literal["function_call"] = "function_call"
    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, JsonValue]

    def arguments_json(self) -> str:
        return json.dumps(
            self.arguments,
            separators=(",", ":"),
            sort_keys=True,
        )


class FunctionResultTrace(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: Literal["function_result"] = "function_result"
    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    output: JsonValue
    is_error: bool

    def output_json(self) -> str:
        return json.dumps(
            self.output,
            separators=(",", ":"),
            sort_keys=True,
        )


class ApplicationDecisionTrace(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type: Literal["application_decision"] = "application_decision"
    decision_id: str = Field(min_length=1)
    source_call_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    accepted: bool
    reason_code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    supporting_turn_ids: tuple[str, ...] = ()


ReasoningTraceEntry = Annotated[
    TurnMessageTrace
    | FunctionCallTrace
    | FunctionResultTrace
    | ApplicationDecisionTrace,
    Field(discriminator="type"),
]
ModelContextItem = InferenceContextMessage | FunctionCallTrace | FunctionResultTrace


class ReasoningContextSnapshot(BaseModel):
    """Deterministic audit fixture for provenance-aware model context."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal[1] = 1
    session_id: str = Field(min_length=1)
    session_version: int = Field(ge=0)
    stable_instructions: str = Field(min_length=1)
    turns: tuple[LogicalTurn, ...]
    trace: tuple[ReasoningTraceEntry, ...]
    fidelity: Literal["application_provider_neutral_context"] = (
        "application_provider_neutral_context"
    )

    @property
    def ledger(self) -> LogicalTurnLedger:
        ledger = LogicalTurnLedger(session_version=self.session_version)
        for turn in self.turns:
            ledger.register(turn)
        return ledger

    @model_validator(mode="after")
    def validate_chronology(self) -> "ReasoningContextSnapshot":
        ledger = self.ledger
        for turn in self.turns:
            if turn.interrupted_turn_id is not None:
                ledger.resolve(turn.interrupted_turn_id)
            if turn.resumed_after_turn_id is not None:
                ledger.resolve(turn.resumed_after_turn_id)

        seen_turns: set[str] = set()
        seen_calls: dict[str, str] = {}
        seen_results: set[str] = set()
        for entry in self.trace:
            if isinstance(entry, TurnMessageTrace):
                turn = ledger.resolve(entry.turn_id)
                if turn.delivery_status is TurnDeliveryStatus.PENDING:
                    raise ValueError(
                        f"turn {entry.turn_id} has no actual retained text"
                    )
                if entry.turn_id in seen_turns:
                    raise ValueError(f"duplicate turn message: {entry.turn_id}")
                seen_turns.add(entry.turn_id)
            elif isinstance(entry, FunctionCallTrace):
                if entry.call_id in seen_calls:
                    raise ValueError(f"duplicate function call: {entry.call_id}")
                seen_calls[entry.call_id] = entry.name
            elif isinstance(entry, FunctionResultTrace):
                call_name = seen_calls.get(entry.call_id)
                if call_name is None:
                    raise ValueError(
                        f"function result {entry.call_id} appears before its function call"
                    )
                if call_name != entry.name:
                    raise ValueError(
                        f"function result {entry.call_id} does not match call name"
                    )
                if entry.call_id in seen_results:
                    raise ValueError(f"duplicate function result: {entry.call_id}")
                seen_results.add(entry.call_id)
            else:
                call_name = seen_calls.get(entry.source_call_id)
                if call_name is None:
                    raise ValueError(
                        f"application decision {entry.decision_id} has no source call"
                    )
                if entry.source_call_id not in seen_results:
                    raise ValueError(
                        f"application decision {entry.decision_id} appears before its function result"
                    )
                ledger.require_turn_ids(entry.supporting_turn_ids)
                source_call = next(
                    call
                    for call in self.trace
                    if isinstance(call, FunctionCallTrace)
                    and call.call_id == entry.source_call_id
                )
                cited_turn_ids = source_call.arguments.get("supportingTurnIds")
                if cited_turn_ids is None:
                    cited_turn_ids = source_call.arguments.get("supporting_turn_ids")
                if cited_turn_ids is not None:
                    if not isinstance(cited_turn_ids, list) or not all(
                        isinstance(turn_id, str) for turn_id in cited_turn_ids
                    ):
                        raise ValueError(
                            f"function call {entry.source_call_id} has invalid turn citations"
                        )
                    if tuple(cited_turn_ids) != entry.supporting_turn_ids:
                        raise ValueError(
                            f"application decision {entry.decision_id} does not match source citations"
                        )

        registered_turns = {turn.turn_id for turn in self.turns}
        missing_turns = registered_turns - seen_turns
        if missing_turns:
            missing = ", ".join(sorted(missing_turns))
            raise ValueError(f"logical turns missing from trace: {missing}")
        return self

    def model_context_items(self) -> tuple[ModelContextItem, ...]:
        ledger = self.ledger
        items: list[ModelContextItem] = [
            InferenceContextMessage(
                role="system",
                content=self.stable_instructions,
            )
        ]
        for entry in self.trace:
            if isinstance(entry, TurnMessageTrace):
                turn = ledger.resolve(entry.turn_id)
                if turn.actual_text is None:
                    raise ValueError(
                        f"turn {turn.turn_id} has no actual retained text"
                    )
                items.extend(
                    (
                        InferenceContextMessage(
                            role="developer",
                            content=format_turn_reference(turn),
                        ),
                        InferenceContextMessage(
                            role=turn.role.value,
                            content=turn.actual_text,
                            provider_item_id=(
                                turn.provider_item_ids[0]
                                if turn.provider_item_ids
                                else None
                            ),
                            interrupted=(
                                turn.delivery_status
                                is TurnDeliveryStatus.INTERRUPTED
                            ),
                            logical_turn_id=turn.turn_id,
                        ),
                    )
                )
            elif isinstance(entry, (FunctionCallTrace, FunctionResultTrace)):
                items.append(entry)
        return tuple(items)

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )


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
