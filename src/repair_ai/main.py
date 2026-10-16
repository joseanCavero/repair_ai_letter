"""FastAPI application entry point."""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from repair_ai.api.router import api_router
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


def create_app() -> FastAPI:
    app = FastAPI(title="Repair AI Service", version="0.1.0")
    app.include_router(api_router)

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
