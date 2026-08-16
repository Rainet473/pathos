from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from voice_presentation.content.repository import DeckPackageRepository
from voice_presentation.transport.conversation import (
    ConversationBootstrapService,
    ConversationService,
    ConversationSessionRequest,
    ConversationSessionResponse,
    UnavailableConversationService,
)
from voice_presentation.voice.sessions import VoiceSessionFactory

logger = logging.getLogger(__name__)

APPLICATION_PRESENTATION_INSTRUCTIONS = (
    "You are the speaking surface for an application-controlled presentation. "
    "Follow the latest application-supplied narration or answer evidence exactly, "
    "stay concise, and never navigate or resume the presentation yourself."
)


def create_app(
    *,
    conversation_service: ConversationService | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if conversation_service is not None:
                await conversation_service.aclose()

    app = FastAPI(
        title="Interruptible Voice Presentation",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/decks/{deck_id}/slides/{slide_id}/render")
    async def get_deck_slide_render(deck_id: str, slide_id: str) -> FileResponse:
        try:
            path = DeckPackageRepository(_asset_root(), deck_id).render_path(slide_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="deck slide render not found",
            ) from None
        return FileResponse(path, media_type="image/png")

    if conversation_service is not None:

        @app.post(
            "/api/live/sessions",
            response_model=ConversationSessionResponse,
            status_code=status.HTTP_201_CREATED,
        )
        async def create_live_session(
            request: ConversationSessionRequest,
        ) -> ConversationSessionResponse:
            try:
                return await conversation_service.create_session(request)
            except Exception as error:
                logger.exception("Could not start live voice provider", exc_info=error)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="live voice provider is unavailable",
                ) from error

    return app


def _selected_voice_session_factory(
    *,
    selected_provider: str,
    google_api_key: str,
    openai_api_key: str,
    livekit_api_key: str,
    livekit_api_secret: str,
) -> VoiceSessionFactory:
    from voice_presentation.adapters.livekit.agents import (
        GeminiAgentSessionFactory,
        LiveKitInferencePipelineFactory,
        OpenAIAgentSessionFactory,
    )

    if selected_provider == "gemini_live":
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for gemini_live")
        return GeminiAgentSessionFactory(api_key=google_api_key)
    if selected_provider == "openai_realtime":
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for openai_realtime")
        return OpenAIAgentSessionFactory(api_key=openai_api_key)
    if selected_provider == "livekit_inference_pipeline":
        return LiveKitInferencePipelineFactory(
            api_key=livekit_api_key,
            api_secret=livekit_api_secret,
        )
    raise ValueError(f"selected VOICE_PROVIDER {selected_provider!r} is not implemented")


def create_configured_app() -> FastAPI:
    from voice_presentation.adapters.livekit.conversation import (
        LiveKitConversationSessionLauncher,
    )
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer
    from voice_presentation.transport.diagnostics import (
        JsonlConversationDiagnosticLedger,
    )
    from voice_presentation.transport.context_trace import (
        JsonlInferenceContextLedger,
    )
    from voice_presentation.transport.usage import JsonlUsageLedger

    server_url = _required_environment("LIVEKIT_URL")
    api_key = _required_environment("LIVEKIT_API_KEY")
    api_secret = _required_environment("LIVEKIT_API_SECRET")
    usage_log = os.getenv("LIVEKIT_USAGE_LOG", ".runtime/livekit-usage.jsonl").strip()
    if not usage_log:
        raise RuntimeError("LIVEKIT_USAGE_LOG must not be empty")
    diagnostics_log = os.getenv(
        "LIVE_DIAGNOSTICS_LOG", ".runtime/conversation-diagnostics.jsonl"
    ).strip()
    if not diagnostics_log:
        raise RuntimeError("LIVE_DIAGNOSTICS_LOG must not be empty")
    context_log = os.getenv(
        "LLM_CONTEXT_LOG", ".runtime/llm-context.jsonl"
    ).strip()
    if not context_log:
        raise RuntimeError("LLM_CONTEXT_LOG must not be empty")
    issuer = LiveKitTokenIssuer(api_key=api_key, api_secret=api_secret)
    usage_ledger = JsonlUsageLedger(usage_log)
    selected_provider = _selected_voice_provider_name()
    google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    try:
        voice_session_factory = _selected_voice_session_factory(
            selected_provider=selected_provider,
            google_api_key=google_api_key,
            openai_api_key=openai_api_key,
            livekit_api_key=api_key,
            livekit_api_secret=api_secret,
        )
    except ValueError as error:
        conversation_service: ConversationService = UnavailableConversationService(
            str(error)
        )
    else:
        conversation_service = ConversationBootstrapService(
            server_url=server_url,
            token_issuer=issuer,
            session_launcher=LiveKitConversationSessionLauncher(
                voice_session_factory=voice_session_factory,
                usage_ledger=usage_ledger,
                diagnostic_ledger=JsonlConversationDiagnosticLedger(
                    diagnostics_log
                ),
                context_ledger=JsonlInferenceContextLedger(context_log),
                presentation_session_factory=_live_presentation_session,
            ),
            instructions=APPLICATION_PRESENTATION_INSTRUCTIONS,
        )
    return create_app(conversation_service=conversation_service)


def _live_presentation_session(session_id: str):
    from voice_presentation.application.live_presentation import (
        ApplicationPresentationSession,
    )

    return ApplicationPresentationSession(_full_deck(), session_id=session_id)


def _full_deck():
    return DeckPackageRepository(
        _asset_root(), "motorcycle-controls"
    ).load()


def _asset_root() -> Path:
    return Path(__file__).resolve().parents[4] / "assets"


def _selected_voice_provider_name() -> str:
    return os.getenv("VOICE_PROVIDER", "livekit_inference_pipeline").strip()


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
