from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import BranchScope, ensure_branch_access
from app.api.errors import raise_bad_request, raise_forbidden, raise_not_found
from app.models import (
    Branch,
    BusinessProfile,
    Customer,
    CustomerLedgerEntryType,
    GSTRegistration,
    Inventory,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    InvoicePaymentStatus,
    InvoiceSequenceType,
    InvoiceStatus,
    InvoiceStatusHistory,
    InvoiceTax,
    InvoiceTaxType,
    InvoiceType,
    PaymentMode,
    PaymentModeType,
    Product,
    ProductBarcode,
    ProductItemType,
    Sale,
    SaleItem,
    StockMovement,
    StockMovementType,
    TaxRate,
    User,
    UserRole,
)
from app.schemas.invoices import (
    InvoiceCancelRequest,
    InvoiceCreate,
    InvoiceIssueRequest,
    InvoiceItemCreate,
    InvoiceItemRead,
    InvoiceListItemRead,
    InvoicePaymentCreate,
    InvoicePaymentRead,
    InvoiceQuoteItemRead,
    InvoiceQuoteRead,
    InvoiceRead,
    InvoiceStatusHistoryRead,
    InvoiceTaxRead,
    POSCheckoutRequest,
    POSProductSearchRead,
)
from app.services.audit import write_audit_log
from app.services.business_settings import generate_next_invoice_number, get_default_company
from app.services.customers import add_customer_ledger_entry, calculate_customer_outstanding, validate_customer_credit_limit

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")
PERCENT = Decimal("100.00")


@dataclass(frozen=True)
class InvoiceFilters:
    branch_id: int | None = None
    customer_id: int | None = None
    status: InvoiceStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    search: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class CalculatedLine:
    product: Product
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cess_rate: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    line_total: Decimal
    gross_profit: Decimal


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(QUANTITY, rounding=ROUND_HALF_UP)


def invoice_options():
    return (
        joinedload(Invoice.branch),
        joinedload(Invoice.customer),
        joinedload(Invoice.creator),
        selectinload(Invoice.items).selectinload(InvoiceItem.taxes),
        selectinload(Invoice.items).joinedload(InvoiceItem.product),
        selectinload(Invoice.taxes),
        selectinload(Invoice.payments).joinedload(InvoicePayment.payment_mode),
        selectinload(Invoice.payments).joinedload(InvoicePayment.receiver),
        selectinload(Invoice.status_history).joinedload(InvoiceStatusHistory.changer),
    )


def date_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(start_date, time.min, tzinfo=UTC) if start_date else None
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC) if end_date else None
    return start, end


def ensure_invoice_write_permission(user: User, branch_id: int) -> None:
    if user.role not in {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF}:
        raise_forbidden("This role is read-only for invoice and POS billing.")
    ensure_branch_access(user, branch_id)


def ensure_invoice_read_permission(user: User, branch_id: int) -> None:
    ensure_branch_access(user, branch_id)


def apply_invoice_scope(statement, branch_scope: BranchScope, filters: InvoiceFilters):
    if branch_scope.all_branches:
        if filters.branch_id is not None:
            statement = statement.where(Invoice.branch_id == filters.branch_id)
    else:
        if filters.branch_id is not None and filters.branch_id not in branch_scope.branch_ids:
            raise_forbidden("You can only access invoices for your assigned branch.")
        statement = statement.where(Invoice.branch_id.in_(branch_scope.branch_ids))

    if filters.customer_id is not None:
        statement = statement.where(Invoice.customer_id == filters.customer_id)
    if filters.status is not None:
        statement = statement.where(Invoice.status == filters.status)
    start, end = date_bounds(filters.start_date, filters.end_date)
    if start is not None:
        statement = statement.where(Invoice.invoice_date >= start)
    if end is not None:
        statement = statement.where(Invoice.invoice_date < end)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        statement = statement.where(
            or_(
                Invoice.invoice_number.ilike(term),
                Invoice.customer.has(Customer.name.ilike(term)),
                Invoice.customer.has(Customer.phone.ilike(term)),
                Invoice.customer.has(Customer.gstin.ilike(term)),
            )
        )
    return statement


def tax_to_read(tax: InvoiceTax) -> InvoiceTaxRead:
    return InvoiceTaxRead.model_validate(tax)


def item_to_read(item: InvoiceItem) -> InvoiceItemRead:
    return InvoiceItemRead(
        id=item.id,
        product_id=item.product_id,
        product_name_snapshot=item.product_name_snapshot,
        sku_snapshot=item.sku_snapshot,
        hsn_sac_code=item.hsn_sac_code,
        quantity=item.quantity,
        unit_price=item.unit_price,
        mrp=item.mrp,
        discount=item.discount,
        taxable_value=item.taxable_value,
        gst_rate=item.gst_rate,
        cgst_total=item.cgst_total,
        sgst_total=item.sgst_total,
        igst_total=item.igst_total,
        cess_total=item.cess_total,
        line_total=item.line_total,
        gross_profit=item.gross_profit,
        taxes=[tax_to_read(tax) for tax in item.taxes],
    )


