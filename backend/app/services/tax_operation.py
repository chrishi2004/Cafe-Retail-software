from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_forbidden, raise_not_found
from app.core.scope import ScopeContext
from app.models import (
    Branch,
    BusinessProfile,
    Company,
    GSTRegistration,
    InvoiceSequence,
    InvoiceSequenceType,
    InvoiceType,
    PrintTemplate,
    PrintTemplateType,
    Sale,
    TaxMode,
    TaxRegistrationStatus,
    User,
)
from app.schemas.invoices import InvoiceCreate, POSCheckoutRequest
from app.schemas.tax_operation import (
    CombinedTurnoverRead,
    GSTActivationRequest,
    TaxOperationRead,
    TaxOperationSettingsUpdate,
    VentureTurnoverRead,
)
from app.services.audit import write_audit_log

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
STEP_UP_WINDOW = timedelta(minutes=10)
COMPLIANCE_NOTICE = (
    "Tax mode is an operational control, not legal or tax advice. GST activation requires "
    "independent CA/GST review and does not make a registration determination."
)
TURNOVER_NOTICE = (
    "Combined turnover is a monitoring aid across this Business Group. It does not determine "
    "GST registration liability or replace professional advice."
)


def _company_id_from_scope(scope: ScopeContext) -> int:
    if scope.company_id is None or scope.all_companies:
        raise_bad_request("Select one venture before viewing or changing its tax operation settings.")
    return scope.company_id


def _profile_for_company(db: Session, company_id: int) -> BusinessProfile:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company_id))
    if profile is None:
        raise_not_found("Business tax profile not found for this venture.")
    return profile


def _primary_registration(db: Session, company_id: int) -> GSTRegistration | None:
    return db.scalar(
        select(GSTRegistration)
        .where(GSTRegistration.company_id == company_id)
        .order_by(GSTRegistration.is_primary.desc(), GSTRegistration.id)
    )


def _masked_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    return f"{gstin[:2]}*********{gstin[-4:]}"


def _activation_prerequisites(
    db: Session,
    *,
    company: Company,
    profile: BusinessProfile,
    registration: GSTRegistration | None,
) -> list[str]:
    missing: list[str] = []
    if profile.tax_registration_status != TaxRegistrationStatus.REGISTERED:
        missing.append("registered tax status")
    if registration is None or not registration.is_active or registration.reference_only:
        missing.append("active non-reference GST registration")
    elif not registration.gstin or not GSTIN_PATTERN.fullmatch(registration.gstin.upper()):
        missing.append("GSTIN format")
    if not (company.legal_name or "").strip():
        missing.append("legal identity")
    if registration is None or not (registration.state or "").strip() or len((registration.state_code or "").strip()) != 2:
        missing.append("registration state and state code")
    gst_sequence = db.scalar(
        select(InvoiceSequence).where(
            InvoiceSequence.company_id == company.id,
            InvoiceSequence.invoice_type == InvoiceSequenceType.GST_INVOICE,
            InvoiceSequence.is_active.is_(True),
        )
    )
    if gst_sequence is None:
        missing.append("active GST invoice sequence")
    gst_template = db.scalar(
        select(PrintTemplate).where(
            PrintTemplate.company_id == company.id,
            PrintTemplate.template_type == PrintTemplateType.A4_GST_INVOICE,
            PrintTemplate.is_active.is_(True),
        )
    )
    if gst_template is None:
        missing.append("active GST invoice template")
    return missing


