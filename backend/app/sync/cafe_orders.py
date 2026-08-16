from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    CafeOrder,
    CafeOrderItem,
    CafeOrderItemStatus,
    CafeOrderSource,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    CafeTable,
    CloudRecordLink,
    Company,
    MenuCategory,
    MenuItem,
    Product,
    TableQRToken,
    TableSession,
    TableSessionStatus,
    TableSessionType,
)
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import PermanentSyncError, enqueue_outbox_event


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise PermanentSyncError(f"Invalid {field} in cloud order snapshot.", code="invalid_order_snapshot")


def _scope_id(value: str | int | None, *, field: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise PermanentSyncError(f"Invalid {field} in cloud order scope.", code="invalid_scope")


def _order_number(now: datetime) -> str:
    return f"C{now:%Y%m%d}-{secrets.token_hex(4).upper()}"


def _active_session(db: Session, *, company_id: int, branch_id: int, table_id: int) -> TableSession | None:
    return db.scalar(
        select(TableSession)
        .where(
            TableSession.company_id == company_id,
            TableSession.branch_id == branch_id,
            TableSession.table_id == table_id,
            TableSession.status.in_(
                [TableSessionStatus.OPEN, TableSessionStatus.BILL_REQUESTED, TableSessionStatus.BILLED]
            ),
        )
        .order_by(TableSession.opened_at.desc(), TableSession.id.desc())
        .with_for_update()
        .execution_options(scope_bypass=True)
    )


def import_cloud_cafe_order(
    db: Session,
    event: EventEnvelope,
    *,
    local_device_id: str,
) -> dict[str, object]:
    if event.event_type != "cafe.order.submitted" or event.aggregate_type != "cafe_order":
        raise PermanentSyncError("Unsupported Cafe cloud order event.", code="unsupported_event")
    if event.source != EventSource.CLOUD_GATEWAY:
        raise PermanentSyncError("Cafe cloud order event has an invalid source.", code="invalid_source")

    company_id = _scope_id(event.company_id, field="company_id")
    branch_id = _scope_id(event.branch_id, field="branch_id")
    business_group_id = _scope_id(event.business_group_id, field="business_group_id")
    company = db.get(Company, company_id, execution_options={"scope_bypass": True})
    branch = db.get(Branch, branch_id, execution_options={"scope_bypass": True})
    if (
        company is None
        or branch is None
        or not company.is_active
        or not branch.is_active
        or branch.company_id != company.id
        or company.business_group_id != business_group_id
    ):
        raise PermanentSyncError("Cloud Cafe order scope is not valid locally.", code="scope_mismatch")

    cloud_public_id = str(event.payload.get("cloud_order_public_id") or event.aggregate_id)
    if cloud_public_id != event.aggregate_id:
        raise PermanentSyncError("Cloud order aggregate reference mismatch.", code="aggregate_mismatch")
    existing_link = db.scalar(
        select(CloudRecordLink).where(
            CloudRecordLink.provider == "cloud_gateway",
            CloudRecordLink.aggregate_type == "cafe_order",
            CloudRecordLink.cloud_record_id == cloud_public_id,
        )
    )
    if existing_link is not None:
        return {
            "status": "already_imported",
            "local_record_id": existing_link.local_record_id,
            "local_public_id": existing_link.local_public_id,
        }

    table_reference = str(event.payload.get("table_public_reference") or "")
    qr = db.scalar(
        select(TableQRToken)
        .where(
            TableQRToken.public_reference == table_reference,
            TableQRToken.company_id == company_id,
            TableQRToken.branch_id == branch_id,
            TableQRToken.revoked_at.is_(None),
            or_(TableQRToken.expires_at.is_(None), TableQRToken.expires_at > datetime.now(UTC)),
        )
        .with_for_update()
        .execution_options(scope_bypass=True)
    )
    if qr is None:
        raise PermanentSyncError("Cloud order references a stale or revoked Cafe QR.", code="stale_qr")
    table = db.get(CafeTable, qr.table_id, execution_options={"scope_bypass": True})
    if (
        table is None
        or not table.is_active
        or table.company_id != company_id
        or table.branch_id != branch_id
        or str(table.id) != str(event.payload.get("source_table_id") or table.id)
    ):
        raise PermanentSyncError("Cloud order table does not match Local Hub authority.", code="table_scope_mismatch")

    session = _active_session(db, company_id=company_id, branch_id=branch_id, table_id=table.id)
    if session is None:
        session = TableSession(
            public_id=secrets.token_urlsafe(18),
            company_id=company_id,
            branch_id=branch_id,
            table_id=table.id,
            session_type=TableSessionType.DINE_IN,
            status=TableSessionStatus.OPEN,
            opened_by=None,
            opened_at=event.occurred_at,
        )
        db.add(session)
        db.flush()
    if session.status != TableSessionStatus.OPEN:
        raise PermanentSyncError("Cafe table session is not accepting new items.", code="session_closed")

    raw_items = event.payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise PermanentSyncError("Cloud order contains no item snapshots.", code="invalid_order_snapshot")
    public_ids = [str(row.get("menu_item_public_id") or "") for row in raw_items if isinstance(row, dict)]
    if len(public_ids) != len(raw_items) or len(public_ids) != len(set(public_ids)):
        raise PermanentSyncError("Cloud order item references are invalid.", code="invalid_order_snapshot")
    menu_rows = list(
        db.scalars(
            select(MenuItem)
            .where(
                MenuItem.company_id == company_id,
                MenuItem.public_id.in_(public_ids),
                MenuItem.is_active.is_(True),
                MenuItem.available.is_(True),
                or_(MenuItem.branch_id.is_(None), MenuItem.branch_id == branch_id),
            )
            .execution_options(scope_bypass=True)
        ).all()
    )
    by_public_id = {row.public_id: row for row in menu_rows}
    if set(by_public_id) != set(public_ids):
        raise PermanentSyncError("Cloud order contains unavailable Cafe items.", code="menu_item_unavailable")
    category_ids = {row.category_id for row in menu_rows}
    active_categories = set(
        db.scalars(
            select(MenuCategory.id)
            .where(
                MenuCategory.id.in_(category_ids),
                MenuCategory.company_id == company_id,
                MenuCategory.is_active.is_(True),
                or_(MenuCategory.branch_id.is_(None), MenuCategory.branch_id == branch_id),
            )
            .execution_options(scope_bypass=True)
        ).all()
    )
    if active_categories != category_ids:
        raise PermanentSyncError("Cloud order references an inactive Cafe category.", code="menu_item_unavailable")

    idempotency_hash = _sha256(f"cloud_gateway:cafe_order:{cloud_public_id}")
    existing_order = db.scalar(
        select(CafeOrder).where(
            CafeOrder.company_id == company_id,
            CafeOrder.idempotency_key_hash == idempotency_hash,
        )
    )
    if existing_order is not None:
        link = CloudRecordLink(
            company_id=company_id,
            branch_id=branch_id,
            provider="cloud_gateway",
            aggregate_type="cafe_order",
            cloud_record_id=cloud_public_id,
            local_record_id=existing_order.id,
            local_public_id=existing_order.public_id,
            source_event_id=str(event.event_id),
        )
        db.add(link)
        db.flush()
        return {"status": "already_imported", "local_record_id": existing_order.id, "local_public_id": existing_order.public_id}

    now = datetime.now(UTC)
    order = CafeOrder(
        public_id=secrets.token_urlsafe(18),
        company_id=company_id,
        branch_id=branch_id,
        table_session_id=session.id,
        guest_access_id=None,
        order_number=_order_number(now),
        order_type=session.session_type,
        source_channel=CafeOrderSource.QR_CUSTOMER,
        status=CafeOrderStatus.PLACED,
        subtotal=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        estimated_total=Decimal("0.00"),
        customer_notes=(str(event.payload.get("customer_notes"))[:500] if event.payload.get("customer_notes") else None),
        idempotency_key_hash=idempotency_hash,
        request_hash=_sha256(str(event.payload)),
        placed_at=event.occurred_at,
    )
    db.add(order)
    db.flush()

    subtotal = Decimal("0.00")
    for raw in raw_items:
        assert isinstance(raw, dict)
        menu_item = by_public_id[str(raw["menu_item_public_id"])]
        quantity = int(raw.get("quantity") or 0)
        if quantity < 1 or quantity > 20:
            raise PermanentSyncError("Cloud order quantity is invalid.", code="invalid_order_snapshot")
        expected_price = _decimal(raw.get("unit_price"), field="unit price")
        local_price = Decimal(menu_item.selling_price).quantize(Decimal("0.01"))
        if expected_price != local_price:
            raise PermanentSyncError("Cloud order price does not match Local Hub authority.", code="price_mismatch")
        expected_line = _decimal(raw.get("line_total"), field="line total")
        line_total = (local_price * quantity).quantize(Decimal("0.01"))
        if expected_line != line_total:
            raise PermanentSyncError("Cloud order line total is invalid.", code="price_mismatch")
        product_sku: str | None = None
        if menu_item.product_id is not None:
            product = db.get(Product, menu_item.product_id, execution_options={"scope_bypass": True})
            if product is None or product.company_id != company_id or not product.is_active:
                raise PermanentSyncError("Linked Cafe product is unavailable.", code="menu_item_unavailable")
            product_sku = product.sku
        subtotal += line_total
        db.add(
            CafeOrderItem(
                company_id=company_id,
                branch_id=branch_id,
                cafe_order_id=order.id,
                menu_item_id=menu_item.id,
                product_id=menu_item.product_id,
                menu_item_public_id_snapshot=menu_item.public_id,
                menu_item_name_snapshot=menu_item.name,
                product_sku_snapshot=product_sku,
                quantity=quantity,
                unit_price_snapshot=local_price,
                discount_amount=Decimal("0.00"),
                line_total=line_total,
                item_status=CafeOrderItemStatus.PLACED,
                preparation_notes=(str(raw.get("notes"))[:300] if raw.get("notes") else None),
                source_channel=CafeOrderSource.QR_CUSTOMER,
            )
        )

    cloud_total = _decimal(event.payload.get("customer_total"), field="customer total")
    subtotal = subtotal.quantize(Decimal("0.01"))
    if cloud_total != subtotal:
        raise PermanentSyncError("Cloud order total does not match Local Hub authority.", code="price_mismatch")
    order.subtotal = subtotal
    order.estimated_total = subtotal
    db.add(
        CafeOrderStatusHistory(
            company_id=company_id,
            branch_id=branch_id,
            cafe_order_id=order.id,
            from_status=None,
            to_status=CafeOrderStatus.PLACED,
            changed_by=None,
            guest_action=True,
            reason="Cloud customer order imported",
            created_at=now,
        )
    )
    link = CloudRecordLink(
        company_id=company_id,
        branch_id=branch_id,
        provider="cloud_gateway",
        aggregate_type="cafe_order",
        cloud_record_id=cloud_public_id,
        local_record_id=order.id,
        local_public_id=order.public_id,
        source_event_id=str(event.event_id),
    )
    db.add(link)

    imported = EventEnvelope(
        event_id=uuid4(),
        event_type="cafe.order.imported",
        source=EventSource.LOCAL_HUB,
        source_device_id=local_device_id,
        business_group_id=str(business_group_id),
        company_id=str(company_id),
        branch_id=str(branch_id),
        aggregate_type="cafe_order",
        aggregate_id=cloud_public_id,
        aggregate_version=2,
        idempotency_key_hash=event.idempotency_key_hash,
        occurred_at=now,
        correlation_id=event.correlation_id,
        causation_id=event.event_id,
        payload={
            "source_event_id": str(event.event_id),
            "local_public_id": order.public_id,
            "status": "awaiting_cafe_confirmation",
        },
    )
    enqueue_outbox_event(db, imported)
    db.flush()
    return {"status": "imported", "local_record_id": order.id, "local_public_id": order.public_id}


def make_cloud_order_handler(local_device_id: str):
    def handler(db: Session, event: EventEnvelope) -> dict[str, object]:
        return import_cloud_cafe_order(db, event, local_device_id=local_device_id)

    return handler


def enqueue_cafe_order_status_snapshot(
    db: Session,
    *,
    order: CafeOrder,
    local_device_id: str,
    status_value: str | None = None,
) -> EventEnvelope:
    link = db.scalar(
        select(CloudRecordLink).where(
            CloudRecordLink.provider == "cloud_gateway",
            CloudRecordLink.aggregate_type == "cafe_order",
            CloudRecordLink.local_record_id == order.id,
        )
    )
    if link is None:
        raise ValueError("Cafe order has no cloud identity link.")
    event = EventEnvelope(
        event_type="cafe.order.status_changed",
        source=EventSource.LOCAL_HUB,
        source_device_id=local_device_id,
        business_group_id=str(db.get(Company, order.company_id, execution_options={"scope_bypass": True}).business_group_id),
        company_id=str(order.company_id),
        branch_id=str(order.branch_id),
        aggregate_type="cafe_order",
        aggregate_id=link.cloud_record_id,
        aggregate_version=max(3, order.version + 1),
        occurred_at=datetime.now(UTC),
        correlation_id=uuid4(),
        payload={"local_public_id": order.public_id, "status": status_value or order.status.value},
    )
    enqueue_outbox_event(db, event)
    return event