def payment_to_read(payment: InvoicePayment) -> InvoicePaymentRead:
    return InvoicePaymentRead(
        id=payment.id,
        invoice_id=payment.invoice_id,
        payment_mode_id=payment.payment_mode_id,
        payment_mode_name=payment.payment_mode.name if payment.payment_mode else None,
        amount=payment.amount,
        payment_datetime=payment.payment_datetime,
        reference_number=payment.reference_number,
        notes=payment.notes,
        received_by=payment.received_by,
        received_by_name=payment.receiver.name if payment.receiver else None,
        is_credit_marker=payment.is_credit_marker,
        created_at=payment.created_at,
    )


def status_history_to_read(history: InvoiceStatusHistory) -> InvoiceStatusHistoryRead:
    return InvoiceStatusHistoryRead(
        id=history.id,
        invoice_id=history.invoice_id,
        from_status=history.from_status,
        to_status=history.to_status,
        changed_by=history.changed_by,
        changed_by_name=history.changer.name if history.changer else None,
        notes=history.notes,
        changed_at=history.changed_at,
    )


def invoice_to_list_read(invoice: Invoice) -> InvoiceListItemRead:
    return InvoiceListItemRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        branch_id=invoice.branch_id,
        branch_name=invoice.branch.name,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer.name if invoice.customer else None,
        sale_id=invoice.sale_id,
        invoice_type=invoice.invoice_type,
        place_of_supply_state=invoice.place_of_supply_state,
        place_of_supply_state_code=invoice.place_of_supply_state_code,
        invoice_date=invoice.invoice_date,
        status=invoice.status,
        payment_status=invoice.payment_status,
        subtotal=invoice.subtotal,
        discount_total=invoice.discount_total,
        taxable_total=invoice.taxable_total,
        cgst_total=invoice.cgst_total,
        sgst_total=invoice.sgst_total,
        igst_total=invoice.igst_total,
        cess_total=invoice.cess_total,
        round_off=invoice.round_off,
        grand_total=invoice.grand_total,
        paid_amount=invoice.paid_amount,
        balance_due=invoice.balance_due,
        created_by=invoice.created_by,
        created_by_name=invoice.creator.name,
        created_at=invoice.created_at,
        issued_at=invoice.issued_at,
    )


def invoice_to_read(invoice: Invoice) -> InvoiceRead:
    list_item = invoice_to_list_read(invoice)
    return InvoiceRead(
        **list_item.model_dump(),
        items=[item_to_read(item) for item in sorted(invoice.items, key=lambda row: row.id)],
        taxes=[tax_to_read(tax) for tax in sorted(invoice.taxes, key=lambda row: row.id)],
        payments=[payment_to_read(payment) for payment in sorted(invoice.payments, key=lambda row: row.id)],
        status_history=[
            status_history_to_read(history) for history in sorted(invoice.status_history, key=lambda row: row.id)
        ],
    )


def get_invoice_or_404(db: Session, invoice_id: int, user: User | None = None) -> Invoice:
    invoice = db.scalar(select(Invoice).options(*invoice_options()).where(Invoice.id == invoice_id))
    if invoice is None:
        raise_not_found("Invoice not found.")
    if user is not None:
        ensure_invoice_read_permission(user, invoice.branch_id)
    return invoice


def list_invoices(db: Session, *, branch_scope: BranchScope, filters: InvoiceFilters) -> list[InvoiceListItemRead]:
    statement = (
        select(Invoice)
        .options(joinedload(Invoice.branch), joinedload(Invoice.customer), joinedload(Invoice.creator))
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .limit(max(1, min(filters.limit, 500)))
    )
    statement = apply_invoice_scope(statement, branch_scope, filters)
    return [invoice_to_list_read(invoice) for invoice in db.scalars(statement).unique().all()]


def get_branch_state(db: Session, branch_id: int) -> tuple[str | None, str | None]:
    registration = db.scalar(
        select(GSTRegistration)
        .where(
            GSTRegistration.branch_id == branch_id,
            GSTRegistration.is_active.is_(True),
        )
        .order_by(GSTRegistration.id)
    )
    if registration is None:
        registration = db.scalar(
            select(GSTRegistration)
            .where(
                GSTRegistration.is_primary.is_(True),
                GSTRegistration.is_active.is_(True),
            )
            .order_by(GSTRegistration.id)
        )
    if registration is not None:
        return registration.state, registration.state_code

    profile = db.scalar(select(BusinessProfile).order_by(BusinessProfile.id))
    if profile is not None:
        return profile.state, profile.state_code
    return None, None


