from __future__ import annotations

import copy

import pytest


@pytest.fixture
def deck_payload() -> dict[str, object]:
    return {
        "id": "motorcycle-controls",
        "title": "How a Motorcycle Responds to Your Controls",
        "slides": [
            {
                "id": "engine-braking",
                "title": "Engine Braking",
                "objective": "Explain why closing the throttle slows the motorcycle.",
                "headline": "Closed throttle turns the engine into resistance.",
                "labels": ["closed throttle", "drivetrain", "rear wheel"],
                "visual_description": "Rear-wheel torque flows back through the drivetrain.",
                "assets": [],
                "beats": [
                    {
                        "id": "reduced-driving-torque",
                        "summary": "Closing the throttle reduces driving torque.",
                        "narration_guidance": "Explain reduced torque without saying the brakes are applied.",
                        "required_concepts": ["reduced driving torque"],
                    },
                    {
                        "id": "low-gear-effect",
                        "summary": "Low gears make engine braking feel stronger.",
                        "narration_guidance": "Connect the stronger sensation to gear ratio.",
                        "required_concepts": ["gear ratio", "stronger low-gear effect"],
                    },
                ],
                "deep_dive": [
                    {
                        "concept": "low gear engine braking",
                        "explanation": "A lower gear couples a larger engine-speed change to a given wheel-speed change.",
                        "caveats": ["Available traction still limits deceleration."],
                    }
                ],
                "related_terms": ["slipper clutch", "back torque"],
            },
            {
                "id": "braking-abs",
                "title": "Braking and ABS",
                "objective": "Explain braking force and ABS pressure modulation.",
                "headline": "ABS manages pressure near wheel lock.",
                "labels": ["brake pressure", "wheel slip", "ABS"],
                "visual_description": "A feedback loop connects wheel sensing to pressure modulation.",
                "assets": [],
                "beats": [
                    {
                        "id": "braking-force",
                        "summary": "Tyres turn braking force into road deceleration.",
                        "narration_guidance": "Keep tyre grip as the limiting factor.",
                        "required_concepts": ["tyre grip", "deceleration"],
                    },
                    {
                        "id": "abs-modulation",
                        "summary": "ABS modulates pressure when lock is imminent.",
                        "narration_guidance": "Do not imply that ABS creates additional grip.",
                        "required_concepts": ["wheel lock", "pressure modulation"],
                    },
                ],
                "deep_dive": [
                    {
                        "concept": "ABS and grip",
                        "explanation": "ABS helps preserve wheel rotation but cannot create tyre-road grip.",
                        "caveats": ["Surface and tyre conditions still matter."],
                    }
                ],
                "related_terms": ["cornering ABS", "wheel-speed sensor"],
            },
        ],
    }


@pytest.fixture
def copied_deck_payload(deck_payload: dict[str, object]):
    def copy_payload() -> dict[str, object]:
        return copy.deepcopy(deck_payload)

    return copy_payload
