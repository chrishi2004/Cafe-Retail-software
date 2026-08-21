from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DeploymentMode, Settings
from app.api.routes.cloud_gateway import cloud_readiness_snapshot
from app.main import create_app


LOCAL_URL = "postgresql+psycopg://local_user@localhost:5432/local_hub"
CLOUD_RUNTIME_URL = "postgresql+psycopg://cloud_user@region.pooler.supabase.invalid:6543/cloud_db"
CLOUD_MIGRATION_URL = "postgresql+psycopg://cloud_user@db.project.supabase.invalid:5432/cloud_db"


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "deployment_mode": DeploymentMode.LOCAL_HUB,
        "database_url": LOCAL_URL,
        "local_database_url": LOCAL_URL,
        # Keep these explicit so tests that exercise missing cloud configuration
        # stay hermetic even when CI exports real cloud test database URLs.
        "cloud_runtime_database_url": None,
        "cloud_migration_database_url": None,
        "api_docs_enabled": False,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def route_paths(app) -> set[str]:
    # Newer Starlette/FastAPI versions may keep internal included-router
    # entries in app.routes; only concrete routes expose a path.
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_local_hub_registers_existing_operational_routes() -> None:
    app = create_app(build_settings())
    paths = route_paths(app)

    assert "/api/health" in paths
    assert "/api/auth/login" in paths
    assert "/api/inventory/adjustments" in paths
    assert "/api/invoices/{invoice_id}/issue" in paths
    assert "/api/purchase-orders/{purchase_order_id}/receive" in paths


def test_cloud_gateway_registers_only_approved_cloud_safe_routes() -> None:
    app = create_app(
        build_settings(
            deployment_mode=DeploymentMode.CLOUD_GATEWAY,
            cloud_runtime_database_url=CLOUD_RUNTIME_URL,
            cloud_migration_database_url=CLOUD_MIGRATION_URL,
        )
    )
    paths = route_paths(app)

    assert paths == {
        "/api/health",
        "/api/cloud/readiness",
        "/api/cloud/devices/heartbeat",
        "/api/cloud/publications/menu",
        "/api/cloud/public/cafe/menu/{publication_id}",
        "/api/cloud/public/cafe/qr/resolve",
        "/api/cloud/public/cafe/orders",
        "/api/cloud/public/cafe/orders/{public_id}",
        "/api/cloud/public/cafe/orders/{public_id}/bill-request",
        "/api/cloud/sync/commands",
        "/api/cloud/sync/events",
        "/api/cloud/sync/receipts",
        "/api/cloud/continuity/lease/acquire",
        "/api/cloud/continuity/lease/renew",
        "/api/cloud/continuity/references",
    }
    assert "/api/auth/login" not in paths
    assert "/api/inventory/adjustments" not in paths
    assert "/api/invoices/{invoice_id}/issue" not in paths
    assert "/api/purchase-orders/{purchase_order_id}/receive" not in paths
    assert "/api/public/cafe/sessions/{public_id}/orders" not in paths
    assert not any(path.startswith("/api/auth") for path in paths)


def test_cloud_gateway_requires_explicit_runtime_database() -> None:
    with pytest.raises(ValidationError, match="CLOUD_RUNTIME_DATABASE_URL is required"):
        build_settings(deployment_mode=DeploymentMode.CLOUD_GATEWAY)


def test_cloud_database_cannot_identify_local_target() -> None:
    same_target = "postgresql+psycopg://another_user@localhost:5432/local_hub"
    with pytest.raises(ValidationError, match="must not target the Local Hub database"):
        build_settings(cloud_migration_database_url=same_target)


def test_local_runtime_preserves_legacy_url_and_allows_explicit_override() -> None:
    # Explicit None isolates the legacy fallback from any LOCAL_DATABASE_URL
    # injected by the surrounding CI workflow.
    legacy = Settings(database_url=LOCAL_URL, local_database_url=None, _env_file=None)
    explicit_url = "postgresql+psycopg://local_user@localhost:5432/explicit_local"
    explicit = Settings(
        database_url=LOCAL_URL,
        local_database_url=explicit_url,
        _env_file=None,
    )

    assert legacy.local_runtime_database_url == LOCAL_URL
    assert legacy.runtime_database_url == LOCAL_URL
    assert explicit.local_runtime_database_url == explicit_url
    assert explicit.local_migration_database_url == explicit_url


def test_cloud_migration_url_is_explicit_and_separate() -> None:
    settings = build_settings(cloud_migration_database_url=CLOUD_MIGRATION_URL)
    assert settings.required_cloud_migration_database_url == CLOUD_MIGRATION_URL

    without_cloud_migration = build_settings()
    with pytest.raises(RuntimeError, match="CLOUD_MIGRATION_DATABASE_URL is required"):
        _ = without_cloud_migration.required_cloud_migration_database_url


def test_cloud_readiness_reports_required_and_recommended_configuration() -> None:
    settings = build_settings(
        deployment_mode=DeploymentMode.CLOUD_GATEWAY,
        cloud_runtime_database_url=CLOUD_RUNTIME_URL,
        cloud_migration_database_url=CLOUD_MIGRATION_URL,
        cloud_gateway_base_url="https://cloud-gateway.example.com/api",
        sync_device_id="hub-demo",
        sync_device_secret="device-secret",
    )

    snapshot = cloud_readiness_snapshot(settings, database_ready=True)

    assert snapshot["status"] == "ready"
    assert snapshot["checks"] == {
        "required": {
            "runtime_database_configured": True,
            "migration_database_configured": True,
        },
        "recommended": {
            "gateway_url_configured": True,
            "sync_device_id_configured": True,
            "sync_device_secret_configured": True,
        },
    }


def test_cloud_readiness_identifies_missing_migration_configuration() -> None:
    settings = build_settings(
        deployment_mode=DeploymentMode.CLOUD_GATEWAY,
        cloud_runtime_database_url=CLOUD_RUNTIME_URL,
    )

    snapshot = cloud_readiness_snapshot(settings, database_ready=True)

    assert snapshot["status"] == "configuration_required"
    assert snapshot["checks"]["required"]["runtime_database_configured"] is True
    assert snapshot["checks"]["required"]["migration_database_configured"] is False


def test_cloud_readiness_never_returns_secret_values() -> None:
    secret = "device-secret-that-must-not-leak"
    settings = build_settings(
        deployment_mode=DeploymentMode.CLOUD_GATEWAY,
        cloud_runtime_database_url=CLOUD_RUNTIME_URL,
        cloud_migration_database_url=CLOUD_MIGRATION_URL,
        sync_device_secret=secret,
    )

    serialized = str(cloud_readiness_snapshot(settings, database_ready=True))

    assert secret not in serialized
    assert "supabase.invalid" not in serialized


def test_production_disables_api_docs_by_default() -> None:
    app = create_app(build_settings(environment="production", api_docs_enabled=None, secret_key="test-production-secret"))
    paths = route_paths(app)

    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths


def test_cloud_alembic_history_is_independent() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    local_env = (backend_root / "alembic" / "env.py").read_text(encoding="utf-8")
    cloud_env = (backend_root / "alembic_cloud" / "env.py").read_text(encoding="utf-8")

    assert "local_migration_database_url" in local_env
    assert "alembic_version_cloud" not in local_env
    assert "required_cloud_migration_database_url" in cloud_env
    assert 'version_table="alembic_version_cloud"' in cloud_env
    assert (backend_root / "alembic_cloud.ini").exists()