def normalize_place_of_supply(
    db: Session,
    *,
    branch_id: int,
    customer: Customer | None,
    place_state: str | None,
    place_state_code: str | None,
) -> tuple[str | None, str | None]:
    seller_state, seller_state_code = get_branch_state(db, branch_id)
    state = place_state or (customer.state if customer else None) or seller_state
    state_code = place_state_code or (customer.state_code if customer else None) or seller_state_code
    return state, state_code


def invoice_sequence_type(invoice_type: InvoiceType) -> InvoiceSequenceType:
    if invoice_type == InvoiceType.NON_GST:
        return InvoiceSequenceType.NON_GST_INVOICE
    return InvoiceSequenceType.GST_INVOICE


def validate_branch_customer(db: Session, payload: InvoiceCreate, user: User) -> tuple[Branch, Customer | None]:
    ensure_invoice_write_permission(user, payload.branch_id)
    branch = db.get(Branch, payload.branch_id)
    if branch is None or not branch.is_active:
        raise_not_found("Branch not found.")

    customer = db.get(Customer, payload.customer_id) if payload.customer_id is not None else None
    if payload.customer_id is not None and customer is None:
        raise_not_found("Customer not found.")
    if customer is not None:
        if not customer.is_active:
            raise_bad_request("Cannot bill an inactive customer.")
        if user.role in {UserRole.STORE_MANAGER, UserRole.STAFF} and customer.branch_id not in {None, payload.branch_id}:
            raise_forbidden("You can only bill customers for your assigned branch.")
    return branch, customer


def load_products(db: Session, items: list[InvoiceItemCreate]) -> dict[int, Product]:
    product_ids = {item.product_id for item in items}
    products = {
        product.id: product
        for product in db.scalars(
            select(Product).options(joinedload(Product.gst_rate)).where(Product.id.in_(product_ids))
        ).all()
    }
    missing = product_ids - products.keys()
    if missing:
        raise_not_found("One or more products were not found.")
    return products


def calculate_line(
    *,
    product: Product,
    payload: InvoiceItemCreate,
    invoice_type: InvoiceType,
    seller_state_code: str | None,
    place_state_code: str | None,
) -> CalculatedLine:
    qty = quantity(payload.quantity)
    unit_price = money(payload.unit_price if payload.unit_price is not None else product.selling_price)
    discount = money(payload.discount)
    gross_line = money(unit_price * qty)
    if discount > gross_line:
        raise_bad_request(f"Discount cannot exceed line value for {product.sku}.")
    taxable_value = money(gross_line - discount)

    gst_rate = Decimal("0.00")
    cess_rate = money(product.cess_rate_percent or Decimal("0.00"))
    if invoice_type == InvoiceType.GST:
        tax_rate = product.gst_rate
        if tax_rate is not None:
            gst_rate = money(tax_rate.rate_percent)
            if cess_rate == Decimal("0.00"):
                cess_rate = money(tax_rate.cess_percent)

    cgst_total = sgst_total = igst_total = Decimal("0.00")
    if invoice_type == InvoiceType.GST and gst_rate > 0:
        if seller_state_code and place_state_code and seller_state_code != place_state_code:
            igst_total = money(taxable_value * gst_rate / PERCENT)
        else:
            half_rate = gst_rate / Decimal("2")
            cgst_total = money(taxable_value * half_rate / PERCENT)
            sgst_total = money(taxable_value * half_rate / PERCENT)

    cess_total = money(taxable_value * cess_rate / PERCENT) if invoice_type == InvoiceType.GST and cess_rate > 0 else Decimal("0.00")
    line_total = money(taxable_value + cgst_total + sgst_total + igst_total + cess_total)
    gross_profit = money(taxable_value - (product.unit_cost * qty))
    return CalculatedLine(
        product=product,
        quantity=qty,
        unit_price=unit_price,
        discount=discount,
        taxable_value=taxable_value,
        gst_rate=gst_rate,
        cess_rate=cess_rate,
        cgst_total=cgst_total,
        sgst_total=sgst_total,
        igst_total=igst_total,
        cess_total=cess_total,
        line_total=line_total,
        gross_profit=gross_profit,
    )


