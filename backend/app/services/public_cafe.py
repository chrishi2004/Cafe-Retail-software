from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_not_found, raise_unauthorized
from app.models import (
    Branch,
    CafeGuestAccess,
    CafeOrder,
    CafeOrderItem,
    CafeOrderItemStatus,
    CafeOrderSource,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    CafeTable,
    Company,
    MenuCategory,
    MenuItem,
    Product,
    PublicRateLimitBucket,
    TableSession,
    TableSessionStatus,
)
from app.schemas.public_cafe import (
    PublicBillRequestRead,
    PublicMenuCategoryRead,
    PublicMenuItemRead,
    PublicMenuRead,
    PublicOrderCreate,
    PublicOrderItemRead,
    PublicOrderRead,
    PublicQrResolveRead,
    PublicSessionOrdersRead,
)
from app.services.cafe import INVALID_QR_MESSAGE, _resolve_qr_record

PUBLIC_GUEST_ACCESS_MINUTES = 60
PUBLIC_RATE_WINDOW_SECONDS = 60
PUBLIC_RESOLVE_LIMIT = 30
PUBLIC_READ_LIMIT = 120
PUBLIC_WRITE_LIMIT = 30
PUBLIC_MAX_BODY_BYTES = 32 * 1024
INVALID_GUEST_MESSAGE = "Guest session is invalid or expired."
SESSION_UNAVAILABLE_MESSAGE = "This table session is not available for ordering."


@dataclass(frozen=True)
class GuestContext:
    access: CafeGuestAccess
    session: TableSession
    table: CafeTable
    company: Company
    branch: Branch


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_secret_pair() -> tuple[str, str, str]:
    public_reference = secrets.token_urlsafe(16)
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    return public_reference, secret, f"{public_reference}.{secret}"


def _generic_guest_failure() -> None:
    raise_unauthorized(INVALID_GUEST_MESSAGE)


def enforce_public_rate_limit(
    db: Session,
    *,
    purpose: str,
    identity: str,
    limit: int,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    key_hash = _sha256(f"{purpose}:{identity}")
    row = db.scalar(
        select(PublicRateLimitBucket)
        .where(PublicRateLimitBucket.key_hash == key_hash)
        .with_for_update()
        .execution_options(scope_bypass=True)
    )
    if row is None:
        row = PublicRateLimitBucket(
            key_hash=key_hash,
            window_started_at=current,
            request_count=1,
        )
        db.add(row)
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            row = db.scalar(
                select(PublicRateLimitBucket)
                .where(PublicRateLimitBucket.key_hash == key_hash)
                .with_for_update()
                .execution_options(scope_bypass=True)
            )
            if row is None:
                raise

    window_started = _aware(row.window_started_at)
    elapsed = (current - window_started).total_seconds()
    if elapsed >= PUBLIC_RATE_WINDOW_SECONDS:
        row.window_started_at = current
        row.request_count = 1
        db.commit()
        return
    if row.request_count >= limit:
        retry_after = max(1, PUBLIC_RATE_WINDOW_SECONDS - int(elapsed))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many requests. Try again shortly."},
            headers={"Retry-After": str(retry_after)},
        )
    row.request_count += 1
    db.commit()


def resolve_qr_for_guest(
    db: Session,
    *,
    raw_qr: str,
    now: datetime | None = None,
) -> PublicQrResolveRead:
    current = now or datetime.now(UTC)
    qr_record, table, company = _resolve_qr_record(db, raw_qr, update_last_used=False)
    session = db.scalar(
        select(TableSession)
        .where(
            TableSession.table_id == table.id,
            TableSession.company_id == company.id,
            TableSession.branch_id == table.branch_id,
            TableSession.status == TableSessionStatus.OPEN,
        )
        .order_by(TableSession.opened_at.desc(), TableSession.id.desc())
        .execution_options(scope_bypass=True)
    )
    if session is None:
        raise_not_found(SESSION_UNAVAILABLE_MESSAGE)

    access_reference, access_secret, raw_access = _new_secret_pair()
    expires_at = current + timedelta(minutes=PUBLIC_GUEST_ACCESS_MINUTES)
    access = CafeGuestAccess(
        public_reference=access_reference,
        company_id=company.id,
        branch_id=table.branch_id,
        table_session_id=session.id,
        token_hash=_sha256(access_secret),
        token_version=1,
        expires_at=expires_at,
        last_used_at=current,
    )
    qr_record.last_used_at = current
    db.add(access)
    db.commit()

    return PublicQrResolveRead(
        cafe_name=company.trade_name or company.name,
        table_code=table.table_code,
        table_display_name=table.display_name,
        session_public_id=session.public_id,
        guest_access=raw_access,
        guest_expires_at=expires_at,
        ordering_enabled=True,
    )


