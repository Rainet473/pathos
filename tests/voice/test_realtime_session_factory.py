from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from voice_presentation.adapters.livekit.agents import (
    GEMINI_LIVE_MODEL,
    LIVEKIT_INFERENCE_LLM_MODEL,
    LIVEKIT_INFERENCE_STT_MODEL,
    LIVEKIT_INFERENCE_TTS_MODEL,
    OPENAI_REALTIME_MODEL,
    GeminiAgentSessionFactory,
    LiveKitInferencePipelineFactory,
    OpenAIAgentSessionFactory,
)
from voice_presentation.voice.sessions import (
    VoiceBackendIdentity,
    VoiceBackendKind,
    VoiceProvider,
)


pytestmark = pytest.mark.offline

MODEL = GEMINI_LIVE_MODEL
INSTRUCTIONS = (
    "You are testing a realtime voice connection. Reply in one concise sentence."
)


@dataclass
class RecordingConstructor:
    result: object
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


def test_backend_identity_is_provider_neutral_and_contains_no_credentials():
    identity = VoiceBackendIdentity(
        provider=VoiceProvider.GEMINI_LIVE,
        kind=VoiceBackendKind.REALTIME,
        model=MODEL,
    )

    assert identity.model_dump(mode="json") == {
        "provider": "gemini_live",
        "kind": "realtime",
        "model": MODEL,
    }
    assert "key" not in identity.model_dump_json().lower()


def test_gemini_factory_builds_one_tool_free_agent_session_with_exact_model():
    realtime_model = object()
    agent_session = object()
    model_constructor = RecordingConstructor(realtime_model)
    session_constructor = RecordingConstructor(agent_session)
    endpointing_config = object()
    endpointing_constructor = RecordingConstructor(endpointing_config)
    factory = GeminiAgentSessionFactory(
        api_key="private-google-key",
        model=MODEL,
        voice="Puck",
        realtime_model_constructor=model_constructor,
        agent_session_constructor=session_constructor,
        realtime_input_config_constructor=endpointing_constructor,
    )

    built = factory.build_session(instructions=INSTRUCTIONS)

    assert built is agent_session
    assert factory.identity == VoiceBackendIdentity(
        provider=VoiceProvider.GEMINI_LIVE,
        kind=VoiceBackendKind.REALTIME,
        model=MODEL,
    )
    assert model_constructor.calls == [
        {
            "api_key": "private-google-key",
            "model": MODEL,
            "voice": "Puck",
            "instructions": INSTRUCTIONS,
            "realtime_input_config": endpointing_config,
        }
    ]
    assert endpointing_constructor.calls == [{"silence_duration_ms": 500}]
    assert session_constructor.calls == [
        {"llm": realtime_model, "aec_warmup_duration": None}
    ]
    assert "private-google-key" not in repr(factory)


@pytest.mark.parametrize("api_key", ["", "   "])
def test_gemini_factory_rejects_missing_key_before_constructing_provider(api_key):
    model_constructor = RecordingConstructor(object())
    session_constructor = RecordingConstructor(object())

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiAgentSessionFactory(
            api_key=api_key,
            realtime_model_constructor=model_constructor,
            agent_session_constructor=session_constructor,
        )

    assert model_constructor.calls == []
    assert session_constructor.calls == []


def test_openai_factory_uses_exact_mini_model_and_eager_interruptible_vad():
    realtime_model = object()
    agent_session = object()
    turn_detection = object()
    model_constructor = RecordingConstructor(realtime_model)
    session_constructor = RecordingConstructor(agent_session)
    turn_detection_constructor = RecordingConstructor(turn_detection)
    factory = OpenAIAgentSessionFactory(
        api_key="private-openai-key",
        realtime_model_constructor=model_constructor,
        agent_session_constructor=session_constructor,
        turn_detection_constructor=turn_detection_constructor,
    )

    built = factory.build_session(instructions=INSTRUCTIONS)

    assert built is agent_session
    assert factory.identity == VoiceBackendIdentity(
        provider=VoiceProvider.OPENAI_REALTIME,
        kind=VoiceBackendKind.REALTIME,
        model=OPENAI_REALTIME_MODEL,
    )
    assert turn_detection_constructor.calls == [
        {
            "type": "semantic_vad",
            "create_response": True,
            "eagerness": "high",
            "interrupt_response": True,
        }
    ]
    assert model_constructor.calls == [
        {
            "api_key": "private-openai-key",
            "model": OPENAI_REALTIME_MODEL,
            "voice": "marin",
            "turn_detection": turn_detection,
        }
    ]
    assert session_constructor.calls == [
        {"llm": realtime_model, "aec_warmup_duration": None}
    ]
    assert "private-openai-key" not in repr(factory)


