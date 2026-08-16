from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.api.errors import raise_not_found
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import CafeTable, TableSession, User, UserRole
from app.schemas.cafe import (
    CafeTableCreate,
    CafeTableRead,
    CafeTableUpdate,
    MenuCategoryCreate,
    MenuCategoryRead,
    MenuCategoryUpdate,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemRead,
    MenuItemUpdate,
    PublicQRResolveRead,
    QRPrintDataRead,
    QRPrintDataRequest,
    QRRevokeRead,
    QRRotateRead,
    QRRotateRequest,
    QRTokenStatusRead,
    TableSessionClose,
    TableSessionOpen,
    TableSessionRead,
)
from app.services.cafe import (
    close_table_session,
    create_cafe_table,
    create_menu_category,
    create_menu_item,
    get_active_table_session,
    get_table_qr_status,
    get_table_session,
    list_cafe_tables,
    list_menu_categories,
    list_menu_items,
    open_table_session,
    resolve_public_qr,
    revoke_table_qr,
    rotate_table_qr,
    table_qr_print_data,
    table_to_read,
    update_cafe_table,
    update_menu_category,
    update_menu_item,
    update_menu_item_availability,
)

router = APIRouter(tags=["cafe"])

CafeAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
CafeReadUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.STORE_MANAGER,
            UserRole.ORDER_TAKER,
            UserRole.KITCHEN,
            UserRole.ANALYST,
        )
    ),
]
CafeSessionUser = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER)),
]
CurrentScope = Annotated[ScopeContext, Depends(get_scope_context)]
Database = Annotated[Session, Depends(get_db)]


@router.get("/cafe/menu/categories", response_model=list[MenuCategoryRead])
def read_menu_categories(
    _user: CafeReadUser,
    scope: CurrentScope,
    db: Database,
    branch_id: int | None = None,
    include_inactive: bool = Query(default=False),
) -> list[MenuCategory]:
    return list_menu_categories(
        db,
        scope=scope,
        branch_id=branch_id,
        include_inactive=include_inactive,
    )


