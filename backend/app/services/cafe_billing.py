from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.core.scope import ScopeContext
from app.models import (
    Branch,
    BusinessProfile,
    BusinessType,
    CafeOrder,
    CafeOrderItem,
    CafeOrderItemStatus,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    Company,
    Customer,
    CustomerLedgerEntryType,
    Inventory,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    InvoicePaymentStatus,
    InvoiceSequenceType,
    InvoiceStatus,
    InvoiceType,
    PaymentMode,
    Product,
    ProductItemType,
    Sale,
    SaleItem,
    StockMovement,
    StockMovementType,
    TableSession,
    TableSessionStatus,
    TaxMode,
    User,
    UserRole,
)
from app.schemas.cafe_billing import (
    CafeBillPaymentRead,
    CafeBillQuoteRead,
    CafeBillRequest,
    CafeBillResultRead,
    CafeBillingItemRead,
    CafePaymentCollectRequest,
    CafeReceiptItemRead,
    CafeReceiptRead,
)
from app.services.audit import write_audit_log
from app.services.business_settings import generate_next_invoice_number
from app.services.customers import add_customer_ledger_entry, validate_customer_credit_limit
from app.services.invoices import add_invoice_payments, add_status_history, invoice_status_for_payment, money, quantity

BILLING_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER}
ELIGIBLE_ORDER_STATUSES = {
    CafeOrderStatus.ACCEPTED,
    CafeOrderStatus.SERVED,
    CafeOrderStatus.BILL_REQUESTED,
}
ELIGIBLE_ITEM_STATUSES = {CafeOrderItemStatus.ACCEPTED, CafeOrderItemStatus.SERVED}
SOURCE_TABLE = "cafe_table_session"
SOURCE_TAKEAWAY = "cafe_takeaway"


def _require_role(scope: ScopeContext) -> None:
    if scope.role != UserRole.SUPER_ADMIN and scope.role not in BILLING_ROLES:
        raise_forbidden("This Cafe billing action is not available to your role.")


def _require_cafe_company(db: Session, scope: ScopeContext) -> Company:
    _require_role(scope)
    if scope.company_id is None:
        raise_forbidden("Select the Cafe venture before using Cafe billing.")
    company = db.get(Company, scope.company_id)
    if company is None or not company.is_active or company.business_type != BusinessType.CAFE:
        raise_forbidden("Cafe billing is not available in this venture.")
    return company


def _ensure_branch(scope: ScopeContext, branch_id: int) -> None:
    if scope.branch_ids and branch_id not in scope.branch_ids:
        raise_forbidden("This Cafe branch is outside your assigned scope.")


def _tax_profile(db: Session, company_id: int) -> BusinessProfile:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company_id))
    if profile is None:
        raise_bad_request("Cafe business profile and tax operation mode must be configured before billing.")
    if profile.default_tax_mode != TaxMode.NON_GST:
        raise_bad_request(
            "This P8 Cafe billing path is restricted to the currently approved Non-GST operating mode."
        )
    return profile


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_hash(payload: CafeBillRequest) -> str:
    canonical = {
        "customer_id": payload.customer_id,
        "payments": [
            {
                "payment_mode_id": row.payment_mode_id,
                "amount": str(money(row.amount)),
                "payment_datetime": row.payment_datetime.isoformat() if row.payment_datetime else None,
                "reference_number": row.reference_number,
                "notes": row.notes,
            }
            for row in payload.payments
        ],
    }
    return _hash(json.dumps(canonical, sort_keys=True, separators=(",", ":")))


def _session_for_scope(
    db: Session,
    *,
    scope: ScopeContext,
    public_id: str,
    lock: bool = False,
) -> TableSession:
    company = _require_cafe_company(db, scope)
    statement = select(TableSession).where(
        TableSession.public_id == public_id,
        TableSession.company_id == company.id,
    )
    if scope.branch_ids:
        statement = statement.where(TableSession.branch_id.in_(scope.branch_ids))
    if lock:
        statement = statement.with_for_update()
    session = db.scalar(statement)
    if session is None:
        raise_not_found("Cafe table session not found.")
    _ensure_branch(scope, session.branch_id)
    return session


