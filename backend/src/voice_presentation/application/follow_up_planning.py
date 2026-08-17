from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from typing import Annotated, Literal, Protocol

from pydantic import Field

from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.contracts import ScopeMode
from voice_presentation.domain.provenance import (
    GroundingSource,
    LogicalTurnLedger,
    TurnDeliveryStatus,
    TurnPurpose,
    TurnRole,
)
from voice_presentation.domain.reasoning import (
    CitationFilterReport,
    MaterialSection,
    PresentationActionKind,
    PlanningContext,
    PlanningRejectionCode,
    PlanningSnapshot,
    PlanningStatus,
    ReasoningModel,
    SearchMaterialInput,
    SearchMaterialResult,
    SubmitAnswerPlanInput,
    SubmitPresentationActionInput,
    ValidatedAnswerPlan,
    ValidatedPresentationAction,
)
from voice_presentation.transport.context_trace import (
    ApplicationDecisionTrace,
    FunctionCallTrace,
    FunctionResultTrace,
)


MAX_SEARCH_CALLS = 2
MAX_TOOL_STEPS = 3
_PLAN_SUFFIX = re.compile(r"([0-9]+)$")


class PlanningProtocolError(RuntimeError):
    def __init__(self, code: PlanningRejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class MaterialSearchPort(Protocol):
    def search(
        self,
        request: SearchMaterialInput,
        *,
        preferred_slide_id: str | None = None,
    ) -> SearchMaterialResult: ...


class FollowUpPlanningSession:
    """Application-owned, non-mutating transaction for one follow-up plan."""

    def __init__(
        self,
        *,
        deck: PresentationDeck,
        provenance: LogicalTurnLedger,
        context: PlanningContext,
        search: MaterialSearchPort | None = None,
        clock: Callable[[], float] = time.monotonic,
        started_at: float | None = None,
        active_identity: Callable[[], tuple[int, str]] | None = None,
    ) -> None:
        if provenance.session_version != context.session_version:
            raise ValueError("planning context and provenance session versions differ")
        follow_up = provenance.resolve(context.follow_up_turn_id)
        if (
            follow_up.role is not TurnRole.USER
            or follow_up.purpose is not TurnPurpose.USER_FOLLOW_UP
            or follow_up.delivery_status is not TurnDeliveryStatus.COMPLETED
        ):
            raise ValueError("planning requires one completed user follow-up turn")
        deck.slide(context.current_slide_id)
        deck.slide(context.visible_slide_id)

        self._deck = deck
        self._provenance = provenance
        self._context = context
        self._search = search or MaterialSearch(deck)
        self._support_search = MaterialSearch(deck)
        self._clock = clock
        self._active_identity = active_identity or (
            lambda: (context.session_version, context.follow_up_turn_id)
        )
        self._started_at = clock() if started_at is None else started_at
        self._status = PlanningStatus.ACTIVE
        self._tool_steps = 0
        self._search_calls = 0
        self._search_results: list[SearchMaterialResult] = []
        self._evidence = {
            hit.evidence_id: hit for hit in context.current_slide_evidence
        }
        follow_up_index = next(
            index
            for index, turn in enumerate(provenance.turns)
            if turn.turn_id == context.follow_up_turn_id
        )
        self._eligible_turn_ids = frozenset(
            turn.turn_id
            for turn in provenance.turns[:follow_up_index]
            if turn.delivery_status is not TurnDeliveryStatus.PENDING
        )
        self._known_turn_ids = frozenset(
            turn.turn_id for turn in provenance.turns
        )
        self._known_slide_ids = frozenset(slide.id for slide in deck.slides)
        self._accepted_plan: ValidatedAnswerPlan | None = None
        self._accepted_action: ValidatedPresentationAction | None = None
        self._citation_filter: CitationFilterReport | None = None
        self._rejection_code: PlanningRejectionCode | None = None
        self._terminal_attempted = False

    @property
    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            status=self._status,
            tool_steps=self._tool_steps,
            search_calls=self._search_calls,
            search_results=tuple(self._search_results),
            terminology_hints=self._context.terminology_hints,
            accepted_plan=self._accepted_plan,
            accepted_action=self._accepted_action,
            citation_filter=self._citation_filter,
            rejection_code=self._rejection_code,
        )

    def search(
        self,
        request: SearchMaterialInput,
        *,
        session_version: int,
        follow_up_turn_id: str,
    ) -> SearchMaterialResult:
        self._assert_action_identity(
            session_version=session_version,
            follow_up_turn_id=follow_up_turn_id,
            terminal=False,
        )
        self._begin_step(search=True)
        try:
            result = self._search.search(
                request,
                preferred_slide_id=self._context.visible_slide_id,
            )
        except ValueError as error:
            self._reject(PlanningRejectionCode.UNKNOWN_SLIDE, str(error))
        self._assert_active_after_dependency()
        self._check_timeout()
        self._search_results.append(result)
        for hit in result.hits:
            self._evidence[hit.evidence_id] = hit
        return result

    def submit(
        self,
        proposal: SubmitAnswerPlanInput,
        *,
        session_version: int,
        follow_up_turn_id: str,
        received_at: float | None = None,
    ) -> ValidatedAnswerPlan:
        self._assert_action_identity(
            session_version=session_version,
            follow_up_turn_id=follow_up_turn_id,
            terminal=True,
            observed_at=received_at,
        )
        self._begin_step(search=False)
        self._terminal_attempted = True
        normalized = self._normalize_proposal(proposal)
        self._validate_proposal(normalized)
        accepted = ValidatedAnswerPlan.model_validate(
            {
                **normalized.model_dump(),
                "plan_id": self._plan_id(),
                "follow_up_turn_id": self._context.follow_up_turn_id,
                "session_version": self._context.session_version,
                "continuation_preference": self._context.continuation_preference,
            }
        )
        self._accepted_plan = accepted
        self._status = PlanningStatus.ACCEPTED
        return accepted

    def submit_action(
        self,
        proposal: SubmitPresentationActionInput,
        *,
        session_version: int,
        follow_up_turn_id: str,
        received_at: float | None = None,
    ) -> ValidatedPresentationAction:
        self._assert_action_identity(
            session_version=session_version,
            follow_up_turn_id=follow_up_turn_id,
            terminal=True,
            observed_at=received_at,
        )
        self._begin_step(search=False)
        self._terminal_attempted = True
        accepted = ValidatedPresentationAction(
            action_id=self._action_id(),
            follow_up_turn_id=self._context.follow_up_turn_id,
            session_version=self._context.session_version,
            action=PresentationActionKind(proposal.action),
        )
        self._accepted_action = accepted
        self._status = PlanningStatus.ACCEPTED
        return accepted

    def recover_rejected_terminal(
        self,
        code: PlanningRejectionCode,
    ) -> PlanningSnapshot:
        """Reopen one bounded, explicitly recoverable terminal rejection."""

        if (
            self._status is not PlanningStatus.REJECTED
            or self._rejection_code is not code
            or not self._terminal_attempted
        ):
            raise PlanningProtocolError(
                self._rejection_code or PlanningRejectionCode.CANCELLED,
                "planning session has no matching rejected terminal call",
            )
        if code is not PlanningRejectionCode.UNKNOWN_EVIDENCE:
            raise PlanningProtocolError(
                code,
                "only unknown historical evidence can be corrected",
            )
        if self._tool_steps >= MAX_TOOL_STEPS:
            raise PlanningProtocolError(
                PlanningRejectionCode.TOOL_STEP_LIMIT,
                "planning has no remaining correction steps",
            )
        self._status = PlanningStatus.ACTIVE
        self._rejection_code = None
        self._terminal_attempted = False
        return self.snapshot

    def cancel(
        self,
        code: PlanningRejectionCode = PlanningRejectionCode.CANCELLED,
    ) -> PlanningSnapshot:
        if self._status is PlanningStatus.ACTIVE:
            self._status = PlanningStatus.CANCELLED
            self._rejection_code = code
        return self.snapshot

    def finish(self) -> PlanningSnapshot:
        if self._status is PlanningStatus.ACTIVE and not self._terminal_attempted:
            self._reject(
                PlanningRejectionCode.MISSING_TERMINAL,
                "planning ended without a terminal submission",
            )
        return self.snapshot

    def _assert_action_identity(
        self,
        *,
        session_version: int,
        follow_up_turn_id: str,
        terminal: bool,
        observed_at: float | None = None,
    ) -> None:
        if self._status is not PlanningStatus.ACTIVE:
            if self._status is PlanningStatus.ACCEPTED and terminal:
                raise PlanningProtocolError(
                    PlanningRejectionCode.DUPLICATE_TERMINAL,
                    "a terminal planning result was already accepted",
                )
            raise PlanningProtocolError(
                self._rejection_code or PlanningRejectionCode.CANCELLED,
                f"planning session is already {self._status.value}",
            )
        self._check_timeout(observed_at)
        if session_version != self._context.session_version:
            self.cancel(PlanningRejectionCode.STALE_SESSION)
            raise PlanningProtocolError(
                PlanningRejectionCode.STALE_SESSION,
                "planning action used a stale session version",
            )
        if follow_up_turn_id != self._context.follow_up_turn_id:
            self.cancel(PlanningRejectionCode.STALE_FOLLOW_UP)
            raise PlanningProtocolError(
                PlanningRejectionCode.STALE_FOLLOW_UP,
                "planning action used a stale follow-up turn",
            )
        self._assert_live_identity()

    def _begin_step(self, *, search: bool) -> None:
        if self._tool_steps >= MAX_TOOL_STEPS:
            self._reject(
                PlanningRejectionCode.TOOL_STEP_LIMIT,
                "planning exceeded the total tool-step limit",
            )
        if search and self._search_calls >= MAX_SEARCH_CALLS:
            self._reject(
                PlanningRejectionCode.SEARCH_LIMIT,
                "planning exceeded the search call limit",
            )
        self._tool_steps += 1
        if search:
            self._search_calls += 1

    def _check_timeout(self, observed_at: float | None = None) -> None:
        now = self._clock() if observed_at is None else observed_at
        if now - self._started_at > self._context.timeout_seconds:
            self.cancel(PlanningRejectionCode.TIMEOUT)
            raise PlanningProtocolError(
                PlanningRejectionCode.TIMEOUT,
                "planning exceeded its deadline",
            )

    def _assert_active_after_dependency(self) -> None:
        if self._status is not PlanningStatus.ACTIVE:
            raise PlanningProtocolError(
                self._rejection_code or PlanningRejectionCode.CANCELLED,
                f"planning session became {self._status.value} during search",
            )
        self._assert_live_identity()

    def _assert_live_identity(self) -> None:
        session_version, follow_up_turn_id = self._active_identity()
        if session_version != self._context.session_version:
            self.cancel(PlanningRejectionCode.STALE_SESSION)
            raise PlanningProtocolError(
                PlanningRejectionCode.STALE_SESSION,
                "active session version changed during planning",
            )
        if follow_up_turn_id != self._context.follow_up_turn_id:
            self.cancel(PlanningRejectionCode.STALE_FOLLOW_UP)
            raise PlanningProtocolError(
                PlanningRejectionCode.STALE_FOLLOW_UP,
                "active follow-up turn changed during planning",
            )

    def _normalize_proposal(
        self,
        proposal: SubmitAnswerPlanInput,
    ) -> SubmitAnswerPlanInput:
        unknown_turn_ids = tuple(
            turn_id
            for turn_id in proposal.supporting_turn_ids
            if turn_id not in self._known_turn_ids
        )
        ineligible_turn_ids = tuple(
            turn_id
            for turn_id in proposal.supporting_turn_ids
            if turn_id in self._known_turn_ids
            and turn_id not in self._eligible_turn_ids
        )
        eligible_turn_ids = tuple(
            turn_id
            for turn_id in proposal.supporting_turn_ids
            if turn_id in self._eligible_turn_ids
        )
        retained_evidence_ids = tuple(
            evidence_id
            for evidence_id in proposal.evidence_ids
            if evidence_id in self._evidence
        )
        untrusted_evidence_ids = tuple(
            evidence_id
            for evidence_id in proposal.evidence_ids
            if evidence_id not in self._evidence
        )
        valid_slide_ids = tuple(
            slide_id
            for slide_id in proposal.supporting_slide_ids
            if slide_id in self._known_slide_ids
        )
        removed_slide_ids = tuple(
            slide_id
            for slide_id in proposal.supporting_slide_ids
            if slide_id not in self._known_slide_ids
        )
        derived_slide_ids = self._unique(
            slide_id
            for evidence_id in proposal.evidence_ids
            if (slide_id := self._slide_id_from_evidence_id(evidence_id))
            is not None
        )
        recovered_slide_ids = tuple(
            slide_id
            for slide_id in derived_slide_ids
            if slide_id not in valid_slide_ids
        )
        retained_evidence_slides = self._unique(
            self._evidence[evidence_id].slide_id
            for evidence_id in retained_evidence_ids
        )
        candidate_slide_ids = self._unique(
            (*retained_evidence_slides, *valid_slide_ids, *derived_slide_ids)
        )[:6]
        has_turn_support = bool(eligible_turn_ids)
        has_presentation_support = bool(
            retained_evidence_ids or candidate_slide_ids
        )

        original_source = proposal.grounding_source
        normalized_source = original_source
        use_turn_support = False
        use_presentation_support = False
        if proposal.scope is ScopeMode.GROUNDED:
            if original_source is GroundingSource.PRESENTATION:
                if has_presentation_support:
                    use_presentation_support = True
                elif has_turn_support:
                    use_turn_support = True
                    normalized_source = GroundingSource.CONVERSATION
            elif original_source is GroundingSource.CONVERSATION:
                if has_turn_support:
                    use_turn_support = True
                elif has_presentation_support:
                    use_presentation_support = True
                    normalized_source = GroundingSource.PRESENTATION
            else:
                use_turn_support = has_turn_support
                use_presentation_support = has_presentation_support
                if use_turn_support and use_presentation_support:
                    normalized_source = (
                        GroundingSource.CONVERSATION_AND_PRESENTATION
                    )
                elif use_presentation_support:
                    normalized_source = GroundingSource.PRESENTATION
                elif use_turn_support:
                    normalized_source = GroundingSource.CONVERSATION
        elif proposal.scope is ScopeMode.EXTENDED_KNOWLEDGE:
            # Model knowledge does not need conversation citations. Filtering them
            # preserves the model's answer decision without treating the request as
            # evidence for itself.
            normalized_source = GroundingSource.MODEL_KNOWLEDGE
        elif proposal.scope is ScopeMode.NEEDS_CLARIFICATION:
            use_turn_support = has_turn_support
            normalized_source = GroundingSource.NONE
        else:
            normalized_source = GroundingSource.NONE

        derived_hits = ()
        normalized_evidence_ids: tuple[str, ...] = ()
        if proposal.scope in {
            ScopeMode.EXTENDED_KNOWLEDGE,
            ScopeMode.NEEDS_CLARIFICATION,
        }:
            normalized_slide_ids = candidate_slide_ids
        elif proposal.scope is ScopeMode.OUT_OF_SCOPE:
            normalized_slide_ids = ()
        else:
            normalized_slide_ids = valid_slide_ids
        if use_presentation_support:
            represented_slides = set(retained_evidence_slides)
            hits = []
            for slide_id in candidate_slide_ids:
                if slide_id in represented_slides:
                    continue
                if len(retained_evidence_ids) + len(hits) >= 10:
                    break
                hits.append(self._support_search.slide_summary_hit(slide_id))
                represented_slides.add(slide_id)
            derived_hits = tuple(hits)
            if derived_hits:
                result = SearchMaterialResult(
                    query_id=(
                        "citation-derived-slide-support-"
                        f"{self._context.follow_up_turn_id}"
                    ),
                    hits=derived_hits,
                )
                self._search_results.append(result)
                for hit in derived_hits:
                    self._evidence[hit.evidence_id] = hit
            all_evidence_ids = self._unique(
                (*retained_evidence_ids, *(hit.evidence_id for hit in derived_hits))
            )[:10]
            evidence_slide_ids = self._unique(
                self._evidence[evidence_id].slide_id
                for evidence_id in all_evidence_ids
            )[:6]
            normalized_slide_ids = evidence_slide_ids
            normalized_evidence_ids = tuple(
                evidence_id
                for evidence_id in all_evidence_ids
                if self._evidence[evidence_id].slide_id in normalized_slide_ids
            )

        normalized_turn_ids = eligible_turn_ids if use_turn_support else ()
        removed_evidence_ids = tuple(
            evidence_id
            for evidence_id in proposal.evidence_ids
            if evidence_id not in normalized_evidence_ids
        )
        unneeded_turn_ids = tuple(
            turn_id
            for turn_id in eligible_turn_ids
            if turn_id not in normalized_turn_ids
        )

        original_focus = proposal.focus_slide_id
        normalized_focus = original_focus
        if proposal.scope in {
            ScopeMode.NEEDS_CLARIFICATION,
            ScopeMode.OUT_OF_SCOPE,
        }:
            normalized_focus = None
        elif original_focus is not None and original_focus not in self._known_slide_ids:
            normalized_focus = next(
                (
                    slide_id
                    for slide_id in derived_slide_ids
                    if slide_id in normalized_slide_ids
                ),
                normalized_slide_ids[0] if normalized_slide_ids else None,
            )
        if normalized_focus is not None:
            cited_turn_slides = {
                slide_id
                for turn_id in normalized_turn_ids
                for turn in (self._provenance.resolve(turn_id),)
                for slide_id in (turn.slide_id, turn.visible_slide_id)
                if slide_id is not None
            }
            if normalized_focus not in (
                set(normalized_slide_ids) | cited_turn_slides
            ):
                normalized_focus = None

        source_changed = normalized_source is not original_source
        focus_changed = normalized_focus != original_focus
        report = CitationFilterReport(
            removed_unknown_turn_ids=unknown_turn_ids,
            removed_ineligible_turn_ids=ineligible_turn_ids,
            removed_unneeded_turn_ids=unneeded_turn_ids,
            removed_evidence_ids=removed_evidence_ids,
            removed_unknown_slide_ids=removed_slide_ids,
            derived_slide_ids_from_evidence=recovered_slide_ids,
            derived_evidence_ids_from_slides=tuple(
                hit.evidence_id for hit in derived_hits
            ),
            removed_focus_slide_id=original_focus if focus_changed else None,
            normalized_focus_slide_id=normalized_focus if focus_changed else None,
            original_grounding_source=original_source if source_changed else None,
            normalized_grounding_source=normalized_source if source_changed else None,
        )
        if any(
            (
                unknown_turn_ids,
                ineligible_turn_ids,
                unneeded_turn_ids,
                removed_evidence_ids,
                removed_slide_ids,
                recovered_slide_ids,
                derived_hits,
                focus_changed,
                source_changed,
            )
        ):
            self._citation_filter = report

        if proposal.scope is ScopeMode.GROUNDED and not (
            normalized_turn_ids or normalized_evidence_ids
        ):
            if ineligible_turn_ids:
                self._reject(
                    PlanningRejectionCode.INELIGIBLE_TURN,
                    "no usable support remained after filtering ineligible turns",
                )
            if unknown_turn_ids:
                self._reject(
                    PlanningRejectionCode.UNKNOWN_TURN,
                    "no usable support remained after filtering unknown turns",
                )
            if untrusted_evidence_ids:
                self._reject(
                    PlanningRejectionCode.UNKNOWN_EVIDENCE,
                    "no usable support remained after filtering evidence",
                )
            if removed_slide_ids:
                self._reject(
                    PlanningRejectionCode.UNKNOWN_SLIDE,
                    "no usable support remained after filtering slides",
                )
            self._reject(
                PlanningRejectionCode.INCOHERENT_PLAN,
                "grounded plan has no usable support after citation filtering",
            )

        return SubmitAnswerPlanInput.model_validate(
            {
                **proposal.model_dump(),
                "grounding_source": normalized_source,
                "supporting_turn_ids": normalized_turn_ids,
                "evidence_ids": normalized_evidence_ids,
                "supporting_slide_ids": normalized_slide_ids,
                "focus_slide_id": normalized_focus,
            }
        )

    def _slide_id_from_evidence_id(self, evidence_id: str) -> str | None:
        prefix = f"{self._deck.id}."
        if not evidence_id.startswith(prefix):
            return None
        parts = evidence_id[len(prefix) :].rsplit(".", 2)
        if len(parts) != 3:
            return None
        slide_id, section, segment_index = parts
        if (
            slide_id not in self._known_slide_ids
            or section not in {value.value for value in MaterialSection}
            or not segment_index.isdigit()
        ):
            return None
        return slide_id

    @staticmethod
    def _unique(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

    def _validate_proposal(self, proposal: SubmitAnswerPlanInput) -> None:
        try:
            cited_turns = self._provenance.require_turn_ids(
                proposal.supporting_turn_ids
            )
        except ValueError as error:
            self._reject(PlanningRejectionCode.UNKNOWN_TURN, str(error))

        ineligible_turns = tuple(
            turn.turn_id
            for turn in cited_turns
            if turn.turn_id not in self._eligible_turn_ids
        )
        if ineligible_turns:
            self._reject(
                PlanningRejectionCode.INELIGIBLE_TURN,
                "turns are not eligible preceding conversation history: "
                + ", ".join(ineligible_turns),
            )

        try:
            for slide_id in proposal.supporting_slide_ids:
                self._deck.slide(slide_id)
            if proposal.focus_slide_id is not None:
                self._deck.slide(proposal.focus_slide_id)
        except ValueError as error:
            self._reject(PlanningRejectionCode.UNKNOWN_SLIDE, str(error))

        missing_evidence = tuple(
            evidence_id
            for evidence_id in proposal.evidence_ids
            if evidence_id not in self._evidence
        )
        if missing_evidence:
            self._reject(
                PlanningRejectionCode.UNKNOWN_EVIDENCE,
                "unknown planning evidence: " + ", ".join(missing_evidence),
            )

        evidence_slides = {
            self._evidence[evidence_id].slide_id
            for evidence_id in proposal.evidence_ids
        }
        if not evidence_slides <= set(proposal.supporting_slide_ids):
            self._reject(
                PlanningRejectionCode.INCOHERENT_PLAN,
                "supporting slides do not contain every cited evidence item",
            )

        cited_turn_slides = {
            slide_id
            for turn in cited_turns
            for slide_id in (turn.slide_id, turn.visible_slide_id)
            if slide_id is not None
        }
        if (
            proposal.focus_slide_id is not None
            and proposal.focus_slide_id
            not in evidence_slides | cited_turn_slides
        ):
            self._reject(
                PlanningRejectionCode.INCOHERENT_PLAN,
                "focus slide is not supported by cited turns or evidence",
            )

    def _plan_id(self) -> str:
        suffix = _PLAN_SUFFIX.search(self._context.follow_up_turn_id)
        if suffix is None:
            return f"answer-plan-{self._context.follow_up_turn_id}"
        return f"answer-plan-{suffix.group(1)}"

    def _action_id(self) -> str:
        suffix = _PLAN_SUFFIX.search(self._context.follow_up_turn_id)
        if suffix is None:
            return f"presentation-action-{self._context.follow_up_turn_id}"
        return f"presentation-action-{suffix.group(1)}"

    def _reject(self, code: PlanningRejectionCode, message: str) -> None:
        self._status = PlanningStatus.REJECTED
        self._rejection_code = code
        raise PlanningProtocolError(code, message)


class RecordedSearchAction(ReasoningModel):
    type: Literal["search_material"] = "search_material"
    input: SearchMaterialInput


class RecordedSubmitPlanAction(ReasoningModel):
    type: Literal["submit_answer_plan"] = "submit_answer_plan"
    input: SubmitAnswerPlanInput


RecordedPlanningAction = Annotated[
    RecordedSearchAction | RecordedSubmitPlanAction,
    Field(discriminator="type"),
]
PlanningTraceEntry = Annotated[
    FunctionCallTrace | FunctionResultTrace | ApplicationDecisionTrace,
    Field(discriminator="type"),
]


class RecordedPlanningCase(ReasoningModel):
    name: str = Field(min_length=1)
    context: PlanningContext
    actions: tuple[RecordedPlanningAction, ...] = Field(min_length=1, max_length=3)


class RecordedPlanningSuite(ReasoningModel):
    cases: tuple[RecordedPlanningCase, ...] = Field(min_length=1)


class RecordedPlanningRun(ReasoningModel):
    case_name: str = Field(min_length=1)
    status: PlanningStatus
    accepted_plan: ValidatedAnswerPlan | None = None
    search_results: tuple[SearchMaterialResult, ...] = ()
    citation_filter: CitationFilterReport | None = None
    rejection_code: PlanningRejectionCode | None = None
    trace: tuple[PlanningTraceEntry, ...]

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            sort_keys=True,
        )


