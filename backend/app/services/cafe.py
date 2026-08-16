from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.core.scope import ScopeContext
from app.models import (
    ACTIVE_TABLE_SESSION_STATUSES,
    Branch,
    BusinessType,
    CafeTable,
    Company,
    MenuCategory,
    MenuItem,
    Product,
    TableQRToken,
    TableSession,
    TableSessionStatus,
    User,
)
from app.schemas.cafe import (
    CafeTableCreate,
    CafeTableRead,
    CafeTableUpdate,
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    PublicQRResolveRead,
    QRPrintDataRead,
    QRRevokeRead,
    QRRotateRead,
    QRRotateRequest,
    QRTokenStatusRead,
    TableSessionClose,
    TableSessionOpen,
    TableSessionRead,
)
from app.services.audit import write_audit_log

INVALID_QR_MESSAGE = "QR code is invalid, expired, or revoked."


def ensure_cafe_scope(db: Session, scope: ScopeContext) -> Company:
    if scope.all_companies or scope.company_id is None:
        raise_bad_request("Select the Cafe venture before using Cafe operations.")
    company = db.get(Company, scope.company_id)
    if company is None or not company.is_active or company.business_type != BusinessType.CAFE:
        raise_forbidden("Cafe operations are not available to this venture.")
    return company


def _branch_for_company(db: Session, *, company_id: int, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id, execution_options={"scope_bypass": True})
    if branch is None or not branch.is_active or branch.company_id != company_id:
        raise_bad_request("Branch is not available to the selected Cafe venture.")
    return branch


def _validate_optional_branch(db: Session, *, company_id: int, branch_id: int | None) -> None:
    if branch_id is not None:
        _branch_for_company(db, company_id=company_id, branch_id=branch_id)


def _menu_branch_filter(statement, scope: ScopeContext, model, branch_id: int | None):
    if branch_id is not None:
        if scope.branch_ids and branch_id not in scope.branch_ids:
            raise_forbidden("You can only access your assigned Cafe branch.")
        return statement.where(or_(model.branch_id.is_(None), model.branch_id == branch_id))
    if scope.branch_ids:
        return statement.where(or_(model.branch_id.is_(None), model.branch_id.in_(scope.branch_ids)))
    return statement


def list_menu_categories(
    db: Session,
    *,
    scope: ScopeContext,
    branch_id: int | None = None,
    include_inactive: bool = False,
) -> list[MenuCategory]:
    company = ensure_cafe_scope(db, scope)
    if branch_id is not None:
        _branch_for_company(db, company_id=company.id, branch_id=branch_id)
    statement = select(MenuCategory).order_by(MenuCategory.display_order, MenuCategory.name, MenuCategory.id)
    statement = _menu_branch_filter(statement, scope, MenuCategory, branch_id)
    if not include_inactive:
        statement = statement.where(MenuCategory.is_active.is_(True))
    return list(db.scalars(statement).all())


def _duplicate_category(
    db: Session,
    *,
    company_id: int,
    branch_id: int | None,
    name: str,
    exclude_id: int | None = None,
) -> bool:
    statement = select(MenuCategory.id).where(
        MenuCategory.company_id == company_id,
        func.lower(MenuCategory.name) == name.lower(),
    )
    if branch_id is None:
        statement = statement.where(MenuCategory.branch_id.is_(None))
    else:
        statement = statement.where(MenuCategory.branch_id == branch_id)
    if exclude_id is not None:
        statement = statement.where(MenuCategory.id != exclude_id)
    return db.scalar(statement) is not None


def create_menu_category(
    db: Session,
    *,
    scope: ScopeContext,
    payload: MenuCategoryCreate,
    user: User,
    request: Request | None,
) -> MenuCategory:
    company = ensure_cafe_scope(db, scope)
    _validate_optional_branch(db, company_id=company.id, branch_id=payload.branch_id)
    if _duplicate_category(db, company_id=company.id, branch_id=payload.branch_id, name=payload.name):
        raise_conflict("A Cafe menu category with this name already exists in this menu scope.")
    category = MenuCategory(company_id=company.id, **payload.model_dump())
    db.add(category)
    db.flush()
    write_audit_log(
        db,
        action="cafe.menu_category.created",
        entity_type="menu_category",
        entity_id=category.id,
        user=user,
        company_id=company.id,
        new_value_json={"name": category.name, "branch_id": category.branch_id},
        request=request,
    )
    db.commit()
    db.refresh(category)
    return category


