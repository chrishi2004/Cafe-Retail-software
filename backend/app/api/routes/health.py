from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi import Request

from app.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(request: Request) -> dict[str, str | bool]:
    settings: Settings = request.app.state.settings
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.environment,
        "deployment_mode": settings.deployment_mode.value,
        "database_configured": bool(settings.runtime_database_url),
        "timestamp": datetime.now(UTC).isoformat(),
    }
