from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel

from voice_presentation.domain.contracts import ContinuationPreference, ScopeMode
from voice_presentation.domain.provenance import GroundingSource


NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_NORMALIZED_SPACE = re.compile(r"\s+")


class ReasoningModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class TerminologyHint(ReasoningModel):
    observed_text: NonBlankString
    authored_term: NonBlankString
    match_kind: Literal["exact", "spaced", "phonetic_neighbor"]


class SearchMaterialInput(ReasoningModel):
    keywords: tuple[NonBlankString, ...] = Field(min_length=1, max_length=8)
    phrases: tuple[NonBlankString, ...] = Field(default=(), max_length=4)
    slide_ids: tuple[NonBlankString, ...] = Field(default=(), max_length=6)
    include_neighbors: bool = False
    max_results: int = Field(default=5, ge=1, le=5)

    @model_validator(mode="after")
    def validate_query_bounds(self) -> "SearchMaterialInput":
        normalized_query = _NORMALIZED_SPACE.sub(
            " ", " ".join((*self.keywords, *self.phrases)).lower()
        ).strip()
        if len(normalized_query) > 512:
            raise ValueError("normalized material query cannot exceed 512 characters")
        if len(set(self.slide_ids)) != len(self.slide_ids):
            raise ValueError("slide_ids must be unique")
        return self


class MaterialSection(StrEnum):
    SUMMARY = "summary"
    NARRATION = "narration"
    DEEP_DIVE = "deep_dive"


class MaterialHit(ReasoningModel):
    evidence_id: NonBlankString
    slide_id: NonBlankString
    slide_number: int = Field(ge=1)
    section: MaterialSection
    segment_index: int = Field(ge=0)
    text: NonBlankString
    previous: NonBlankString | None = None
    next: NonBlankString | None = None
    matched_on: tuple[NonBlankString, ...] = Field(min_length=1)


class SearchMaterialResult(ReasoningModel):
    query_id: NonBlankString
    hits: tuple[MaterialHit, ...]
    truncated: bool = False

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )


class SubmitAnswerPlanInput(ReasoningModel):
    scope: ScopeMode
    grounding_source: GroundingSource
    answer_brief: NonBlankString = Field(max_length=600)
    supporting_turn_ids: tuple[NonBlankString, ...] = Field(
        default=(), max_length=8
    )
    evidence_ids: tuple[NonBlankString, ...] = Field(default=(), max_length=10)
    supporting_slide_ids: tuple[NonBlankString, ...] = Field(
        default=(), max_length=6
    )
    focus_slide_id: NonBlankString | None = None
    clarification_prompt: NonBlankString | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def validate_plan_coherence(self) -> "SubmitAnswerPlanInput":
        if len(self.answer_brief.split()) > 80:
            raise ValueError("answer_brief cannot exceed 80 words")
        for field_name in (
            "supporting_turn_ids",
            "evidence_ids",
            "supporting_slide_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")

        if self.scope is ScopeMode.GROUNDED:
            if self.grounding_source not in {
                GroundingSource.CONVERSATION,
                GroundingSource.PRESENTATION,
                GroundingSource.CONVERSATION_AND_PRESENTATION,
            }:
                raise ValueError("grounded scope requires a grounded source")
            if self.clarification_prompt is not None:
                raise ValueError("grounded plans cannot include clarification_prompt")
        elif self.scope is ScopeMode.EXTENDED_KNOWLEDGE:
            if self.grounding_source is not GroundingSource.MODEL_KNOWLEDGE:
                raise ValueError(
                    "extended_knowledge requires model_knowledge grounding source"
                )
            if self.clarification_prompt is not None:
                raise ValueError(
                    "extended_knowledge cannot include clarification_prompt"
                )
        elif self.scope is ScopeMode.NEEDS_CLARIFICATION:
            if self.grounding_source is not GroundingSource.NONE:
                raise ValueError("needs_clarification requires no grounding source")
            if self.clarification_prompt is None:
                raise ValueError("needs_clarification requires clarification_prompt")
            if (
                not self.clarification_prompt.endswith("?")
                or self.clarification_prompt.count("?") != 1
            ):
                raise ValueError("clarification_prompt must be exactly one question")
        else:
            if self.grounding_source is not GroundingSource.NONE:
                raise ValueError("out_of_scope requires no grounding source")
            if self.clarification_prompt is not None:
                raise ValueError(
                    "out_of_scope cannot request clarification"
                )
        return self


