from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_not_found
from app.cloud_db.release_schema import cloud_bill_requests
from app.cloud_db.schema import (
    cloud_orders,
    published_menu_versions,
    published_table_tokens,
    sync_commands,
)
from app.schemas.hc3 import CloudBillRequestCreate, CloudBillRequestRead

INVALID_QR = "Cafe access reference is invalid, expired, or disabled."


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _resolve_table(db: Session, *, publication_id: UUID, opaque_qr: str):
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
    if not hmac.compare_digest(_sha256(proof), row["qr_hash"]):
        raise_not_found(INVALID_QR)
    return row


def _read(db: Session, public_id: UUID, *, replayed: bool = False) -> CloudBillRequestRead:
    row = db.execute(
        select(cloud_bill_requests).where(cloud_bill_requests.c.public_id == public_id)
    ).mappings().first()
    if row is None:
        raise_not_found("Cloud Cafe bill request was not found.")
    return CloudBillRequestRead(
        order_public_id=row["order_public_id"],
        bill_requested_at=row["requested_at"],
        replayed=replayed,
    )


def queue_cloud_bill_request(
    db: Session,
    *,
    order_public_id: UUID,
    payload: CloudBillRequestCreate,
    idempotency_key: str,
) -> CloudBillRequestRead:
    if not 8 <= len(idempotency_key) <= 200:
        raise_bad_request("Idempotency-Key must be between 8 and 200 characters.")

    table = _resolve_table(db, publication_id=payload.publication_id, opaque_qr=payload.opaque_qr)
    order = db.execute(
        select(cloud_orders).where(cloud_orders.c.public_id == order_public_id)
    ).mappings().first()
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
                "order_public_id": str(order_public_id),
                "publication_id": str(payload.publication_id),
                "table_public_reference": str(table["qr_public_reference"]),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    existing = db.execute(
        select(cloud_bill_requests).where(
            cloud_bill_requests.c.company_id == company_id,
            cloud_bill_requests.c.branch_id == branch_id,
            cloud_bill_requests.c.idempotency_key_hash == key_hash,
        )
    ).mappings().first()
    if existing is not None:
        if existing["request_hash"] != request_hash or existing["order_public_id"] != order_public_id:
            raise_conflict("This retry key was already used for a different bill request.")
        return _read(db, existing["public_id"], replayed=True)

    request_public_id = uuid4()
    event_id = uuid4()
    correlation_id = uuid4()
    now = datetime.now(UTC)
    command_payload = {
        "bill_request_public_id": str(request_public_id),
        "cloud_order_public_id": str(order_public_id),
        "publication_id": str(payload.publication_id),
        "table_public_reference": str(table["qr_public_reference"]),
        "source_table_id": str(table["source_table_id"]),
        "requested_at": now.isoformat(),
    }

    try:
        db.execute(
            insert(cloud_bill_requests).values(
                id=uuid4(),
                public_id=request_public_id,
                order_public_id=order_public_id,
                business_group_id=business_group_id,
                company_id=company_id,
                branch_id=branch_id,
                table_public_reference=str(table["qr_public_reference"]),
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                status="queued",
                requested_at=now,
                updated_at=now,
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
                aggregate_type="cafe_bill_request",
                aggregate_id=str(request_public_id),
                aggregate_version=1,
                correlation_id=correlation_id,
                causation_id=None,
                payload=command_payload,
                status="pending",
                recorded_at=now,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(cloud_bill_requests).where(
                cloud_bill_requests.c.company_id == company_id,
                cloud_bill_requests.c.branch_id == branch_id,
                cloud_bill_requests.c.idempotency_key_hash == key_hash,
            )
        ).mappings().first()
        if existing is not None and existing["request_hash"] == request_hash and existing["order_public_id"] == order_public_id:
            return _read(db, existing["public_id"], replayed=True)
        raise_conflict("This retry key cannot be reused for a different bill request.")

    return _read(db, request_public_id)
