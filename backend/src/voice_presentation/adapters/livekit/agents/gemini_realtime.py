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


GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


def _default_realtime_model_constructor(**kwargs: Any) -> object:
    from livekit.plugins import google

    return google.realtime.RealtimeModel(**kwargs)


def _default_realtime_input_config_constructor(**kwargs: Any) -> object:
    from google.genai import types

    return types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            silence_duration_ms=kwargs["silence_duration_ms"],
        )
    )


class GeminiAgentSessionFactory(AgentSessionFactoryBase):
    """Construct a tool-free LiveKit AgentSession backed by Gemini Live."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = GEMINI_LIVE_MODEL,
        voice: str = "Puck",
        end_of_speech_silence_ms: int = 500,
        realtime_model_constructor: KeywordConstructor = (
            _default_realtime_model_constructor
        ),
        agent_session_constructor: KeywordConstructor = (
            default_agent_session_constructor
        ),
        realtime_input_config_constructor: KeywordConstructor = (
            _default_realtime_input_config_constructor
        ),
    ) -> None:
        api_key = require_text(api_key, name="GOOGLE_API_KEY")
        model = require_text(model, name="model")
        voice = require_text(voice, name="voice")
        if not 100 <= end_of_speech_silence_ms <= 2_000:
            raise ValueError("end-of-speech silence must be between 100 and 2000 ms")

        super().__init__(
            identity=VoiceBackendIdentity(
                provider=VoiceProvider.GEMINI_LIVE,
                kind=VoiceBackendKind.REALTIME,
                model=model,
            ),
            voice=voice,
        )
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._end_of_speech_silence_ms = end_of_speech_silence_ms
        self._realtime_model_constructor = realtime_model_constructor
        self._agent_session_constructor = agent_session_constructor
        self._realtime_input_config_constructor = realtime_input_config_constructor

    def _build_session(self, *, instructions: str) -> object:
        realtime_input_config = self._realtime_input_config_constructor(
            silence_duration_ms=self._end_of_speech_silence_ms
        )
        realtime_model = self._realtime_model_constructor(
            api_key=self._api_key,
            model=self._model,
            voice=self._voice,
            instructions=instructions,
            realtime_input_config=realtime_input_config,
        )
        return self._agent_session_constructor(
            llm=realtime_model,
            aec_warmup_duration=None,
        )
