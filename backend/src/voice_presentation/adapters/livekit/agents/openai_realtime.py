from __future__ import annotations

from typing import Any

from voice_presentation.adapters.livekit.agents.base import (
    AgentSessionFactoryBase,
    KeywordConstructor,
    default_agent_session_constructor,
    require_text,
)
from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


OPENAI_REALTIME_MODEL = "gpt-realtime-2.1-mini"


def _default_realtime_model_constructor(**kwargs: Any) -> object:
    from livekit.plugins import openai

    return openai.realtime.RealtimeModel(**kwargs)


def _default_turn_detection_constructor(**kwargs: Any) -> object:
    from openai.types import realtime

    return realtime.realtime_audio_input_turn_detection.SemanticVad(**kwargs)


class OpenAIAgentSessionFactory(AgentSessionFactoryBase):
    """Construct a tool-free LiveKit AgentSession backed by OpenAI Realtime."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = OPENAI_REALTIME_MODEL,
        voice: str = "marin",
        realtime_model_constructor: KeywordConstructor = (
            _default_realtime_model_constructor
        ),
        agent_session_constructor: KeywordConstructor = (
            default_agent_session_constructor
        ),
        turn_detection_constructor: KeywordConstructor = (
            _default_turn_detection_constructor
        ),
    ) -> None:
        api_key = require_text(api_key, name="OPENAI_API_KEY")
        model = require_text(model, name="model")
        voice = require_text(voice, name="voice")
        super().__init__(
            identity=VoiceBackendIdentity(
                provider=VoiceProvider.OPENAI_REALTIME,
                kind=VoiceBackendKind.REALTIME,
                model=model,
            ),
            voice=voice,
        )
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._realtime_model_constructor = realtime_model_constructor
        self._agent_session_constructor = agent_session_constructor
        self._turn_detection_constructor = turn_detection_constructor

    def _build_session(self, *, instructions: str) -> object:
        turn_detection = self._turn_detection_constructor(
            type="semantic_vad",
            create_response=True,
            eagerness="high",
            interrupt_response=True,
        )
        realtime_model = self._realtime_model_constructor(
            api_key=self._api_key,
            model=self._model,
            voice=self._voice,
            turn_detection=turn_detection,
        )
        return self._agent_session_constructor(
            llm=realtime_model,
            aec_warmup_duration=None,
        )
