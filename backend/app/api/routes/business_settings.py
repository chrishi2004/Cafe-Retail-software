from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.errors import raise_bad_request
from app.db.session import get_db
from app.models import TaxMode, User
from app.schemas.business_settings import (
    BusinessProfilePayload,
    BusinessProfileRead,
    InvoiceSequenceCreate,
    InvoiceSequenceRead,
    InvoiceSequenceUpdate,
    PaymentModeCreate,
    PaymentModeRead,
    PaymentModeUpdate,
    TaxRateCreate,
    TaxRateRead,
    TaxRateUpdate,
)
from app.services.business_settings import (
    create_invoice_sequence,
    create_payment_mode,
    create_tax_rate,
    get_business_profile,
    list_invoice_sequences,
    list_payment_modes,
    list_tax_rates,
    update_invoice_sequence,
    update_payment_mode,
    update_tax_rate,
    upsert_business_profile,
)

router = APIRouter(tags=["business settings"])


@router.get("/business-profile", response_model=BusinessProfileRead)
def read_business_profile(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessProfileRead:
    return get_business_profile(db)


@router.put("/business-profile", response_model=BusinessProfileRead)
def update_business_profile(
    payload: BusinessProfilePayload,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessProfileRead:
    try:
        current = get_business_profile(db)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # The legacy profile endpoint may still create the first business
        # profile, but P4 requires that first operational state to be Non-GST.
        if payload.default_tax_mode != TaxMode.NON_GST:
            raise_bad_request("Initial business operation must start in Non-GST mode.")
    else:
        if payload.default_tax_mode != current.default_tax_mode:
            raise_bad_request("Tax mode is controlled by the guarded tax-operation workflow.")
    return upsert_business_profile(db, payload=payload, user=admin, request=request)


@router.get("/tax-rates", response_model=list[TaxRateRead])
def read_tax_rates(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
):
    return list_tax_rates(db, include_inactive=include_inactive)


@router.post("/tax-rates", response_model=TaxRateRead, status_code=status.HTTP_201_CREATED)
def add_tax_rate(
    payload: TaxRateCreate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return create_tax_rate(db, payload=payload, user=admin, request=request)


@router.put("/tax-rates/{tax_rate_id}", response_model=TaxRateRead)
def edit_tax_rate(
    tax_rate_id: int,
    payload: TaxRateUpdate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return update_tax_rate(db, tax_rate_id=tax_rate_id, payload=payload, user=admin, request=request)


@router.get("/payment-modes", response_model=list[PaymentModeRead])
def read_payment_modes(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
):
    return list_payment_modes(db, include_inactive=include_inactive)


@router.post("/payment-modes", response_model=PaymentModeRead, status_code=status.HTTP_201_CREATED)
def add_payment_mode(
    payload: PaymentModeCreate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return create_payment_mode(db, payload=payload, user=admin, request=request)


@router.put("/payment-modes/{payment_mode_id}", response_model=PaymentModeRead)
def edit_payment_mode(
    payment_mode_id: int,
    payload: PaymentModeUpdate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return update_payment_mode(db, payment_mode_id=payment_mode_id, payload=payload, user=admin, request=request)


@router.get("/invoice-sequences", response_model=list[InvoiceSequenceRead])
def read_invoice_sequences(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[InvoiceSequenceRead]:
    return list_invoice_sequences(db, include_inactive=include_inactive)


@router.post("/invoice-sequences", response_model=InvoiceSequenceRead, status_code=status.HTTP_201_CREATED)
def add_invoice_sequence(
    payload: InvoiceSequenceCreate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceSequenceRead:
    return create_invoice_sequence(db, payload=payload, user=admin, request=request)


@router.put("/invoice-sequences/{sequence_id}", response_model=InvoiceSequenceRead)
def edit_invoice_sequence(
    sequence_id: int,
    payload: InvoiceSequenceUpdate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceSequenceRead:
    return update_invoice_sequence(db, sequence_id=sequence_id, payload=payload, user=admin, request=request)