def _parse_guest_access(raw_access: str) -> tuple[str, str]:
    try:
        public_reference, secret = raw_access.split(".", 1)
    except ValueError:
        _generic_guest_failure()
    if not public_reference or len(secret) < 40:
        _generic_guest_failure()
    return public_reference, secret


def require_guest_context(
    db: Session,
    *,
    session_public_id: str,
    raw_access: str,
    require_open: bool = False,
    now: datetime | None = None,
) -> GuestContext:
    current = now or datetime.now(UTC)
    public_reference, secret = _parse_guest_access(raw_access)
    access = db.scalar(
        select(CafeGuestAccess)
        .where(CafeGuestAccess.public_reference == public_reference)
        .execution_options(scope_bypass=True)
    )
    if access is None or access.revoked_at is not None or _aware(access.expires_at) <= current:
        _generic_guest_failure()
    if not hmac.compare_digest(_sha256(secret), access.token_hash):
        _generic_guest_failure()

    session = db.get(TableSession, access.table_session_id, execution_options={"scope_bypass": True})
    if session is None or session.public_id != session_public_id:
        raise_not_found("Table session not found or unavailable.")
    if session.company_id != access.company_id or session.branch_id != access.branch_id:
        raise_not_found("Table session not found or unavailable.")
    if session.status in {TableSessionStatus.CLOSED, TableSessionStatus.CANCELLED}:
        raise_not_found(SESSION_UNAVAILABLE_MESSAGE)
    if require_open and session.status != TableSessionStatus.OPEN:
        raise_conflict("This table session is no longer accepting items.")

    table = db.get(CafeTable, session.table_id, execution_options={"scope_bypass": True})
    company = db.get(Company, session.company_id, execution_options={"scope_bypass": True})
    branch = db.get(Branch, session.branch_id, execution_options={"scope_bypass": True})
    if (
        table is None
        or company is None
        or branch is None
        or not table.is_active
        or not company.is_active
        or not branch.is_active
        or table.company_id != company.id
        or table.branch_id != branch.id
    ):
        raise_not_found(SESSION_UNAVAILABLE_MESSAGE)

    access.last_used_at = current
    db.flush()
    return GuestContext(access=access, session=session, table=table, company=company, branch=branch)


def _menu_rows(db: Session, context: GuestContext) -> tuple[list[MenuCategory], list[MenuItem]]:
    categories = list(
        db.scalars(
            select(MenuCategory)
            .where(
                MenuCategory.company_id == context.company.id,
                MenuCategory.is_active.is_(True),
                or_(MenuCategory.branch_id.is_(None), MenuCategory.branch_id == context.branch.id),
            )
            .execution_options(scope_bypass=True)
            .order_by(MenuCategory.display_order, MenuCategory.name, MenuCategory.id)
        ).all()
    )
    category_ids = {row.id for row in categories}
    items = list(
        db.scalars(
            select(MenuItem)
            .where(
                MenuItem.company_id == context.company.id,
                MenuItem.is_active.is_(True),
                MenuItem.category_id.in_(category_ids or {-1}),
                or_(MenuItem.branch_id.is_(None), MenuItem.branch_id == context.branch.id),
            )
            .execution_options(scope_bypass=True)
            .order_by(MenuItem.display_order, MenuItem.name, MenuItem.id)
        ).all()
    )
    return categories, items


def get_public_menu(db: Session, *, session_public_id: str, raw_access: str) -> PublicMenuRead:
    context = require_guest_context(
        db,
        session_public_id=session_public_id,
        raw_access=raw_access,
    )
    categories, items = _menu_rows(db, context)
    category_public_ids = {row.id: row.public_id for row in categories}
    db.commit()
    return PublicMenuRead(
        cafe_name=context.company.trade_name or context.company.name,
        table_code=context.table.table_code,
        table_display_name=context.table.display_name,
        session_public_id=context.session.public_id,
        session_status=context.session.status.value,
        categories=[
            PublicMenuCategoryRead(
                public_id=row.public_id,
                name=row.name,
                display_order=row.display_order,
            )
            for row in categories
        ],
        items=[
            PublicMenuItemRead(
                public_id=row.public_id,
                category_public_id=category_public_ids[row.category_id],
                name=row.name,
                description=row.description,
                image_reference=row.image_reference,
                selling_price=row.selling_price,
                preparation_area=row.preparation_area.value,
                available=row.available and context.session.status == TableSessionStatus.OPEN,
                display_order=row.display_order,
            )
            for row in items
        ],
    )