def _standalone_order_for_scope(
    db: Session,
    *,
    scope: ScopeContext,
    public_id: str,
    lock: bool = False,
) -> CafeOrder:
    company = _require_cafe_company(db, scope)
    statement = select(CafeOrder).where(
        CafeOrder.public_id == public_id,
        CafeOrder.company_id == company.id,
        CafeOrder.table_session_id.is_(None),
    )
    if scope.branch_ids:
        statement = statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    if lock:
        statement = statement.with_for_update()
    order = db.scalar(statement)
    if order is None:
        raise_not_found("Cafe takeaway/counter order not found.")
    _ensure_branch(scope, order.branch_id)
    return order


def _orders_for_session(db: Session, session: TableSession, *, lock: bool = False) -> list[CafeOrder]:
    statement = select(CafeOrder).where(
        CafeOrder.company_id == session.company_id,
        CafeOrder.branch_id == session.branch_id,
        CafeOrder.table_session_id == session.id,
    ).order_by(CafeOrder.id)
    if lock:
        statement = statement.with_for_update()
    return list(db.scalars(statement).all())


def _items_for_orders(db: Session, orders: list[CafeOrder], *, lock: bool = False) -> list[CafeOrderItem]:
    order_ids = [row.id for row in orders]
    if not order_ids:
        return []
    statement = select(CafeOrderItem).where(CafeOrderItem.cafe_order_id.in_(order_ids)).order_by(
        CafeOrderItem.cafe_order_id, CafeOrderItem.id
    )
    if lock:
        statement = statement.with_for_update()
    return list(db.scalars(statement).all())


def _quote_from_rows(
    *,
    source_type: str,
    source_id: str,
    branch_id: int,
    source_version: int,
    orders: list[CafeOrder],
    items: list[CafeOrderItem],
    session: TableSession | None,
) -> CafeBillQuoteRead:
    by_order = {row.id: row for row in orders}
    eligible: list[CafeBillingItemRead] = []
    excluded: list[CafeBillingItemRead] = []
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    taxable_total = Decimal("0.00")

    for item in items:
        order = by_order[item.cafe_order_id]
        billed = item.billed_invoice_item_id is not None
        reason = None
        if billed:
            reason = "already_billed"
        elif order.status not in ELIGIBLE_ORDER_STATUSES:
            reason = f"order_{order.status.value}"
        elif item.item_status not in ELIGIBLE_ITEM_STATUSES:
            reason = f"item_{item.item_status.value}"

        row = CafeBillingItemRead(
            order_public_id=order.public_id,
            order_number=order.order_number,
            source_channel=order.source_channel,
            order_status=order.status,
            order_item_id=item.id,
            menu_item_name=item.menu_item_name_snapshot,
            product_id=item.product_id,
            sku=item.product_sku_snapshot,
            quantity=item.quantity,
            unit_price=item.unit_price_snapshot,
            discount=item.discount_amount,
            line_total=item.line_total,
            billed=billed,
            excluded_reason=reason,
        )
        if reason is None:
            eligible.append(row)
            subtotal += money(item.unit_price_snapshot * item.quantity)
            discount_total += money(item.discount_amount)
            taxable_total += money(item.line_total)
        else:
            excluded.append(row)

    taxable_total = money(taxable_total)
    return CafeBillQuoteRead(
        source_type=source_type,
        source_id=source_id,
        branch_id=branch_id,
        table_session_public_id=session.public_id if session else None,
        table_session_status=session.status if session else None,
        source_version=source_version,
        subtotal=money(subtotal),
        discount_total=money(discount_total),
        taxable_total=taxable_total,
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("0.00"),
        cess_total=Decimal("0.00"),
        round_off=Decimal("0.00"),
        grand_total=taxable_total,
        eligible_items=eligible,
        excluded_items=excluded,
    )


def quote_table_session(
    db: Session, *, scope: ScopeContext, session_public_id: str
) -> CafeBillQuoteRead:
    session = _session_for_scope(db, scope=scope, public_id=session_public_id)
    _tax_profile(db, session.company_id)
    orders = _orders_for_session(db, session)
    items = _items_for_orders(db, orders)
    return _quote_from_rows(
        source_type=SOURCE_TABLE,
        source_id=session.public_id,
        branch_id=session.branch_id,
        source_version=session.version,
        orders=orders,
        items=items,
        session=session,
    )


