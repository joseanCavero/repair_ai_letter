"""API router grouping all endpoints under the /v1 prefix."""

from fastapi import APIRouter

from repair_ai.api.endpoints import repair_descriptions

api_router = APIRouter(prefix="/v1")
api_router.include_router(repair_descriptions.router)
