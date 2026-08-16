from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.cloud_db.schema import (
    cloud_idempotency_keys,
    cloud_order_events,
    cloud_order_items,
    cloud_orders,
    inventory_availability_snapshots,
    published_menu_categories,
    published_menu_items,
    published_menu_versions,
    published_table_tokens,
    sync_commands,
    sync_receipts,
)
from app.models import (
    CafeOrder,
    CafeOrderStatus,
    CloudRecordLink,
    Inventory,
    Invoice,
    Sale,
    StockMovement,
    TableQRToken,
)
from app.schemas.hc3 import CloudOrderCreate
from app.schemas.sync import EventEnvelope, EventSource
from app.services.cafe_cloud_publication import build_cafe_publication
from app.services.cloud_coordination import publish_menu_snapshot
from app.services.hc3_cloud_orders import apply_local_sync_event, create_cloud_order
from app.sync.cafe_orders import enqueue_cafe_order_status_snapshot, make_cloud_order_handler
from app.sync.service import consume_incoming_event, process_outbox_batch
from tests.p6_fixtures import seed_p6_public_ordering

DEVICE_ID = "hc3-local-hub"


def _cloud_url() -> str:
    value = os.environ.get("HC3_TEST_CLOUD_DATABASE_URL") or os.environ.get("HC2_TEST_CLOUD_DATABASE_URL")
    if not value:
        pytest.skip("HC3_TEST_CLOUD_DATABASE_URL is required for HC3 convergence tests.")
    return value


