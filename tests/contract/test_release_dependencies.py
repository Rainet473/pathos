from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


pytestmark = pytest.mark.offline


def test_optional_realtime_plugins_are_not_default_runtime_dependencies():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    default_dependencies = project["dependencies"]
    optional_dependencies = project["optional-dependencies"]

    assert not any("plugins-google" in item for item in default_dependencies)
    assert not any("plugins-openai" in item for item in default_dependencies)
    assert optional_dependencies["gemini-realtime"] == [
        "livekit-plugins-google==1.5.17"
    ]
    assert optional_dependencies["openai-realtime"] == [
        "livekit-plugins-openai==1.5.17"
    ]


def test_provider_factories_have_importable_dedicated_modules():
    from voice_presentation.adapters.livekit.agents.base import (
        AgentSessionFactoryBase,
    )
    from voice_presentation.adapters.livekit.agents.gemini_realtime import (
        GeminiAgentSessionFactory,
    )
    from voice_presentation.adapters.livekit.agents.inference_pipeline import (
        LiveKitInferencePipelineFactory,
    )
    from voice_presentation.adapters.livekit.agents.openai_realtime import (
        OpenAIAgentSessionFactory,
    )

    assert issubclass(GeminiAgentSessionFactory, AgentSessionFactoryBase)
    assert issubclass(OpenAIAgentSessionFactory, AgentSessionFactoryBase)
    assert issubclass(LiveKitInferencePipelineFactory, AgentSessionFactoryBase)