def _request_hash(payload: PublicOrderCreate) -> str:
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return _sha256(serialized)


def _idempotency_hash(*, company_id: int, guest_access_id: int, key: str) -> str:
    return _sha256(f"{company_id}:{guest_access_id}:public_order:{key}")


def _order_number(now: datetime) -> str:
    return f"C{now:%Y%m%d}-{secrets.token_hex(4).upper()}"


def _order_to_read(db: Session, order: CafeOrder, *, replayed: bool = False) -> PublicOrderRead:
    items = list(
        db.scalars(
            select(CafeOrderItem)
            .where(CafeOrderItem.cafe_order_id == order.id)
            .execution_options(scope_bypass=True)
            .order_by(CafeOrderItem.id)
        ).all()
    )
    return PublicOrderRead(
        public_id=order.public_id,
        order_number=order.order_number,
        status=order.status.value,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        estimated_total=order.estimated_total,
        customer_notes=order.customer_notes,
        placed_at=order.placed_at,
        replayed=replayed,
        items=[
            PublicOrderItemRead(
                menu_item_public_id=item.menu_item_public_id_snapshot,
                name=item.menu_item_name_snapshot,
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                line_total=item.line_total,
                status=item.item_status.value,
                notes=item.preparation_notes,
            )
            for item in items
        ],
    )


def create_public_order(
    db: Session,
    *,
    session_public_id: str,
    raw_access: str,
    idempotency_key: str,
    payload: PublicOrderCreate,
) -> PublicOrderRead:
    if not 8 <= len(idempotency_key) <= 200:
        raise_bad_request("Idempotency-Key must be between 8 and 200 characters.")
    context = require_guest_context(
        db,
        session_public_id=session_public_id,
        raw_access=raw_access,
        require_open=True,
    )
    key_hash = _idempotency_hash(
        company_id=context.company.id,
        guest_access_id=context.access.id,
        key=idempotency_key,
    )
    request_hash = _request_hash(payload)
    existing = db.scalar(
        select(CafeOrder)
        .where(
            CafeOrder.company_id == context.company.id,
            CafeOrder.idempotency_key_hash == key_hash,
        )
        .execution_options(scope_bypass=True)
    )
    if existing is not None:
        if existing.request_hash != request_hash or existing.guest_access_id != context.access.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "idempotency_conflict", "message": "This retry key was already used for a different order."},
            )
        db.commit()
        return _order_to_read(db, existing, replayed=True)

    locked_session = db.scalar(
        select(TableSession)
        .where(TableSession.id == context.session.id)
        .with_for_update()
        .execution_options(scope_bypass=True)
    )
    if locked_session is None or locked_session.status != TableSessionStatus.OPEN:
        raise_conflict("This table session is no longer accepting items.")

    requested_ids = [row.menu_item_public_id for row in payload.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise_bad_request("Each menu item may appear only once per order.")
    menu_items = list(
        db.scalars(
            select(MenuItem)
            .where(
                MenuItem.company_id == context.company.id,
                MenuItem.public_id.in_(requested_ids),
                MenuItem.is_active.is_(True),
                MenuItem.available.is_(True),
                or_(MenuItem.branch_id.is_(None), MenuItem.branch_id == context.branch.id),
            )
            .execution_options(scope_bypass=True)
        ).all()
    )
    by_public_id = {row.public_id: row for row in menu_items}
    if set(by_public_id) != set(requested_ids):
        raise_conflict("One or more selected menu items are unavailable.")

    active_categories = set(
        db.scalars(
            select(MenuCategory.id)
            .where(
                MenuCategory.company_id == context.company.id,
                MenuCategory.is_active.is_(True),
                or_(MenuCategory.branch_id.is_(None), MenuCategory.branch_id == context.branch.id),
            )
            .execution_options(scope_bypass=True)
        ).all()
    )
    if any(item.category_id not in active_categories for item in menu_items):
        raise_conflict("One or more selected menu items are unavailable.")

    now = datetime.now(UTC)
    order = CafeOrder(
        public_id=secrets.token_urlsafe(18),
        company_id=context.company.id,
        branch_id=context.branch.id,
        table_session_id=locked_session.id,
        guest_access_id=context.access.id,
        order_number=_order_number(now),
        order_type=locked_session.session_type,
        source_channel=CafeOrderSource.QR_CUSTOMER,
        status=CafeOrderStatus.PLACED,
        subtotal=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        estimated_total=Decimal("0.00"),
        customer_notes=payload.customer_notes,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        placed_at=now,
    )
    db.add(order)
    db.flush()

    subtotal = Decimal("0.00")
    for requested in payload.items:
        menu_item = by_public_id[requested.menu_item_public_id]
        product_sku: str | None = None
        if menu_item.product_id is not None:
            product = db.get(Product, menu_item.product_id, execution_options={"scope_bypass": True})
            if product is None or product.company_id != context.company.id or not product.is_active:
                raise_conflict("One or more selected menu items are unavailable.")
            product_sku = product.sku
        line_total = (menu_item.selling_price * requested.quantity).quantize(Decimal("0.01"))
        subtotal += line_total
        db.add(
            CafeOrderItem(
                company_id=context.company.id,
                branch_id=context.branch.id,
                cafe_order_id=order.id,
                menu_item_id=menu_item.id,
                product_id=menu_item.product_id,
                menu_item_public_id_snapshot=menu_item.public_id,
                menu_item_name_snapshot=menu_item.name,
                product_sku_snapshot=product_sku,
                quantity=requested.quantity,
                unit_price_snapshot=menu_item.selling_price,
                discount_amount=Decimal("0.00"),
                line_total=line_total,
                item_status=CafeOrderItemStatus.PLACED,
                preparation_notes=requested.notes,
                source_channel=CafeOrderSource.QR_CUSTOMER,
            )
        )
    order.subtotal = subtotal
    order.estimated_total = subtotal
    db.add(
        CafeOrderStatusHistory(
            company_id=context.company.id,
            branch_id=context.branch.id,
            cafe_order_id=order.id,
            from_status=None,
            to_status=CafeOrderStatus.PLACED,
            changed_by=None,
            guest_action=True,
            reason="Customer order placed",
            created_at=now,
        )
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CafeOrder)
            .where(
                CafeOrder.company_id == context.company.id,
                CafeOrder.idempotency_key_hash == key_hash,
            )
            .execution_options(scope_bypass=True)
        )
        if existing is not None and existing.request_hash == request_hash and existing.guest_access_id == context.access.id:
            return _order_to_read(db, existing, replayed=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": "This retry key cannot be reused for a different order."},
        )
    db.refresh(order)
    return _order_to_read(db, order)