@router.post("/cafe/menu/categories", response_model=MenuCategoryRead, status_code=status.HTTP_201_CREATED)
def add_menu_category(
    payload: MenuCategoryCreate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> MenuCategory:
    return create_menu_category(db, scope=scope, payload=payload, user=admin, request=request)


@router.put("/cafe/menu/categories/{category_id}", response_model=MenuCategoryRead)
def edit_menu_category(
    category_id: int,
    payload: MenuCategoryUpdate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> MenuCategory:
    return update_menu_category(
        db,
        scope=scope,
        category_id=category_id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.get("/cafe/menu/items", response_model=list[MenuItemRead])
def read_menu_items(
    _user: CafeReadUser,
    scope: CurrentScope,
    db: Database,
    branch_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    include_inactive: bool = Query(default=False),
) -> list[MenuItem]:
    return list_menu_items(
        db,
        scope=scope,
        branch_id=branch_id,
        category_id=category_id,
        search=search,
        include_inactive=include_inactive,
    )


@router.post("/cafe/menu/items", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
def add_menu_item(
    payload: MenuItemCreate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> MenuItem:
    return create_menu_item(db, scope=scope, payload=payload, user=admin, request=request)


@router.put("/cafe/menu/items/{item_id}", response_model=MenuItemRead)
def edit_menu_item(
    item_id: int,
    payload: MenuItemUpdate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> MenuItem:
    return update_menu_item(
        db,
        scope=scope,
        item_id=item_id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.patch("/cafe/menu/items/{item_id}/availability", response_model=MenuItemRead)
def set_menu_item_availability(
    item_id: int,
    payload: MenuItemAvailabilityUpdate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> MenuItem:
    return update_menu_item_availability(
        db,
        scope=scope,
        item_id=item_id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.get("/cafe/tables", response_model=list[CafeTableRead])
def read_cafe_tables(
    _user: CafeReadUser,
    scope: CurrentScope,
    db: Database,
    branch_id: int | None = None,
    include_inactive: bool = Query(default=False),
) -> list[CafeTableRead]:
    return list_cafe_tables(
        db,
        scope=scope,
        branch_id=branch_id,
        include_inactive=include_inactive,
    )


@router.post("/cafe/tables", response_model=CafeTableRead, status_code=status.HTTP_201_CREATED)
def add_cafe_table(
    payload: CafeTableCreate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> CafeTableRead:
    return create_cafe_table(db, scope=scope, payload=payload, user=admin, request=request)


@router.put("/cafe/tables/{table_id}", response_model=CafeTableRead)
def edit_cafe_table(
    table_id: int,
    payload: CafeTableUpdate,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> CafeTableRead:
    return update_cafe_table(
        db,
        scope=scope,
        table_id=table_id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.post("/cafe/tables/{table_id}/deactivate", response_model=CafeTableRead)
def deactivate_cafe_table(
    table_id: int,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> CafeTableRead:
    table = db.get(CafeTable, table_id)
    if table is None:
        raise_not_found("Cafe table not found.")
    payload = CafeTableUpdate(
        branch_id=table.branch_id,
        table_code=table.table_code,
        display_name=table.display_name,
        capacity=table.capacity,
        area=table.area,
        is_active=False,
        expected_version=table.version,
    )
    return update_cafe_table(
        db,
        scope=scope,
        table_id=table.id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.post("/cafe/tables/{table_id}/qr/rotate", response_model=QRRotateRead)
def rotate_qr(
    table_id: int,
    payload: QRRotateRequest,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> QRRotateRead:
    return rotate_table_qr(
        db,
        scope=scope,
        table_id=table_id,
        payload=payload,
        user=admin,
        request=request,
    )


@router.get("/cafe/tables/{table_id}/qr/status", response_model=QRTokenStatusRead | None)
def read_qr_status(
    table_id: int,
    _admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> QRTokenStatusRead | None:
    return get_table_qr_status(db, scope=scope, table_id=table_id)


@router.post("/cafe/tables/{table_id}/qr/revoke", response_model=QRRevokeRead)
def revoke_qr(
    table_id: int,
    request: Request,
    admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> QRRevokeRead:
    return revoke_table_qr(
        db,
        scope=scope,
        table_id=table_id,
        user=admin,
        request=request,
    )


@router.post("/cafe/tables/{table_id}/qr/print-data", response_model=QRPrintDataRead)
def print_qr_data(
    table_id: int,
    payload: QRPrintDataRequest,
    _admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> QRPrintDataRead:
    return table_qr_print_data(
        db,
        scope=scope,
        table_id=table_id,
        raw_token=payload.raw_token,
        public_base_url=payload.public_base_url,
    )


@router.post("/cafe/table-sessions", response_model=TableSessionRead, status_code=status.HTTP_201_CREATED)
def open_session(
    payload: TableSessionOpen,
    request: Request,
    actor: CafeSessionUser,
    scope: CurrentScope,
    db: Database,
) -> TableSession:
    return open_table_session(db, scope=scope, payload=payload, user=actor, request=request)


@router.get("/cafe/table-sessions/{public_id}", response_model=TableSessionRead)
def read_session(
    public_id: str,
    _actor: CafeSessionUser,
    scope: CurrentScope,
    db: Database,
) -> TableSession:
    return get_table_session(db, scope=scope, public_id=public_id)


@router.get("/cafe/tables/{table_id}/active-session", response_model=TableSessionRead | None)
def read_active_session(
    table_id: int,
    _actor: CafeSessionUser,
    scope: CurrentScope,
    db: Database,
) -> TableSession | None:
    return get_active_table_session(db, scope=scope, table_id=table_id)


@router.post("/cafe/table-sessions/{public_id}/close", response_model=TableSessionRead)
def close_session(
    public_id: str,
    payload: TableSessionClose,
    request: Request,
    actor: CafeSessionUser,
    scope: CurrentScope,
    db: Database,
) -> TableSession:
    return close_table_session(
        db,
        scope=scope,
        public_id=public_id,
        payload=payload,
        user=actor,
        request=request,
    )


@router.post("/public/cafe/qr/{opaque_token}/resolve", response_model=PublicQRResolveRead)
def resolve_qr_token(opaque_token: str, db: Database) -> PublicQRResolveRead:
    # P5 validates the QR and returns only display identity. It deliberately does
    # not open a session or accept an order. P6 owns customer-order lifecycle.
    return resolve_public_qr(db, opaque_token)
