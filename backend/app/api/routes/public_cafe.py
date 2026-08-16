from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.public_cafe import (
    PublicBillRequestRead,
    PublicMenuRead,
    PublicOrderCreate,
    PublicOrderRead,
    PublicQrResolveRead,
    PublicSessionOrdersRead,
)
from app.services.public_cafe import (
    PUBLIC_MAX_BODY_BYTES,
    PUBLIC_READ_LIMIT,
    PUBLIC_RESOLVE_LIMIT,
    PUBLIC_WRITE_LIMIT,
    enforce_public_rate_limit,
    get_public_menu,
    list_public_orders,
    request_public_bill,
)
from app.services.public_cafe_entry import resolve_qr_and_open_visit
from app.services.public_cafe_ordering import create_public_order

router = APIRouter(prefix="/public/cafe", tags=["public-cafe"])
Database = Annotated[Session, Depends(get_db)]
GuestAccess = Annotated[str, Header(alias="X-Guest-Access", min_length=40, max_length=256)]


def _request_ip(request: Request) -> str:
    # Direct client address is used until the Phase 11 trusted-proxy hardening
    # defines which forwarded headers are authoritative.
    return request.client.host if request.client else "unknown"


def _check_declared_body_size(request: Request) -> None:
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        size = int(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_request", "message": "Invalid request size."},
        )
    if size > PUBLIC_MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "payload_too_large", "message": "Request body is too large."},
        )


def _limit(
    db: Session,
    *,
    purpose: str,
    ip: str,
    access: str | None,
    limit: int,
) -> None:
    enforce_public_rate_limit(db, purpose=f"{purpose}:ip", identity=ip, limit=limit)
    if access:
        enforce_public_rate_limit(db, purpose=f"{purpose}:guest", identity=access, limit=limit)


@router.post("/qr/{opaque_token}/resolve", response_model=PublicQrResolveRead)
def resolve_qr(
    opaque_token: str,
    request: Request,
    db: Database,
) -> PublicQrResolveRead:
    ip = _request_ip(request)
    enforce_public_rate_limit(
        db,
        purpose="qr_resolve:ip",
        identity=ip,
        limit=PUBLIC_RESOLVE_LIMIT,
    )
    enforce_public_rate_limit(
        db,
        purpose="qr_resolve:qr",
        identity=opaque_token,
        limit=PUBLIC_RESOLVE_LIMIT,
    )
    return resolve_qr_and_open_visit(db, raw_qr=opaque_token)


@router.get("/sessions/{public_id}/menu", response_model=PublicMenuRead)
def read_menu(
    public_id: str,
    request: Request,
    guest_access: GuestAccess,
    db: Database,
) -> PublicMenuRead:
    _limit(
        db,
        purpose="session_read",
        ip=_request_ip(request),
        access=guest_access,
        limit=PUBLIC_READ_LIMIT,
    )
    return get_public_menu(db, session_public_id=public_id, raw_access=guest_access)


@router.post("/sessions/{public_id}/orders", response_model=PublicOrderRead, status_code=status.HTTP_201_CREATED)
def submit_order(
    public_id: str,
    payload: PublicOrderCreate,
    request: Request,
    guest_access: GuestAccess,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
    db: Database,
) -> PublicOrderRead:
    _check_declared_body_size(request)
    _limit(
        db,
        purpose="order_write",
        ip=_request_ip(request),
        access=guest_access,
        limit=PUBLIC_WRITE_LIMIT,
    )
    return create_public_order(
        db,
        session_public_id=public_id,
        raw_access=guest_access,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.get("/sessions/{public_id}/orders", response_model=PublicSessionOrdersRead)
def read_orders(
    public_id: str,
    request: Request,
    guest_access: GuestAccess,
    db: Database,
) -> PublicSessionOrdersRead:
    _limit(
        db,
        purpose="session_read",
        ip=_request_ip(request),
        access=guest_access,
        limit=PUBLIC_READ_LIMIT,
    )
    return list_public_orders(db, session_public_id=public_id, raw_access=guest_access)


@router.post("/sessions/{public_id}/bill-request", response_model=PublicBillRequestRead)
def request_bill(
    public_id: str,
    request: Request,
    guest_access: GuestAccess,
    db: Database,
) -> PublicBillRequestRead:
    _check_declared_body_size(request)
    _limit(
        db,
        purpose="bill_request",
        ip=_request_ip(request),
        access=guest_access,
        limit=PUBLIC_WRITE_LIMIT,
    )
    return request_public_bill(db, session_public_id=public_id, raw_access=guest_access)
