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


LIVEKIT_INFERENCE_STT_MODEL = "deepgram/nova-3"
LIVEKIT_INFERENCE_LLM_MODEL = "google/gemma-4-31b-it"
LIVEKIT_INFERENCE_TTS_MODEL = "inworld/inworld-tts-2"


def _default_stt_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.STT(**kwargs)


def _default_llm_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.LLM(**kwargs)


def _default_tts_constructor(**kwargs: Any) -> object:
    from livekit.agents import inference

    return inference.TTS(**kwargs)


def _default_turn_handling_constructor(**kwargs: Any) -> object:
    from livekit.agents import TurnHandlingOptions

    return TurnHandlingOptions(**kwargs)


class LiveKitInferencePipelineFactory(AgentSessionFactoryBase):
    """Construct the verified Deepgram, Gemma and Inworld voice pipeline."""

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
        stt_constructor: KeywordConstructor = _default_stt_constructor,
        llm_constructor: KeywordConstructor = _default_llm_constructor,
        tts_constructor: KeywordConstructor = _default_tts_constructor,
        turn_handling_constructor: KeywordConstructor = (
            _default_turn_handling_constructor
        ),
        agent_session_constructor: KeywordConstructor = (
            default_agent_session_constructor
        ),
    ) -> None:
        api_key = require_text(api_key, name="LIVEKIT_API_KEY")
        api_secret = require_text(api_secret, name="LIVEKIT_API_SECRET")
        stt_model = require_text(stt_model, name="stt_model")
        llm_model = require_text(llm_model, name="llm_model")
        tts_model = require_text(tts_model, name="tts_model")
        stt_language = require_text(stt_language, name="stt_language")
        tts_voice = require_text(tts_voice, name="tts_voice")

        super().__init__(
            identity=VoiceBackendIdentity(
                provider=VoiceProvider.LIVEKIT_INFERENCE_PIPELINE,
                kind=VoiceBackendKind.PIPELINE,
                model=f"{stt_model} + {llm_model} + {tts_model}",
            ),
            voice=tts_voice,
        )
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

    def _build_session(self, *, instructions: str) -> object:
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
