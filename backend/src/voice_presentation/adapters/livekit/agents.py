from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
OPENAI_REALTIME_MODEL = "gpt-realtime-2.1-mini"
LIVEKIT_INFERENCE_STT_MODEL = "deepgram/nova-3"
LIVEKIT_INFERENCE_LLM_MODEL = "google/gemma-4-31b-it"
LIVEKIT_INFERENCE_TTS_MODEL = "inworld/inworld-tts-2"

KeywordConstructor = Callable[..., object]


def _default_realtime_model_constructor(**kwargs: Any) -> object:
    from livekit.plugins import google

    return google.realtime.RealtimeModel(**kwargs)


def _default_agent_session_constructor(**kwargs: Any) -> object:
    from livekit.agents import AgentSession

    return AgentSession(**kwargs)


def _default_realtime_input_config_constructor(**kwargs: Any) -> object:
    from google.genai import types

    return types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            silence_duration_ms=kwargs["silence_duration_ms"],
        )
    )


def _default_openai_realtime_model_constructor(**kwargs: Any) -> object:
    from livekit.plugins import openai

    return openai.realtime.RealtimeModel(**kwargs)


def _default_openai_turn_detection_constructor(**kwargs: Any) -> object:
    from openai.types import realtime

    return realtime.realtime_audio_input_turn_detection.SemanticVad(**kwargs)


def _default_inference_stt_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.STT(**kwargs)


def _default_inference_llm_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.LLM(**kwargs)


def _default_inference_tts_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.TTS(**kwargs)


def _default_turn_handling_constructor(**kwargs: Any) -> object:
    from livekit.agents import TurnHandlingOptions

    return TurnHandlingOptions(**kwargs)


class GeminiAgentSessionFactory:
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
            _default_agent_session_constructor
        ),
        realtime_input_config_constructor: KeywordConstructor = (
            _default_realtime_input_config_constructor
        ),
    ) -> None:
        if not api_key.strip():
            raise ValueError("GOOGLE_API_KEY must be configured")
        if not model.strip():
            raise ValueError("model must not be blank")
        if not voice.strip():
            raise ValueError("voice must not be blank")
        if not 100 <= end_of_speech_silence_ms <= 2_000:
            raise ValueError("end-of-speech silence must be between 100 and 2000 ms")

        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._end_of_speech_silence_ms = end_of_speech_silence_ms
        self._realtime_model_constructor = realtime_model_constructor
        self._agent_session_constructor = agent_session_constructor
        self._realtime_input_config_constructor = (
            realtime_input_config_constructor
        )
        self._identity = VoiceBackendIdentity(
            provider=VoiceProvider.GEMINI_LIVE,
            kind=VoiceBackendKind.REALTIME,
            model=model,
        )

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._identity

    def build_session(self, *, instructions: str) -> object:
        if not instructions.strip():
            raise ValueError("instructions must not be blank")

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

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={self.identity.provider.value!r}, "
            f"model={self.identity.model!r}, voice={self._voice!r})"
        )


class OpenAIAgentSessionFactory:
    """Construct a tool-free LiveKit AgentSession backed by OpenAI Realtime."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = OPENAI_REALTIME_MODEL,
        voice: str = "marin",
        realtime_model_constructor: KeywordConstructor = (
            _default_openai_realtime_model_constructor
        ),
        agent_session_constructor: KeywordConstructor = (
            _default_agent_session_constructor
        ),
        turn_detection_constructor: KeywordConstructor = (
            _default_openai_turn_detection_constructor
        ),
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY must be configured")
        if not model.strip():
            raise ValueError("model must not be blank")
        if not voice.strip():
            raise ValueError("voice must not be blank")

        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._realtime_model_constructor = realtime_model_constructor
        self._agent_session_constructor = agent_session_constructor
        self._turn_detection_constructor = turn_detection_constructor
        self._identity = VoiceBackendIdentity(
            provider=VoiceProvider.OPENAI_REALTIME,
            kind=VoiceBackendKind.REALTIME,
            model=model,
        )

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._identity

    def build_session(self, *, instructions: str) -> object:
        if not instructions.strip():
            raise ValueError("instructions must not be blank")

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

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={self.identity.provider.value!r}, "
            f"model={self.identity.model!r}, voice={self._voice!r})"
        )


class LiveKitInferencePipelineFactory:
    """Construct LiveKit's documented starter STT-LLM-TTS pipeline."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        stt_model: str = LIVEKIT_INFERENCE_STT_MODEL,
        llm_model: str = LIVEKIT_INFERENCE_LLM_MODEL,
        tts_model: str = LIVEKIT_INFERENCE_TTS_MODEL,
        stt_language: str = "multi",
        tts_voice: str = "Ashley",
        stt_constructor: KeywordConstructor = _default_inference_stt_constructor,
        llm_constructor: KeywordConstructor = _default_inference_llm_constructor,
        tts_constructor: KeywordConstructor = _default_inference_tts_constructor,
        turn_handling_constructor: KeywordConstructor = (
            _default_turn_handling_constructor
        ),
        agent_session_constructor: KeywordConstructor = (
            _default_agent_session_constructor
        ),
    ) -> None:
        if not api_key.strip():
            raise ValueError("LIVEKIT_API_KEY must be configured")
        if not api_secret.strip():
            raise ValueError("LIVEKIT_API_SECRET must be configured")
        values = {
            "stt_model": stt_model,
            "llm_model": llm_model,
            "tts_model": tts_model,
            "stt_language": stt_language,
            "tts_voice": tts_voice,
        }
        for name, value in values.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        self._api_key = api_key
        self._api_secret = api_secret
        self._stt_model = stt_model
        self._llm_model = llm_model
        self._tts_model = tts_model
        self._stt_language = stt_language
        self._tts_voice = tts_voice
        self._stt_constructor = stt_constructor
        self._llm_constructor = llm_constructor
        self._tts_constructor = tts_constructor
        self._turn_handling_constructor = turn_handling_constructor
        self._agent_session_constructor = agent_session_constructor
        self._identity = VoiceBackendIdentity(
            provider=VoiceProvider.LIVEKIT_INFERENCE_PIPELINE,
            kind=VoiceBackendKind.PIPELINE,
            model=f"{stt_model} + {llm_model} + {tts_model}",
        )

    @property
    def identity(self) -> VoiceBackendIdentity:
        return self._identity

    def build_session(self, *, instructions: str) -> object:
        if not instructions.strip():
            raise ValueError("instructions must not be blank")

        stt = self._stt_constructor(
            model=self._stt_model,
            language=self._stt_language,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        llm = self._llm_constructor(
            model=self._llm_model,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        tts = self._tts_constructor(
            model=self._tts_model,
            voice=self._tts_voice,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        turn_handling = self._turn_handling_constructor(
            turn_detection="stt",
            endpointing={"min_delay": 1.2, "max_delay": 3.0},
            preemptive_generation={"enabled": False},
        )
        return self._agent_session_constructor(
            stt=stt,
            llm=llm,
            tts=tts,
            turn_handling=turn_handling,
            aec_warmup_duration=None,
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={self.identity.provider.value!r}, "
            f"model={self.identity.model!r}, voice={self._tts_voice!r})"
        )