def quote_standalone_order(
    db: Session, *, scope: ScopeContext, order_public_id: str
) -> CafeBillQuoteRead:
    order = _standalone_order_for_scope(db, scope=scope, public_id=order_public_id)
    _tax_profile(db, order.company_id)
    items = _items_for_orders(db, [order])
    return _quote_from_rows(
        source_type=SOURCE_TAKEAWAY,
        source_id=order.public_id,
        branch_id=order.branch_id,
        source_version=order.version,
        orders=[order],
        items=items,
        session=None,
    )


def _validate_customer(db: Session, *, company_id: int, branch_id: int, customer_id: int | None) -> Customer | None:
    if customer_id is None:
        return None
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.company_id == company_id)
    )
    if customer is None or not customer.is_active:
        raise_not_found("Cafe customer not found.")
    if customer.branch_id not in {None, branch_id}:
        raise_forbidden("Customer is outside this Cafe branch.")
    return customer


def _validate_payment_modes(db: Session, *, company_id: int, payload: CafeBillRequest) -> None:
    for row in payload.payments:
        if row.payment_mode_id is None:
            continue
        mode = db.scalar(
            select(PaymentMode).where(
                PaymentMode.id == row.payment_mode_id,
                PaymentMode.company_id == company_id,
                PaymentMode.is_active.is_(True),
            )
        )
        if mode is None:
            raise_not_found("Payment mode not found for this Cafe venture.")
        if mode.requires_reference and not row.reference_number:
            raise_bad_request(f"Reference number is required for {mode.name}.")


def _existing_idempotent_invoice(
    db: Session,
    *,
    company_id: int,
    idempotency_hash: str,
    request_hash: str,
    source_type: str,
    source_id: str,
) -> Invoice | None:
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.billing_idempotency_key_hash == idempotency_hash,
        )
    )
    if invoice is None:
        return None
    if invoice.billing_request_hash != request_hash:
        raise_conflict("The same Idempotency-Key was already used with a different billing request.")
    if invoice.source_type != source_type or invoice.source_id != source_id:
        raise_conflict("The Idempotency-Key belongs to a different Cafe billing source.")
    return invoice


def _active_source_invoice(
    db: Session, *, company_id: int, source_type: str, source_id: str
) -> Invoice | None:
    return db.scalar(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.source_type == source_type,
            Invoice.source_id == source_id,
            Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED]),
        )
    )


