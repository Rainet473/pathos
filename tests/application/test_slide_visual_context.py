from voice_presentation.application.live_presentation import ApplicationPresentationSession
from voice_presentation.domain.content import PresentationDeck


def test_live_view_preserves_authored_visual_description(copied_deck_payload):
    deck = PresentationDeck.model_validate(copied_deck_payload())
    view = ApplicationPresentationSession(deck, session_id="live-visuals").view()

    assert [slide.visual_description for slide in view.slides] == [
        slide.visual_description for slide in deck.slides
    ]
