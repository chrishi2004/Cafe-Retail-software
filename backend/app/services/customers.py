from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import BranchScope, ensure_branch_access
from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.models import (
    Branch,
    Company,
    Customer,
    CustomerAddress,
    CustomerAddressType,
    CustomerLedgerEntry,
    CustomerLedgerEntryType,
    CustomerPayment,
    PaymentMode,
    User,
    UserRole,
)
from app.schemas.customers import (
    CustomerCreate,
    CustomerLedgerEntryRead,
    CustomerOutstandingRead,
    CustomerPaymentCreate,
    CustomerPaymentRead,
    CustomerRead,
    CustomerUpdate,
)
from app.services.audit import write_audit_log
from app.services.business_settings import get_default_company

MONEY = Decimal("0.01")


def money(value: Decimal | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def customer_options():
    return (
        joinedload(Customer.branch),
        selectinload(Customer.addresses),
        selectinload(Customer.ledger_entries),
    )


def customer_is_accessible(user: User, customer: Customer) -> bool:
    if user.role in {UserRole.ADMIN, UserRole.ANALYST}:
        return True
    return user.branch_id is not None and customer.branch_id in {None, user.branch_id}


def ensure_customer_read_access(user: User, customer: Customer) -> None:
    if not customer_is_accessible(user, customer):
        raise_forbidden("You can only access customers for your assigned branch.")


def ensure_customer_manage_access(user: User, customer_branch_id: int | None) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role != UserRole.STORE_MANAGER:
        raise_forbidden("Only Admin and Store Manager roles can manage customer accounts.")
    if user.branch_id is None:
        raise_forbidden("This user does not have an assigned branch.")
    if customer_branch_id != user.branch_id:
        raise_forbidden("Store Managers can only manage customers for their assigned branch.")


def ensure_customer_payment_access(user: User, branch_id: int | None) -> None:
    if user.role not in {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF}:
        raise_forbidden("This role is read-only for customer payments.")
    if branch_id is not None:
        ensure_branch_access(user, branch_id)
    elif user.role in {UserRole.STORE_MANAGER, UserRole.STAFF}:
        raise_forbidden("A branch is required for customer payments by branch-scoped users.")


def normalize_branch_for_customer_write(db: Session, user: User, branch_id: int | None) -> int | None:
    effective_branch_id = branch_id
    if user.role == UserRole.STORE_MANAGER:
        if branch_id is not None and branch_id != user.branch_id:
            raise_forbidden("Store Managers can only manage customers for their assigned branch.")
        effective_branch_id = user.branch_id
    ensure_customer_manage_access(user, effective_branch_id)
    if effective_branch_id is not None:
        branch = db.get(Branch, effective_branch_id)
        if branch is None or not branch.is_active:
            raise_not_found("Branch not found.")
    return effective_branch_id


def get_company_id(db: Session, company_id: int | None) -> int | None:
    if company_id is not None:
        if db.get(Company, company_id) is None:
            raise_not_found("Company not found.")
        return company_id
    try:
        return get_default_company(db).id
    except Exception:
        return None


def customer_payload_data(payload: CustomerCreate | CustomerUpdate) -> dict:
    return payload.model_dump()


def calculate_customer_outstanding(db: Session, customer_id: int) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(CustomerLedgerEntry.debit - CustomerLedgerEntry.credit), 0)).where(
            CustomerLedgerEntry.customer_id == customer_id
        )
    )
    return money(value or Decimal("0.00"))


def available_credit(customer: Customer, outstanding_balance: Decimal) -> Decimal:
    return money(customer.credit_limit - outstanding_balance)


def sync_default_customer_addresses(db: Session, customer: Customer) -> None:
    for address_type, address_value in [
        (CustomerAddressType.BILLING, customer.billing_address),
        (CustomerAddressType.SHIPPING, customer.shipping_address or customer.billing_address),
    ]:
        existing = next((address for address in customer.addresses if address.address_type == address_type and address.is_default), None)
        if not address_value:
            if existing is not None:
                db.delete(existing)
            continue
        if existing is None:
            db.add(
                CustomerAddress(
                    customer_id=customer.id,
                    address_type=address_type,
                    recipient_name=customer.name,
                    phone=customer.phone,
                    address=address_value,
                    city=customer.city,
                    state=customer.state,
                    state_code=customer.state_code,
                    pincode=customer.pincode,
                    gstin=customer.gstin,
                    is_default=True,
                )
            )
        else:
            existing.recipient_name = customer.name
            existing.phone = customer.phone
            existing.address = address_value
            existing.city = customer.city
            existing.state = customer.state
            existing.state_code = customer.state_code
            existing.pincode = customer.pincode
            existing.gstin = customer.gstin


