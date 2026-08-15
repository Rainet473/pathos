from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from voice_presentation.transport.bootstrap import (
    ProbeBootstrapService,
    ProbeSessionRequest,
    ProbeSessionResponse,
)

logger = logging.getLogger(__name__)


def create_app(bootstrap_service: ProbeBootstrapService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            await bootstrap_service.aclose()

    app = FastAPI(
        title="Interruptible Voice Presentation",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/probe/sessions",
        response_model=ProbeSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_probe_session(request: ProbeSessionRequest) -> ProbeSessionResponse:
        try:
            return await bootstrap_service.create_session(request)
        except Exception as error:
            logger.exception("Could not start LiveKit transport probe", exc_info=error)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="voice transport is unavailable",
            ) from error

    return app


def create_configured_app() -> FastAPI:
    from voice_presentation.adapters.livekit.probe import LiveKitProbeSessionLauncher
    from voice_presentation.adapters.livekit.tokens import LiveKitTokenIssuer
    from voice_presentation.transport.usage import JsonlUsageLedger

    server_url = _required_environment("LIVEKIT_URL")
    api_key = _required_environment("LIVEKIT_API_KEY")
    api_secret = _required_environment("LIVEKIT_API_SECRET")
    usage_log = os.getenv("LIVEKIT_USAGE_LOG", ".runtime/livekit-usage.jsonl").strip()
    if not usage_log:
        raise RuntimeError("LIVEKIT_USAGE_LOG must not be empty")
    issuer = LiveKitTokenIssuer(api_key=api_key, api_secret=api_secret)
    launcher = LiveKitProbeSessionLauncher(usage_ledger=JsonlUsageLedger(usage_log))
    return create_app(
        ProbeBootstrapService(
            server_url=server_url,
            token_issuer=issuer,
            session_launcher=launcher,
        )
    )


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