def add_item_tax_rows(db: Session, invoice_id: int, item: InvoiceItem, line: CalculatedLine, invoice_type: InvoiceType) -> None:
    if invoice_type != InvoiceType.GST:
        return

    if line.igst_total > 0 or (line.gst_rate >= 0 and line.cgst_total == 0 and line.sgst_total == 0):
        db.add(
            InvoiceTax(
                invoice_id=invoice_id,
                invoice_item_id=item.id,
                tax_type=InvoiceTaxType.IGST,
                tax_rate=line.gst_rate,
                taxable_value=line.taxable_value,
                tax_amount=line.igst_total,
            )
        )
    else:
        half_rate = money(line.gst_rate / Decimal("2"))
        db.add_all(
            [
                InvoiceTax(
                    invoice_id=invoice_id,
                    invoice_item_id=item.id,
                    tax_type=InvoiceTaxType.CGST,
                    tax_rate=half_rate,
                    taxable_value=line.taxable_value,
                    tax_amount=line.cgst_total,
                ),
                InvoiceTax(
                    invoice_id=invoice_id,
                    invoice_item_id=item.id,
                    tax_type=InvoiceTaxType.SGST,
                    tax_rate=half_rate,
                    taxable_value=line.taxable_value,
                    tax_amount=line.sgst_total,
                ),
            ]
        )
    if line.cess_rate > 0 or line.cess_total > 0:
        db.add(
            InvoiceTax(
                invoice_id=invoice_id,
                invoice_item_id=item.id,
                tax_type=InvoiceTaxType.CESS,
                tax_rate=line.cess_rate,
                taxable_value=line.taxable_value,
                tax_amount=line.cess_total,
            )
        )


def quote_invoice(db: Session, *, payload: InvoiceCreate, user: User) -> InvoiceQuoteRead:
    _, customer = validate_branch_customer(db, payload, user)
    seller_state, seller_state_code = get_branch_state(db, payload.branch_id)
    place_state, place_state_code = normalize_place_of_supply(
        db,
        branch_id=payload.branch_id,
        customer=customer,
        place_state=payload.place_of_supply_state,
        place_state_code=payload.place_of_supply_state_code,
    )
    products = load_products(db, payload.items)
    requested_by_product: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for item in payload.items:
        product = products[item.product_id]
        if not product.is_active:
            raise_bad_request(f"Inactive product {product.sku} cannot be billed.")
        if product.item_type != ProductItemType.SERVICE.value:
            requested_by_product[item.product_id] += quantity(item.quantity)

    inventories = {
        inventory.product_id: inventory
        for inventory in db.scalars(
            select(Inventory).where(
                Inventory.branch_id == payload.branch_id,
                Inventory.product_id.in_(products.keys()),
            )
        ).all()
    }

    quote_items: list[InvoiceQuoteItemRead] = []
    subtotal = discount_total = taxable_total = Decimal("0.00")
    cgst_total = sgst_total = igst_total = cess_total = Decimal("0.00")
    for item_payload in payload.items:
        product = products[item_payload.product_id]
        inventory = inventories.get(product.id)
        quantity_on_hand = quantity(inventory.quantity_on_hand if inventory is not None else Decimal("0.00"))
        requested_quantity = requested_by_product.get(product.id, Decimal("0.00"))
        if product.item_type != ProductItemType.SERVICE.value and requested_quantity > quantity_on_hand:
            raise_bad_request(
                f"Insufficient stock for {product.sku}. Available {quantity_on_hand}, requested {requested_quantity}."
            )

        line = calculate_line(
            product=product,
            payload=item_payload,
            invoice_type=payload.invoice_type,
            seller_state_code=seller_state_code,
            place_state_code=place_state_code,
        )
        quote_items.append(
            InvoiceQuoteItemRead(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                barcode=product.primary_barcode,
                hsn_sac_code=product.hsn_sac_code,
                quantity=line.quantity,
                unit_price=line.unit_price,
                mrp=product.mrp,
                discount=line.discount,
                taxable_value=line.taxable_value,
                gst_rate=line.gst_rate,
                cgst_total=line.cgst_total,
                sgst_total=line.sgst_total,
                igst_total=line.igst_total,
                cess_total=line.cess_total,
                line_total=line.line_total,
                gross_profit=line.gross_profit,
                quantity_on_hand=quantity_on_hand,
            )
        )
        subtotal += money(line.unit_price * line.quantity)
        discount_total += line.discount
        taxable_total += line.taxable_value
        cgst_total += line.cgst_total
        sgst_total += line.sgst_total
        igst_total += line.igst_total
        cess_total += line.cess_total

    grand_total = money(taxable_total + cgst_total + sgst_total + igst_total + cess_total)
    return InvoiceQuoteRead(
        branch_id=payload.branch_id,
        customer_id=payload.customer_id,
        invoice_type=payload.invoice_type,
        place_of_supply_state=place_state,
        place_of_supply_state_code=place_state_code,
        subtotal=money(subtotal),
        discount_total=money(discount_total),
        taxable_total=money(taxable_total),
        cgst_total=money(cgst_total),
        sgst_total=money(sgst_total),
        igst_total=money(igst_total),
        cess_total=money(cess_total),
        round_off=Decimal("0.00"),
        grand_total=grand_total,
        paid_amount=Decimal("0.00"),
        balance_due=grand_total,
        items=quote_items,
    )