def add_customer_ledger_entry(
    db: Session,
    *,
    customer_id: int,
    branch_id: int | None,
    entry_type: CustomerLedgerEntryType,
    debit: Decimal = Decimal("0.00"),
    credit: Decimal = Decimal("0.00"),
    reference_type: str | None = None,
    reference_id: int | None = None,
    reason: str | None = None,
    notes: str | None = None,
    user: User | None = None,
    entry_datetime: datetime | None = None,
) -> CustomerLedgerEntry:
    debit = money(debit)
    credit = money(credit)
    if debit <= 0 and credit <= 0:
        raise_bad_request("Ledger entry must include a debit or credit amount.")
    entry = CustomerLedgerEntry(
        customer_id=customer_id,
        branch_id=branch_id,
        entry_type=entry_type,
        debit=debit,
        credit=credit,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        notes=notes,
        created_by=user.id if user else None,
        entry_datetime=entry_datetime or datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    db.add(entry)
    db.flush()
    return entry


def customer_to_read(db: Session, customer: Customer) -> CustomerRead:
    outstanding = calculate_customer_outstanding(db, customer.id)
    return CustomerRead(
        id=customer.id,
        company_id=customer.company_id,
        branch_id=customer.branch_id,
        branch_name=customer.branch.name if customer.branch else None,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        gstin=customer.gstin,
        billing_address=customer.billing_address,
        shipping_address=customer.shipping_address,
        city=customer.city,
        state=customer.state,
        state_code=customer.state_code,
        pincode=customer.pincode,
        credit_limit=customer.credit_limit,
        opening_balance=customer.opening_balance,
        outstanding_balance=outstanding,
        available_credit=available_credit(customer, outstanding),
        is_active=customer.is_active,
        addresses=sorted(customer.addresses, key=lambda address: (address.address_type.value, address.id)),
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def get_customer_or_404(db: Session, customer_id: int, user: User | None = None) -> Customer:
    customer = db.scalar(select(Customer).options(*customer_options()).where(Customer.id == customer_id))
    if customer is None:
        raise_not_found("Customer not found.")
    if user is not None:
        ensure_customer_read_access(user, customer)
    return customer


def apply_customer_scope(statement, branch_scope: BranchScope, branch_id: int | None):
    if branch_scope.all_branches:
        if branch_id is not None:
            statement = statement.where(Customer.branch_id == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access customers for your assigned branch.")
    scoped_branch_ids = branch_scope.branch_ids
    return statement.where(or_(Customer.branch_id.is_(None), Customer.branch_id.in_(scoped_branch_ids)))


def list_customers(
    db: Session,
    *,
    branch_scope: BranchScope,
    search: str | None = None,
    branch_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[CustomerRead]:
    statement = select(Customer).options(*customer_options()).order_by(Customer.name).limit(max(1, min(limit, 500)))
    statement = apply_customer_scope(statement, branch_scope, branch_id)
    if not include_inactive:
        statement = statement.where(Customer.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Customer.name.ilike(term),
                Customer.phone.ilike(term),
                Customer.email.ilike(term),
                Customer.gstin.ilike(term),
            )
        )
    return [customer_to_read(db, customer) for customer in db.scalars(statement).unique().all()]


def create_customer(db: Session, *, payload: CustomerCreate, user: User, request: Request) -> CustomerRead:
    data = customer_payload_data(payload)
    data["branch_id"] = normalize_branch_for_customer_write(db, user, payload.branch_id)
    data["company_id"] = get_company_id(db, payload.company_id)
    customer = Customer(**data)
    db.add(customer)
    try:
        db.flush()
        sync_default_customer_addresses(db, customer)
        if customer.opening_balance > 0:
            add_customer_ledger_entry(
                db,
                customer_id=customer.id,
                branch_id=customer.branch_id,
                entry_type=CustomerLedgerEntryType.OPENING_BALANCE,
                debit=customer.opening_balance,
                reason="Opening balance",
                user=user,
            )
        write_audit_log(
            db,
            action="customer.create",
            entity_type="customer",
            entity_id=customer.id,
            user=user,
            new_value_json=payload.model_dump(mode="json"),
            request=request,
        )
        customer_id = customer.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise_conflict("Customer phone, email, or GSTIN already exists.")
    except Exception:
        db.rollback()
        raise
    db.expire_all()
    return customer_to_read(db, get_customer_or_404(db, customer_id))


def update_customer(
    db: Session,
    *,
    customer_id: int,
    payload: CustomerUpdate,
    user: User,
    request: Request,
) -> CustomerRead:
    customer = get_customer_or_404(db, customer_id, user=user)
    ensure_customer_manage_access(user, customer.branch_id)
    data = customer_payload_data(payload)
    data["branch_id"] = normalize_branch_for_customer_write(db, user, payload.branch_id)
    data["company_id"] = get_company_id(db, payload.company_id)
    old_value = customer_to_read(db, customer).model_dump(mode="json")
    old_opening_balance = customer.opening_balance
    for field, value in data.items():
        setattr(customer, field, value)

    try:
        db.flush()
        sync_default_customer_addresses(db, customer)
        opening_delta = money(customer.opening_balance - old_opening_balance)
        if opening_delta > 0:
            add_customer_ledger_entry(
                db,
                customer_id=customer.id,
                branch_id=customer.branch_id,
                entry_type=CustomerLedgerEntryType.ADJUSTMENT,
                debit=opening_delta,
                reason="Opening balance increased",
                user=user,
            )
        elif opening_delta < 0:
            add_customer_ledger_entry(
                db,
                customer_id=customer.id,
                branch_id=customer.branch_id,
                entry_type=CustomerLedgerEntryType.ADJUSTMENT,
                credit=abs(opening_delta),
                reason="Opening balance reduced",
                user=user,
            )
        write_audit_log(
            db,
            action="customer.update",
            entity_type="customer",
            entity_id=customer.id,
            user=user,
            old_value_json=old_value,
            new_value_json=payload.model_dump(mode="json"),
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise_conflict("Customer phone, email, or GSTIN already exists.")
    except Exception:
        db.rollback()
        raise
    db.expire_all()
    return customer_to_read(db, get_customer_or_404(db, customer_id))


def deactivate_customer(db: Session, *, customer_id: int, user: User, request: Request) -> CustomerRead:
    customer = get_customer_or_404(db, customer_id, user=user)
    ensure_customer_manage_access(user, customer.branch_id)
    old_value = {"is_active": customer.is_active}
    customer.is_active = False
    write_audit_log(
        db,
        action="customer.deactivate",
        entity_type="customer",
        entity_id=customer.id,
        user=user,
        old_value_json=old_value,
        new_value_json={"is_active": False},
        request=request,
    )
    db.commit()
    return customer_to_read(db, get_customer_or_404(db, customer_id))


def ledger_entry_to_read(entry: CustomerLedgerEntry, running_balance: Decimal) -> CustomerLedgerEntryRead:
    return CustomerLedgerEntryRead(
        id=entry.id,
        customer_id=entry.customer_id,
        branch_id=entry.branch_id,
        branch_name=entry.branch.name if entry.branch else None,
        entry_type=entry.entry_type,
        debit=entry.debit,
        credit=entry.credit,
        running_balance=money(running_balance),
        reference_type=entry.reference_type,
        reference_id=entry.reference_id,
        reason=entry.reason,
        notes=entry.notes,
        created_by=entry.created_by,
        created_by_name=entry.creator.name if entry.creator else None,
        entry_datetime=entry.entry_datetime,
        created_at=entry.created_at,
    )


def get_customer_ledger(db: Session, *, customer_id: int, user: User) -> list[CustomerLedgerEntryRead]:
    customer = get_customer_or_404(db, customer_id, user=user)
    entries = list(
        db.scalars(
            select(CustomerLedgerEntry)
            .options(joinedload(CustomerLedgerEntry.branch), joinedload(CustomerLedgerEntry.creator))
            .where(CustomerLedgerEntry.customer_id == customer.id)
            .order_by(CustomerLedgerEntry.entry_datetime, CustomerLedgerEntry.id)
        ).all()
    )
    running_balance = Decimal("0.00")
    result: list[CustomerLedgerEntryRead] = []
    for entry in entries:
        running_balance = money(running_balance + entry.debit - entry.credit)
        result.append(ledger_entry_to_read(entry, running_balance))
    return result


def payment_to_read(db: Session, payment: CustomerPayment) -> CustomerPaymentRead:
    return CustomerPaymentRead(
        id=payment.id,
        customer_id=payment.customer_id,
        branch_id=payment.branch_id,
        branch_name=payment.branch.name if payment.branch else None,
        payment_mode_id=payment.payment_mode_id,
        payment_mode_name=payment.payment_mode.name if payment.payment_mode else None,
        amount=payment.amount,
        payment_datetime=payment.payment_datetime,
        reference_number=payment.reference_number,
        notes=payment.notes,
        received_by=payment.received_by,
        received_by_name=payment.receiver.name if payment.receiver else None,
        ledger_entry_id=payment.ledger_entry_id,
        outstanding_balance=calculate_customer_outstanding(db, payment.customer_id),
        created_at=payment.created_at,
    )


def record_customer_payment(
    db: Session,
    *,
    customer_id: int,
    payload: CustomerPaymentCreate,
    user: User,
    request: Request,
) -> CustomerPaymentRead:
    customer = get_customer_or_404(db, customer_id, user=user)
    if not customer.is_active:
        raise_bad_request("Cannot record payment for an inactive customer.")
    branch_id = payload.branch_id if payload.branch_id is not None else customer.branch_id
    if branch_id is None and user.role in {UserRole.STORE_MANAGER, UserRole.STAFF}:
        branch_id = user.branch_id
    ensure_customer_payment_access(user, branch_id)
    if payload.payment_mode_id is not None and db.get(PaymentMode, payload.payment_mode_id) is None:
        raise_not_found("Payment mode not found.")

    payment = CustomerPayment(
        customer_id=customer.id,
        branch_id=branch_id,
        payment_mode_id=payload.payment_mode_id,
        amount=money(payload.amount),
        payment_datetime=payload.payment_datetime or datetime.now(UTC),
        reference_number=payload.reference_number,
        notes=payload.notes,
        received_by=user.id,
    )
    try:
        db.add(payment)
        db.flush()
        ledger_entry = add_customer_ledger_entry(
            db,
            customer_id=customer.id,
            branch_id=branch_id,
            entry_type=CustomerLedgerEntryType.PAYMENT,
            credit=payment.amount,
            reference_type="customer_payment",
            reference_id=payment.id,
            reason="Customer payment received",
            notes=payment.notes,
            user=user,
            entry_datetime=payment.payment_datetime,
        )
        payment.ledger_entry_id = ledger_entry.id
        write_audit_log(
            db,
            action="customer.payment",
            entity_type="customer_payment",
            entity_id=payment.id,
            user=user,
            new_value_json=payload.model_dump(mode="json"),
            request=request,
        )
        payment_id = payment.id
        db.commit()
    except Exception:
        db.rollback()
        raise

    payment = db.scalar(
        select(CustomerPayment)
        .options(joinedload(CustomerPayment.branch), joinedload(CustomerPayment.payment_mode), joinedload(CustomerPayment.receiver))
        .where(CustomerPayment.id == payment_id)
    )
    return payment_to_read(db, payment)


def outstanding_to_read(db: Session, customer: Customer) -> CustomerOutstandingRead:
    outstanding = calculate_customer_outstanding(db, customer.id)
    available = available_credit(customer, outstanding)
    return CustomerOutstandingRead(
        customer_id=customer.id,
        customer_name=customer.name,
        phone=customer.phone,
        gstin=customer.gstin,
        branch_id=customer.branch_id,
        branch_name=customer.branch.name if customer.branch else None,
        credit_limit=customer.credit_limit,
        outstanding_balance=outstanding,
        available_credit=available,
        is_over_credit_limit=outstanding > customer.credit_limit,
        is_active=customer.is_active,
    )


def list_customer_outstanding(
    db: Session,
    *,
    branch_scope: BranchScope,
    branch_id: int | None = None,
    include_zero: bool = False,
) -> list[CustomerOutstandingRead]:
    statement = select(Customer).options(joinedload(Customer.branch)).order_by(Customer.name)
    statement = apply_customer_scope(statement, branch_scope, branch_id)
    rows = [outstanding_to_read(db, customer) for customer in db.scalars(statement).unique().all()]
    if not include_zero:
        rows = [row for row in rows if row.outstanding_balance != Decimal("0.00")]
    return sorted(rows, key=lambda row: (row.outstanding_balance <= 0, row.customer_name))


def validate_customer_credit_limit(db: Session, *, customer_id: int, additional_debit: Decimal) -> Decimal:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise_not_found("Customer not found.")
    if not customer.is_active:
        raise_bad_request("Cannot extend credit to an inactive customer.")
    projected = money(calculate_customer_outstanding(db, customer_id) + additional_debit)
    if projected > customer.credit_limit:
        raise_bad_request(
            f"Credit limit exceeded for {customer.name}. Limit {customer.credit_limit}, projected outstanding {projected}."
        )
    return projected
