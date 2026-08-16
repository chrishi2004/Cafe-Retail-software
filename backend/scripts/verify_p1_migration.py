"""Prepare and verify a legacy HC1 database around the P1 migration.

Used by CI only. It deliberately talks to the database through SQL text so the
pre-P1 schema can be populated without importing the newer ORM metadata.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "LOCAL_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi",
)


def prepare() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO companies
                    (id, code, name, legal_name, trade_name, default_currency, is_active)
                VALUES
                    (1, 'LEGACY_RETAIL', 'Legacy Retail', 'Legacy Retail', 'Legacy Retail', 'INR', true)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO branches (id, name, address, city, manager_name, is_active)
                VALUES (1, 'Legacy Main', '1 Legacy Road', 'Bengaluru', 'Legacy Manager', true)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users
                    (id, name, email, password_hash, role, branch_id, is_active)
                VALUES
                    (1, 'Legacy Admin', 'legacy-admin@example.test', 'legacy-hash', 'admin', NULL, true)
                """
            )
        )
        connection.execute(
            text("INSERT INTO categories (id, name, description) VALUES (1, 'Legacy Category', 'fixture')")
        )
        connection.execute(
            text(
                """
                INSERT INTO suppliers
                    (id, name, contact_person, lead_time_days, is_active)
                VALUES (1, 'Legacy Supplier', 'Fixture', 3, true)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO products
                    (id, sku, name, category_id, supplier_id, unit_cost, selling_price,
                     reorder_threshold, target_stock_level, is_active)
                VALUES
                    (1, 'LEGACY-SKU', 'Legacy Product', 1, 1, 10.00, 15.00, 2.00, 10.00, true)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO inventory
                    (id, product_id, branch_id, quantity_on_hand, quantity_reserved, quantity_on_order)
                VALUES (1, 1, 1, 7.00, 0.00, 0.00)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO customers
                    (id, company_id, branch_id, name, phone, credit_limit, opening_balance, is_active)
                VALUES (1, 1, 1, 'Legacy Customer', '9000000001', 1000.00, 0.00, true)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO sales
                    (id, sale_number, branch_id, sale_datetime, subtotal, discount_total,
                     tax_total, total_amount, created_by)
                VALUES
                    (1, 'SALE-LEGACY-001', 1, now(), 150.00, 0.00, 0.00, 150.00, 1)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO invoices
                    (id, invoice_number, branch_id, customer_id, sale_id, invoice_type,
                     invoice_date, status, subtotal, discount_total, taxable_total,
                     cgst_total, sgst_total, igst_total, cess_total, round_off,
                     grand_total, paid_amount, balance_due, payment_status, created_by)
                VALUES
                    (1, 'INV-LEGACY-001', 1, 1, 1, 'non_gst', now(), 'issued',
                     150.00, 0.00, 150.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                     150.00, 0.00, 150.00, 'unpaid', 1)
                """
            )
        )
    engine.dispose()


def verify() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        group_count = connection.scalar(text("SELECT COUNT(*) FROM business_groups"))
        assert group_count and group_count >= 1

        branch_company = connection.scalar(text("SELECT company_id FROM branches WHERE id = 1"))
        product_company = connection.scalar(text("SELECT company_id FROM products WHERE id = 1"))
        inventory_company = connection.scalar(text("SELECT company_id FROM inventory WHERE id = 1"))
        assert branch_company == product_company == inventory_company == 1

        user = connection.execute(
            text("SELECT role, company_id, token_version FROM users WHERE id = 1")
        ).one()
        assert user.role == "super_admin"
        assert user.company_id is None
        assert user.token_version >= 2

        sale = connection.execute(
            text("SELECT sale_number, total_amount, company_id FROM sales WHERE id = 1")
        ).one()
        assert sale.sale_number == "SALE-LEGACY-001"
        assert Decimal(sale.total_amount) == Decimal("150.00")
        assert sale.company_id == 1

        invoice = connection.execute(
            text("SELECT invoice_number, grand_total, balance_due, company_id FROM invoices WHERE id = 1")
        ).one()
        assert invoice.invoice_number == "INV-LEGACY-001"
        assert Decimal(invoice.grand_total) == Decimal("150.00")
        assert Decimal(invoice.balance_due) == Decimal("150.00")
        assert invoice.company_id == 1
    engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "verify"}:
        raise SystemExit("usage: verify_p1_migration.py prepare|verify")
    globals()[sys.argv[1]]()