def add_status_history(
    db: Session,
    *,
    invoice: Invoice,
    from_status: InvoiceStatus | None,
    to_status: InvoiceStatus,
    user: User,
    notes: str | None = None,
) -> None:
    db.add(
        InvoiceStatusHistory(
            invoice_id=invoice.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=user.id,
            notes=notes,
            changed_at=datetime.now(UTC),
        )
    )


def create_draft_invoice_record(db: Session, *, payload: InvoiceCreate, user: User, request: Request | None) -> Invoice:
    _, customer = validate_branch_customer(db, payload, user)
    seller_state, seller_state_code = get_branch_state(db, payload.branch_id)
    place_state, place_state_code = normalize_place_of_supply(
        db,
        branch_id=payload.branch_id,
        customer=customer,
        place_state=payload.place_of_supply_state,
        place_state_code=payload.place_of_supply_state_code,
    )
    products = load_products(db, payload.items)
    for item in payload.items:
        product = products[item.product_id]
        if not product.is_active:
            raise_bad_request(f"Inactive product {product.sku} cannot be billed.")

    company = get_default_company(db)
    invoice_number = generate_next_invoice_number(
        db,
        invoice_type=invoice_sequence_type(payload.invoice_type),
        branch_id=payload.branch_id,
        company_id=company.id,
    )
    invoice = Invoice(
        invoice_number=invoice_number,
        branch_id=payload.branch_id,
        customer_id=payload.customer_id,
        invoice_type=payload.invoice_type,
        place_of_supply_state=place_state,
        place_of_supply_state_code=place_state_code,
        invoice_date=payload.invoice_date or datetime.now(UTC),
        status=InvoiceStatus.DRAFT,
        payment_status=InvoicePaymentStatus.UNPAID,
        created_by=user.id,
    )
    db.add(invoice)
    db.flush()
    add_status_history(db, invoice=invoice, from_status=None, to_status=InvoiceStatus.DRAFT, user=user, notes="Draft created")

    subtotal = discount_total = taxable_total = Decimal("0.00")
    cgst_total = sgst_total = igst_total = cess_total = Decimal("0.00")
    for item_payload in payload.items:
        product = products[item_payload.product_id]
        line = calculate_line(
            product=product,
            payload=item_payload,
            invoice_type=payload.invoice_type,
            seller_state_code=seller_state_code,
            place_state_code=place_state_code,
        )
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            sku_snapshot=product.sku,
            hsn_sac_code=product.hsn_sac_code,
            quantity=line.quantity,
            unit_price=line.unit_price,
            mrp=product.mrp,
            discount=line.discount,
            taxable_value=line.taxable_value,
            gst_rate=line.gst_rate,
            cgst_total=line.cgst_total,
            sgst_total=line.sgst_total,
            igst_total=line.igst_total,
            cess_total=line.cess_total,
            line_total=line.line_total,
            gross_profit=line.gross_profit,
        )
        db.add(invoice_item)
        db.flush()
        add_item_tax_rows(db, invoice.id, invoice_item, line, payload.invoice_type)

        subtotal += money(line.unit_price * line.quantity)
        discount_total += line.discount
        taxable_total += line.taxable_value
        cgst_total += line.cgst_total
        sgst_total += line.sgst_total
        igst_total += line.igst_total
        cess_total += line.cess_total

    invoice.subtotal = money(subtotal)
    invoice.discount_total = money(discount_total)
    invoice.taxable_total = money(taxable_total)
    invoice.cgst_total = money(cgst_total)
    invoice.sgst_total = money(sgst_total)
    invoice.igst_total = money(igst_total)
    invoice.cess_total = money(cess_total)
    invoice.round_off = Decimal("0.00")
    invoice.grand_total = money(invoice.taxable_total + invoice.cgst_total + invoice.sgst_total + invoice.igst_total + invoice.cess_total)
    invoice.balance_due = invoice.grand_total
    db.flush()

    write_audit_log(
        db,
        action="invoice.draft_create",
        entity_type="invoice",
        entity_id=invoice.id,
        user=user,
        new_value_json={
            "invoice_number": invoice.invoice_number,
            "branch_id": invoice.branch_id,
            "customer_id": invoice.customer_id,
            "invoice_type": invoice.invoice_type.value,
            "grand_total": str(invoice.grand_total),
        },
        request=request,
    )
    return invoice


def create_invoice(db: Session, *, payload: InvoiceCreate, user: User, request: Request) -> InvoiceRead:
    try:
        invoice = create_draft_invoice_record(db, payload=payload, user=user, request=request)
        invoice_id = invoice.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=user))


