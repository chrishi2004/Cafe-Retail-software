from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.cloud_db.schema import (
    cloud_idempotency_keys,
    cloud_order_events,
    cloud_order_items,
    cloud_orders,
    cloud_tombstones,
    continuity_transactions,
    dashboard_snapshots,
    device_heartbeats,
    device_registrations,
    inventory_availability_snapshots,
    published_menu_categories,
    published_menu_items,
    published_menu_versions,
    published_table_tokens,
    sync_commands,
    sync_receipts,
    writer_leases,
)
from app.core.config import DeploymentMode, Settings
from app.db.session import get_db
from app.main import create_app


DEVICE_ID = "hc2-test-device"
DEVICE_PROOF = "hc2-test-installation-proof"


def _cloud_url() -> str:
    value = os.environ.get("HC2_TEST_CLOUD_DATABASE_URL")
    if not value:
        pytest.skip("HC2_TEST_CLOUD_DATABASE_URL is required for cloud coordination tests.")
    return value


@pytest.fixture()
def cloud_factory() -> sessionmaker[Session]:
    engine = create_engine(_cloud_url(), pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_cloud_state(cloud_factory: sessionmaker[Session]) -> None:
    child_to_parent = (
        cloud_order_items,
        cloud_order_events,
        cloud_idempotency_keys,
        sync_receipts,
        sync_commands,
        published_table_tokens,
        published_menu_items,
        published_menu_categories,
        inventory_availability_snapshots,
        dashboard_snapshots,
        cloud_tombstones,
        continuity_transactions,
        cloud_orders,
        published_menu_versions,
        device_heartbeats,
        writer_leases,
        device_registrations,
    )
    with cloud_factory() as db:
        for table in child_to_parent:
            db.execute(delete(table))
        db.commit()


@pytest.fixture()
def cloud_client(cloud_factory: sessionmaker[Session]):
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
        with cloud_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_device(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        db.execute(
            insert(device_registrations).values(
                device_id=DEVICE_ID,
                business_group_id="1",
                company_id="2",
                branch_id="3",
                display_name="HC2 Test Hub",
                credential_hash=hashlib.sha256(DEVICE_PROOF.encode("utf-8")).hexdigest(),
                status="active",
                allowed_purposes=["heartbeat", "menu_publication"],
            )
        )
        db.commit()


def _headers() -> dict[str, str]:
    return {"X-Device-Id": DEVICE_ID, "X-Device-Proof": DEVICE_PROOF}


def _publication(publication_id=None, *, company_id="2", branch_id="3", version=1):
    qr_proof = "table-proof-hc2"
    return {
        "publication_id": str(publication_id or uuid4()),
        "business_group_id": "1",
        "company_id": company_id,
        "branch_id": branch_id,
        "version": version,
        "snapshot_at": datetime.now(UTC).isoformat(),
        "categories": [
            {"source_category_id": "10", "name": "Coffee", "display_order": 1, "is_active": True}
        ],
        "items": [
            {
                "source_menu_item_id": "20",
                "source_product_id": "30",
                "source_category_id": "10",
                "name": "Cappuccino",
                "description": "Espresso with milk",
                "image_reference": None,
                "selling_price": "140.00",
                "preparation_area": "beverage",
                "available": True,
                "display_order": 1,
            }
        ],
        "tables": [
            {
                "source_table_id": "40",
                "table_code": "T01",
                "table_display_name": "Table 1",
                "public_reference": "hc2-table-ref",
                "verifier_digest": hashlib.sha256(qr_proof.encode("utf-8")).hexdigest(),
                "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
                "disabled_at": None,
                "available": True,
            }
        ],
        "availability": [{"source_product_id": "30", "available": True}],
    }, f"hc2-table-ref.{qr_proof}"


def test_cloud_schema_exists_and_rls_is_enabled(cloud_factory: sessionmaker[Session]) -> None:
    with cloud_factory() as db:
        tables = {
            row[0]
            for row in db.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'coordination'")
            ).all()
        }
        required = {
            "device_registrations",
            "device_heartbeats",
            "writer_leases",
            "published_menu_versions",
            "published_menu_categories",
            "published_menu_items",
            "published_table_tokens",
            "cloud_orders",
            "cloud_order_items",
            "cloud_order_events",
            "cloud_idempotency_keys",
            "sync_commands",
            "sync_receipts",
            "dashboard_snapshots",
            "inventory_availability_snapshots",
            "continuity_transactions",
            "cloud_tombstones",
        }
        assert required <= tables
        rls = dict(
            db.execute(
                text(
                    "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='coordination' AND c.relkind='r'"
                )
            ).all()
        )
        assert all(rls[name] for name in required)


def test_cloud_route_discovery_excludes_local_authoritative_writes(cloud_client) -> None:
    paths = {route.path for route in cloud_client.app.routes}
    assert "/api/health" in paths
    assert "/api/cloud/readiness" in paths
    assert "/api/cloud/publications/menu" in paths
    assert "/api/cloud/public/cafe/qr/resolve" in paths
    assert "/api/inventory/adjustments" not in paths
    assert "/api/invoices/{invoice_id}/issue" not in paths
    assert "/api/purchase-orders/{purchase_order_id}/receive" not in paths
    assert not any(path.startswith("/api/auth") for path in paths)


def test_publication_replay_is_idempotent_and_safe(cloud_client, cloud_factory) -> None:
    _seed_device(cloud_factory)
    publication_id = uuid4()
    payload, opaque_qr = _publication(publication_id)

    first = cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "active"
    assert first.json()["replayed"] is False

    replay = cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True

    with cloud_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(published_menu_versions).where(
                published_menu_versions.c.publication_id == publication_id
            )
        ) == 1

    menu = cloud_client.get(f"/api/cloud/public/cafe/menu/{publication_id}")
    assert menu.status_code == 200
    body = menu.json()
    assert "company_id" not in body
    assert "branch_id" not in body
    assert "business_group_id" not in body
    assert body["items"][0]["selling_price"] == "140.00"
    assert "cost" not in menu.text.lower()

    qr = cloud_client.post("/api/cloud/public/cafe/qr/resolve", json={"opaque_token": opaque_qr})
    assert qr.status_code == 200
    assert qr.json()["ordering_enabled"] is False
    assert "company_id" not in qr.json()


