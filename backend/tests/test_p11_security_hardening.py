from fastapi.testclient import TestClient

from app.core.config import DeploymentMode, Settings
from app.core.security_hardening import (
    RequestRateLimiter,
    validate_production_security_settings,
)
from app.main import create_app


def test_security_headers_are_present_on_health_response() -> None:
    app = create_app(Settings(environment="test", security_headers_enabled=True))
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"].startswith("default-src 'self'")


def test_production_docs_and_secret_are_rejected() -> None:
    settings = Settings(
        environment="production",
        secret_key="change-me-in-development",
        api_docs_enabled=True,
        deployment_mode=DeploymentMode.CLOUD_GATEWAY,
        cloud_runtime_database_url="postgresql+psycopg://cloud:secret@private-db:5432/app",
    )
    try:
        validate_production_security_settings(settings)
    except ValueError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("unsafe production configuration was accepted")


def test_auth_rate_limiter_returns_retryable_limit() -> None:
    limiter = RequestRateLimiter()
    assert limiter.allow(bucket="login", identity="127.0.0.1", limit=1, window_seconds=60)
    assert not limiter.allow(bucket="login", identity="127.0.0.1", limit=1, window_seconds=60)


def test_production_wildcard_cors_is_rejected() -> None:
    settings = Settings(
        environment="production",
        secret_key="production-only-test-secret",
        api_docs_enabled=False,
        frontend_origin="*",
    )
    try:
        validate_production_security_settings(settings)
    except ValueError as exc:
        assert "Wildcard CORS" in str(exc)
    else:
        raise AssertionError("wildcard production CORS was accepted")
