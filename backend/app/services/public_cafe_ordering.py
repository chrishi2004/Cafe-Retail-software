from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request
from app.models import CafeOrder, CafeOrderSource
from app.schemas.public_cafe import PublicOrderCreate, PublicOrderRead
from app.services.cafe_order_engine import CafeOrderLineInput, create_order_snapshot
from app.services.public_cafe import (
    _idempotency_hash,
    _order_to_read,
    _request_hash,
    require_guest_context,
)


def create_public_order(
    db: Session,
    *,
    session_public_id: str,
    raw_access: str,
    idempotency_key: str,
    payload: PublicOrderCreate,
) -> PublicOrderRead:
    """P7-compatible public entry that uses the shared Cafe order engine."""

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
        select(CafeOrder).where(
            CafeOrder.company_id == context.company.id,
            CafeOrder.idempotency_key_hash == key_hash,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash or existing.guest_access_id != context.access.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_conflict",
                    "message": "This retry key was already used for a different order.",
                },
            )
        db.commit()
        return _order_to_read(db, existing, replayed=True)

    order = create_order_snapshot(
        db,
        company_id=context.company.id,
        branch_id=context.branch.id,
        table_session_id=context.session.id,
        order_type=context.session.session_type,
        source_channel=CafeOrderSource.QR_CUSTOMER,
        guest_access_id=context.access.id,
        created_by=None,
        lines=[
            CafeOrderLineInput(
                menu_item_public_id=row.menu_item_public_id,
                quantity=row.quantity,
                notes=row.notes,
            )
            for row in payload.items
        ],
        customer_notes=payload.customer_notes,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        guest_action=True,
        history_reason="Customer order placed",
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CafeOrder).where(
                CafeOrder.company_id == context.company.id,
                CafeOrder.idempotency_key_hash == key_hash,
            )
        )
        if (
            existing is not None
            and existing.request_hash == request_hash
            and existing.guest_access_id == context.access.id
        ):
            return _order_to_read(db, existing, replayed=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "idempotency_conflict",
                "message": "This retry key cannot be reused for a different order.",
            },
        )

    db.refresh(order)
    return _order_to_read(db, order)