def get_tax_operation(db: Session, *, scope: ScopeContext) -> TaxOperationRead:
    company_id = _company_id_from_scope(scope)
    company = db.get(Company, company_id)
    if company is None or not company.is_active:
        raise_not_found("Venture not found.")
    profile = _profile_for_company(db, company_id)
    registration = _primary_registration(db, company_id)
    missing = _activation_prerequisites(db, company=company, profile=profile, registration=registration)
    return TaxOperationRead(
        company_id=company.id,
        company_name=company.name,
        tax_registration_status=profile.tax_registration_status,
        default_tax_mode=profile.default_tax_mode,
        gst_effective_from=profile.gst_effective_from,
        customer_details_on_bill=profile.customer_details_on_bill,
        b2b_gst_enabled=profile.b2b_gst_enabled,
        include_customer_in_gst_reports=profile.include_customer_in_gst_reports,
        gst_registration_id=registration.id if registration else None,
        gst_registration_configured=bool(registration and registration.gstin),
        gst_registration_active=bool(registration and registration.is_active and not registration.reference_only),
        gstin_masked=_masked_gstin(registration.gstin if registration else None),
        can_activate_gst=not missing,
        missing_activation_prerequisites=missing,
        compliance_notice=COMPLIANCE_NOTICE,
    )


def update_tax_operation_settings(
    db: Session,
    *,
    scope: ScopeContext,
    payload: TaxOperationSettingsUpdate,
    user: User,
    request: Request | None,
) -> TaxOperationRead:
    company_id = _company_id_from_scope(scope)
    profile = _profile_for_company(db, company_id)
    old = {
        "tax_registration_status": profile.tax_registration_status.value,
        "default_tax_mode": profile.default_tax_mode.value,
        "gst_effective_from": profile.gst_effective_from.isoformat() if profile.gst_effective_from else None,
        "customer_details_on_bill": profile.customer_details_on_bill.value,
        "b2b_gst_enabled": profile.b2b_gst_enabled,
        "include_customer_in_gst_reports": profile.include_customer_in_gst_reports,
    }

    profile.tax_registration_status = payload.tax_registration_status
    profile.customer_details_on_bill = payload.customer_details_on_bill
    profile.b2b_gst_enabled = payload.b2b_gst_enabled
    profile.include_customer_in_gst_reports = payload.include_customer_in_gst_reports

    registrations = list(db.scalars(select(GSTRegistration).where(GSTRegistration.company_id == company_id)).all())
    if payload.tax_registration_status == TaxRegistrationStatus.UNREGISTERED:
        profile.default_tax_mode = TaxMode.NON_GST
        profile.gst_effective_from = None
        for registration in registrations:
            registration.is_active = False
            registration.reference_only = True
    elif payload.registration_active:
        if payload.registration_id is None:
            raise_bad_request("Select a GST registration before marking it active.")
        selected = next((row for row in registrations if row.id == payload.registration_id), None)
        if selected is None:
            raise_bad_request("GST registration does not belong to the selected venture.")
        for registration in registrations:
            registration.is_active = registration.id == selected.id
            registration.reference_only = registration.id != selected.id

    write_audit_log(
        db,
        action="tax_operation.settings_updated",
        entity_type="business_profile",
        entity_id=profile.id,
        user=user,
        company_id=company_id,
        old_value_json=old,
        new_value_json={
            "tax_registration_status": profile.tax_registration_status.value,
            "default_tax_mode": profile.default_tax_mode.value,
            "gst_effective_from": profile.gst_effective_from.isoformat() if profile.gst_effective_from else None,
            "customer_details_on_bill": profile.customer_details_on_bill.value,
            "b2b_gst_enabled": profile.b2b_gst_enabled,
            "include_customer_in_gst_reports": profile.include_customer_in_gst_reports,
        },
        request=request,
    )
    db.commit()
    return get_tax_operation(db, scope=scope)