def _create_invoice_and_items(
    db: Session,
    *,
    company_id: int,
    branch_id: int,
    source_type: str,
    source_id: str,
    idempotency_hash: str,
    request_hash: str,
    customer_id: int | None,
    quote: CafeBillQuoteRead,
    order_items: list[CafeOrderItem],
    user: User,
) -> tuple[Invoice, dict[int, InvoiceItem]]:
    invoice_number = generate_next_invoice_number(
        db,
        invoice_type=InvoiceSequenceType.NON_GST_INVOICE,
        branch_id=branch_id,
        company_id=company_id,
    )
    invoice = Invoice(
        company_id=company_id,
        invoice_number=invoice_number,
        branch_id=branch_id,
        customer_id=customer_id,
        invoice_type=InvoiceType.NON_GST,
        source_type=source_type,
        source_id=source_id,
        billing_idempotency_key_hash=idempotency_hash,
        billing_request_hash=request_hash,
        invoice_date=datetime.now(UTC),
        status=InvoiceStatus.DRAFT,
        payment_status=InvoicePaymentStatus.UNPAID,
        subtotal=quote.subtotal,
        discount_total=quote.discount_total,
        taxable_total=quote.taxable_total,
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("0.00"),
        cess_total=Decimal("0.00"),
        round_off=Decimal("0.00"),
        grand_total=quote.grand_total,
        paid_amount=Decimal("0.00"),
        balance_due=quote.grand_total,
        created_by=user.id,
    )
    db.add(invoice)
    db.flush()
    add_status_history(
        db,
        invoice=invoice,
        from_status=None,
        to_status=InvoiceStatus.DRAFT,
        user=user,
        notes="Cafe bill draft created",
    )

    products: dict[int, Product] = {}
    product_ids = {row.product_id for row in order_items if row.product_id is not None}
    if product_ids:
        products = {
            row.id: row
            for row in db.scalars(
                select(Product).where(Product.id.in_(product_ids), Product.company_id == company_id)
            ).all()
        }
        if set(product_ids) != set(products):
            raise_bad_request("One or more Cafe order items reference an invalid venture product.")

    eligible_ids = {row.order_item_id for row in quote.eligible_items}
    invoice_items: dict[int, InvoiceItem] = {}
    for source_item in order_items:
        if source_item.id not in eligible_ids:
            continue
        product = products.get(source_item.product_id) if source_item.product_id is not None else None
        qty = quantity(source_item.quantity)
        line_total = money(source_item.line_total)
        gross_profit = (
            money(line_total - (product.unit_cost * qty)) if product is not None else Decimal("0.00")
        )
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=source_item.product_id,
            product_name_snapshot=source_item.menu_item_name_snapshot,
            sku_snapshot=(
                source_item.product_sku_snapshot
                or f"CAFE-{source_item.menu_item_public_id_snapshot}"[:64]
            ),
            hsn_sac_code=product.hsn_sac_code if product is not None else None,
            quantity=qty,
            unit_price=money(source_item.unit_price_snapshot),
            mrp=product.mrp if product is not None else None,
            discount=money(source_item.discount_amount),
            taxable_value=line_total,
            gst_rate=Decimal("0.00"),
            cgst_total=Decimal("0.00"),
            sgst_total=Decimal("0.00"),
            igst_total=Decimal("0.00"),
            cess_total=Decimal("0.00"),
            line_total=line_total,
            gross_profit=gross_profit,
        )
        db.add(invoice_item)
        db.flush()
        source_item.billed_invoice_item_id = invoice_item.id
        source_item.item_status = CafeOrderItemStatus.BILLED
        source_item.version += 1
        invoice_items[source_item.id] = invoice_item
    return invoice, invoice_items


def _apply_stock_and_sale(
    db: Session,
    *,
    invoice: Invoice,
    invoice_items: dict[int, InvoiceItem],
    user: User,
) -> Sale:
    product_ids = {row.product_id for row in invoice_items.values() if row.product_id is not None}
    products = {
        row.id: row
        for row in db.scalars(select(Product).where(Product.id.in_(product_ids or {-1}))).all()
    }
    inventories = {
        row.product_id: row
        for row in db.scalars(
            select(Inventory)
            .where(
                Inventory.company_id == invoice.company_id,
                Inventory.branch_id == invoice.branch_id,
                Inventory.product_id.in_(product_ids or {-1}),
            )
            .with_for_update()
        ).all()
    }
    now = datetime.now(UTC)
    for item in invoice_items.values():
        if item.product_id is None:
            continue
        product = products[item.product_id]
        if product.item_type == ProductItemType.SERVICE.value:
            continue
        inventory = inventories.get(item.product_id)
        if inventory is None:
            raise_bad_request(f"No inventory record exists for {product.sku} at this Cafe branch.")
        if inventory.quantity_on_hand < item.quantity:
            raise_bad_request(
                f"Insufficient stock for {product.sku}. Available {inventory.quantity_on_hand}, requested {item.quantity}."
            )
        inventory.quantity_on_hand = quantity(inventory.quantity_on_hand - item.quantity)
        inventory.last_updated_at = now
        db.add(
            StockMovement(
                company_id=invoice.company_id,
                product_id=item.product_id,
                branch_id=invoice.branch_id,
                movement_type=StockMovementType.SALE,
                quantity_change=-item.quantity,
                reason=f"Cafe invoice {invoice.invoice_number}",
                reference_type="invoice",
                reference_id=invoice.id,
                created_by=user.id,
                created_at=now,
            )
        )

    sale = Sale(
        company_id=invoice.company_id,
        sale_number=f"INV-{invoice.id}-{invoice.invoice_number}"[:50],
        branch_id=invoice.branch_id,
        sale_datetime=invoice.invoice_date,
        subtotal=invoice.taxable_total,
        discount_total=invoice.discount_total,
        tax_total=Decimal("0.00"),
        total_amount=invoice.grand_total,
        created_by=user.id,
    )
    db.add(sale)
    db.flush()
    for item in invoice_items.values():
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
    return sale