def validate_stock_for_invoice(db: Session, invoice: Invoice) -> dict[int, Inventory]:
    requested_by_product: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    product_ids: set[int] = set()
    for item in invoice.items:
        product_ids.add(item.product_id)
        if item.product.item_type != ProductItemType.SERVICE.value:
            requested_by_product[item.product_id] += quantity(item.quantity)

    if not requested_by_product:
        return {}

    inventories = {
        inventory.product_id: inventory
        for inventory in db.scalars(
            select(Inventory)
            .where(
                Inventory.branch_id == invoice.branch_id,
                Inventory.product_id.in_(product_ids),
            )
            .with_for_update()
        ).all()
    }
    products_by_id = {item.product_id: item.product for item in invoice.items}
    for product_id, requested_quantity in requested_by_product.items():
        product = products_by_id[product_id]
        inventory = inventories.get(product_id)
        if inventory is None:
            raise_bad_request(f"No inventory record exists for {product.sku} at this branch.")
        if inventory.quantity_on_hand < requested_quantity:
            raise_bad_request(
                f"Insufficient stock for {product.sku}. Available {inventory.quantity_on_hand}, requested {requested_quantity}."
            )
    return inventories


def load_payment_mode(db: Session, payment_mode_id: int | None) -> PaymentMode | None:
    if payment_mode_id is None:
        return None
    payment_mode = db.get(PaymentMode, payment_mode_id)
    if payment_mode is None or not payment_mode.is_active:
        raise_not_found("Payment mode not found.")
    return payment_mode


def add_invoice_payments(
    db: Session,
    *,
    invoice: Invoice,
    payment_payloads: list[InvoicePaymentCreate],
    user: User,
    allow_credit_marker: bool,
) -> Decimal:
    actual_paid = Decimal("0.00")
    for payload in payment_payloads:
        payment_mode = load_payment_mode(db, payload.payment_mode_id)
        is_credit_marker = payment_mode is not None and payment_mode.mode_type == PaymentModeType.CREDIT
        if is_credit_marker and not allow_credit_marker:
            raise_bad_request("Credit payment mode cannot be used for payment collection.")
        if payment_mode is not None and payment_mode.requires_reference and not payload.reference_number:
            raise_bad_request(f"Reference number is required for {payment_mode.name}.")

        amount = money(payload.amount)
        db.add(
            InvoicePayment(
                invoice_id=invoice.id,
                payment_mode_id=payload.payment_mode_id,
                amount=amount,
                payment_datetime=payload.payment_datetime or datetime.now(UTC),
                reference_number=payload.reference_number,
                notes=payload.notes,
                received_by=user.id,
                is_credit_marker=is_credit_marker,
            )
        )
        if not is_credit_marker:
            actual_paid += amount
    return money(actual_paid)


def invoice_status_for_payment(grand_total: Decimal, paid_amount: Decimal, customer_id: int | None) -> tuple[InvoiceStatus, InvoicePaymentStatus]:
    balance_due = money(grand_total - paid_amount)
    if balance_due <= 0:
        return InvoiceStatus.PAID, InvoicePaymentStatus.PAID
    if paid_amount > 0:
        return InvoiceStatus.PARTIAL_PAID, InvoicePaymentStatus.PARTIAL_PAID
    if customer_id is not None:
        return InvoiceStatus.CREDIT, InvoicePaymentStatus.CREDIT
    return InvoiceStatus.ISSUED, InvoicePaymentStatus.UNPAID


def create_sales_compatibility_record(db: Session, *, invoice: Invoice, user: User) -> Sale:
    sale = Sale(
        sale_number=f"INV-{invoice.id}-{invoice.invoice_number}"[:50],
        branch_id=invoice.branch_id,
        sale_datetime=invoice.invoice_date,
        subtotal=invoice.taxable_total,
        discount_total=invoice.discount_total,
        tax_total=money(invoice.cgst_total + invoice.sgst_total + invoice.igst_total + invoice.cess_total),
        total_amount=invoice.grand_total,
        created_by=user.id,
    )
    db.add(sale)
    db.flush()
    for item in invoice.items:
        db.add(
            SaleItem(
                sale_id=sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount,
                line_total=item.taxable_value,
            )
        )
    invoice.sale_id = sale.id
    db.flush()
    return sale