def list_public_orders(
    db: Session,
    *,
    session_public_id: str,
    raw_access: str,
) -> PublicSessionOrdersRead:
    context = require_guest_context(db, session_public_id=session_public_id, raw_access=raw_access)
    orders = list(
        db.scalars(
            select(CafeOrder)
            .where(
                CafeOrder.company_id == context.company.id,
                CafeOrder.branch_id == context.branch.id,
                CafeOrder.table_session_id == context.session.id,
                CafeOrder.guest_access_id == context.access.id,
                CafeOrder.source_channel == CafeOrderSource.QR_CUSTOMER,
            )
            .execution_options(scope_bypass=True)
            .order_by(CafeOrder.placed_at, CafeOrder.id)
        ).all()
    )
    db.commit()
    return PublicSessionOrdersRead(
        cafe_name=context.company.trade_name or context.company.name,
        table_code=context.table.table_code,
        table_display_name=context.table.display_name,
        session_public_id=context.session.public_id,
        session_status=context.session.status.value,
        orders=[_order_to_read(db, row) for row in orders],
    )


def request_public_bill(
    db: Session,
    *,
    session_public_id: str,
    raw_access: str,
) -> PublicBillRequestRead:
    context = require_guest_context(db, session_public_id=session_public_id, raw_access=raw_access)
    session = db.scalar(
        select(TableSession)
        .where(TableSession.id == context.session.id)
        .with_for_update()
        .execution_options(scope_bypass=True)
    )
    if session is None:
        raise_not_found(SESSION_UNAVAILABLE_MESSAGE)
    if session.status == TableSessionStatus.BILL_REQUESTED and session.bill_requested_at is not None:
        db.commit()
        return PublicBillRequestRead(
            session_public_id=session.public_id,
            session_status=session.status.value,
            bill_requested_at=session.bill_requested_at,
        )
    if session.status != TableSessionStatus.OPEN:
        raise_conflict("A bill cannot be requested for this table session.")
    session.status = TableSessionStatus.BILL_REQUESTED
    session.bill_requested_at = datetime.now(UTC)
    session.version += 1
    db.commit()
    return PublicBillRequestRead(
        session_public_id=session.public_id,
        session_status=session.status.value,
        bill_requested_at=session.bill_requested_at,
    )
