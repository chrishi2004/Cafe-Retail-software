from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    CafeOrder, CafeOrderItem, CafeOrderSource, CafeOrderStatus, CafeTable,
    Company, Invoice, InvoiceItem, InvoicePayment, InvoicePaymentStatus,
    InvoiceStatus, InvoiceType, MenuCategory, MenuItem, PaymentMode,
    PaymentModeType, TableSession, TableSessionStatus, TableSessionType,
)
from tests.multi_venture_fixtures import seed_two_ventures


def seed_p9(factory: sessionmaker[Session]) -> dict[str, int]:
    ids = seed_two_ventures(factory)
    with factory() as db:
        now = datetime.now(UTC)
        category = MenuCategory(company_id=2, branch_id=ids["cafe_branch"], name="Drinks")
        db.add(category)
        db.flush()
        item = MenuItem(
            company_id=2, branch_id=ids["cafe_branch"], category_id=category.id,
            name="Cafe Latte", selling_price=Decimal("40"), available=True,
        )
        table = CafeTable(
            company_id=2, branch_id=ids["cafe_branch"], table_code="T1", display_name="Table 1",
        )
        mode = PaymentMode(company_id=2, name="Cash", mode_type=PaymentModeType.CASH)
        retail_mode = PaymentMode(company_id=1, name="Retail Cash", mode_type=PaymentModeType.CASH)
        db.add_all([item, table, mode, retail_mode])
        db.flush()
        session = TableSession(
            company_id=2, branch_id=ids["cafe_branch"], table_id=table.id,
            public_id="p9-session-1",
            session_type=TableSessionType.DINE_IN, status=TableSessionStatus.OPEN,
            opened_at=now,
        )
        db.add(session)
        db.flush()
        order = CafeOrder(
            company_id=2, branch_id=ids["cafe_branch"], table_session_id=session.id,
            public_id="p9-order-1", order_number="P9-CAFE-1",
            order_type=TableSessionType.DINE_IN, source_channel=CafeOrderSource.QR_CUSTOMER,
            status=CafeOrderStatus.SERVED, subtotal=Decimal("40"),
            estimated_total=Decimal("40"), placed_at=now, created_by=ids["cafe_admin"],
        )
        cancelled = CafeOrder(
            company_id=2, branch_id=ids["cafe_branch"], public_id="p9-order-2",
            order_number="P9-CAFE-2", order_type=TableSessionType.TAKEAWAY,
            source_channel=CafeOrderSource.ORDER_TAKER, status=CafeOrderStatus.CANCELLED,
            subtotal=Decimal("20"), estimated_total=Decimal("20"), placed_at=now,
            created_by=ids["cafe_admin"],
        )
        db.add_all([order, cancelled])
        db.flush()
        db.add(
            CafeOrderItem(
                company_id=2, branch_id=ids["cafe_branch"], cafe_order_id=order.id,
                menu_item_id=item.id, product_id=ids["cafe_product"],
                menu_item_public_id_snapshot=item.public_id, menu_item_name_snapshot=item.name,
                product_sku_snapshot="CAFE-PRODUCT", quantity=1, unit_price_snapshot=Decimal("40"),
                line_total=Decimal("40"), source_channel=CafeOrderSource.QR_CUSTOMER,
            )
        )
        db.flush()
        cafe_invoice = Invoice(
            company_id=2, branch_id=ids["cafe_branch"], invoice_number="P9-CAFE-INV",
            invoice_type=InvoiceType.NON_GST, source_type="cafe_table_session",
            source_id=session.public_id, invoice_date=now, status=InvoiceStatus.PAID,
            payment_status=InvoicePaymentStatus.PAID, subtotal=Decimal("40"),
            taxable_total=Decimal("40"), grand_total=Decimal("40"), paid_amount=Decimal("40"),
            balance_due=Decimal("0"), created_by=ids["cafe_admin"], issued_at=now,
        )
        retail_invoice = Invoice(
            company_id=1, branch_id=ids["retail_branch"], invoice_number="P9-RETAIL-INV",
            invoice_type=InvoiceType.NON_GST, invoice_date=now, status=InvoiceStatus.PAID,
            payment_status=InvoicePaymentStatus.PAID, subtotal=Decimal("60"),
            taxable_total=Decimal("60"), grand_total=Decimal("60"), paid_amount=Decimal("60"),
            balance_due=Decimal("0"), created_by=1, issued_at=now,
        )
        db.add_all([cafe_invoice, retail_invoice])
        db.flush()
        db.add_all([
            InvoicePayment(invoice_id=cafe_invoice.id, payment_mode_id=mode.id, amount=Decimal("40"), payment_datetime=now),
            InvoicePayment(invoice_id=retail_invoice.id, payment_mode_id=retail_mode.id, amount=Decimal("60"), payment_datetime=now),
        ])
        db.commit()
        return {**ids, "cafe_invoice": cafe_invoice.id, "retail_invoice": retail_invoice.id}


def login_headers(client, email: str) -> dict[str, str]:
    from tests.multi_venture_fixtures import login_headers as _login
    return _login(client, email)