@pytest.mark.parametrize("api_key", ["", "   "])
def test_openai_factory_rejects_missing_key_without_provider_call(api_key):
    model_constructor = RecordingConstructor(object())

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIAgentSessionFactory(
            api_key=api_key,
            realtime_model_constructor=model_constructor,
        )

    assert model_constructor.calls == []


def test_livekit_inference_factory_uses_documented_three_model_starter():
    stt = object()
    llm = object()
    tts = object()
    turn_handling = object()
    agent_session = object()
    stt_constructor = RecordingConstructor(stt)
    llm_constructor = RecordingConstructor(llm)
    tts_constructor = RecordingConstructor(tts)
    turn_handling_constructor = RecordingConstructor(turn_handling)
    session_constructor = RecordingConstructor(agent_session)
    factory = LiveKitInferencePipelineFactory(
        api_key="private-livekit-key",
        api_secret="private-livekit-secret",
        stt_constructor=stt_constructor,
        llm_constructor=llm_constructor,
        tts_constructor=tts_constructor,
        turn_handling_constructor=turn_handling_constructor,
        agent_session_constructor=session_constructor,
    )

    built = factory.build_session(instructions=INSTRUCTIONS)

    assert built is agent_session
    assert factory.identity == VoiceBackendIdentity(
        provider=VoiceProvider.LIVEKIT_INFERENCE_PIPELINE,
        kind=VoiceBackendKind.PIPELINE,
        model=(
            f"{LIVEKIT_INFERENCE_STT_MODEL} + {LIVEKIT_INFERENCE_LLM_MODEL} + "
            f"{LIVEKIT_INFERENCE_TTS_MODEL}"
        ),
    )
    assert stt_constructor.calls == [
        {
            "model": LIVEKIT_INFERENCE_STT_MODEL,
            "language": "multi",
            "api_key": "private-livekit-key",
            "api_secret": "private-livekit-secret",
        }
    ]
    assert llm_constructor.calls == [
        {
            "model": LIVEKIT_INFERENCE_LLM_MODEL,
            "api_key": "private-livekit-key",
            "api_secret": "private-livekit-secret",
        }
    ]
    assert tts_constructor.calls == [
        {
            "model": LIVEKIT_INFERENCE_TTS_MODEL,
            "voice": "Ashley",
            "api_key": "private-livekit-key",
            "api_secret": "private-livekit-secret",
        }
    ]
    assert turn_handling_constructor.calls == [
        {
            "turn_detection": "stt",
            "endpointing": {"min_delay": 1.2, "max_delay": 3.0},
        }
    ]
    assert session_constructor.calls == [
        {
            "stt": stt,
            "llm": llm,
            "tts": tts,
            "turn_handling": turn_handling,
            "aec_warmup_duration": None,
        }
    ]
    assert "private-livekit-key" not in repr(factory)
    assert "private-livekit-secret" not in repr(factory)


@pytest.mark.parametrize(
    ("api_key", "api_secret"),
    [("", "configured-secret"), ("configured-key", ""), (" ", " ")],
)
def test_livekit_inference_factory_requires_project_credentials(
    api_key, api_secret
):
    stt_constructor = RecordingConstructor(object())

    with pytest.raises(ValueError, match="LIVEKIT_API"):
        LiveKitInferencePipelineFactory(
            api_key=api_key,
            api_secret=api_secret,
            stt_constructor=stt_constructor,
        )

    assert stt_constructor.calls == []


def test_gemini_factory_rejects_blank_instructions_without_provider_call():
    model_constructor = RecordingConstructor(object())
    session_constructor = RecordingConstructor(object())
    factory = GeminiAgentSessionFactory(
        api_key="private-google-key",
        realtime_model_constructor=model_constructor,
        agent_session_constructor=session_constructor,
    )

    with pytest.raises(ValueError, match="instructions"):
        factory.build_session(instructions="  ")

    assert model_constructor.calls == []
    assert session_constructor.calls == []
