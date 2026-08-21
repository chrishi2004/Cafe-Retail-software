from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_not_found
from app.cloud_db.schema import (
    cloud_idempotency_keys,
    cloud_order_events,
    cloud_order_items,
    cloud_orders,
    published_menu_items,
    published_menu_versions,
    published_table_tokens,
    sync_commands,
    sync_receipts,
)
from app.schemas.hc3 import (
    CloudBillRequestCreate,
    CloudBillRequestRead,
    CloudOrderCreate,
    CloudOrderItemRead,
    CloudOrderRead,
    CloudSyncPushRead,
    CloudSyncReceiptInput,
)
from app.schemas.sync import EventEnvelope

INVALID_QR = "Cafe access reference is invalid, expired, or disabled."
SAFE_CLOUD_STATUSES = {
    "awaiting_cafe_confirmation",
    "accepted",
    "preparing",
    "ready",
    "served",
    "bill_requested",
    "billed",
    "rejected",
    "closed",
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _resolve_ordering_table(db: Session, *, publication_id: UUID, opaque_qr: str):
    try:
        public_reference, proof = opaque_qr.split(".", 1)
    except ValueError:
        raise_not_found(INVALID_QR)
    if not public_reference or not proof:
        raise_not_found(INVALID_QR)

    row = db.execute(
        select(
            published_table_tokens,
            published_menu_versions.c.publication_id,
            published_menu_versions.c.business_group_id,
            published_menu_versions.c.company_id,
            published_menu_versions.c.branch_id,
            published_menu_versions.c.snapshot_at,
        )
        .join(
            published_menu_versions,
            published_menu_versions.c.id == published_table_tokens.c.menu_version_id,
        )
        .where(
            published_menu_versions.c.publication_id == publication_id,
            published_menu_versions.c.state == "active",
            published_table_tokens.c.qr_public_reference == public_reference,
        )
    ).mappings().first()
    if row is None or row["revoked_at"] is not None or not row["available"]:
        raise_not_found(INVALID_QR)
    expires_at = row["qr_expires_at"]
    if expires_at is not None and _aware(expires_at) <= datetime.now(UTC):
        raise_not_found(INVALID_QR)
    candidate = _sha256(proof)
    if not hmac.compare_digest(candidate, row["qr_hash"]):
        raise_not_found(INVALID_QR)
    return row


def _canonical_request_hash(payload: CloudOrderCreate, *, table_reference: str) -> str:
    canonical = {
        "publication_id": str(payload.publication_id),
        "table_public_reference": table_reference,
        "customer_notes": payload.customer_notes,
        "items": [
            {
                "menu_item_public_id": row.menu_item_public_id,
                "quantity": row.quantity,
                "notes": row.notes,
            }
            for row in payload.items
        ],
    }
    return _sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")))


def _read_cloud_order(db: Session, public_id: UUID, *, replayed: bool = False) -> CloudOrderRead:
    order = db.execute(select(cloud_orders).where(cloud_orders.c.public_id == public_id)).mappings().first()
    if order is None:
        raise_not_found("Cloud Cafe order was not found.")
    rows = db.execute(
        select(cloud_order_items)
        .where(cloud_order_items.c.order_id == order["id"])
        .order_by(cloud_order_items.c.id)
    ).mappings().all()
    return CloudOrderRead(
        public_id=order["public_id"],
        status=order["status"],
        estimated_total=order["customer_total"] or Decimal("0.00"),
        created_at=order["created_at"],
        replayed=replayed,
        items=[
            CloudOrderItemRead(
                menu_item_public_id=row["source_menu_item_id"],
                name=row["name_snapshot"],
                quantity=int(row["quantity"]),
                unit_price=row["unit_price_snapshot"],
                line_total=row["line_total"],
            )
            for row in rows
        ],
    )


def create_cloud_order(
    db: Session,
    *,
    payload: CloudOrderCreate,
    idempotency_key: str,
) -> CloudOrderRead:
    if not 8 <= len(idempotency_key) <= 200:
        raise_bad_request("Idempotency-Key must be between 8 and 200 characters.")
    table = _resolve_ordering_table(db, publication_id=payload.publication_id, opaque_qr=payload.opaque_qr)
    company_id = str(table["company_id"])
    branch_id = str(table["branch_id"])
    business_group_id = str(table["business_group_id"])
    key_hash = _sha256(f"{company_id}:{branch_id}:cloud_cafe_order:{idempotency_key}")
    request_hash = _canonical_request_hash(payload, table_reference=table["qr_public_reference"])

    prior = db.execute(
        select(cloud_idempotency_keys).where(
            cloud_idempotency_keys.c.company_id == company_id,
            cloud_idempotency_keys.c.branch_id == branch_id,
            cloud_idempotency_keys.c.purpose == "cafe_order",
            cloud_idempotency_keys.c.key_hash == key_hash,
        )
    ).mappings().first()
    if prior is not None:
        if prior["request_hash"] != request_hash:
            raise_conflict("This retry key was already used for a different cloud order.")
        return _read_cloud_order(db, UUID(prior["result_reference"]), replayed=True)

    requested_ids = [row.menu_item_public_id for row in payload.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise_bad_request("Each menu item may appear only once per order.")
    item_rows = db.execute(
        select(published_menu_items).where(
            published_menu_items.c.menu_version_id == table["menu_version_id"],
            published_menu_items.c.source_menu_item_id.in_(requested_ids),
            published_menu_items.c.available.is_(True),
        )
    ).mappings().all()
    by_id = {row["source_menu_item_id"]: row for row in item_rows}
    if set(by_id) != set(requested_ids):
        raise_conflict("One or more selected Cafe items are unavailable in the active publication.")

    public_id = uuid4()
    event_id = uuid4()
    correlation_id = uuid4()
    now = datetime.now(UTC)
    subtotal = Decimal("0.00")
    snapshots: list[dict[str, object]] = []
    for requested in payload.items:
        item = by_id[requested.menu_item_public_id]
        line_total = (item["selling_price"] * requested.quantity).quantize(Decimal("0.01"))
        subtotal += line_total
        snapshots.append(
            {
                "menu_item_public_id": item["source_menu_item_id"],
                "source_product_id": item["source_product_id"],
                "name": item["name"],
                "quantity": requested.quantity,
                "unit_price": str(item["selling_price"]),
                "line_total": str(line_total),
                "notes": requested.notes,
            }
        )

    event_payload = {
        "cloud_order_public_id": str(public_id),
        "publication_id": str(payload.publication_id),
        "table_public_reference": table["qr_public_reference"],
        "source_table_id": table["source_table_id"],
        "snapshot_at": _aware(table["snapshot_at"]).isoformat(),
        "customer_notes": payload.customer_notes,
        "customer_total": str(subtotal),
        "items": snapshots,
    }

    try:
        order_id = db.execute(
            insert(cloud_orders)
            .values(
                public_id=public_id,
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                table_public_reference=table["qr_public_reference"],
                status="awaiting_cafe_confirmation",
                idempotency_key_hash=key_hash,
                payload_hash=request_hash,
                customer_total=subtotal,
                created_at=now,
                updated_at=now,
            )
            .returning(cloud_orders.c.id)
        ).scalar_one()
        db.execute(
            insert(cloud_order_items),
            [
                {
                    "order_id": order_id,
                    "source_menu_item_id": row["menu_item_public_id"],
                    "name_snapshot": row["name"],
                    "unit_price_snapshot": Decimal(str(row["unit_price"])),
                    "quantity": row["quantity"],
                    "line_total": Decimal(str(row["line_total"])),
                }
                for row in snapshots
            ],
        )
        db.execute(
            insert(cloud_order_events).values(
                event_id=event_id,
                order_id=order_id,
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                event_type="cafe.order.submitted",
                schema_version=1,
                aggregate_version=1,
                correlation_id=correlation_id,
                payload=event_payload,
                recorded_at=now,
            )
        )
        db.execute(
            insert(sync_commands).values(
                event_id=event_id,
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                target_device_id=None,
                event_type="cafe.order.submitted",
                schema_version=1,
                aggregate_type="cafe_order",
                aggregate_id=str(public_id),
                aggregate_version=1,
                correlation_id=correlation_id,
                causation_id=None,
                payload=event_payload,
                status="pending",
                recorded_at=now,
            )
        )
        db.execute(
            insert(cloud_idempotency_keys).values(
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                purpose="cafe_order",
                key_hash=key_hash,
                request_hash=request_hash,
                result_reference=str(public_id),
                created_at=now,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.execute(
            select(cloud_idempotency_keys).where(
                cloud_idempotency_keys.c.company_id == company_id,
                cloud_idempotency_keys.c.branch_id == branch_id,
                cloud_idempotency_keys.c.purpose == "cafe_order",
                cloud_idempotency_keys.c.key_hash == key_hash,
            )
        ).mappings().first()
        if prior is not None and prior["request_hash"] == request_hash:
            return _read_cloud_order(db, UUID(prior["result_reference"]), replayed=True)
        raise_conflict("This retry key cannot be reused for a different cloud order.")

    return _read_cloud_order(db, public_id)


def get_cloud_order(db: Session, public_id: UUID) -> CloudOrderRead:
    return _read_cloud_order(db, public_id)


def _read_cloud_bill_request(db: Session, public_id: UUID, *, replayed: bool = False) -> CloudBillRequestRead:
    order = db.execute(select(cloud_orders).where(cloud_orders.c.public_id == public_id)).mappings().first()
    if order is None:
        raise_not_found("Cloud Cafe order was not found.")
    requested_at = db.execute(
        select(cloud_order_events.c.recorded_at)
        .where(
            cloud_order_events.c.order_id == order["id"],
            cloud_order_events.c.event_type == "cafe.bill.requested",
        )
        .order_by(cloud_order_events.c.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if requested_at is None:
        raise_not_found("Cloud Cafe bill request was not found.")
    return CloudBillRequestRead(
        order_public_id=public_id,
        bill_requested_at=requested_at,
        replayed=replayed,
    )


def queue_cloud_bill_request(
    db: Session,
    *,
    public_id: UUID,
    payload: CloudBillRequestCreate,
    idempotency_key: str,
) -> CloudBillRequestRead:
    if not 8 <= len(idempotency_key) <= 200:
        raise_bad_request("Idempotency-Key must be between 8 and 200 characters.")

    table = _resolve_ordering_table(db, publication_id=payload.publication_id, opaque_qr=payload.opaque_qr)
    order = db.execute(select(cloud_orders).where(cloud_orders.c.public_id == public_id)).mappings().first()
    if order is None:
        raise_not_found("Cloud Cafe order was not found.")
    if (
        str(order["business_group_id"]) != str(table["business_group_id"])
        or str(order["company_id"]) != str(table["company_id"])
        or str(order["branch_id"]) != str(table["branch_id"])
        or str(order["table_public_reference"]) != str(table["qr_public_reference"])
    ):
        raise_not_found("Cloud Cafe order was not found for this table.")
    if str(order["status"]) in {"rejected", "closed", "billed"}:
        raise_conflict("This Cafe order can no longer request a bill.")

    company_id = str(order["company_id"])
    branch_id = str(order["branch_id"])
    business_group_id = str(order["business_group_id"])
    key_hash = _sha256(f"{company_id}:{branch_id}:cloud_cafe_bill_request:{idempotency_key}")
    request_hash = _sha256(
        json.dumps(
            {
                "order_public_id": str(public_id),
                "publication_id": str(payload.publication_id),
                "table_public_reference": str(table["qr_public_reference"]),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    prior = db.execute(
        select(cloud_idempotency_keys).where(
            cloud_idempotency_keys.c.company_id == company_id,
            cloud_idempotency_keys.c.branch_id == branch_id,
            cloud_idempotency_keys.c.purpose == "cafe_bill_request",
            cloud_idempotency_keys.c.key_hash == key_hash,
        )
    ).mappings().first()
    if prior is not None:
        if prior["request_hash"] != request_hash or prior["result_reference"] != str(public_id):
            raise_conflict("This retry key was already used for a different bill request.")
        return _read_cloud_bill_request(db, public_id, replayed=True)

    prior_version = db.execute(
        select(cloud_order_events.c.aggregate_version)
        .where(cloud_order_events.c.order_id == order["id"])
        .order_by(cloud_order_events.c.aggregate_version.desc())
        .limit(1)
    ).scalar_one_or_none() or 1
    aggregate_version = int(prior_version) + 1
    event_id = uuid4()
    correlation_id = uuid4()
    now = datetime.now(UTC)
    event_payload = {
        "cloud_order_public_id": str(public_id),
        "publication_id": str(payload.publication_id),
        "table_public_reference": str(table["qr_public_reference"]),
        "source_table_id": str(table["source_table_id"]),
        "requested_at": now.isoformat(),
    }

    try:
        db.execute(
            insert(cloud_order_events).values(
                event_id=event_id,
                order_id=order["id"],
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                event_type="cafe.bill.requested",
                schema_version=1,
                aggregate_version=aggregate_version,
                correlation_id=correlation_id,
                payload=event_payload,
                recorded_at=now,
            )
        )
        db.execute(
            insert(sync_commands).values(
                event_id=event_id,
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                target_device_id=None,
                event_type="cafe.bill.requested",
                schema_version=1,
                aggregate_type="cafe_order",
                aggregate_id=str(public_id),
                aggregate_version=aggregate_version,
                correlation_id=correlation_id,
                causation_id=None,
                payload=event_payload,
                status="pending",
                recorded_at=now,
            )
        )
        db.execute(
            insert(cloud_idempotency_keys).values(
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                purpose="cafe_bill_request",
                key_hash=key_hash,
                request_hash=request_hash,
                result_reference=str(public_id),
                created_at=now,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.execute(
            select(cloud_idempotency_keys).where(
                cloud_idempotency_keys.c.company_id == company_id,
                cloud_idempotency_keys.c.branch_id == branch_id,
                cloud_idempotency_keys.c.purpose == "cafe_bill_request",
                cloud_idempotency_keys.c.key_hash == key_hash,
            )
        ).mappings().first()
        if prior is not None and prior["request_hash"] == request_hash and prior["result_reference"] == str(public_id):
            return _read_cloud_bill_request(db, public_id, replayed=True)
        raise_conflict("This retry key cannot be reused for a different bill request.")

    return _read_cloud_bill_request(db, public_id)


def record_sync_receipt(
    db: Session,
    *,
    device_id: str,
    receipt: CloudSyncReceiptInput,
) -> CloudSyncPushRead:
    existing = db.execute(
        select(sync_receipts).where(sync_receipts.c.event_id == receipt.event_id)
    ).mappings().first()
    if existing is not None:
        return CloudSyncPushRead(accepted=True, event_id=receipt.event_id, duplicate=True)
    command = db.execute(
        select(sync_commands).where(sync_commands.c.event_id == receipt.event_id)
    ).mappings().first()
    if command is None:
        raise_not_found("Synchronization command was not found.")
    db.execute(
        insert(sync_receipts).values(
            event_id=receipt.event_id,
            device_id=device_id,
            business_group_id=command["business_group_id"],
            company_id=command["company_id"],
            branch_id=command["branch_id"],
            status=receipt.status,
            result_reference=receipt.result_reference,
        )
    )
    db.execute(
        update(sync_commands)
        .where(sync_commands.c.event_id == receipt.event_id)
        .values(status="acknowledged" if receipt.status in {"committed", "duplicate"} else "rejected")
    )
    db.commit()
    return CloudSyncPushRead(accepted=True, event_id=receipt.event_id)


def apply_local_sync_event(db: Session, *, event: EventEnvelope) -> CloudSyncPushRead:
    duplicate = db.execute(
        select(cloud_order_events.c.id).where(cloud_order_events.c.event_id == event.event_id)
    ).first()
    if duplicate is not None:
        return CloudSyncPushRead(accepted=True, event_id=event.event_id, duplicate=True)
    if event.aggregate_type != "cafe_order":
        raise_bad_request("Unsupported synchronization aggregate.")
    try:
        public_id = UUID(event.aggregate_id)
    except ValueError:
        raise_bad_request("Invalid cloud order aggregate reference.")
    order = db.execute(select(cloud_orders).where(cloud_orders.c.public_id == public_id)).mappings().first()
    if order is None:
        raise_not_found("Cloud Cafe order was not found.")
    if str(event.company_id) != str(order["company_id"]) or str(event.branch_id) != str(order["branch_id"]):
        raise_conflict("Synchronization event scope does not match the cloud order.")

    prior_version = db.execute(
        select(cloud_order_events.c.aggregate_version)
        .where(cloud_order_events.c.order_id == order["id"])
        .order_by(cloud_order_events.c.aggregate_version.desc())
        .limit(1)
    ).scalar_one_or_none() or 0
    if event.aggregate_version > prior_version + 1:
        raise_conflict("Cloud order status event arrived out of sequence.")
    if event.aggregate_version <= prior_version:
        return CloudSyncPushRead(accepted=True, event_id=event.event_id, duplicate=True)

    status_value = str(event.payload.get("status", ""))
    if event.event_type == "cafe.order.imported":
        status_value = order["status"]
    elif event.event_type == "cafe.order.status_changed":
        if status_value not in SAFE_CLOUD_STATUSES:
            raise_bad_request("Unsupported mirrored Cafe order status.")
        db.execute(
            update(cloud_orders)
            .where(cloud_orders.c.id == order["id"])
            .values(status=status_value, updated_at=datetime.now(UTC))
        )
    else:
        raise_bad_request("Unsupported local synchronization event type.")

    db.execute(
        insert(cloud_order_events).values(
            event_id=event.event_id,
            order_id=order["id"],
            business_group_id=str(order["business_group_id"]),
            company_id=str(order["company_id"]),
            branch_id=str(order["branch_id"]),
            event_type=event.event_type,
            schema_version=event.schema_version,
            aggregate_version=event.aggregate_version,
            correlation_id=event.correlation_id,
            payload=event.payload,
            recorded_at=event.recorded_at,
        )
    )
    source_event_id = event.payload.get("source_event_id")
    if event.event_type == "cafe.order.imported" and source_event_id:
        try:
            source_uuid = UUID(str(source_event_id))
        except ValueError:
            raise_bad_request("Invalid source synchronization event reference.")
        command = db.execute(select(sync_commands).where(sync_commands.c.event_id == source_uuid)).mappings().first()
        if command is not None:
            receipt = db.execute(select(sync_receipts).where(sync_receipts.c.event_id == source_uuid)).first()
            if receipt is None:
                db.execute(
                    insert(sync_receipts).values(
                        event_id=source_uuid,
                        device_id=event.source_device_id or "local_hub",
                        business_group_id=command["business_group_id"],
                        company_id=command["company_id"],
                        branch_id=command["branch_id"],
                        status="committed",
                        result_reference=str(event.payload.get("local_public_id") or ""),
                    )
                )
            db.execute(update(sync_commands).where(sync_commands.c.event_id == source_uuid).values(status="acknowledged"))
    db.commit()
    return CloudSyncPushRead(accepted=True, event_id=event.event_id)