def update_menu_category(
    db: Session,
    *,
    scope: ScopeContext,
    category_id: int,
    payload: MenuCategoryUpdate,
    user: User,
    request: Request | None,
) -> MenuCategory:
    company = ensure_cafe_scope(db, scope)
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise_not_found("Cafe menu category not found.")
    _validate_optional_branch(db, company_id=company.id, branch_id=payload.branch_id)
    if _duplicate_category(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        name=payload.name,
        exclude_id=category.id,
    ):
        raise_conflict("A Cafe menu category with this name already exists in this menu scope.")
    old = {"name": category.name, "branch_id": category.branch_id, "is_active": category.is_active}
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    write_audit_log(
        db,
        action="cafe.menu_category.updated",
        entity_type="menu_category",
        entity_id=category.id,
        user=user,
        company_id=company.id,
        old_value_json=old,
        new_value_json={"name": category.name, "branch_id": category.branch_id, "is_active": category.is_active},
        request=request,
    )
    db.commit()
    db.refresh(category)
    return category


def list_menu_items(
    db: Session,
    *,
    scope: ScopeContext,
    branch_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    include_inactive: bool = False,
) -> list[MenuItem]:
    company = ensure_cafe_scope(db, scope)
    if branch_id is not None:
        _branch_for_company(db, company_id=company.id, branch_id=branch_id)
    statement = select(MenuItem).order_by(MenuItem.display_order, MenuItem.name, MenuItem.id)
    statement = _menu_branch_filter(statement, scope, MenuItem, branch_id)
    if category_id is not None:
        statement = statement.where(MenuItem.category_id == category_id)
    if search and search.strip():
        pattern = f"%{search.strip().lower()}%"
        statement = statement.where(func.lower(MenuItem.name).like(pattern))
    if not include_inactive:
        statement = statement.where(MenuItem.is_active.is_(True))
    return list(db.scalars(statement).all())


def _validate_menu_references(
    db: Session,
    *,
    company_id: int,
    branch_id: int | None,
    category_id: int,
    product_id: int | None,
) -> None:
    _validate_optional_branch(db, company_id=company_id, branch_id=branch_id)
    category = db.get(MenuCategory, category_id, execution_options={"scope_bypass": True})
    if category is None or category.company_id != company_id:
        raise_bad_request("Menu category is not available to the selected Cafe venture.")
    if category.branch_id is not None and branch_id is not None and category.branch_id != branch_id:
        raise_bad_request("Menu item branch does not match its branch-specific category.")
    if category.branch_id is not None and branch_id is None:
        raise_bad_request("A company-wide menu item cannot use a branch-specific category.")
    if product_id is not None:
        product = db.get(Product, product_id, execution_options={"scope_bypass": True})
        if product is None or product.company_id != company_id or not product.is_active:
            raise_bad_request("Linked product is not available to the selected Cafe venture.")


def create_menu_item(
    db: Session,
    *,
    scope: ScopeContext,
    payload: MenuItemCreate,
    user: User,
    request: Request | None,
) -> MenuItem:
    company = ensure_cafe_scope(db, scope)
    _validate_menu_references(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        category_id=payload.category_id,
        product_id=payload.product_id,
    )
    item = MenuItem(company_id=company.id, **payload.model_dump())
    db.add(item)
    db.flush()
    write_audit_log(
        db,
        action="cafe.menu_item.created",
        entity_type="menu_item",
        entity_id=item.id,
        user=user,
        company_id=company.id,
        new_value_json={
            "name": item.name,
            "branch_id": item.branch_id,
            "category_id": item.category_id,
            "product_id": item.product_id,
            "selling_price": str(item.selling_price),
            "preparation_area": item.preparation_area.value,
        },
        request=request,
    )
    db.commit()
    db.refresh(item)
    return item


def _check_version(current: int, expected: int | None) -> None:
    if expected is not None and current != expected:
        raise_conflict("This record changed since it was loaded. Refresh and try again.")


