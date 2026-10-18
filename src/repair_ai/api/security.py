"""API-key authentication for the generation endpoint.

Lightweight single-user PoC measure, not a substitute for enterprise
identity and authorization. The expected key is provided via the
``REPAIR_AI_API_KEY`` environment variable.

Behavior (fail closed):
- key not configured -> 503 (the service is never silently unprotected)
- missing ``X-API-Key`` header -> 401
- incorrect key -> 403

The comparison uses ``secrets.compare_digest`` and the key is never logged.
"""

import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from repair_ai.core.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    x_api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.api_key is None:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured on this service.",
        )
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key.")
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key.")
