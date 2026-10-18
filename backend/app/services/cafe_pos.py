"""Atomic POS orchestration of the existing Cafe order and billing services."""
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict
from app.core.scope import ScopeContext
from app.models import CafeOrderStatus, Invoice, PaymentMode, PaymentModeType, User
from app.schemas.cafe_billing import CafeBillRequest, CafeBillResultRead
from app.schemas.cafe_orders import StaffOrderCreate
from app.schemas.cafe_pos import CafeCheckoutRequest
from app.services.cafe_billing import (
    SOURCE_TAKEAWAY, _bill, _hash, _require_cafe_company, _result_for_invoice,
    quote_standalone_order,
)
from app.services.cafe_staff_orders import _resolve_branch, create_staff_order, transition_order
from app.services.governance import ensure_business_day_open
from app.services.business_day import business_today


def checkout(db: Session, *, scope: ScopeContext, user: User, payload: CafeCheckoutRequest,
             idempotency_key: str, request: Request | None = None) -> CafeBillResultRead:
    company = _require_cafe_company(db, scope)
    branch = _resolve_branch(db, scope, payload.branch_id)
    key = _hash(idempotency_key.strip())
    request_hash = _hash(payload.model_dump_json())

    def replay():
        invoice = db.scalar(select(Invoice).where(
            Invoice.company_id == company.id, Invoice.billing_idempotency_key_hash == key))
        if invoice is None:
            return None
        if (invoice.source_type != SOURCE_TAKEAWAY
                or invoice.billing_request_hash != request_hash or invoice.branch_id != branch.id):
            raise_conflict('This checkout key was already used for a different sale.')
        return _result_for_invoice(db, scope=scope, invoice=invoice, replay=True)

    try:
        # Serialize the day boundary and concurrent retries on the authorized branch.
        existing = replay()
        if existing is not None:
            return existing
        ensure_business_day_open(db, company_id=company.id, branch_id=branch.id, business_date=business_today())
        existing = replay()
        if existing is not None:
            return existing
        mode = db.scalar(select(PaymentMode).where(
            PaymentMode.id == payload.payment_mode_id, PaymentMode.company_id == company.id,
            PaymentMode.is_active.is_(True)))
        if mode is None or mode.mode_type not in {PaymentModeType.CASH, PaymentModeType.UPI, PaymentModeType.CARD}:
            raise_bad_request('Select an active Cash, UPI or Card payment mode.')
        order = create_staff_order(db, scope=scope, user=user, payload=StaffOrderCreate(
            order_type=payload.order_type, branch_id=branch.id, items=payload.items), request=request, commit=False)
        source_id = order.public_id
        accepted = transition_order(db, scope=scope, user=user, public_id=source_id,
            expected_version=order.version, target=CafeOrderStatus.ACCEPTED, request=request, commit=False)
        quote = quote_standalone_order(db, scope=scope, order_public_id=source_id)
        return _bill(db, scope=scope, user=user, source_type=SOURCE_TAKEAWAY, source_id=source_id,
            payload=CafeBillRequest(expected_version=accepted.version, payments=[{
                'payment_mode_id': mode.id, 'amount': quote.grand_total,
                'reference_number': payload.reference_number,
            }]), idempotency_key=idempotency_key, request=request, request_hash=request_hash)
    except IntegrityError:
        db.rollback()
        existing = replay()
        if existing is not None:
            return existing
        raise_conflict('Checkout changed concurrently. Retry with the same checkout key.')
    except Exception:
        db.rollback()
        raise