def update_menu_item(
    db: Session,
    *,
    scope: ScopeContext,
    item_id: int,
    payload: MenuItemUpdate,
    user: User,
    request: Request | None,
) -> MenuItem:
    company = ensure_cafe_scope(db, scope)
    item = db.get(MenuItem, item_id)
    if item is None:
        raise_not_found("Cafe menu item not found.")
    _check_version(item.version, payload.expected_version)
    _validate_menu_references(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        category_id=payload.category_id,
        product_id=payload.product_id,
    )
    old = {
        "name": item.name,
        "selling_price": str(item.selling_price),
        "available": item.available,
        "is_active": item.is_active,
        "version": item.version,
    }
    data = payload.model_dump(exclude={"expected_version"})
    for key, value in data.items():
        setattr(item, key, value)
    item.version += 1
    write_audit_log(
        db,
        action="cafe.menu_item.updated",
        entity_type="menu_item",
        entity_id=item.id,
        user=user,
        company_id=company.id,
        old_value_json=old,
        new_value_json={
            "name": item.name,
            "selling_price": str(item.selling_price),
            "available": item.available,
            "is_active": item.is_active,
            "version": item.version,
        },
        request=request,
    )
    db.commit()
    db.refresh(item)
    return item


def update_menu_item_availability(
    db: Session,
    *,
    scope: ScopeContext,
    item_id: int,
    payload: MenuItemAvailabilityUpdate,
    user: User,
    request: Request | None,
) -> MenuItem:
    company = ensure_cafe_scope(db, scope)
    item = db.get(MenuItem, item_id)
    if item is None:
        raise_not_found("Cafe menu item not found.")
    _check_version(item.version, payload.expected_version)
    old_available = item.available
    item.available = payload.available
    item.version += 1
    write_audit_log(
        db,
        action="cafe.menu_item.availability_updated",
        entity_type="menu_item",
        entity_id=item.id,
        user=user,
        company_id=company.id,
        old_value_json={"available": old_available},
        new_value_json={"available": item.available, "version": item.version},
        request=request,
    )
    db.commit()
    db.refresh(item)
    return item


def _active_session_for_table(db: Session, table_id: int) -> TableSession | None:
    return db.scalar(
        select(TableSession)
        .where(
            TableSession.table_id == table_id,
            TableSession.status.in_(ACTIVE_TABLE_SESSION_STATUSES),
        )
        .order_by(TableSession.opened_at.desc(), TableSession.id.desc())
    )


def _active_qr_for_table(db: Session, table_id: int, *, now: datetime | None = None) -> TableQRToken | None:
    current = now or datetime.now(UTC)
    return db.scalar(
        select(TableQRToken)
        .where(
            TableQRToken.table_id == table_id,
            TableQRToken.revoked_at.is_(None),
            or_(TableQRToken.expires_at.is_(None), TableQRToken.expires_at > current),
        )
        .order_by(TableQRToken.created_at.desc(), TableQRToken.id.desc())
    )


def table_to_read(db: Session, table: CafeTable) -> CafeTableRead:
    session = _active_session_for_table(db, table.id)
    qr = _active_qr_for_table(db, table.id)
    return CafeTableRead(
        id=table.id,
        company_id=table.company_id,
        branch_id=table.branch_id,
        table_code=table.table_code,
        display_name=table.display_name,
        capacity=table.capacity,
        area=table.area,
        is_active=table.is_active,
        version=table.version,
        active_session_public_id=session.public_id if session else None,
        active_session_status=session.status if session else None,
        qr_active=qr is not None,
        qr_public_reference=qr.public_reference if qr else None,
        created_at=table.created_at,
        updated_at=table.updated_at,
    )


def list_cafe_tables(
    db: Session,
    *,
    scope: ScopeContext,
    branch_id: int | None = None,
    include_inactive: bool = False,
) -> list[CafeTableRead]:
    company = ensure_cafe_scope(db, scope)
    if branch_id is not None:
        _branch_for_company(db, company_id=company.id, branch_id=branch_id)
        if scope.branch_ids and branch_id not in scope.branch_ids:
            raise_forbidden("You can only access your assigned Cafe branch.")
    statement = select(CafeTable).order_by(CafeTable.area, CafeTable.table_code, CafeTable.id)
    if branch_id is not None:
        statement = statement.where(CafeTable.branch_id == branch_id)
    if not include_inactive:
        statement = statement.where(CafeTable.is_active.is_(True))
    return [table_to_read(db, table) for table in db.scalars(statement).all()]


