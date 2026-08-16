"""Vercel entry point for the limited cloud gateway deployment."""

from app.core.config import DeploymentMode, settings

if settings.deployment_mode != DeploymentMode.CLOUD_GATEWAY:
    raise RuntimeError(
        "backend/server.py requires DEPLOYMENT_MODE=cloud_gateway. "
        "Use app.main:app for the Local Hub."
    )

from app.main import create_app  # noqa: E402

app = create_app(settings)

