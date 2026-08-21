from __future__ import annotations

from sqlalchemy import func, select

from app.cloud_db.release_schema import cloud_bill_requests
from app.cloud_db.schema import sync_commands
from app.models import Invoice, Sale, StockMovement, TableSession, TableSessionStatus
from app.schemas.hc3 import CloudBillRequestCreate
from app.schemas.sync import EventEnvelope, EventSource
from app.services.hc3_cloud_bill_requests import queue_cloud_bill_request
from app.sync.cafe_bill_requests import make_cloud_bill_request_handler
from app.sync.cafe_orders import make_cloud_order_handler
from app.sync.service import consume_incoming_event
from tests.test_hc3_cloud_order_convergence import (
    DEVICE_ID,
    _command_event,
    _publish_local_fixture,
    _submit,
    hc3_cloud_factory,
)


def _bill_command_event(cloud_factory) -> EventEnvelope:
    with cloud_factory() as db:
        command = db.execute(
            select(sync_commands).where(sync_commands.c.event_type == "cafe.bill.requested")
        ).mappings().one()
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
            occurred_at=command["recorded_at"],
            recorded_at=command["recorded_at"],
            correlation_id=command["correlation_id"],
            causation_id=command["causation_id"],
            payload=command["payload"],
        )


def test_cloud_bill_request_has_independent_aggregate_and_no_financial_effects(
    db_session_factory,
    seed_auth_data,
    hc3_cloud_factory,
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)
    cloud_order = _submit(hc3_cloud_factory, publication, ids, key="release-bill-order-001")

    order_event = _command_event(hc3_cloud_factory, cloud_order.public_id)
    order_result = consume_incoming_event(
        db_session_factory,
        order_event,
        make_cloud_order_handler(DEVICE_ID),
    )
    assert order_result.status == "processed"

    payload = CloudBillRequestCreate(
        publication_id=publication.publication_id,
        opaque_qr=str(ids["raw_qr"]),
    )
    with hc3_cloud_factory() as cloud:
        first = queue_cloud_bill_request(
            cloud,
            order_public_id=cloud_order.public_id,
            payload=payload,
            idempotency_key="release-bill-request-001",
        )
        replay = queue_cloud_bill_request(
            cloud,
            order_public_id=cloud_order.public_id,
            payload=payload,
            idempotency_key="release-bill-request-001",
        )
        assert first.order_public_id == cloud_order.public_id
        assert replay.replayed is True
        assert cloud.scalar(select(func.count()).select_from(cloud_bill_requests)) == 1

        command = cloud.execute(
            select(sync_commands).where(sync_commands.c.event_type == "cafe.bill.requested")
        ).mappings().one()
        assert command["aggregate_type"] == "cafe_bill_request"
        assert command["aggregate_version"] == 1
        assert command["payload"]["cloud_order_public_id"] == str(cloud_order.public_id)

    bill_event = _bill_command_event(hc3_cloud_factory)
    first_delivery = consume_incoming_event(
        db_session_factory,
        bill_event,
        make_cloud_bill_request_handler(),
    )
    duplicate_delivery = consume_incoming_event(
        db_session_factory,
        bill_event,
        make_cloud_bill_request_handler(),
    )
    assert first_delivery.status == "processed"
    assert duplicate_delivery.duplicate is True

    with db_session_factory() as db:
        session = db.get(TableSession, int(ids["table_session"]))
        assert session is not None
        assert session.status == TableSessionStatus.BILL_REQUESTED
        assert session.bill_requested_at is not None
        assert db.scalar(select(func.count(Invoice.id))) == 0
        assert db.scalar(select(func.count(Sale.id))) == 0
        assert db.scalar(select(func.count(StockMovement.id))) == 0