class DeterministicPlannerHarness:
    """Replay recorded model tool actions against the real offline boundaries."""

    def __init__(
        self,
        *,
        deck: PresentationDeck,
        provenance: LogicalTurnLedger,
    ) -> None:
        self._deck = deck
        self._provenance = provenance

    def run(self, case: RecordedPlanningCase) -> RecordedPlanningRun:
        session = FollowUpPlanningSession(
            deck=self._deck,
            provenance=self._provenance,
            context=case.context,
        )
        trace: list[
            FunctionCallTrace | FunctionResultTrace | ApplicationDecisionTrace
        ] = []
        for step, action in enumerate(case.actions, start=1):
            call_id = f"call-{action.type}-{step}"
            trace.append(
                FunctionCallTrace(
                    call_id=call_id,
                    name=action.type,
                    arguments=action.input.model_dump(mode="json", by_alias=True),
                )
            )
            try:
                if isinstance(action, RecordedSearchAction):
                    result = session.search(
                        action.input,
                        session_version=case.context.session_version,
                        follow_up_turn_id=case.context.follow_up_turn_id,
                    )
                    trace.append(
                        FunctionResultTrace(
                            call_id=call_id,
                            name=action.type,
                            output=result.model_dump(mode="json", by_alias=True),
                            is_error=False,
                        )
                    )
                else:
                    plan = session.submit(
                        action.input,
                        session_version=case.context.session_version,
                        follow_up_turn_id=case.context.follow_up_turn_id,
                    )
                    citation_filter = session.snapshot.citation_filter
                    result_output: dict[str, object] = {
                        "accepted": True,
                        "planId": plan.plan_id,
                    }
                    if citation_filter is not None:
                        result_output["citationFilter"] = (
                            citation_filter.model_dump(mode="json", by_alias=True)
                        )
                    trace.extend(
                        (
                            FunctionResultTrace(
                                call_id=call_id,
                                name=action.type,
                                output=result_output,
                                is_error=False,
                            ),
                            ApplicationDecisionTrace(
                                decision_id=f"decision-{case.name}",
                                source_call_id=call_id,
                                plan_id=plan.plan_id,
                                accepted=True,
                                reason_code=(
                                    "accepted_with_filtered_citations"
                                    if citation_filter is not None
                                    else "accepted"
                                ),
                                supporting_turn_ids=plan.supporting_turn_ids,
                            ),
                        )
                    )
            except PlanningProtocolError as error:
                trace.append(
                    FunctionResultTrace(
                        call_id=call_id,
                        name=action.type,
                        output={
                            "accepted": False,
                            "reasonCode": error.code.value,
                        },
                        is_error=True,
                    )
                )
                if isinstance(action, RecordedSubmitPlanAction):
                    trace.append(
                        ApplicationDecisionTrace(
                            decision_id=f"decision-{case.name}",
                            source_call_id=call_id,
                            plan_id=f"rejected-plan-{case.name}",
                            accepted=False,
                            reason_code=error.code.value,
                            supporting_turn_ids=(),
                        )
                    )
                break

        try:
            snapshot = session.finish()
        except PlanningProtocolError:
            snapshot = session.snapshot
        if (
            snapshot.status is not PlanningStatus.ACCEPTED
            and not any(
                isinstance(entry, ApplicationDecisionTrace) for entry in trace
            )
        ):
            source_call = next(
                entry
                for entry in reversed(trace)
                if isinstance(entry, FunctionCallTrace)
            )
            reason_code = snapshot.rejection_code or PlanningRejectionCode.CANCELLED
            trace.append(
                ApplicationDecisionTrace(
                    decision_id=f"decision-{case.name}",
                    source_call_id=source_call.call_id,
                    plan_id=f"rejected-plan-{case.name}",
                    accepted=False,
                    reason_code=reason_code.value,
                )
            )
        return RecordedPlanningRun(
            case_name=case.name,
            status=snapshot.status,
            accepted_plan=snapshot.accepted_plan,
            search_results=snapshot.search_results,
            citation_filter=snapshot.citation_filter,
            rejection_code=snapshot.rejection_code,
            trace=tuple(trace),
        )
