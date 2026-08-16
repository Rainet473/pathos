from __future__ import annotations

from pathlib import Path

import pytest

from voice_presentation.content.repository import JsonMaterialRepository
from voice_presentation.content.search import MaterialSearch
from voice_presentation.domain.content import PresentationDeck
from voice_presentation.domain.reasoning import SearchMaterialInput


pytestmark = pytest.mark.offline

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIX_SLIDE_DECK = (
    REPOSITORY_ROOT / "assets" / "motorcycle-controls" / "slide-breakdown.json"
)


def _search(*, max_serialized_bytes: int = 8192) -> MaterialSearch:
    return MaterialSearch(
        JsonMaterialRepository(SIX_SLIDE_DECK).load(),
        max_serialized_bytes=max_serialized_bytes,
    )


def test_phrase_and_multi_term_search_returns_stable_clutch_evidence_with_neighbors():
    request = SearchMaterialInput(
        keywords=("clutch", "plates", "friction zone", "partial engagement"),
        phrases=("friction zone", "partial engagement"),
        slide_ids=("clutch-and-gears",),
        include_neighbors=True,
        max_results=3,
    )

    first = _search().search(request, preferred_slide_id="control-loop")
    second = _search().search(request, preferred_slide_id="control-loop")

    assert first == second
    assert first.query_id.startswith("material-query-")
    assert first.hits[0].evidence_id == (
        "motorcycle-controls.clutch-and-gears.narration.1"
    )
    assert first.hits[0].slide_id == "clutch-and-gears"
    assert first.hits[0].slide_number == 2
    assert first.hits[0].section == "narration"
    assert first.hits[0].segment_index == 1
    assert "friction zone" in first.hits[0].matched_on
    assert first.hits[0].previous is not None
    assert "controllable connection" in first.hits[0].previous.lower()
    assert first.hits[0].next is not None
    assert "drivetrain load" in first.hits[0].next.lower()


def test_stronger_cross_slide_match_beats_preferred_visible_slide():
    result = _search().search(
        SearchMaterialInput(
            keywords=("wheel lock", "pressure modulation", "ABS"),
            phrases=("wheel lock", "pressure modulation"),
            max_results=2,
        ),
        preferred_slide_id="clutch-and-gears",
    )

    assert result.hits[0].slide_id == "braking-abs"
    assert result.hits[0].evidence_id == (
        "motorcycle-controls.braking-abs.narration.3"
    )


def test_preferred_slide_breaks_an_equal_relevance_tie(deck_payload):
    for slide in deck_payload["slides"]:
        slide["headline"] = "Shared coupling response."
        slide["objective"] = "Explain shared coupling response."
        slide["beats"] = [
            {
                "id": f"{slide['id']}-shared",
                "summary": "Shared coupling connects input and output.",
                "narration_guidance": "Explain shared coupling.",
                "required_concepts": ["shared coupling"],
            }
        ]
        slide["deep_dive"] = [
            {
                "concept": "shared coupling",
                "explanation": "Shared coupling connects input and output.",
                "caveats": [],
            }
        ]
        slide["related_terms"] = []
    search = MaterialSearch(PresentationDeck.model_validate(deck_payload))

    result = search.search(
        SearchMaterialInput(
            keywords=("shared", "coupling", "input", "output"),
            phrases=("shared coupling",),
            max_results=1,
        ),
        preferred_slide_id="braking-abs",
    )

    assert result.hits[0].slide_id == "braking-abs"


def test_slide_filter_is_validated_and_strict():
    search = _search()
    with pytest.raises(ValueError, match="unknown slide id"):
        search.search(
            SearchMaterialInput(
                keywords=("clutch",),
                slide_ids=("missing-slide",),
            )
        )

    result = search.search(
        SearchMaterialInput(
            keywords=("engine", "speed", "wheel"),
            slide_ids=("power-to-wheel",),
            max_results=5,
        )
    )
    assert result.hits
    assert {hit.slide_id for hit in result.hits} == {"power-to-wheel"}


def test_serialized_result_is_bounded_by_dropping_lower_ranked_hits():
    search = _search(max_serialized_bytes=1200)
    result = search.search(
        SearchMaterialInput(
            keywords=("wheel", "gear", "engine", "clutch", "brake"),
            include_neighbors=True,
            max_results=5,
        )
    )

    assert result.hits
    assert result.truncated is True
    assert len(result.to_json().encode("utf-8")) <= 1200


def test_no_match_is_a_stable_empty_result():
    request = SearchMaterialInput(keywords=("photosynthesis", "chlorophyll"))

    result = _search().search(request)

    assert result.hits == ()
    assert result.truncated is False
    assert result == _search().search(request)
