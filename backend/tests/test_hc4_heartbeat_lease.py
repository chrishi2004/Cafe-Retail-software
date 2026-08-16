from __future__ import annotations

import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.cloud_db.hc4_schema import continuity_request_nonces
from app.cloud_db.schema import (
    continuity_transactions,
    device_heartbeats,
    device_registrations,
    sync_commands,
    writer_leases,
)
from app.core.config import DeploymentMode, Settings
from app.db.session import get_db
from app.main import create_app
from app.schemas.hc4 import ContinuityReferenceInput, SignedHeartbeatInput, WriterLeaseInput
from app.services.cloud_transport import _signed_device_headers

DEVICE_ID = "hc4-test-device"
DEVICE_PROOF = "hc4-installation-proof"


def _cloud_url() -> str:
    value = os.environ.get("HC4_TEST_CLOUD_DATABASE_URL")
    if not value:
        pytest.skip("HC4_TEST_CLOUD_DATABASE_URL is required for HC4 cloud tests.")
    return value


@pytest.fixture()
def hc4_cloud_factory() -> sessionmaker[Session]:
    engine = create_engine(_cloud_url(), pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_hc4_cloud(hc4_cloud_factory: sessionmaker[Session]) -> None:
    with hc4_cloud_factory() as db:
        for table in (
            continuity_request_nonces,
            sync_commands,
            continuity_transactions,
            device_heartbeats,
            writer_leases,
            device_registrations,
        ):
            db.execute(delete(table))
        db.commit()


@pytest.fixture()
def hc4_cloud_client(hc4_cloud_factory: sessionmaker[Session]):
    local_url = os.environ.get(
        "LOCAL_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi",
    )
    app = create_app(
        Settings(
            environment="test",
            deployment_mode=DeploymentMode.CLOUD_GATEWAY,
            database_url=local_url,
            local_database_url=local_url,
            cloud_runtime_database_url=_cloud_url(),
            cloud_migration_database_url=_cloud_url(),
            api_docs_enabled=False,
            writer_lease_seconds=30,
            _env_file=None,
        )
    )

    def override_db():
        with hc4_cloud_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_device(factory: sessionmaker[Session], *, device_id: str = DEVICE_ID) -> None:
    proof = DEVICE_PROOF if device_id == DEVICE_ID else f"proof-{device_id}"
    with factory() as db:
        db.execute(
            insert(device_registrations).values(
                device_id=device_id,
                business_group_id="1",
                company_id="2",
                branch_id="3",
                display_name="HC4 Test Hub",
                credential_hash=hashlib.sha256(proof.encode("utf-8")).hexdigest(),
                status="active",
                allowed_purposes=["heartbeat", "sync_pull", "sync_push"],
            )
        )
        db.commit()


def _post_signed(client: TestClient, path: str, payload, *, timestamp: str | None = None, nonce: str | None = None):
    headers = _signed_device_headers(
        DEVICE_ID,
        DEVICE_PROOF,
        payload,
        timestamp=timestamp,
        nonce=nonce,
    )
    body = payload.model_dump(mode="json")
    return client.post(path, headers=headers, json=body), headers


def test_signed_heartbeat_accepts_once_and_rejects_nonce_replay(hc4_cloud_client, hc4_cloud_factory) -> None:
    _seed_device(hc4_cloud_factory)
    payload = SignedHeartbeatInput(mode="local_writer", fencing_epoch=0, pending_outbox=4)
    first, headers = _post_signed(
        hc4_cloud_client,
        "/api/cloud/devices/heartbeat",
        payload,
        nonce="hc4-heartbeat-once",
    )
    assert first.status_code == 200, first.text
    assert first.json()["business_group_id"] == "1"
    assert first.json()["company_id"] == "2"
    assert first.json()["branch_id"] == "3"

    replay = hc4_cloud_client.post(
        "/api/cloud/devices/heartbeat",
        headers=headers,
        json=payload.model_dump(mode="json"),
    )
    assert replay.status_code == 409
    with hc4_cloud_factory() as db:
        assert db.scalar(select(func.count()).select_from(device_heartbeats)) == 1
        assert db.scalar(select(func.count()).select_from(continuity_request_nonces)) == 1


def test_stale_signed_heartbeat_fails_closed(hc4_cloud_client, hc4_cloud_factory) -> None:
    _seed_device(hc4_cloud_factory)
    payload = SignedHeartbeatInput()
    stale = str(int(time.time()) - 1000)
    response, _ = _post_signed(
        hc4_cloud_client,
        "/api/cloud/devices/heartbeat",
        payload,
        timestamp=stale,
    )
    assert response.status_code == 401


def test_expired_writer_lease_takeover_increments_fencing_epoch(hc4_cloud_client, hc4_cloud_factory) -> None:
    _seed_device(hc4_cloud_factory)
    payload = WriterLeaseInput(
        scope_key="group:1:company:2:branch:3",
        business_group_id="1",
        company_id="2",
        branch_id="3",
        requested_mode="recovering",
    )
    first, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/lease/acquire", payload)
    assert first.status_code == 200, first.text
    assert first.json()["fencing_epoch"] == 1

    with hc4_cloud_factory() as db:
        db.execute(
            update(writer_leases)
            .where(writer_leases.c.scope_key == payload.scope_key)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        db.commit()

    second_payload = payload.model_copy(update={"fencing_epoch": 1})
    second, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/lease/acquire", second_payload)
    assert second.status_code == 200, second.text
    assert second.json()["fencing_epoch"] == 2

    stale_renew, _ = _post_signed(
        hc4_cloud_client,
        "/api/cloud/continuity/lease/renew",
        payload.model_copy(update={"fencing_epoch": 1}),
    )
    assert stale_renew.status_code == 409


def test_continuity_reference_requires_current_epoch_and_replays_idempotently(
    hc4_cloud_client,
    hc4_cloud_factory,
) -> None:
    _seed_device(hc4_cloud_factory)
    lease_payload = WriterLeaseInput(
        scope_key="group:1:company:2:branch:3",
        business_group_id="1",
        company_id="2",
        branch_id="3",
    )
    lease, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/lease/acquire", lease_payload)
    assert lease.status_code == 200
    epoch = lease.json()["fencing_epoch"]
    reference = uuid4()

    stale = ContinuityReferenceInput(
        continuity_reference=reference,
        scope_key=lease_payload.scope_key,
        business_group_id="1",
        company_id="2",
        branch_id="3",
        purpose="payment_capture",
        fencing_epoch=max(0, epoch - 1),
        payload={"external_reference": "upi-hc4-001", "amount": "250.00"},
    )
    denied, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/references", stale)
    assert denied.status_code == 409

    current = stale.model_copy(update={"fencing_epoch": epoch})
    created, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/references", current)
    assert created.status_code == 201, created.text
    assert created.json()["replayed"] is False

    replay, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/references", current)
    assert replay.status_code == 201
    assert replay.json()["replayed"] is True

    changed = current.model_copy(update={"payload": {"external_reference": "upi-hc4-001", "amount": "999.00"}})
    conflict, _ = _post_signed(hc4_cloud_client, "/api/cloud/continuity/references", changed)
    assert conflict.status_code == 409

    with hc4_cloud_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(continuity_transactions).where(
                continuity_transactions.c.continuity_reference == reference
            )
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(sync_commands).where(
                sync_commands.c.aggregate_id == str(reference)
            )
        ) == 1
