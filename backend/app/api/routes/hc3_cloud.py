from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query
from sqlalchemy import or_, select

from app.api.routes.cloud_gateway import Database, _active_device, _require_scope_values
from app.cloud_db.schema import cloud_orders, sync_commands
from app.schemas.hc3 import (
    CloudBillRequestCreate,
    CloudBillRequestRead,
    CloudCommandBatch,
    CloudOrderCreate,
    CloudOrderRead,
    CloudSyncPushRead,
    CloudSyncReceiptInput,
)
from app.schemas.sync import EventEnvelope, EventSource
from app.services.hc3_cloud_bill_requests import queue_cloud_bill_request
from app.services.hc3_cloud_orders import (
    apply_local_sync_event,
    create_cloud_order,
    get_cloud_order,
    record_sync_receipt,
)

router = APIRouter(prefix="/cloud", tags=["hc3-cloud-orders"])


@router.post("/public/cafe/orders", response_model=CloudOrderRead, status_code=201)
def submit_cloud_order(
    payload: CloudOrderCreate,
    db: Database,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> CloudOrderRead:
    return create_cloud_order(db, payload=payload, idempotency_key=idempotency_key)


@router.get("/public/cafe/orders/{public_id}", response_model=CloudOrderRead)
def read_cloud_order(public_id: UUID, db: Database) -> CloudOrderRead:
    return get_cloud_order(db, public_id)


@router.post("/public/cafe/orders/{public_id}/bill-request", response_model=CloudBillRequestRead, status_code=202)
def submit_cloud_bill_request(
    public_id: UUID,
    payload: CloudBillRequestCreate,
    db: Database,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> CloudBillRequestRead:
    # This is a durable guest command only. It never creates an invoice,
    # payment, ledger entry, or stock movement in the cloud gateway.
    return queue_cloud_bill_request(
        db,
        order_public_id=public_id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/sync/commands", response_model=CloudCommandBatch)
def pull_commands(
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> CloudCommandBatch:
    device = _active_device(
        db,
        device_id=x_device_id,
        proof=x_device_proof,
        purpose="sync_pull",
    )
    statement = select(sync_commands).where(
        sync_commands.c.status == "pending",
        sync_commands.c.business_group_id == str(device["business_group_id"]),
        or_(sync_commands.c.target_device_id.is_(None), sync_commands.c.target_device_id == x_device_id),
    )
    if device["company_id"] is not None:
        statement = statement.where(sync_commands.c.company_id == str(device["company_id"]))
    if device["branch_id"] is not None:
        statement = statement.where(sync_commands.c.branch_id == str(device["branch_id"]))
    rows = db.execute(statement.order_by(sync_commands.c.recorded_at, sync_commands.c.id).limit(limit)).mappings().all()
    events: list[EventEnvelope] = []
    for row in rows:
        idempotency_hash = None
        if row["aggregate_type"] == "cafe_order":
            try:
                order_public_id = UUID(str(row["aggregate_id"]))
            except ValueError:
                order_public_id = None
            if order_public_id is not None:
                idempotency_hash = db.execute(
                    select(cloud_orders.c.idempotency_key_hash).where(cloud_orders.c.public_id == order_public_id)
                ).scalar_one_or_none()
        events.append(
            EventEnvelope(
                event_id=row["event_id"],
                event_type=row["event_type"],
                schema_version=row["schema_version"],
                source=EventSource.CLOUD_GATEWAY,
                source_device_id=None,
                business_group_id=row["business_group_id"],
                company_id=row["company_id"],
                branch_id=row["branch_id"],
                aggregate_type=row["aggregate_type"],
                aggregate_id=row["aggregate_id"],
                aggregate_version=row["aggregate_version"],
                idempotency_key_hash=idempotency_hash,
                occurred_at=row["recorded_at"],
                recorded_at=row["recorded_at"],
                correlation_id=row["correlation_id"],
                causation_id=row["causation_id"],
                payload=row["payload"] or {},
            )
        )
    return CloudCommandBatch(events=events)


@router.post("/sync/receipts", response_model=CloudSyncPushRead)
def push_receipt(
    payload: CloudSyncReceiptInput,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
) -> CloudSyncPushRead:
    device = _active_device(db, device_id=x_device_id, proof=x_device_proof, purpose="sync_push")
    command = db.execute(select(sync_commands).where(sync_commands.c.event_id == payload.event_id)).mappings().first()
    if command is not None:
        _require_scope_values(
            device,
            business_group_id=str(command["business_group_id"]),
            company_id=str(command["company_id"]) if command["company_id"] is not None else None,
            branch_id=str(command["branch_id"]) if command["branch_id"] is not None else None,
        )
    return record_sync_receipt(db, device_id=x_device_id, receipt=payload)


@router.post("/sync/events", response_model=CloudSyncPushRead)
def push_local_event(
    payload: EventEnvelope,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
) -> CloudSyncPushRead:
    device = _active_device(db, device_id=x_device_id, proof=x_device_proof, purpose="sync_push")
    if payload.source != EventSource.LOCAL_HUB or payload.source_device_id != x_device_id:
        from app.api.errors import raise_forbidden

        raise_forbidden("Synchronization event source is not authorized for this device.")

    # For mirrored Cafe order events, authorize against the stored cloud order
    # scope rather than trusting the submitted envelope to describe its group.
    stored_order = None
    if payload.aggregate_type == "cafe_order":
        try:
            order_public_id = UUID(str(payload.aggregate_id))
        except ValueError:
            order_public_id = None
        if order_public_id is not None:
            stored_order = db.execute(
                select(
                    cloud_orders.c.business_group_id,
                    cloud_orders.c.company_id,
                    cloud_orders.c.branch_id,
                ).where(cloud_orders.c.public_id == order_public_id)
            ).mappings().first()

    if stored_order is not None:
        _require_scope_values(
            device,
            business_group_id=str(stored_order["business_group_id"]),
            company_id=str(stored_order["company_id"]) if stored_order["company_id"] is not None else None,
            branch_id=str(stored_order["branch_id"]) if stored_order["branch_id"] is not None else None,
        )
    else:
        _require_scope_values(
            device,
            business_group_id=str(payload.business_group_id),
            company_id=str(payload.company_id) if payload.company_id is not None else None,
            branch_id=str(payload.branch_id) if payload.branch_id is not None else None,
        )
    return apply_local_sync_event(db, event=payload)