def _add_order_history(
    db: Session,
    *,
    order: CafeOrder,
    old: CafeOrderStatus,
    new: CafeOrderStatus,
    user: User,
    reason: str,
) -> None:
    db.add(
        CafeOrderStatusHistory(
            company_id=order.company_id,
            branch_id=order.branch_id,
            cafe_order_id=order.id,
            from_status=old,
            to_status=new,
            changed_by=user.id,
            guest_action=False,
            reason=reason,
            created_at=datetime.now(UTC),
        )
    )


def _mark_billed(
    db: Session,
    *,
    invoice: Invoice,
    orders: list[CafeOrder],
    session: TableSession | None,
    user: User,
) -> None:
    for order in orders:
        if order.billed_invoice_id is not None:
            continue
        if order.status not in ELIGIBLE_ORDER_STATUSES:
            continue
        old = order.status
        order.status = CafeOrderStatus.BILLED
        order.billed_invoice_id = invoice.id
        order.version += 1
        _add_order_history(
            db,
            order=order,
            old=old,
            new=CafeOrderStatus.BILLED,
            user=user,
            reason=f"Billed on invoice {invoice.invoice_number}",
        )
    if session is not None:
        session.status = TableSessionStatus.BILLED
        session.billed_invoice_id = invoice.id
        session.version += 1


def _close_source_if_settled(
    db: Session,
    *,
    invoice: Invoice,
    orders: list[CafeOrder],
    session: TableSession | None,
    user: User,
) -> bool:
    if invoice.balance_due > 0 or invoice.payment_status != InvoicePaymentStatus.PAID:
        return False
    now = datetime.now(UTC)
    for order in orders:
        if order.billed_invoice_id != invoice.id or order.status != CafeOrderStatus.BILLED:
            continue
        old = order.status
        order.status = CafeOrderStatus.CLOSED
        order.version += 1
        _add_order_history(
            db,
            order=order,
            old=old,
            new=CafeOrderStatus.CLOSED,
            user=user,
            reason=f"Settled by invoice {invoice.invoice_number}",
        )
    if session is not None:
        session.status = TableSessionStatus.CLOSED
        session.closed_by = user.id
        session.closed_at = now
        session.version += 1
    return True


def _issue_financial_effects(
    db: Session,
    *,
    invoice: Invoice,
    invoice_items: dict[int, InvoiceItem],
    payload: CafeBillRequest,
    user: User,
    request: Request | None,
) -> None:
    actual_paid = add_invoice_payments(
        db,
        invoice=invoice,
        payment_payloads=list(payload.payments),
        user=user,
        allow_credit_marker=True,
    )
    if actual_paid > invoice.grand_total:
        raise_bad_request("Payment amount cannot exceed Cafe bill total.")
    balance_due = money(invoice.grand_total - actual_paid)
    if balance_due > 0 and invoice.customer_id is None:
        raise_bad_request("Anonymous Cafe bills must be fully covered by non-credit payments.")
    if invoice.customer_id is not None and balance_due > 0:
        validate_customer_credit_limit(db, customer_id=invoice.customer_id, additional_debit=balance_due)

    _apply_stock_and_sale(db, invoice=invoice, invoice_items=invoice_items, user=user)
    old_status = invoice.status
    invoice.paid_amount = money(actual_paid)
    invoice.balance_due = balance_due
    invoice.status, invoice.payment_status = invoice_status_for_payment(
        invoice.grand_total, invoice.paid_amount, invoice.customer_id
    )
    invoice.issued_at = datetime.now(UTC)
    add_status_history(
        db,
        invoice=invoice,
        from_status=old_status,
        to_status=invoice.status,
        user=user,
        notes="Cafe bill issued",
    )
    if invoice.customer_id is not None and invoice.balance_due > 0:
        add_customer_ledger_entry(
            db,
            customer_id=invoice.customer_id,
            branch_id=invoice.branch_id,
            entry_type=CustomerLedgerEntryType.INVOICE,
            debit=invoice.balance_due,
            reference_type="invoice",
            reference_id=invoice.id,
            reason=f"Cafe invoice {invoice.invoice_number} balance due",
            user=user,
            entry_datetime=invoice.invoice_date,
        )
    write_audit_log(
        db,
        action="cafe_billing_issue",
        entity_type="invoice",
        entity_id=invoice.id,
        user=user,
        company_id=invoice.company_id,
        new_value_json={
            "invoice_number": invoice.invoice_number,
            "source_type": invoice.source_type,
            "source_id": invoice.source_id,
            "grand_total": str(invoice.grand_total),
            "paid_amount": str(invoice.paid_amount),
            "balance_due": str(invoice.balance_due),
            "sale_id": invoice.sale_id,
        },
        request=request,
    )