class PlanningContext(ReasoningModel):
    follow_up_turn_id: NonBlankString
    session_version: int = Field(ge=0)
    current_slide_id: NonBlankString
    visible_slide_id: NonBlankString
    continuation_preference: ContinuationPreference
    current_slide_evidence: tuple[MaterialHit, ...] = Field(default=(), max_length=5)
    terminology_hints: tuple[TerminologyHint, ...] = Field(default=(), max_length=4)
    timeout_seconds: float = Field(default=30.0, gt=0, le=60)

    @model_validator(mode="after")
    def validate_current_evidence(self) -> "PlanningContext":
        evidence_ids = tuple(hit.evidence_id for hit in self.current_slide_evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("current_slide_evidence IDs must be unique")
        if any(
            hit.slide_id != self.current_slide_id
            for hit in self.current_slide_evidence
        ):
            raise ValueError(
                "current_slide_evidence must belong to current_slide_id"
            )
        return self


class ValidatedAnswerPlan(SubmitAnswerPlanInput):
    plan_id: NonBlankString
    follow_up_turn_id: NonBlankString
    session_version: int = Field(ge=0)
    continuation_preference: ContinuationPreference

    @model_validator(mode="after")
    def validate_application_grounding(self) -> "ValidatedAnswerPlan":
        if self.focus_slide_id is not None and (
            self.focus_slide_id not in self.supporting_slide_ids
        ):
            raise ValueError("focus_slide_id must be a supporting slide")

        if self.scope is ScopeMode.GROUNDED:
            if self.grounding_source is GroundingSource.CONVERSATION:
                if not self.supporting_turn_ids or self.evidence_ids:
                    raise ValueError(
                        "conversation grounding requires turns and no deck evidence"
                    )
            elif self.grounding_source is GroundingSource.PRESENTATION:
                if not self.evidence_ids:
                    raise ValueError(
                        "presentation grounding requires validated deck evidence"
                    )
            elif (
                self.grounding_source
                is GroundingSource.CONVERSATION_AND_PRESENTATION
            ):
                if not self.supporting_turn_ids or not self.evidence_ids:
                    raise ValueError(
                        "combined grounding requires turns and validated deck evidence"
                    )
        elif self.scope is ScopeMode.EXTENDED_KNOWLEDGE:
            if self.supporting_turn_ids or self.evidence_ids:
                raise ValueError(
                    "extended_knowledge cannot claim turn or deck evidence"
                )
        elif self.scope is ScopeMode.NEEDS_CLARIFICATION:
            if self.evidence_ids or self.focus_slide_id is not None:
                raise ValueError(
                    "needs_clarification cannot claim evidence or focus navigation"
                )
        elif any(
            (
                self.supporting_turn_ids,
                self.evidence_ids,
                self.supporting_slide_ids,
                self.focus_slide_id,
            )
        ):
            raise ValueError("out_of_scope cannot include grounding citations")
        return self


class PresentationActionKind(StrEnum):
    CONTINUE_PRESENTATION = "continue_presentation"


class SubmitPresentationActionInput(ReasoningModel):
    action: PresentationActionKind


class ValidatedPresentationAction(SubmitPresentationActionInput):
    action_id: NonBlankString
    follow_up_turn_id: NonBlankString
    session_version: int = Field(ge=0)


class CitationFilterReport(ReasoningModel):
    removed_unknown_turn_ids: tuple[NonBlankString, ...] = ()
    removed_ineligible_turn_ids: tuple[NonBlankString, ...] = ()
    removed_unneeded_turn_ids: tuple[NonBlankString, ...] = ()
    removed_evidence_ids: tuple[NonBlankString, ...] = ()
    removed_unknown_slide_ids: tuple[NonBlankString, ...] = ()
    derived_slide_ids_from_evidence: tuple[NonBlankString, ...] = ()
    derived_evidence_ids_from_slides: tuple[NonBlankString, ...] = ()
    removed_focus_slide_id: NonBlankString | None = None
    normalized_focus_slide_id: NonBlankString | None = None
    original_grounding_source: GroundingSource | None = None
    normalized_grounding_source: GroundingSource | None = None


class PlanningStatus(StrEnum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PlanningStage(StrEnum):
    UNDERSTANDING = "understanding"
    SEARCHING = "searching"
    PREPARING = "preparing"


class PlanningRejectionCode(StrEnum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    STALE_SESSION = "stale_session"
    STALE_FOLLOW_UP = "stale_follow_up"
    SEARCH_LIMIT = "search_limit"
    TOOL_STEP_LIMIT = "tool_step_limit"
    DUPLICATE_TERMINAL = "duplicate_terminal"
    MISSING_TERMINAL = "missing_terminal"
    UNKNOWN_TURN = "unknown_turn"
    INELIGIBLE_TURN = "ineligible_turn"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    UNKNOWN_SLIDE = "unknown_slide"
    INCOHERENT_PLAN = "incoherent_plan"


class PlanningSnapshot(ReasoningModel):
    status: PlanningStatus
    tool_steps: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    search_results: tuple[SearchMaterialResult, ...] = ()
    terminology_hints: tuple[TerminologyHint, ...] = ()
    accepted_plan: ValidatedAnswerPlan | None = None
    accepted_action: ValidatedPresentationAction | None = None
    citation_filter: CitationFilterReport | None = None
    rejection_code: PlanningRejectionCode | None = None

    @model_validator(mode="after")
    def validate_single_terminal(self) -> "PlanningSnapshot":
        accepted = sum(
            terminal is not None
            for terminal in (self.accepted_plan, self.accepted_action)
        )
        if accepted > 1:
            raise ValueError("planning can accept only one terminal result")
        if self.status is PlanningStatus.ACCEPTED and accepted != 1:
            raise ValueError("accepted planning requires one terminal result")
        if self.status is not PlanningStatus.ACCEPTED and accepted:
            raise ValueError("non-accepted planning cannot contain a terminal result")
        return self