def _duplicate_table_code(
    db: Session,
    *,
    company_id: int,
    branch_id: int,
    table_code: str,
    exclude_id: int | None = None,
) -> bool:
    statement = select(CafeTable.id).where(
        CafeTable.company_id == company_id,
        CafeTable.branch_id == branch_id,
        func.upper(CafeTable.table_code) == table_code.upper(),
    )
    if exclude_id is not None:
        statement = statement.where(CafeTable.id != exclude_id)
    return db.scalar(statement) is not None


def create_cafe_table(
    db: Session,
    *,
    scope: ScopeContext,
    payload: CafeTableCreate,
    user: User,
    request: Request | None,
) -> CafeTableRead:
    company = ensure_cafe_scope(db, scope)
    _branch_for_company(db, company_id=company.id, branch_id=payload.branch_id)
    if _duplicate_table_code(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        table_code=payload.table_code,
    ):
        raise_conflict("This table code already exists in the selected Cafe branch.")
    table = CafeTable(company_id=company.id, **payload.model_dump())
    db.add(table)
    db.flush()
    write_audit_log(
        db,
        action="cafe.table.created",
        entity_type="cafe_table",
        entity_id=table.id,
        user=user,
        company_id=company.id,
        new_value_json={"branch_id": table.branch_id, "table_code": table.table_code, "display_name": table.display_name},
        request=request,
    )
    db.commit()
    db.refresh(table)
    return table_to_read(db, table)


def update_cafe_table(
    db: Session,
    *,
    scope: ScopeContext,
    table_id: int,
    payload: CafeTableUpdate,
    user: User,
    request: Request | None,
) -> CafeTableRead:
    company = ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    _check_version(table.version, payload.expected_version)
    _branch_for_company(db, company_id=company.id, branch_id=payload.branch_id)
    if _duplicate_table_code(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        table_code=payload.table_code,
        exclude_id=table.id,
    ):
        raise_conflict("This table code already exists in the selected Cafe branch.")
    if not payload.is_active and _active_session_for_table(db, table.id) is not None:
        raise_conflict("Close the active table session before deactivating this table.")
    old = {
        "branch_id": table.branch_id,
        "table_code": table.table_code,
        "display_name": table.display_name,
        "is_active": table.is_active,
        "version": table.version,
    }
    for key, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(table, key, value)
    table.version += 1
    write_audit_log(
        db,
        action="cafe.table.updated",
        entity_type="cafe_table",
        entity_id=table.id,
        user=user,
        company_id=company.id,
        old_value_json=old,
        new_value_json={
            "branch_id": table.branch_id,
            "table_code": table.table_code,
            "display_name": table.display_name,
            "is_active": table.is_active,
            "version": table.version,
        },
        request=request,
    )
    db.commit()
    db.refresh(table)
    return table_to_read(db, table)


def _generate_qr_credential() -> tuple[str, str, str, str]:
    # token_bytes(32) gives 256 bits of cryptographic randomness for the secret.
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    public_reference = secrets.token_urlsafe(16)
    raw_token = f"{public_reference}.{secret}"
    token_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    token_prefix = secret[:10]
    return public_reference, secret, raw_token, token_hash


def _qr_payload(base_url: str, raw_token: str) -> str:
    return f"{base_url.rstrip('/')}/{raw_token}"


