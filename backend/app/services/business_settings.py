from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import raise_conflict, raise_not_found
from app.models import (
    BusinessProfile,
    Company,
    GSTRegistration,
    InvoiceSequence,
    InvoiceSequenceType,
    PaymentMode,
    TaxRate,
    User,
)
from app.schemas.business_settings import (
    BusinessProfilePayload,
    BusinessProfileRead,
    InvoiceSequenceCreate,
    InvoiceSequenceRead,
    InvoiceSequenceUpdate,
    PaymentModeCreate,
    PaymentModeUpdate,
    TaxRateCreate,
    TaxRateUpdate,
)
from app.services.audit import write_audit_log


def preview_invoice_number(sequence: InvoiceSequence, number: int | None = None) -> str:
    current = sequence.next_number if number is None else number
    padded = f"{current:0{sequence.padding}d}"
    return f"{sequence.prefix}{padded}{sequence.suffix or ''}"


def get_default_company(db: Session) -> Company:
    company = db.scalar(select(Company).where(Company.is_active.is_(True)).order_by(Company.id))
    if company is None:
        raise_not_found("Business profile is not configured yet.")
    return company


def get_business_profile(db: Session) -> BusinessProfileRead:
    profile = db.scalar(select(BusinessProfile).order_by(BusinessProfile.id))
    if profile is None:
        raise_not_found("Business profile is not configured yet.")
    company = db.get(Company, profile.company_id)
    if company is None:
        raise_not_found("Configured company record was not found.")
    gst_registration = db.scalar(
        select(GSTRegistration)
        .where(
            GSTRegistration.company_id == company.id,
            GSTRegistration.is_primary.is_(True),
        )
        .order_by(GSTRegistration.id)
    )
    return business_profile_to_read(company, profile, gst_registration)


def business_profile_to_read(
    company: Company,
    profile: BusinessProfile,
    gst_registration: GSTRegistration | None,
) -> BusinessProfileRead:
    return BusinessProfileRead(
        company_id=company.id,
        business_profile_id=profile.id,
        gst_registration_id=gst_registration.id if gst_registration else None,
        company_code=company.code,
        legal_name=profile.legal_name,
        trade_name=profile.trade_name,
        pan=profile.pan,
        email=profile.email,
        phone=profile.phone,
        address=profile.address,
        city=profile.city,
        state=profile.state,
        state_code=profile.state_code,
        pincode=profile.pincode,
        gstin=gst_registration.gstin if gst_registration else None,
        default_tax_mode=profile.default_tax_mode,
        default_currency=profile.default_currency,
        terms_and_conditions=profile.terms_and_conditions,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def upsert_business_profile(
    db: Session,
    *,
    payload: BusinessProfilePayload,
    user: User,
    request,
) -> BusinessProfileRead:
    company = db.scalar(select(Company).order_by(Company.id))
    old_value = None
    if company is None:
        company = Company(
            code=payload.company_code,
            name=payload.trade_name or payload.legal_name,
            legal_name=payload.legal_name,
            trade_name=payload.trade_name,
            pan=payload.pan,
            default_currency=payload.default_currency,
        )
        db.add(company)
        db.flush()
        profile = BusinessProfile(
            company_id=company.id,
            legal_name=payload.legal_name,
            trade_name=payload.trade_name,
            pan=payload.pan,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            state_code=payload.state_code,
            pincode=payload.pincode,
            default_tax_mode=payload.default_tax_mode,
            default_currency=payload.default_currency,
            terms_and_conditions=payload.terms_and_conditions,
        )
        db.add(profile)
        db.flush()
    else:
        profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company.id))
        if profile is None:
            profile = BusinessProfile(
                company_id=company.id,
                legal_name=payload.legal_name,
                default_tax_mode=payload.default_tax_mode,
                default_currency=payload.default_currency,
            )
            db.add(profile)
            db.flush()
        old_value = business_profile_to_read(
            company,
            profile,
            db.scalar(
                select(GSTRegistration)
                .where(
                    GSTRegistration.company_id == company.id,
                    GSTRegistration.is_primary.is_(True),
                )
                .order_by(GSTRegistration.id)
            ),
        ).model_dump(mode="json")
        company.code = payload.company_code
        company.name = payload.trade_name or payload.legal_name
        company.legal_name = payload.legal_name
        company.trade_name = payload.trade_name
        company.pan = payload.pan
        company.default_currency = payload.default_currency
        profile.legal_name = payload.legal_name
        profile.trade_name = payload.trade_name
        profile.pan = payload.pan
        profile.email = payload.email
        profile.phone = payload.phone
        profile.address = payload.address
        profile.city = payload.city
        profile.state = payload.state
        profile.state_code = payload.state_code
        profile.pincode = payload.pincode
        profile.default_tax_mode = payload.default_tax_mode
        profile.default_currency = payload.default_currency
        profile.terms_and_conditions = payload.terms_and_conditions

    gst_registration = db.scalar(
        select(GSTRegistration)
        .where(
            GSTRegistration.company_id == company.id,
            GSTRegistration.is_primary.is_(True),
        )
        .order_by(GSTRegistration.id)
    )
    if payload.gstin or payload.state_code or payload.state:
        if gst_registration is None:
            gst_registration = GSTRegistration(
                company_id=company.id,
                branch_id=None,
                gstin=payload.gstin,
                legal_name=payload.legal_name,
                trade_name=payload.trade_name,
                state=payload.state or "Not configured",
                state_code=payload.state_code or "00",
                address=payload.address,
                pincode=payload.pincode,
                is_primary=True,
                is_active=True,
            )
            db.add(gst_registration)
        else:
            gst_registration.gstin = payload.gstin
            gst_registration.legal_name = payload.legal_name
            gst_registration.trade_name = payload.trade_name
            gst_registration.state = payload.state or gst_registration.state
            gst_registration.state_code = payload.state_code or gst_registration.state_code
            gst_registration.address = payload.address
            gst_registration.pincode = payload.pincode

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise_conflict("Business profile conflicts with an existing company code, name, or GSTIN.")

    result = business_profile_to_read(company, profile, gst_registration)
    write_audit_log(
        db,
        action="business_profile.upsert",
        entity_type="business_profile",
        entity_id=profile.id,
        user=user,
        old_value_json=old_value,
        new_value_json=result.model_dump(mode="json"),
        request=request,
    )
    db.commit()
    return get_business_profile(db)


