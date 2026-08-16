from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AIChatSession,
    BusinessProfile,
    Customer,
    Forecast,
    ForecastType,
    Invoice,
    InvoiceType,
    Product,
    PurchaseOrder,
    Sale,
    SaleItem,
    Supplier,
    TaxMode,
    User,
)
from tests.multi_venture_fixtures import login_headers, seed_two_ventures


def _seed_reporting_rows(factory: sessionmaker[Session], ids: dict[str, int]) -> dict[str, int]:
    with factory() as db:
        retail_admin = db.query(User).filter(User.email == "admin@hybridretail.test").one()
        cafe_admin = db.get(User, ids["cafe_admin"])
        assert cafe_admin is not None
        retail_product = db.get(Product, ids["retail_product"])
        cafe_product = db.get(Product, ids["cafe_product"])
        retail_supplier = db.get(Supplier, ids["retail_supplier"])
        cafe_supplier = db.get(Supplier, ids["cafe_supplier"])
        assert retail_product and cafe_product and retail_supplier and cafe_supplier

        retail_customer = Customer(company_id=1, branch_id=ids["retail_branch"], name="Retail Customer", phone="9100000001")
        cafe_customer = Customer(company_id=2, branch_id=ids["cafe_branch"], name="Cafe Customer", phone="9100000002")
        db.add_all([retail_customer, cafe_customer])
        db.flush()

        retail_sale = Sale(
            company_id=1,
            sale_number="RETAIL-SALE-P2",
            branch_id=ids["retail_branch"],
            sale_datetime=datetime.now(UTC),
            subtotal=Decimal("15"),
            total_amount=Decimal("15"),
            created_by=retail_admin.id,
        )
        cafe_sale = Sale(
            company_id=2,
            sale_number="CAFE-SALE-P2",
            branch_id=ids["cafe_branch"],
            sale_datetime=datetime.now(UTC),
            subtotal=Decimal("30"),
            total_amount=Decimal("30"),
            created_by=cafe_admin.id,
        )
        db.add_all([retail_sale, cafe_sale])
        db.flush()
        db.add_all([
            SaleItem(sale_id=retail_sale.id, product_id=retail_product.id, quantity=Decimal("1"), unit_price=Decimal("15"), line_total=Decimal("15")),
            SaleItem(sale_id=cafe_sale.id, product_id=cafe_product.id, quantity=Decimal("1"), unit_price=Decimal("30"), line_total=Decimal("30")),
        ])

        retail_invoice = Invoice(
            company_id=1,
            invoice_number="RETAIL-INV-P2",
            branch_id=ids["retail_branch"],
            customer_id=retail_customer.id,
            sale_id=retail_sale.id,
            invoice_type=InvoiceType.NON_GST,
            invoice_date=datetime.now(UTC),
            subtotal=Decimal("15"),
            taxable_total=Decimal("15"),
            grand_total=Decimal("15"),
            balance_due=Decimal("15"),
            created_by=retail_admin.id,
        )
        cafe_invoice = Invoice(
            company_id=2,
            invoice_number="CAFE-INV-P2",
            branch_id=ids["cafe_branch"],
            customer_id=cafe_customer.id,
            sale_id=cafe_sale.id,
            invoice_type=InvoiceType.NON_GST,
            invoice_date=datetime.now(UTC),
            subtotal=Decimal("30"),
            taxable_total=Decimal("30"),
            grand_total=Decimal("30"),
            balance_due=Decimal("30"),
            created_by=cafe_admin.id,
        )
        db.add_all([retail_invoice, cafe_invoice])

        retail_po = PurchaseOrder(company_id=1, po_number="RETAIL-PO-P2", supplier_id=retail_supplier.id, branch_id=ids["retail_branch"], order_date=date.today(), total_amount=Decimal("10"), created_by=retail_admin.id)
        cafe_po = PurchaseOrder(company_id=2, po_number="CAFE-PO-P2", supplier_id=cafe_supplier.id, branch_id=ids["cafe_branch"], order_date=date.today(), total_amount=Decimal("20"), created_by=cafe_admin.id)
        db.add_all([retail_po, cafe_po])

        retail_forecast = Forecast(company_id=1, product_id=retail_product.id, category_id=ids["retail_category"], branch_id=ids["retail_branch"], forecast_type=ForecastType.DEMAND, forecast_start_date=date.today(), forecast_end_date=date.today(), forecast_value=Decimal("5"), model_name="p2-test")
        cafe_forecast = Forecast(company_id=2, product_id=cafe_product.id, category_id=ids["cafe_category"], branch_id=ids["cafe_branch"], forecast_type=ForecastType.DEMAND, forecast_start_date=date.today(), forecast_end_date=date.today(), forecast_value=Decimal("7"), model_name="p2-test")
        db.add_all([retail_forecast, cafe_forecast])

        db.add_all([
            BusinessProfile(company_id=1, legal_name="Retail Profile", default_tax_mode=TaxMode.NON_GST),
            BusinessProfile(company_id=2, legal_name="Cafe Profile", default_tax_mode=TaxMode.NON_GST),
            AIChatSession(company_id=1, user_id=retail_admin.id, branch_id=ids["retail_branch"], title="Retail confidential chat"),
            AIChatSession(company_id=2, user_id=cafe_admin.id, branch_id=ids["cafe_branch"], title="Cafe chat"),
        ])
        db.commit()
        return {
            "retail_customer": retail_customer.id,
            "cafe_customer": cafe_customer.id,
            "retail_sale": retail_sale.id,
            "cafe_sale": cafe_sale.id,
            "retail_invoice": retail_invoice.id,
            "cafe_invoice": cafe_invoice.id,
            "retail_po": retail_po.id,
            "cafe_po": cafe_po.id,
            "retail_forecast": retail_forecast.id,
            "cafe_forecast": cafe_forecast.id,
        }


