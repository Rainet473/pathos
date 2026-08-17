from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.offline

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "frontend" / "src" / "live" / "LiveConversationApp.tsx"
STYLES = ROOT / "frontend" / "src" / "styles.css"


def test_live_workspace_has_explicit_slide_first_regions():
    app = APP.read_text(encoding="utf-8")

    regions = (
        'className="workspace-header"',
        'className="deck-rail"',
        'className="presentation-stage"',
        'className="state-panel session-inspector"',
        'className="workspace-dock"',
    )
    for region in regions:
        assert region in app

    assert app.index(regions[0]) < app.index(regions[1])
    assert app.index(regions[1]) < app.index(regions[2])
    assert app.index(regions[2]) < app.index(regions[3])
    assert app.index(regions[3]) < app.index(regions[4])


def test_deck_rail_is_navigable_and_identifies_the_visible_slide():
    app = APP.read_text(encoding="utf-8")

    assert 'aria-label="Presentation slides"' in app
    assert "snapshot.slides.map" in app
    assert "navigateToSlide(slide.id)" in app
    assert 'aria-current={slide.id === visibleSlide.id ? "page" : undefined}' in app
    assert "deckSlideRenderUrl(snapshot.deckId, slide.id)" in app


def test_css_prioritizes_the_stage_and_collapses_secondary_evidence_on_narrow_screens():
    styles = STYLES.read_text(encoding="utf-8")

    assert 'grid-template-areas:' in styles
    assert '"rail stage inspector"' in styles
    assert '"rail dock inspector"' in styles
    assert ".presentation-stage" in styles
    assert "aspect-ratio: 1376 / 768" in styles
    assert "@media (max-width: 720px)" in styles
    assert ".deck-rail" in styles
    assert "overflow-x: auto" in styles
    assert ".workspace-events" in styles
    assert "display: none" in styles


def test_inspector_renders_a_connected_observable_answer_pathway():
    app = APP.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "<AnswerPathway" in app
    assert 'aria-label="Answer pathway"' in app
    assert "Search if needed" in app
    assert 'className={`pathway-step is-${node.status}`}' in app
    assert ".answer-pathway" in styles
    assert ".pathway-step::after" in styles
    assert ".pathway-step.is-active" in styles
    assert "box-shadow" in styles


def test_desktop_transcript_uses_the_full_remaining_dock_height():
    styles = STYLES.read_text(encoding="utf-8")

    card_rule = styles.split(".workspace-transcript {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "display: flex" in card_rule
    assert "flex-direction: column" in card_rule
    assert ".workspace-transcript .live-transcript" in styles
    transcript_rule = styles.split(
        ".workspace-transcript .live-transcript", maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    assert "flex: 1" in transcript_rule
    assert "min-height: 0" in transcript_rule
    assert "max-height: none" in transcript_rule
    assert "overflow-y: auto" in transcript_rule