def _load_invoice_for_receipt(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments).selectinload(InvoicePayment.payment_mode),
        )
        .where(Invoice.id == invoice_id)
    )
    if invoice is None:
        raise_not_found("Cafe invoice not found.")
    return invoice


def receipt_for_invoice(
    db: Session, *, scope: ScopeContext, invoice_id: int
) -> CafeReceiptRead:
    company = _require_cafe_company(db, scope)
    invoice = _load_invoice_for_receipt(db, invoice_id)
    if invoice.company_id != company.id or invoice.source_type not in {SOURCE_TABLE, SOURCE_TAKEAWAY}:
        raise_not_found("Cafe invoice not found.")
    _ensure_branch(scope, invoice.branch_id)
    branch = db.get(Branch, invoice.branch_id)
    return CafeReceiptRead(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        source_type=invoice.source_type or "",
        source_id=invoice.source_id or "",
        cafe_name=company.trade_name or company.name,
        branch_name=branch.name if branch else "Cafe",
        invoice_type=invoice.invoice_type.value,
        invoice_status=invoice.status,
        payment_status=invoice.payment_status,
        issued_at=invoice.issued_at,
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
        gstin=None,
        items=[
            CafeReceiptItemRead(
                name=row.product_name_snapshot,
                sku=row.sku_snapshot,
                quantity=row.quantity,
                unit_price=row.unit_price,
                discount=row.discount,
                line_total=row.line_total,
            )
            for row in sorted(invoice.items, key=lambda item: item.id)
        ],
        payments=[
            CafeBillPaymentRead(
                mode_name=row.payment_mode.name if row.payment_mode else None,
                amount=row.amount,
                reference_number=row.reference_number,
                is_credit_marker=row.is_credit_marker,
            )
            for row in sorted(invoice.payments, key=lambda payment: payment.id)
        ],
    )


def _result_for_invoice(
    db: Session,
    *,
    scope: ScopeContext,
    invoice: Invoice,
    replay: bool,
) -> CafeBillResultRead:
    receipt = receipt_for_invoice(db, scope=scope, invoice_id=invoice.id)
    session_status = None
    order_status = None
    closed = False
    if invoice.source_type == SOURCE_TABLE and invoice.source_id:
        session = db.scalar(
            select(TableSession).where(
                TableSession.company_id == invoice.company_id,
                TableSession.public_id == invoice.source_id,
            )
        )
        session_status = session.status if session else None
        closed = session_status == TableSessionStatus.CLOSED
    elif invoice.source_type == SOURCE_TAKEAWAY and invoice.source_id:
        order = db.scalar(
            select(CafeOrder).where(
                CafeOrder.company_id == invoice.company_id,
                CafeOrder.public_id == invoice.source_id,
            )
        )
        order_status = order.status if order else None
        closed = order_status == CafeOrderStatus.CLOSED
    return CafeBillResultRead(
        receipt=receipt,
        table_session_status=session_status,
        order_status=order_status,
        closed=closed,
        idempotent_replay=replay,
    )