@pytest.fixture()
def hc3_cloud_factory() -> sessionmaker[Session]:
    engine = create_engine(_cloud_url(), pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        for table in (
            cloud_order_items,
            cloud_order_events,
            cloud_idempotency_keys,
            sync_receipts,
            sync_commands,
            inventory_availability_snapshots,
            published_table_tokens,
            published_menu_items,
            published_menu_categories,
            cloud_orders,
            published_menu_versions,
        ):
            db.execute(delete(table))
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


def _publish_local_fixture(local_factory, cloud_factory):
    ids = seed_p6_public_ordering(local_factory)
    with local_factory() as local:
        publication = build_cafe_publication(
            local,
            company_id=int(ids["cafe_company"]),
            branch_id=int(ids["cafe_branch"]),
            version=1,
        )
    with cloud_factory() as cloud:
        result = publish_menu_snapshot(cloud, payload=publication, source_device_id=DEVICE_ID)
        assert result.state == "active"
    return ids, publication


def _submit(cloud_factory, publication, ids, *, key="hc3-order-001"):
    payload = CloudOrderCreate(
        publication_id=publication.publication_id,
        opaque_qr=str(ids["raw_qr"]),
        items=[{"menu_item_public_id": str(ids["menu_item_public_id"]), "quantity": 2, "notes": "less sugar"}],
        customer_notes="table order",
    )
    with cloud_factory() as db:
        return create_cloud_order(db, payload=payload, idempotency_key=key)


def _command_event(cloud_factory, public_id: UUID) -> EventEnvelope:
    with cloud_factory() as db:
        command = db.execute(
            select(sync_commands).where(sync_commands.c.aggregate_id == str(public_id))
        ).mappings().one()
        order = db.execute(select(cloud_orders).where(cloud_orders.c.public_id == public_id)).mappings().one()
        return EventEnvelope(
            event_id=command["event_id"],
            event_type=command["event_type"],
            schema_version=command["schema_version"],
            source=EventSource.CLOUD_GATEWAY,
            business_group_id=command["business_group_id"],
            company_id=command["company_id"],
            branch_id=command["branch_id"],
            aggregate_type=command["aggregate_type"],
            aggregate_id=command["aggregate_id"],
            aggregate_version=command["aggregate_version"],
            idempotency_key_hash=order["idempotency_key_hash"],
            occurred_at=command["recorded_at"],
            recorded_at=command["recorded_at"],
            correlation_id=command["correlation_id"],
            causation_id=command["causation_id"],
            payload=command["payload"],
        )


class DirectCloudTransport:
    def __init__(self, cloud_factory):
        self.cloud_factory = cloud_factory

    def send(self, event: EventEnvelope):
        with self.cloud_factory() as db:
            return apply_local_sync_event(db, event=event).model_dump(mode="json")


def test_duplicate_customer_taps_and_worker_delivery_create_one_effect(
    db_session_factory, seed_auth_data, hc3_cloud_factory
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)
    first = _submit(hc3_cloud_factory, publication, ids)
    replay = _submit(hc3_cloud_factory, publication, ids)
    assert first.public_id == replay.public_id
    assert replay.replayed is True

    event = _command_event(hc3_cloud_factory, first.public_id)
    handler = make_cloud_order_handler(DEVICE_ID)
    one = consume_incoming_event(db_session_factory, event, handler)
    two = consume_incoming_event(db_session_factory, event, handler)
    assert one.status == "processed"
    assert two.duplicate is True
    with db_session_factory() as db:
        order = db.scalar(select(CafeOrder))
        assert order is not None
        assert order.table_session_id == int(ids["table_session"])
        assert db.scalar(select(func.count(CafeOrder.id))) == 1
        assert db.scalar(select(func.count(CloudRecordLink.id))) == 1
        assert db.scalar(select(func.count(Invoice.id))) == 0
        assert db.scalar(select(func.count(Sale.id))) == 0
        assert db.scalar(select(func.count(StockMovement.id))) == 0

    result = process_outbox_batch(
        db_session_factory,
        DirectCloudTransport(hc3_cloud_factory),
        limit=20,
        jitter_ratio=0,
    )
    assert result.processed == 1
    with hc3_cloud_factory() as db:
        command_status = db.execute(
            select(sync_commands.c.status).where(sync_commands.c.aggregate_id == str(first.public_id))
        ).scalar_one()
        assert command_status == "acknowledged"
        assert db.scalar(select(func.count()).select_from(sync_receipts)) == 1


def test_local_rejection_mirrors_safe_cloud_status(
    db_session_factory, seed_auth_data, hc3_cloud_factory
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)
    cloud_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-reject-001")
    event = _command_event(hc3_cloud_factory, cloud_order.public_id)
    consume_incoming_event(db_session_factory, event, make_cloud_order_handler(DEVICE_ID))
    process_outbox_batch(db_session_factory, DirectCloudTransport(hc3_cloud_factory), limit=20, jitter_ratio=0)

    with db_session_factory() as db:
        order = db.scalar(select(CafeOrder).where(CafeOrder.company_id == int(ids["cafe_company"])))
        assert order is not None
        order.status = CafeOrderStatus.REJECTED
        order.version += 1
        enqueue_cafe_order_status_snapshot(db, order=order, local_device_id=DEVICE_ID)
        db.commit()
    process_outbox_batch(db_session_factory, DirectCloudTransport(hc3_cloud_factory), limit=20, jitter_ratio=0)
    with hc3_cloud_factory() as db:
        status_value = db.execute(
            select(cloud_orders.c.status).where(cloud_orders.c.public_id == cloud_order.public_id)
        ).scalar_one()
        assert status_value == "rejected"


def test_local_outage_leaves_order_durable_until_later_import(
    db_session_factory, seed_auth_data, hc3_cloud_factory
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)
    cloud_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-offline-001")
    with hc3_cloud_factory() as db:
        assert db.scalar(select(func.count()).select_from(cloud_orders)) == 1
        assert db.scalar(select(func.count()).select_from(sync_commands).where(sync_commands.c.status == "pending")) == 1
    with db_session_factory() as db:
        assert db.scalar(select(func.count(CafeOrder.id))) == 0

    event = _command_event(hc3_cloud_factory, cloud_order.public_id)
    consume_incoming_event(db_session_factory, event, make_cloud_order_handler(DEVICE_ID))
    with db_session_factory() as db:
        assert db.scalar(select(func.count(CafeOrder.id))) == 1


def test_tampered_price_cross_venture_and_stale_qr_fail_closed(
    db_session_factory, seed_auth_data, hc3_cloud_factory
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)

    price_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-price-001")
    price_event = _command_event(hc3_cloud_factory, price_order.public_id)
    tampered = price_event.model_copy(deep=True)
    tampered.payload["items"][0]["unit_price"] = "1.00"
    result = consume_incoming_event(db_session_factory, tampered, make_cloud_order_handler(DEVICE_ID))
    assert result.status == "dead_letter"

    scope_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-scope-001")
    scope_event = _command_event(hc3_cloud_factory, scope_order.public_id).model_copy(update={"company_id": "999999"})
    result = consume_incoming_event(db_session_factory, scope_event, make_cloud_order_handler(DEVICE_ID))
    assert result.status == "dead_letter"

    stale_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-stale-001")
    stale_event = _command_event(hc3_cloud_factory, stale_order.public_id)
    with db_session_factory() as db:
        qr = db.scalar(select(TableQRToken).where(TableQRToken.public_reference == stale_event.payload["table_public_reference"]))
        assert qr is not None
        from datetime import UTC, datetime

        qr.revoked_at = datetime.now(UTC)
        db.commit()
    result = consume_incoming_event(db_session_factory, stale_event, make_cloud_order_handler(DEVICE_ID))
    assert result.status == "dead_letter"
    with db_session_factory() as db:
        assert db.scalar(select(func.count(CafeOrder.id))) == 0
        assert db.scalar(select(func.coalesce(func.sum(Inventory.quantity_on_hand), 0))) is not None