def activate_gst_operation(
    db: Session,
    *,
    scope: ScopeContext,
    payload: GSTActivationRequest,
    user: User,
    request: Request | None,
) -> TaxOperationRead:
    company_id = _company_id_from_scope(scope)
    if not payload.acknowledge_professional_review:
        raise_bad_request("Explicit CA/GST review acknowledgement is required before activation.")
    if payload.confirmation.strip().upper() != "ACTIVATE GST":
        raise_bad_request('Type "ACTIVATE GST" to confirm this effective-dated change.')
    if payload.effective_from < date.today():
        raise_bad_request("GST activation cannot be backdated. Choose today or a future effective date.")
    if user.last_step_up_at is None:
        raise_forbidden("Recent step-up authentication is required.")
    step_up_at = user.last_step_up_at
    if step_up_at.tzinfo is None:
        step_up_at = step_up_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - step_up_at > STEP_UP_WINDOW:
        raise_forbidden("Step-up authentication has expired. Verify credentials again.")

    company = db.get(Company, company_id)
    if company is None:
        raise_not_found("Venture not found.")
    profile = _profile_for_company(db, company_id)
    registration = _primary_registration(db, company_id)
    missing = _activation_prerequisites(db, company=company, profile=profile, registration=registration)
    if missing:
        raise_bad_request("GST activation prerequisites are incomplete: " + ", ".join(missing) + ".")

    old = {
        "default_tax_mode": profile.default_tax_mode.value,
        "gst_effective_from": profile.gst_effective_from.isoformat() if profile.gst_effective_from else None,
    }
    profile.default_tax_mode = TaxMode.GST
    profile.gst_effective_from = payload.effective_from
    write_audit_log(
        db,
        action="tax_operation.gst_activated",
        entity_type="business_profile",
        entity_id=profile.id,
        user=user,
        company_id=company_id,
        old_value_json=old,
        new_value_json={
            "default_tax_mode": TaxMode.GST.value,
            "gst_effective_from": payload.effective_from.isoformat(),
            "professional_review_acknowledged": True,
        },
        request=request,
        notes=COMPLIANCE_NOTICE,
    )
    db.commit()
    return get_tax_operation(db, scope=scope)


def enforce_invoice_tax_policy(
    db: Session,
    *,
    payload: InvoiceCreate | POSCheckoutRequest,
) -> InvoiceCreate | POSCheckoutRequest:
    branch = db.get(Branch, payload.branch_id)
    if branch is None or not branch.is_active:
        raise_not_found("Branch not found.")
    profile = _profile_for_company(db, branch.company_id)
    invoice_day: date = (payload.invoice_date or datetime.now(UTC)).date()

    gst_active_for_date = (
        profile.default_tax_mode == TaxMode.GST
        and profile.tax_registration_status == TaxRegistrationStatus.REGISTERED
        and profile.gst_effective_from is not None
        and invoice_day >= profile.gst_effective_from
    )
    authoritative_type = InvoiceType.GST if gst_active_for_date else InvoiceType.NON_GST
    if payload.invoice_type != authoritative_type:
        if payload.invoice_type == InvoiceType.GST:
            raise_bad_request("GST billing is not active for this venture on the invoice date.")
        raise_bad_request("Non-GST billing cannot be forced after this venture's GST effective date.")
    return payload.model_copy(update={"invoice_type": authoritative_type})


def combined_turnover(db: Session, *, scope: ScopeContext) -> CombinedTurnoverRead:
    rows = db.execute(
        select(
            Company.id,
            Company.name,
            Company.business_type,
            func.coalesce(func.sum(Sale.total_amount), 0),
        )
        .outerjoin(Sale, Sale.company_id == Company.id)
        .where(Company.business_group_id == scope.business_group_id, Company.is_active.is_(True))
        .group_by(Company.id, Company.name, Company.business_type)
        .order_by(Company.name)
        .execution_options(scope_bypass=True)
    ).all()
    ventures = [
        VentureTurnoverRead(
            company_id=row[0],
            company_name=row[1],
            business_type=row[2].value if hasattr(row[2], "value") else str(row[2]),
            turnover=Decimal(str(row[3])),
        )
        for row in rows
    ]
    return CombinedTurnoverRead(
        business_group_id=scope.business_group_id,
        ventures=ventures,
        combined_turnover=sum((row.turnover for row in ventures), Decimal("0.00")),
        review_notice=TURNOVER_NOTICE,
    )