def issue_invoice_record(
    db: Session,
    *,
    invoice: Invoice,
    payload: InvoiceIssueRequest,
    user: User,
    request: Request | None,
) -> Invoice:
    if invoice.status != InvoiceStatus.DRAFT:
        raise_bad_request("Only draft invoices can be issued.")
    ensure_invoice_write_permission(user, invoice.branch_id)
    inventories = validate_stock_for_invoice(db, invoice)

    actual_paid = add_invoice_payments(
        db,
        invoice=invoice,
        payment_payloads=payload.payments,
        user=user,
        allow_credit_marker=True,
    )
    if actual_paid > invoice.grand_total:
        raise_bad_request("Payment amount cannot exceed invoice total.")

    balance_due = money(invoice.grand_total - actual_paid)
    if balance_due > 0 and invoice.customer_id is None:
        raise_bad_request("A customer is required for credit or partial invoices.")
    if invoice.customer_id is not None and balance_due > 0:
        validate_customer_credit_limit(db, customer_id=invoice.customer_id, additional_debit=balance_due)

    now = datetime.now(UTC)
    for item in invoice.items:
        if item.product.item_type == ProductItemType.SERVICE.value:
            continue
        inventory = inventories[item.product_id]
        inventory.quantity_on_hand = quantity(inventory.quantity_on_hand - item.quantity)
        inventory.last_updated_at = now
        db.add(
            StockMovement(
                product_id=item.product_id,
                branch_id=invoice.branch_id,
                movement_type=StockMovementType.SALE,
                quantity_change=-item.quantity,
                reason=f"Invoice {invoice.invoice_number}",
                reference_type="invoice",
                reference_id=invoice.id,
                created_by=user.id,
                created_at=now,
            )
        )

    invoice.paid_amount = money(actual_paid)
    invoice.balance_due = balance_due
    old_status = invoice.status
    invoice.status, invoice.payment_status = invoice_status_for_payment(invoice.grand_total, invoice.paid_amount, invoice.customer_id)
    invoice.issued_at = now
    add_status_history(db, invoice=invoice, from_status=old_status, to_status=invoice.status, user=user, notes=payload.notes)

    create_sales_compatibility_record(db, invoice=invoice, user=user)

    if invoice.customer_id is not None and invoice.balance_due > 0:
        add_customer_ledger_entry(
            db,
            customer_id=invoice.customer_id,
            branch_id=invoice.branch_id,
            entry_type=CustomerLedgerEntryType.INVOICE,
            debit=invoice.balance_due,
            reference_type="invoice",
            reference_id=invoice.id,
            reason=f"Invoice {invoice.invoice_number} balance due",
            user=user,
            entry_datetime=invoice.invoice_date,
        )

    write_audit_log(
        db,
        action="invoice.issue",
        entity_type="invoice",
        entity_id=invoice.id,
        user=user,
        new_value_json={
            "invoice_number": invoice.invoice_number,
            "status": invoice.status.value,
            "paid_amount": str(invoice.paid_amount),
            "balance_due": str(invoice.balance_due),
            "sale_id": invoice.sale_id,
        },
        request=request,
    )
    db.flush()
    return invoice


def issue_invoice(
    db: Session,
    *,
    invoice_id: int,
    payload: InvoiceIssueRequest,
    user: User,
    request: Request,
) -> InvoiceRead:
    try:
        invoice = get_invoice_or_404(db, invoice_id, user=user)
        issue_invoice_record(db, invoice=invoice, payload=payload, user=user, request=request)
        invoice_id = invoice.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=user))


def pos_checkout(db: Session, *, payload: POSCheckoutRequest, user: User, request: Request) -> InvoiceRead:
    try:
        invoice = create_draft_invoice_record(db, payload=payload, user=user, request=request)
        issue_invoice_record(
            db,
            invoice=invoice,
            payload=InvoiceIssueRequest(payments=payload.payments, notes="POS checkout"),
            user=user,
            request=request,
        )
        invoice_id = invoice.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=user))


def cancel_invoice(
    db: Session,
    *,
    invoice_id: int,
    payload: InvoiceCancelRequest,
    user: User,
    request: Request,
) -> InvoiceRead:
    try:
        invoice = get_invoice_or_404(db, invoice_id, user=user)
        ensure_invoice_write_permission(user, invoice.branch_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise_bad_request("Only draft invoices can be cancelled in this phase. Use return/credit-note workflow for issued invoices.")
        old_status = invoice.status
        invoice.status = InvoiceStatus.CANCELLED
        invoice.cancelled_at = datetime.now(UTC)
        invoice.cancellation_reason = payload.reason
        add_status_history(db, invoice=invoice, from_status=old_status, to_status=InvoiceStatus.CANCELLED, user=user, notes=payload.reason)
        write_audit_log(
            db,
            action="invoice.cancel",
            entity_type="invoice",
            entity_id=invoice.id,
            user=user,
            new_value_json={"reason": payload.reason},
            request=request,
        )
        db.commit()
        invoice_id = invoice.id
    except Exception:
        db.rollback()
        raise
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=user))