def _bill(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    source_type: str,
    source_id: str,
    payload: CafeBillRequest,
    idempotency_key: str,
    request: Request | None,
) -> CafeBillResultRead:
    company = _require_cafe_company(db, scope)
    if len(idempotency_key.strip()) < 8 or len(idempotency_key) > 200:
        raise_bad_request("A stable Idempotency-Key of at least 8 characters is required.")
    idem_hash = _hash(idempotency_key.strip())
    req_hash = _request_hash(payload)

    existing = _existing_idempotent_invoice(
        db,
        company_id=company.id,
        idempotency_hash=idem_hash,
        request_hash=req_hash,
        source_type=source_type,
        source_id=source_id,
    )
    if existing is not None:
        return _result_for_invoice(db, scope=scope, invoice=existing, replay=True)

    existing_source = _active_source_invoice(
        db, company_id=company.id, source_type=source_type, source_id=source_id
    )
    if existing_source is not None:
        raise_conflict("This Cafe billing source already has an active invoice.")

    session: TableSession | None = None
    if source_type == SOURCE_TABLE:
        session = _session_for_scope(db, scope=scope, public_id=source_id, lock=True)
        if session.status not in {TableSessionStatus.OPEN, TableSessionStatus.BILL_REQUESTED}:
            raise_conflict("This table session is already billed, closed, or cancelled.")
        if payload.expected_version is None or session.version != payload.expected_version:
            raise_conflict("This table session changed. Refresh the bill quote and try again.")
        orders = _orders_for_session(db, session, lock=True)
        source_version = session.version
        branch_id = session.branch_id
    else:
        order = _standalone_order_for_scope(db, scope=scope, public_id=source_id, lock=True)
        if order.status in {CafeOrderStatus.BILLED, CafeOrderStatus.CLOSED, CafeOrderStatus.CANCELLED, CafeOrderStatus.REJECTED}:
            raise_conflict("This takeaway/counter order cannot be billed.")
        if payload.expected_version is None or order.version != payload.expected_version:
            raise_conflict("This Cafe order changed. Refresh the bill quote and try again.")
        orders = [order]
        source_version = order.version
        branch_id = order.branch_id

    _tax_profile(db, company.id)
    _validate_customer(db, company_id=company.id, branch_id=branch_id, customer_id=payload.customer_id)
    _validate_payment_modes(db, company_id=company.id, payload=payload)
    items = _items_for_orders(db, orders, lock=True)
    quote = _quote_from_rows(
        source_type=source_type,
        source_id=source_id,
        branch_id=branch_id,
        source_version=source_version,
        orders=orders,
        items=items,
        session=session,
    )
    if not quote.eligible_items:
        raise_conflict("No eligible unbilled Cafe items remain for this billing source.")

    invoice, invoice_items = _create_invoice_and_items(
        db,
        company_id=company.id,
        branch_id=branch_id,
        source_type=source_type,
        source_id=source_id,
        idempotency_hash=idem_hash,
        request_hash=req_hash,
        customer_id=payload.customer_id,
        quote=quote,
        order_items=items,
        user=user,
    )
    _issue_financial_effects(
        db,
        invoice=invoice,
        invoice_items=invoice_items,
        payload=payload,
        user=user,
        request=request,
    )
    _mark_billed(db, invoice=invoice, orders=orders, session=session, user=user)
    closed = _close_source_if_settled(
        db, invoice=invoice, orders=orders, session=session, user=user
    )
    write_audit_log(
        db,
        action="cafe_billing_source_close" if closed else "cafe_billing_source_billed",
        entity_type="table_session" if session else "cafe_order",
        entity_id=session.id if session else orders[0].id,
        user=user,
        company_id=company.id,
        new_value_json={
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "closed": closed,
        },
        request=request,
    )
    db.commit()
    return _result_for_invoice(db, scope=scope, invoice=invoice, replay=False)


def bill_table_session(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    session_public_id: str,
    payload: CafeBillRequest,
    idempotency_key: str,
    request: Request | None = None,
) -> CafeBillResultRead:
    try:
        return _bill(
            db,
            scope=scope,
            user=user,
            source_type=SOURCE_TABLE,
            source_id=session_public_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request=request,
        )
    except IntegrityError:
        db.rollback()
        company = _require_cafe_company(db, scope)
        invoice = _existing_idempotent_invoice(
            db,
            company_id=company.id,
            idempotency_hash=_hash(idempotency_key.strip()),
            request_hash=_request_hash(payload),
            source_type=SOURCE_TABLE,
            source_id=session_public_id,
        )
        if invoice is not None:
            return _result_for_invoice(db, scope=scope, invoice=invoice, replay=True)
        raise_conflict("This table session was billed concurrently. Refresh before continuing.")
    except Exception:
        db.rollback()
        raise