def rotate_table_qr(
    db: Session,
    *,
    scope: ScopeContext,
    table_id: int,
    payload: QRRotateRequest,
    user: User,
    request: Request | None,
) -> QRRotateRead:
    company = ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None or not table.is_active:
        raise_not_found("Active Cafe table not found.")
    now = datetime.now(UTC)
    for existing in db.scalars(
        select(TableQRToken).where(TableQRToken.table_id == table.id, TableQRToken.revoked_at.is_(None))
    ).all():
        existing.revoked_at = now

    public_reference, _secret, raw_token, token_hash = _generate_qr_credential()
    token = TableQRToken(
        company_id=company.id,
        branch_id=table.branch_id,
        table_id=table.id,
        public_reference=public_reference,
        token_hash=token_hash,
        token_prefix=raw_token.split(".", 1)[1][:10],
        expires_at=now + timedelta(days=payload.expires_in_days),
        created_by=user.id,
    )
    db.add(token)
    db.flush()
    write_audit_log(
        db,
        action="cafe.table_qr.rotated",
        entity_type="table_qr_token",
        entity_id=token.id,
        user=user,
        company_id=company.id,
        new_value_json={
            "table_id": table.id,
            "public_reference": token.public_reference,
            "token_prefix": token.token_prefix,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        },
        request=request,
        notes="Raw QR secret intentionally omitted from audit data.",
    )
    db.commit()
    db.refresh(token)
    return QRRotateRead(
        table_code=table.table_code,
        table_display_name=table.display_name,
        qr_payload=_qr_payload(payload.public_base_url, raw_token),
        public_reference=token.public_reference,
        token_prefix=token.token_prefix,
        expires_at=token.expires_at,
        raw_token=raw_token,
    )


def _token_is_active(token: TableQRToken, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    expires_at = token.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return token.revoked_at is None and (expires_at is None or expires_at > current)


def get_table_qr_status(db: Session, *, scope: ScopeContext, table_id: int) -> QRTokenStatusRead | None:
    ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    token = db.scalar(
        select(TableQRToken)
        .where(TableQRToken.table_id == table.id)
        .order_by(TableQRToken.created_at.desc(), TableQRToken.id.desc())
    )
    if token is None:
        return None
    return QRTokenStatusRead(
        public_reference=token.public_reference,
        token_prefix=token.token_prefix,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
        last_used_at=token.last_used_at,
        active=_token_is_active(token),
        created_at=token.created_at,
    )


def revoke_table_qr(
    db: Session,
    *,
    scope: ScopeContext,
    table_id: int,
    user: User,
    request: Request | None,
) -> QRRevokeRead:
    company = ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    token = _active_qr_for_table(db, table.id)
    if token is None:
        raise_not_found("Active QR token not found for this table.")
    token.revoked_at = datetime.now(UTC)
    write_audit_log(
        db,
        action="cafe.table_qr.revoked",
        entity_type="table_qr_token",
        entity_id=token.id,
        user=user,
        company_id=company.id,
        new_value_json={"table_id": table.id, "public_reference": token.public_reference},
        request=request,
    )
    db.commit()
    return QRRevokeRead(public_reference=token.public_reference, revoked_at=token.revoked_at)


def _parse_raw_token(raw_token: str) -> tuple[str, str]:
    try:
        public_reference, secret = raw_token.split(".", 1)
    except ValueError:
        raise_not_found(INVALID_QR_MESSAGE)
    if not public_reference or len(secret) < 40:
        raise_not_found(INVALID_QR_MESSAGE)
    return public_reference, secret


def _resolve_qr_record(db: Session, raw_token: str, *, update_last_used: bool) -> tuple[TableQRToken, CafeTable, Company]:
    public_reference, secret = _parse_raw_token(raw_token)
    token = db.scalar(
        select(TableQRToken)
        .where(TableQRToken.public_reference == public_reference)
        .execution_options(scope_bypass=True)
    )
    if token is None or not _token_is_active(token):
        raise_not_found(INVALID_QR_MESSAGE)
    candidate_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate_hash, token.token_hash):
        raise_not_found(INVALID_QR_MESSAGE)
    table = db.get(CafeTable, token.table_id, execution_options={"scope_bypass": True})
    company = db.get(Company, token.company_id, execution_options={"scope_bypass": True})
    branch = db.get(Branch, token.branch_id, execution_options={"scope_bypass": True})
    if (
        table is None
        or company is None
        or branch is None
        or not table.is_active
        or not company.is_active
        or not branch.is_active
        or company.business_type != BusinessType.CAFE
        or table.company_id != company.id
        or table.branch_id != branch.id
    ):
        raise_not_found(INVALID_QR_MESSAGE)
    if update_last_used:
        token.last_used_at = datetime.now(UTC)
        db.commit()
    return token, table, company


