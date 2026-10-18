"""HTTP endpoint for repair description generation.

Handles HTTP input/output only; generation logic lives in the application
service and LangChain pipeline.
"""

from functools import lru_cache

from fastapi import APIRouter, Depends

from repair_ai.api.security import require_api_key
from repair_ai.core.config import get_settings
from repair_ai.llm.chain import LangChainGenerator
from repair_ai.schemas.generation import RepairDescriptionResponse
from repair_ai.schemas.repair import RepairDescriptionRequest
from repair_ai.services.repair_description_service import RepairDescriptionService
from repair_ai.validation.output_validator import RepairOutputValidator

router = APIRouter(tags=["repair-descriptions"])


@lru_cache
def get_repair_description_service() -> RepairDescriptionService:
    """Build the service with its real dependencies.

    Cached so the LangChain pipeline is constructed once per process. Tests
    replace this with a fake via ``app.dependency_overrides``.
    """
    settings = get_settings()
    return RepairDescriptionService(
        generator=LangChainGenerator(settings),
        validator=RepairOutputValidator(),
        settings=settings,
    )


@router.post(
    "/repair-descriptions",
    response_model=RepairDescriptionResponse,
    dependencies=[Depends(require_api_key)],
)
def create_repair_description(
    request: RepairDescriptionRequest,
    service: RepairDescriptionService = Depends(get_repair_description_service),
) -> RepairDescriptionResponse:
    return service.generate_description(request)
