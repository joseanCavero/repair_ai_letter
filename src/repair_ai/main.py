"""FastAPI application entry point."""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from repair_ai.api.endpoints import health
from repair_ai.api.router import api_router
from repair_ai.core.config import get_settings
from repair_ai.core.exceptions import (
    GenerationProviderError,
    OutputValidationError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_environment(dotenv_path: str | None = None) -> None:
    """Load variables from ``.env`` into the process environment.

    pydantic-settings uses ``.env`` only to populate the ``Settings`` model;
    it does not export anything. The OpenAI client, however, reads
    ``OPENAI_API_KEY`` from the process environment — so ``.env`` must be
    loaded explicitly at startup. Existing environment variables take
    precedence over ``.env`` values.
    """
    load_dotenv(dotenv_path)


load_environment()

#: Static PoC UI served from the repository root (``ui/`` next to ``src/``).
UI_DIR = Path(__file__).resolve().parents[2] / "ui"


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose declared body exceeds a configured limit.

    This is a lightweight first line of defense; the Pydantic contracts
    remain the authoritative validation of body content.
    """

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Repair AI Service", version="0.1.0")
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=get_settings().max_request_body_bytes,
    )
    app.include_router(health.router)
    app.include_router(api_router)
    # Mounted last so /v1, /health and /docs keep precedence. The UI contains
    # no secrets; the generation endpoint remains API-key protected.
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.exception_handler(GenerationProviderError)
    async def handle_provider_error(
        request: Request, exc: GenerationProviderError
    ) -> JSONResponse:
        logger.error("Generation provider failure: %s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Text generation is temporarily unavailable. "
                "Please retry later or use the manual fallback process."
            },
        )

    @app.exception_handler(OutputValidationError)
    async def handle_validation_error(
        request: Request, exc: OutputValidationError
    ) -> JSONResponse:
        # Violations are logged but not exposed; the rejected draft is
        # never returned to the caller.
        logger.error("Output validation rejected a draft: %s", exc.violations)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "The generated draft failed validation and was "
                "discarded. Please retry or use the manual fallback process."
            },
        )

    return app


app = create_app()