def table_qr_print_data(
    db: Session,
    *,
    scope: ScopeContext,
    table_id: int,
    raw_token: str,
    public_base_url: str,
) -> QRPrintDataRead:
    company = ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    token, resolved_table, resolved_company = _resolve_qr_record(db, raw_token, update_last_used=False)
    if resolved_table.id != table.id or resolved_company.id != company.id:
        raise_not_found("QR token is not available to this table.")
    return QRPrintDataRead(
        table_code=table.table_code,
        table_display_name=table.display_name,
        qr_payload=_qr_payload(public_base_url, raw_token),
        public_reference=token.public_reference,
        token_prefix=token.token_prefix,
        expires_at=token.expires_at,
    )


def resolve_public_qr(db: Session, raw_token: str) -> PublicQRResolveRead:
    _token, table, company = _resolve_qr_record(db, raw_token, update_last_used=True)
    return PublicQRResolveRead(
        cafe_name=company.trade_name or company.name,
        table_code=table.table_code,
        table_display_name=table.display_name,
        ordering_enabled=False,
        message="QR verified. Customer ordering remains disabled until later release gates pass.",
    )


def open_table_session(
    db: Session,
    *,
    scope: ScopeContext,
    payload: TableSessionOpen,
    user: User,
    request: Request | None,
) -> TableSession:
    company = ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, payload.table_id)
    if table is None or not table.is_active:
        raise_not_found("Active Cafe table not found.")
    existing = _active_session_for_table(db, table.id)
    if existing is not None:
        raise_conflict("This table already has an active session.")
    session = TableSession(
        company_id=company.id,
        branch_id=table.branch_id,
        table_id=table.id,
        public_id=secrets.token_urlsafe(18),
        session_type=payload.session_type,
        status=TableSessionStatus.OPEN,
        opened_by=user.id,
        opened_at=datetime.now(UTC),
    )
    db.add(session)
    try:
        db.flush()
        write_audit_log(
            db,
            action="cafe.table_session.opened",
            entity_type="table_session",
            entity_id=session.id,
            user=user,
            company_id=company.id,
            new_value_json={
                "public_id": session.public_id,
                "table_id": table.id,
                "session_type": session.session_type.value,
            },
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise_conflict("This table already has an active session.")
    db.refresh(session)
    return session


def get_table_session(
    db: Session,
    *,
    scope: ScopeContext,
    public_id: str,
) -> TableSession:
    ensure_cafe_scope(db, scope)
    session = db.scalar(select(TableSession).where(TableSession.public_id == public_id))
    if session is None:
        raise_not_found("Cafe table session not found.")
    return session


def get_active_table_session(
    db: Session,
    *,
    scope: ScopeContext,
    table_id: int,
) -> TableSession | None:
    ensure_cafe_scope(db, scope)
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    return _active_session_for_table(db, table.id)


def close_table_session(
    db: Session,
    *,
    scope: ScopeContext,
    public_id: str,
    payload: TableSessionClose,
    user: User,
    request: Request | None,
) -> TableSession:
    company = ensure_cafe_scope(db, scope)
    session = get_table_session(db, scope=scope, public_id=public_id)
    if session.status not in {
        TableSessionStatus.OPEN,
        TableSessionStatus.BILL_REQUESTED,
        TableSessionStatus.BILLED,
    }:
        raise_conflict("This table session is already closed.")
    _check_version(session.version, payload.expected_version)
    old_status = session.status
    session.status = TableSessionStatus.CANCELLED if payload.cancel else TableSessionStatus.CLOSED
    session.closed_by = user.id
    session.closed_at = datetime.now(UTC)
    session.version += 1
    write_audit_log(
        db,
        action="cafe.table_session.closed" if not payload.cancel else "cafe.table_session.cancelled",
        entity_type="table_session",
        entity_id=session.id,
        user=user,
        company_id=company.id,
        old_value_json={"status": old_status.value},
        new_value_json={"status": session.status.value, "version": session.version},
        request=request,
    )
    db.commit()
    db.refresh(session)
    return session