def list_tax_rates(db: Session, *, include_inactive: bool = False) -> list[TaxRate]:
    statement = select(TaxRate).order_by(TaxRate.rate_percent, TaxRate.name)
    if not include_inactive:
        statement = statement.where(TaxRate.is_active.is_(True))
    return list(db.scalars(statement).all())


def ensure_tax_rate_name_available(db: Session, name: str, tax_rate_id: int | None = None) -> None:
    existing = db.scalar(select(TaxRate).where(TaxRate.name == name))
    if existing is not None and existing.id != tax_rate_id:
        raise_conflict("Tax rate name already exists.")


def create_tax_rate(db: Session, *, payload: TaxRateCreate, user: User, request) -> TaxRate:
    ensure_tax_rate_name_available(db, payload.name)
    tax_rate = TaxRate(**payload.model_dump())
    db.add(tax_rate)
    db.flush()
    write_audit_log(
        db,
        action="tax_rate.create",
        entity_type="tax_rate",
        entity_id=tax_rate.id,
        user=user,
        new_value_json=payload.model_dump(mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(tax_rate)
    return tax_rate


def update_tax_rate(db: Session, *, tax_rate_id: int, payload: TaxRateUpdate, user: User, request) -> TaxRate:
    tax_rate = db.get(TaxRate, tax_rate_id)
    if tax_rate is None:
        raise_not_found("Tax rate not found.")
    ensure_tax_rate_name_available(db, payload.name, tax_rate_id=tax_rate.id)
    old_value = tax_rate_read_json(tax_rate)
    for field, value in payload.model_dump().items():
        setattr(tax_rate, field, value)
    write_audit_log(
        db,
        action="tax_rate.update",
        entity_type="tax_rate",
        entity_id=tax_rate.id,
        user=user,
        old_value_json=old_value,
        new_value_json=payload.model_dump(mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(tax_rate)
    return tax_rate


def tax_rate_read_json(tax_rate: TaxRate) -> dict:
    return {
        "id": tax_rate.id,
        "name": tax_rate.name,
        "rate_percent": str(tax_rate.rate_percent),
        "cess_percent": str(tax_rate.cess_percent),
        "description": tax_rate.description,
        "is_active": tax_rate.is_active,
    }


def list_payment_modes(db: Session, *, include_inactive: bool = False) -> list[PaymentMode]:
    company = get_default_company(db)
    statement = (
        select(PaymentMode)
        .where(PaymentMode.company_id == company.id)
        .order_by(PaymentMode.display_order, PaymentMode.name)
    )
    if not include_inactive:
        statement = statement.where(PaymentMode.is_active.is_(True))
    return list(db.scalars(statement).all())


def ensure_payment_mode_name_available(db: Session, company_id: int, name: str, payment_mode_id: int | None = None) -> None:
    existing = db.scalar(select(PaymentMode).where(PaymentMode.company_id == company_id, PaymentMode.name == name))
    if existing is not None and existing.id != payment_mode_id:
        raise_conflict("Payment mode name already exists for this company.")


def create_payment_mode(db: Session, *, payload: PaymentModeCreate, user: User, request) -> PaymentMode:
    company = db.get(Company, payload.company_id) if payload.company_id else get_default_company(db)
    if company is None:
        raise_not_found("Company not found.")
    ensure_payment_mode_name_available(db, company.id, payload.name)
    data = payload.model_dump(exclude={"company_id"})
    payment_mode = PaymentMode(company_id=company.id, **data)
    db.add(payment_mode)
    db.flush()
    write_audit_log(
        db,
        action="payment_mode.create",
        entity_type="payment_mode",
        entity_id=payment_mode.id,
        user=user,
        new_value_json={**payload.model_dump(mode="json"), "company_id": company.id},
        request=request,
    )
    db.commit()
    db.refresh(payment_mode)
    return payment_mode


def update_payment_mode(db: Session, *, payment_mode_id: int, payload: PaymentModeUpdate, user: User, request) -> PaymentMode:
    payment_mode = db.get(PaymentMode, payment_mode_id)
    if payment_mode is None:
        raise_not_found("Payment mode not found.")
    ensure_payment_mode_name_available(db, payment_mode.company_id, payload.name, payment_mode_id=payment_mode.id)
    old_value = {
        "id": payment_mode.id,
        "name": payment_mode.name,
        "mode_type": payment_mode.mode_type.value,
        "requires_reference": payment_mode.requires_reference,
        "display_order": payment_mode.display_order,
        "is_active": payment_mode.is_active,
    }
    for field, value in payload.model_dump().items():
        setattr(payment_mode, field, value)
    write_audit_log(
        db,
        action="payment_mode.update",
        entity_type="payment_mode",
        entity_id=payment_mode.id,
        user=user,
        old_value_json=old_value,
        new_value_json=payload.model_dump(mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(payment_mode)
    return payment_mode


def invoice_sequence_to_read(sequence: InvoiceSequence) -> InvoiceSequenceRead:
    return InvoiceSequenceRead(
        id=sequence.id,
        company_id=sequence.company_id,
        branch_id=sequence.branch_id,
        invoice_type=sequence.invoice_type,
        fiscal_year=sequence.fiscal_year,
        prefix=sequence.prefix,
        suffix=sequence.suffix,
        next_number=sequence.next_number,
        padding=sequence.padding,
        reset_rule=sequence.reset_rule,
        is_active=sequence.is_active,
        last_generated_at=sequence.last_generated_at,
        preview_next_number=preview_invoice_number(sequence),
        created_at=sequence.created_at,
        updated_at=sequence.updated_at,
    )


def list_invoice_sequences(db: Session, *, include_inactive: bool = False) -> list[InvoiceSequenceRead]:
    company = get_default_company(db)
    statement = (
        select(InvoiceSequence)
        .where(InvoiceSequence.company_id == company.id)
        .order_by(InvoiceSequence.fiscal_year.desc(), InvoiceSequence.invoice_type, InvoiceSequence.branch_id)
    )
    if not include_inactive:
        statement = statement.where(InvoiceSequence.is_active.is_(True))
    return [invoice_sequence_to_read(sequence) for sequence in db.scalars(statement).all()]


def create_invoice_sequence(db: Session, *, payload: InvoiceSequenceCreate, user: User, request) -> InvoiceSequenceRead:
    company = db.get(Company, payload.company_id) if payload.company_id else get_default_company(db)
    if company is None:
        raise_not_found("Company not found.")
    ensure_invoice_sequence_available(
        db,
        company_id=company.id,
        branch_id=payload.branch_id,
        invoice_type=payload.invoice_type,
        fiscal_year=payload.fiscal_year,
    )
    data = payload.model_dump(exclude={"company_id"})
    sequence = InvoiceSequence(company_id=company.id, **data)
    db.add(sequence)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise_conflict("Invoice sequence already exists for this scope, type, and fiscal year.")
    write_audit_log(
        db,
        action="invoice_sequence.create",
        entity_type="invoice_sequence",
        entity_id=sequence.id,
        user=user,
        new_value_json=invoice_sequence_to_read(sequence).model_dump(mode="json"),
        request=request,
    )
    db.commit()
    return invoice_sequence_to_read(db.get(InvoiceSequence, sequence.id))


def update_invoice_sequence(
    db: Session,
    *,
    sequence_id: int,
    payload: InvoiceSequenceUpdate,
    user: User,
    request,
) -> InvoiceSequenceRead:
    sequence = db.get(InvoiceSequence, sequence_id)
    if sequence is None:
        raise_not_found("Invoice sequence not found.")
    old_value = invoice_sequence_to_read(sequence).model_dump(mode="json")
    company_id = payload.company_id or sequence.company_id
    if db.get(Company, company_id) is None:
        raise_not_found("Company not found.")
    ensure_invoice_sequence_available(
        db,
        company_id=company_id,
        branch_id=payload.branch_id,
        invoice_type=payload.invoice_type,
        fiscal_year=payload.fiscal_year,
        sequence_id=sequence.id,
    )
    for field, value in payload.model_dump(exclude={"company_id"}).items():
        setattr(sequence, field, value)
    sequence.company_id = company_id
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise_conflict("Invoice sequence already exists for this scope, type, and fiscal year.")
    write_audit_log(
        db,
        action="invoice_sequence.update",
        entity_type="invoice_sequence",
        entity_id=sequence.id,
        user=user,
        old_value_json=old_value,
        new_value_json=invoice_sequence_to_read(sequence).model_dump(mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(sequence)
    return invoice_sequence_to_read(sequence)


def ensure_invoice_sequence_available(
    db: Session,
    *,
    company_id: int,
    branch_id: int | None,
    invoice_type: InvoiceSequenceType,
    fiscal_year: str,
    sequence_id: int | None = None,
) -> None:
    statement = select(InvoiceSequence).where(
        InvoiceSequence.company_id == company_id,
        InvoiceSequence.invoice_type == invoice_type,
        InvoiceSequence.fiscal_year == fiscal_year,
    )
    if branch_id is None:
        statement = statement.where(InvoiceSequence.branch_id.is_(None))
    else:
        statement = statement.where(InvoiceSequence.branch_id == branch_id)
    existing = db.scalar(statement)
    if existing is not None and existing.id != sequence_id:
        raise_conflict("Invoice sequence already exists for this scope, type, and fiscal year.")


def generate_next_invoice_number(
    db: Session,
    *,
    invoice_type: InvoiceSequenceType,
    branch_id: int | None = None,
    company_id: int | None = None,
    fiscal_year: str | None = None,
) -> str:
    company = db.get(Company, company_id) if company_id else get_default_company(db)
    if company is None:
        raise_not_found("Company not found.")

    statement = (
        select(InvoiceSequence)
        .where(
            InvoiceSequence.company_id == company.id,
            InvoiceSequence.invoice_type == invoice_type,
            InvoiceSequence.is_active.is_(True),
        )
        .with_for_update()
        .order_by(InvoiceSequence.id)
    )
    if fiscal_year is not None:
        statement = statement.where(InvoiceSequence.fiscal_year == fiscal_year)
    if branch_id is not None:
        statement = statement.where((InvoiceSequence.branch_id == branch_id) | (InvoiceSequence.branch_id.is_(None)))
    else:
        statement = statement.where(InvoiceSequence.branch_id.is_(None))

    sequences = list(db.scalars(statement).all())
    sequence = None
    if branch_id is not None:
        sequence = next((candidate for candidate in sequences if candidate.branch_id == branch_id), None)
    if sequence is None:
        sequence = next((candidate for candidate in sequences if candidate.branch_id is None), None)
    if sequence is None:
        raise_not_found("No active invoice sequence is configured for this invoice type.")

    invoice_number = preview_invoice_number(sequence)
    sequence.next_number += 1
    sequence.last_generated_at = datetime.now(UTC)
    db.flush()
    return invoice_number
