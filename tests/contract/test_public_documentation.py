from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

import pytest


pytestmark = pytest.mark.offline

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ARCHITECTURE_HERO = ROOT / "docs" / "assets" / "pathos-architecture.svg"
PUBLIC_GUIDES = {
    "concepts": ROOT / "docs" / "concepts.md",
    "advantages": ROOT / "docs" / "advantages.md",
    "limitations": ROOT / "docs" / "limitations.md",
}


def test_readme_leads_with_architecture_and_has_a_linear_onboarding_path():
    readme = README.read_text(encoding="utf-8")

    assert "docs/assets/pathos-architecture.svg" in readme
    assert "assets/motorcycle-controls/renders/control-loop.png" not in readme
    assert "<!-- DEMO_VIDEO_PLACEHOLDER -->" in readme
    for heading in (
        "## What Pathos does",
        "## Architecture",
        "## Why Pathos",
        "## Demo",
        "## Quick start",
        "## Documentation",
        "## Development and verification",
    ):
        assert heading in readme

    assert readme.index("## Architecture") < readme.index("## Quick start")
    assert readme.index("## Demo") < readme.index("## Quick start")


def test_public_guides_separate_concepts_advantages_and_limitations():
    required_headings = {
        "concepts": (
            "# How Pathos works",
            "## Core concepts",
            "### 1. The application is the presenter",
            "### 2. The deck has two positions",
            "### 3. A spoken turn is not a committed beat",
            "### 4. Questions take one of four paths",
            "### 5. Evidence must be valid before the model speaks",
        ),
        "advantages": ("# Advantages",),
        "limitations": (
            "# Limitations",
            "## Reasoning adds follow-up latency",
            "## Retrieval is lexical, local, and bounded",
            "## The agent does not see slide pixels",
            "## Provider caching is not guaranteed",
        ),
    }

    for name, path in PUBLIC_GUIDES.items():
        text = path.read_text(encoding="utf-8")
        for heading in required_headings[name]:
            assert heading in text

    concepts = PUBLIC_GUIDES["concepts"].read_text(encoding="utf-8")
    assert "sequenceDiagram" not in concepts
    assert concepts.count("```mermaid\nflowchart") >= 2

    advantages = PUBLIC_GUIDES["advantages"].read_text(encoding="utf-8")
    assert len(advantages.splitlines()) <= 40
    assert advantages.count("\n1. **") == 1
    assert sum(1 for line in advantages.splitlines() if re.match(r"\d+\. \*\*", line)) >= 6


def test_architecture_hero_is_a_self_contained_accessible_svg():
    root = ElementTree.parse(ARCHITECTURE_HERO).getroot()
    document = ARCHITECTURE_HERO.read_text(encoding="utf-8")

    assert root.tag.endswith("svg")
    assert root.attrib.get("role") == "img"
    assert "Pathos" in document
    assert "Application control plane" in document
    assert "Voice model port" in document
    for role_icon in ("🎧", "🌐", "🧠", "🤖", "🎙️", "📚"):
        assert role_icon in document
    assert not re.search(r"(?:href|src)=[\"']https?://", document)


def test_readme_relative_links_resolve_inside_the_repository():
    readme = README.read_text(encoding="utf-8")
    targets = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", readme)

    for raw_target in targets:
        target = raw_target.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        assert (ROOT / target).exists(), f"README link does not exist: {raw_target}"
