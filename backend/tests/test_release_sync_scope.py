from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert
from sqlalchemy.orm import Session, sessionmaker

from app.cloud_db.schema import device_registrations, sync_commands, sync_receipts
from app.core.config import DeploymentMode, Settings
from app.db.session import get_db
from app.main import create_app

DEVICE_ID = "release-scope-device"
DEVICE_PROOF = "release-scope-proof"


def _cloud_url() -> str:
    value = os.environ.get("HC2_TEST_CLOUD_DATABASE_URL")
    if not value:
        pytest.skip("HC2_TEST_CLOUD_DATABASE_URL is required for release sync-scope tests.")
    return value


@pytest.fixture()
def scope_cloud_factory() -> sessionmaker[Session]:
    engine = create_engine(_cloud_url(), pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.execute(delete(sync_receipts))
        db.execute(delete(sync_commands))
        db.execute(delete(device_registrations))
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def scope_cloud_client(scope_cloud_factory: sessionmaker[Session]):
    local_url = os.environ.get(
        "LOCAL_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi",
    )
    cloud_url = _cloud_url()
    app = create_app(
        Settings(
            environment="test",
            deployment_mode=DeploymentMode.CLOUD_GATEWAY,
            database_url=local_url,
            local_database_url=local_url,
            cloud_runtime_database_url=cloud_url,
            cloud_migration_database_url=cloud_url,
            api_docs_enabled=False,
            _env_file=None,
        )
    )

    def override_db():
        with scope_cloud_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_device_and_commands(factory: sessionmaker[Session]):
    own_event = uuid4()
    foreign_event = uuid4()
    with factory() as db:
        db.execute(
            insert(device_registrations).values(
                device_id=DEVICE_ID,
                business_group_id="1",
                company_id=None,
                branch_id=None,
                display_name="Business Group Hub",
                credential_hash=hashlib.sha256(DEVICE_PROOF.encode("utf-8")).hexdigest(),
                status="active",
                allowed_purposes=["sync_pull", "sync_push"],
            )
        )
        for event_id, group_id in ((own_event, "1"), (foreign_event, "2")):
            db.execute(
                insert(sync_commands).values(
                    event_id=event_id,
                    business_group_id=group_id,
                    company_id=None,
                    branch_id=None,
                    target_device_id=None,
                    event_type="release.scope.test",
                    schema_version=1,
                    aggregate_type="release_scope",
                    aggregate_id=str(event_id),
                    aggregate_version=1,
                    correlation_id=uuid4(),
                    causation_id=None,
                    payload={"group": group_id},
                    status="pending",
                )
            )
        db.commit()
    return own_event, foreign_event


def _headers() -> dict[str, str]:
    return {"X-Device-Id": DEVICE_ID, "X-Device-Proof": DEVICE_PROOF}


def test_business_group_device_only_pulls_its_own_group(scope_cloud_client, scope_cloud_factory) -> None:
    own_event, foreign_event = _seed_device_and_commands(scope_cloud_factory)

    response = scope_cloud_client.get("/api/cloud/sync/commands", headers=_headers())
    assert response.status_code == 200, response.text
    event_ids = {row["event_id"] for row in response.json()["events"]}
    assert event_ids == {str(own_event)}
    assert str(foreign_event) not in event_ids


def test_business_group_device_cannot_ack_foreign_command(scope_cloud_client, scope_cloud_factory) -> None:
    _, foreign_event = _seed_device_and_commands(scope_cloud_factory)

    response = scope_cloud_client.post(
        "/api/cloud/sync/receipts",
        headers=_headers(),
        json={"event_id": str(foreign_event), "status": "committed", "result_reference": "forbidden"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"