def bill_standalone_order(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    order_public_id: str,
    payload: CafeBillRequest,
    idempotency_key: str,
    request: Request | None = None,
) -> CafeBillResultRead:
    try:
        return _bill(
            db,
            scope=scope,
            user=user,
            source_type=SOURCE_TAKEAWAY,
            source_id=order_public_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request=request,
        )
    except IntegrityError:
        db.rollback()
        company = _require_cafe_company(db, scope)
        invoice = _existing_idempotent_invoice(
            db,
            company_id=company.id,
            idempotency_hash=_hash(idempotency_key.strip()),
            request_hash=_request_hash(payload),
            source_type=SOURCE_TAKEAWAY,
            source_id=order_public_id,
        )
        if invoice is not None:
            return _result_for_invoice(db, scope=scope, invoice=invoice, replay=True)
        raise_conflict("This Cafe order was billed concurrently. Refresh before continuing.")
    except Exception:
        db.rollback()
        raise


def collect_invoice_payment(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    invoice_id: int,
    payload: CafePaymentCollectRequest,
    request: Request | None = None,
) -> CafeBillResultRead:
    company = _require_cafe_company(db, scope)
    try:
        invoice = db.scalar(
            select(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.company_id == company.id,
                Invoice.source_type.in_([SOURCE_TABLE, SOURCE_TAKEAWAY]),
            )
            .with_for_update()
        )
        if invoice is None:
            raise_not_found("Cafe invoice not found.")
        _ensure_branch(scope, invoice.branch_id)
        if invoice.balance_due <= 0:
            raise_conflict("This Cafe invoice is already settled.")
        wrapped = CafeBillRequest(payments=[payload.payment])
        _validate_payment_modes(db, company_id=company.id, payload=wrapped)
        actual_paid = add_invoice_payments(
            db,
            invoice=invoice,
            payment_payloads=[payload.payment],
            user=user,
            allow_credit_marker=False,
        )
        if actual_paid > invoice.balance_due:
            raise_bad_request("Payment amount cannot exceed the Cafe invoice balance.")
        old_status = invoice.status
        invoice.paid_amount = money(invoice.paid_amount + actual_paid)
        invoice.balance_due = money(invoice.grand_total - invoice.paid_amount)
        invoice.status, invoice.payment_status = invoice_status_for_payment(
            invoice.grand_total, invoice.paid_amount, invoice.customer_id
        )
        if invoice.customer_id is not None:
            add_customer_ledger_entry(
                db,
                customer_id=invoice.customer_id,
                branch_id=invoice.branch_id,
                entry_type=CustomerLedgerEntryType.PAYMENT,
                credit=actual_paid,
                reference_type="invoice_payment",
                reference_id=invoice.id,
                reason=f"Payment collected for Cafe invoice {invoice.invoice_number}",
                user=user,
                entry_datetime=payload.payment.payment_datetime or datetime.now(UTC),
            )
        if old_status != invoice.status:
            add_status_history(
                db,
                invoice=invoice,
                from_status=old_status,
                to_status=invoice.status,
                user=user,
                notes="Cafe payment collected",
            )

        if invoice.source_type == SOURCE_TABLE:
            session = db.scalar(
                select(TableSession)
                .where(
                    TableSession.company_id == company.id,
                    TableSession.public_id == invoice.source_id,
                )
                .with_for_update()
            )
            orders = _orders_for_session(db, session, lock=True) if session else []
        else:
            session = None
            order = _standalone_order_for_scope(
                db, scope=scope, public_id=invoice.source_id or "", lock=True
            )
            orders = [order]
        closed = _close_source_if_settled(
            db, invoice=invoice, orders=orders, session=session, user=user
        )
        write_audit_log(
            db,
            action="cafe_billing_payment",
            entity_type="invoice",
            entity_id=invoice.id,
            user=user,
            company_id=company.id,
            new_value_json={
                "payment_amount": str(actual_paid),
                "paid_amount": str(invoice.paid_amount),
                "balance_due": str(invoice.balance_due),
                "closed": closed,
            },
            request=request,
        )
        db.commit()
        return _result_for_invoice(db, scope=scope, invoice=invoice, replay=False)
    except Exception:
        db.rollback()
        raise