def add_invoice_payment(
    db: Session,
    *,
    invoice_id: int,
    payload: InvoicePaymentCreate,
    user: User,
    request: Request,
) -> InvoiceRead:
    try:
        invoice = get_invoice_or_404(db, invoice_id, user=user)
        ensure_invoice_write_permission(user, invoice.branch_id)
        if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED}:
            raise_bad_request("Payments can only be collected against issued invoices.")
        if invoice.balance_due <= 0:
            raise_bad_request("Invoice has no balance due.")

        actual_paid = add_invoice_payments(
            db,
            invoice=invoice,
            payment_payloads=[payload],
            user=user,
            allow_credit_marker=False,
        )
        if actual_paid > invoice.balance_due:
            raise_bad_request("Payment amount cannot exceed invoice balance due.")

        old_status = invoice.status
        invoice.paid_amount = money(invoice.paid_amount + actual_paid)
        invoice.balance_due = money(invoice.grand_total - invoice.paid_amount)
        invoice.status, invoice.payment_status = invoice_status_for_payment(invoice.grand_total, invoice.paid_amount, invoice.customer_id)
        if invoice.customer_id is not None:
            add_customer_ledger_entry(
                db,
                customer_id=invoice.customer_id,
                branch_id=invoice.branch_id,
                entry_type=CustomerLedgerEntryType.PAYMENT,
                credit=actual_paid,
                reference_type="invoice_payment",
                reference_id=invoice.id,
                reason=f"Payment collected for invoice {invoice.invoice_number}",
                user=user,
                entry_datetime=payload.payment_datetime or datetime.now(UTC),
            )
        if old_status != invoice.status:
            add_status_history(db, invoice=invoice, from_status=old_status, to_status=invoice.status, user=user, notes="Payment collected")
        write_audit_log(
            db,
            action="invoice.payment",
            entity_type="invoice",
            entity_id=invoice.id,
            user=user,
            new_value_json={
                "payment_amount": str(actual_paid),
                "paid_amount": str(invoice.paid_amount),
                "balance_due": str(invoice.balance_due),
                "payment_status": invoice.payment_status.value,
            },
            request=request,
        )
        db.commit()
        invoice_id = invoice.id
    except Exception:
        db.rollback()
        raise
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=user))


def search_pos_products(
    db: Session,
    *,
    query: str,
    user: User,
    branch_id: int | None = None,
    limit: int = 20,
) -> list[POSProductSearchRead]:
    effective_branch_id = branch_id
    if effective_branch_id is None and user.role in {UserRole.STORE_MANAGER, UserRole.STAFF}:
        effective_branch_id = user.branch_id
    if effective_branch_id is not None:
        ensure_branch_access(user, effective_branch_id)

    term = f"%{query.strip()}%"
    statement = (
        select(Product)
        .options(joinedload(Product.gst_rate))
        .outerjoin(ProductBarcode)
        .where(Product.is_active.is_(True))
        .where(
            or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Product.primary_barcode.ilike(term),
                ProductBarcode.barcode.ilike(term),
            )
        )
        .order_by(Product.name)
        .limit(max(1, min(limit, 50)))
    )
    products = list(db.scalars(statement).unique().all())
    if not products:
        return []

    inventory_statement = select(Inventory).where(Inventory.product_id.in_([product.id for product in products]))
    if effective_branch_id is not None:
        inventory_statement = inventory_statement.where(Inventory.branch_id == effective_branch_id)
    inventories = list(db.scalars(inventory_statement).all())
    inventory_by_product: dict[int, list[Inventory]] = defaultdict(list)
    for inventory in inventories:
        inventory_by_product[inventory.product_id].append(inventory)

    branch_names = {}
    if effective_branch_id is not None:
        branch = db.get(Branch, effective_branch_id)
        branch_names[effective_branch_id] = branch.name if branch else None

    rows: list[POSProductSearchRead] = []
    for product in products:
        product_inventories = inventory_by_product.get(product.id, [])
        quantity_on_hand = sum((inventory.quantity_on_hand for inventory in product_inventories), Decimal("0.00"))
        rows.append(
            POSProductSearchRead(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                primary_barcode=product.primary_barcode,
                hsn_sac_code=product.hsn_sac_code,
                gst_rate=product.gst_rate.rate_percent if product.gst_rate else Decimal("0.00"),
                cess_rate_percent=product.cess_rate_percent,
                unit_of_measure=product.unit_of_measure,
                mrp=product.mrp,
                selling_price=product.selling_price,
                unit_cost=product.unit_cost,
                branch_id=effective_branch_id,
                branch_name=branch_names.get(effective_branch_id),
                quantity_on_hand=quantity(quantity_on_hand),
                is_active=product.is_active,
            )
        )
    return rows
