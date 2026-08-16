from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from voice_presentation.domain.contracts import ScopeMode


class TurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class TurnPurpose(StrEnum):
    NARRATION = "narration"
    USER_FOLLOW_UP = "user_follow_up"
    ANSWER = "answer"


class TurnDeliveryStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class GroundingSource(StrEnum):
    CONVERSATION = "conversation"
    PRESENTATION = "presentation"
    CONVERSATION_AND_PRESENTATION = "conversation_and_presentation"
    MODEL_KNOWLEDGE = "model_knowledge"
    NONE = "none"


class LogicalTurn(BaseModel):
    """Application-owned identity and observable provenance for one spoken turn."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    turn_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    role: TurnRole
    purpose: TurnPurpose
    session_version: int = Field(ge=0)
    slide_id: str | None = Field(default=None, min_length=1)
    beat_index: int | None = Field(default=None, ge=0)
    visible_slide_id: str | None = Field(default=None, min_length=1)
    interrupted_turn_id: str | None = Field(default=None, min_length=1)
    provider_item_ids: tuple[str, ...] = ()
    actual_text: str | None = Field(default=None, min_length=1)
    delivery_status: TurnDeliveryStatus = TurnDeliveryStatus.PENDING
    plan_id: str | None = Field(default=None, min_length=1)
    scope_mode: ScopeMode | None = None
    grounding_source: GroundingSource | None = None
    resumed_after_turn_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_coherence(self) -> "LogicalTurn":
        expected_role = (
            TurnRole.USER
            if self.purpose is TurnPurpose.USER_FOLLOW_UP
            else TurnRole.ASSISTANT
        )
        if self.role is not expected_role:
            raise ValueError("logical turn role and purpose are incoherent")

        if self.purpose is TurnPurpose.NARRATION:
            if self.slide_id is None or self.beat_index is None:
                raise ValueError("narration turns require slide_id and beat_index")
        elif self.beat_index is not None:
            raise ValueError("beat_index is only valid for narration turns")

        if self.delivery_status is TurnDeliveryStatus.PENDING:
            if self.actual_text is not None:
                raise ValueError("pending turns cannot claim actual retained text")
        elif self.actual_text is None:
            raise ValueError("delivered turns require actual retained text")

        if len(set(self.provider_item_ids)) != len(self.provider_item_ids):
            raise ValueError("provider_item_ids must be unique within a logical turn")
        if any(not item_id.strip() for item_id in self.provider_item_ids):
            raise ValueError("provider_item_ids cannot contain blank values")

        if (self.scope_mode is None) is not (self.grounding_source is None):
            raise ValueError("scope_mode and grounding_source must be supplied together")
        return self


class LogicalTurnLedger:
    """Mutable application ledger keyed by logical and provider turn identity."""

    def __init__(self, *, session_version: int) -> None:
        if session_version < 0:
            raise ValueError("session version must be non-negative")
        self._session_version = session_version
        self._turns: dict[str, LogicalTurn] = {}
        self._provider_turn_ids: dict[str, str] = {}

    @property
    def session_version(self) -> int:
        return self._session_version

    @property
    def turns(self) -> tuple[LogicalTurn, ...]:
        return tuple(self._turns.values())

    def register(self, turn: LogicalTurn) -> LogicalTurn:
        self._require_session_version(turn.session_version)
        existing = self._turns.get(turn.turn_id)
        if existing is not None:
            if existing == turn:
                return existing
            raise ValueError(f"conflicting logical turn: {turn.turn_id}")

        for provider_item_id in turn.provider_item_ids:
            owner = self._provider_turn_ids.get(provider_item_id)
            if owner is not None and owner != turn.turn_id:
                raise ValueError(
                    f"provider item {provider_item_id} already belongs to {owner}"
                )

        self._turns[turn.turn_id] = turn
        for provider_item_id in turn.provider_item_ids:
            self._provider_turn_ids[provider_item_id] = turn.turn_id
        return turn

    def record_actual_text(
        self,
        *,
        turn_id: str,
        provider_item_id: str,
        actual_text: str,
        interrupted: bool,
        session_version: int,
    ) -> LogicalTurn:
        self._require_session_version(session_version)
        turn = self.resolve(turn_id)
        provider_item_id = provider_item_id.strip()
        actual_text = actual_text.strip()
        if not provider_item_id:
            raise ValueError("provider_item_id cannot be blank")
        if not actual_text:
            raise ValueError("actual_text cannot be blank")

        requested_status = (
            TurnDeliveryStatus.INTERRUPTED
            if interrupted
            else TurnDeliveryStatus.COMPLETED
        )
        if turn.delivery_status is not TurnDeliveryStatus.PENDING:
            if (
                turn.delivery_status is requested_status
                and turn.actual_text == actual_text
                and provider_item_id in turn.provider_item_ids
            ):
                return turn
            if not (
                turn.delivery_status is TurnDeliveryStatus.INTERRUPTED
                and requested_status is TurnDeliveryStatus.INTERRUPTED
            ):
                raise ValueError(
                    f"cannot replace terminal {turn.delivery_status.value} turn {turn_id}"
                )

        owner = self._provider_turn_ids.get(provider_item_id)
        if owner is not None and owner != turn_id:
            raise ValueError(f"provider item {provider_item_id} already belongs to {owner}")

        provider_item_ids = (*turn.provider_item_ids, provider_item_id)
        delivered = LogicalTurn.model_validate(
            {
                **turn.model_dump(),
                "provider_item_ids": tuple(dict.fromkeys(provider_item_ids)),
                "actual_text": actual_text,
                "delivery_status": requested_status,
            }
        )
        self._turns[turn_id] = delivered
        self._provider_turn_ids[provider_item_id] = turn_id
        return delivered

    def resolve(self, turn_id: str) -> LogicalTurn:
        turn_id = turn_id.strip()
        turn = self._turns.get(turn_id)
        if turn is None:
            raise ValueError(f"unknown logical turn: {turn_id}")
        return turn

    def resolve_provider_item(self, provider_item_id: str) -> LogicalTurn:
        provider_item_id = provider_item_id.strip()
        turn_id = self._provider_turn_ids.get(provider_item_id)
        if turn_id is None:
            raise ValueError(f"unknown provider item: {provider_item_id}")
        return self._turns[turn_id]

    def require_turn_ids(self, turn_ids: tuple[str, ...]) -> tuple[LogicalTurn, ...]:
        return tuple(self.resolve(turn_id) for turn_id in turn_ids)

    def _require_session_version(self, session_version: int) -> None:
        if session_version != self._session_version:
            raise ValueError(
                "session version does not match the active provenance ledger: "
                f"expected {self._session_version}, received {session_version}"
            )


def format_turn_reference(turn: LogicalTurn) -> str:
    """Return deterministic metadata for the immediately following plain message."""

    fields = [f"Turn reference: {turn.turn_id}", f"purpose={turn.purpose.value}"]
    if turn.slide_id is not None:
        fields.append(f"slide={turn.slide_id}")
    if turn.beat_index is not None:
        fields.append(f"beat={turn.beat_index + 1}")
    if turn.visible_slide_id is not None:
        fields.append(f"visible_slide={turn.visible_slide_id}")
    if turn.interrupted_turn_id is not None:
        fields.append(f"interrupted_turn={turn.interrupted_turn_id}")
    if turn.plan_id is not None:
        fields.append(f"plan={turn.plan_id}")
    if turn.scope_mode is not None:
        fields.append(f"scope={turn.scope_mode.value}")
    if turn.grounding_source is not None:
        fields.append(f"source={turn.grounding_source.value}")
    if turn.resumed_after_turn_id is not None:
        fields.append(f"resumed_after={turn.resumed_after_turn_id}")
    return "; ".join(fields) + "."