def test_cafe_admin_cannot_obtain_retail_operational_rows_or_counts(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    _seed_reporting_rows(db_session_factory, ids)
    headers = login_headers(client, "cafe.admin@example.test")

    customers = client.get("/api/customers", headers=headers)
    sales = client.get("/api/sales", headers=headers)
    invoices = client.get("/api/invoices", headers=headers)
    purchase_orders = client.get("/api/purchase-orders", headers=headers)
    forecasts = client.get("/api/forecasts", headers=headers)
    overview = client.get("/api/dashboard/overview", headers=headers)
    profile = client.get("/api/business-profile", headers=headers)

    for response in (customers, sales, invoices, purchase_orders, forecasts, overview, profile):
        assert response.status_code == 200, response.text
        assert "Retail" not in response.text

    assert {row["name"] for row in customers.json()} == {"Cafe Customer"}
    assert {row["sale_number"] for row in sales.json()} == {"CAFE-SALE-P2"}
    assert {row["invoice_number"] for row in invoices.json()} == {"CAFE-INV-P2"}
    assert {row["po_number"] for row in purchase_orders.json()} == {"CAFE-PO-P2"}
    assert profile.json()["legal_name"] == "Cafe Profile"
    assert overview.json()["kpis"]["sales"]["transaction_count"] == 1


def test_exports_and_ai_sessions_do_not_cross_venture(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    _seed_reporting_rows(db_session_factory, ids)
    headers = login_headers(client, "cafe.admin@example.test")

    export = client.get("/api/exports/sales", headers=headers)
    assert export.status_code == 200
    assert "CAFE-SALE-P2" in export.text
    assert "RETAIL-SALE-P2" not in export.text
    assert "Retail Secret Product" not in export.text

    sessions = client.get("/api/ai/sessions", headers=headers)
    assert sessions.status_code == 200
    assert {row["title"] for row in sessions.json()} == {"Cafe chat"}
    assert "Retail confidential chat" not in sessions.text
