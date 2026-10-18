"""Health endpoints for load balancer / platform health checks.

They never call the LLM and never expose secrets, configuration values,
stack traces, or customer data. They are intentionally unauthenticated so
Render can use them as health-check paths.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    """Liveness: the process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict[str, str]:
    """Readiness: the app has initialized and can accept requests."""
    return {"status": "ready"}