def test_changed_replay_and_cross_venture_publication_fail_closed(cloud_client, cloud_factory) -> None:
    _seed_device(cloud_factory)
    publication_id = uuid4()
    payload, _ = _publication(publication_id)
    assert cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=payload).status_code == 200

    changed = dict(payload)
    changed["items"] = [dict(payload["items"][0], selling_price="150.00")]
    assert cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=changed).status_code == 409

    retail_payload, _ = _publication(uuid4(), company_id="1", branch_id="1", version=2)
    denied = cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=retail_payload)
    assert denied.status_code == 403


def test_staging_publication_is_never_publicly_active(cloud_client, cloud_factory) -> None:
    staging_id = uuid4()
    with cloud_factory() as db:
        db.execute(
            insert(published_menu_versions).values(
                publication_id=staging_id,
                business_group_id="1",
                company_id="2",
                branch_id="3",
                version=99,
                state="staging",
                content_hash="0" * 64,
                source_device_id=DEVICE_ID,
                category_count=1,
                item_count=1,
                table_count=1,
                snapshot_at=datetime.now(UTC),
            )
        )
        db.commit()
    assert cloud_client.get(f"/api/cloud/public/cafe/menu/{staging_id}").status_code == 404


def test_revoked_device_and_table_reference_fail_closed(cloud_client, cloud_factory) -> None:
    _seed_device(cloud_factory)
    payload, opaque_qr = _publication(uuid4())
    assert cloud_client.post("/api/cloud/publications/menu", headers=_headers(), json=payload).status_code == 200
    assert cloud_client.post("/api/cloud/public/cafe/qr/resolve", json={"opaque_token": opaque_qr}).status_code == 200

    with cloud_factory() as db:
        db.execute(
            update(published_table_tokens)
            .where(published_table_tokens.c.qr_public_reference == "hc2-table-ref")
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()
    assert cloud_client.post("/api/cloud/public/cafe/qr/resolve", json={"opaque_token": opaque_qr}).status_code == 404

    with cloud_factory() as db:
        db.execute(
            update(device_registrations)
            .where(device_registrations.c.device_id == DEVICE_ID)
            .values(status="revoked", revoked_at=datetime.now(UTC))
        )
        db.commit()
    heartbeat = cloud_client.post(
        "/api/cloud/devices/heartbeat",
        headers=_headers(),
        json={"mode": "local_writer", "fencing_epoch": 1, "event_schema_version": 1},
    )
    assert heartbeat.status_code == 401
