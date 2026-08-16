"""add invoice and pos billing backend tables

Revision ID: 20260521_0006
Revises: 20260521_0005
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0006"
down_revision: str | None = "20260521_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=80), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("invoice_type", sa.String(length=20), nullable=False),
        sa.Column("place_of_supply_state", sa.String(length=100), nullable=True),
        sa.Column("place_of_supply_state_code", sa.String(length=2), nullable=True),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cgst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sgst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("igst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cess_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("round_off", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("invoice_type IN ('gst', 'non_gst')", name="ck_invoices_invoice_type"),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'paid', 'partial_paid', 'credit', 'cancelled', 'returned')",
            name="ck_invoices_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('unpaid', 'paid', 'partial_paid', 'credit')",
            name="ck_invoices_payment_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        sa.CheckConstraint("discount_total >= 0", name="ck_invoices_discount_total_non_negative"),
        sa.CheckConstraint("taxable_total >= 0", name="ck_invoices_taxable_total_non_negative"),
        sa.CheckConstraint("grand_total >= 0", name="ck_invoices_grand_total_non_negative"),
        sa.CheckConstraint("paid_amount >= 0", name="ck_invoices_paid_amount_non_negative"),
        sa.CheckConstraint("balance_due >= 0", name="ck_invoices_balance_due_non_negative"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_branch_id", "invoices", ["branch_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_payment_status", "invoices", ["payment_status"])
    op.create_index("ix_invoices_sale_id", "invoices", ["sale_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=64), nullable=False),
        sa.Column("hsn_sac_code", sa.String(length=20), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("mrp", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("taxable_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("cgst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sgst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("igst_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cess_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("gross_profit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_invoice_items_unit_price_non_negative"),
        sa.CheckConstraint("discount >= 0", name="ck_invoice_items_discount_non_negative"),
        sa.CheckConstraint("taxable_value >= 0", name="ck_invoice_items_taxable_value_non_negative"),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_items_line_total_non_negative"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
    op.create_index("ix_invoice_items_product_id", "invoice_items", ["product_id"])

    op.create_table(
        "invoice_taxes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("invoice_item_id", sa.Integer(), nullable=True),
        sa.Column("tax_type", sa.String(length=20), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("taxable_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.CheckConstraint("tax_type IN ('cgst', 'sgst', 'igst', 'cess')", name="ck_invoice_taxes_tax_type"),
        sa.CheckConstraint("tax_rate >= 0", name="ck_invoice_taxes_rate_non_negative"),
        sa.CheckConstraint("taxable_value >= 0", name="ck_invoice_taxes_taxable_non_negative"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoice_taxes_amount_non_negative"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_item_id"], ["invoice_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_taxes_invoice_id", "invoice_taxes", ["invoice_id"])
    op.create_index("ix_invoice_taxes_invoice_item_id", "invoice_taxes", ["invoice_item_id"])
    op.create_index("ix_invoice_taxes_tax_type", "invoice_taxes", ["tax_type"])

    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("payment_mode_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_by", sa.Integer(), nullable=True),
        sa.Column("is_credit_marker", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_invoice_payments_amount_positive"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_payments_invoice_id", "invoice_payments", ["invoice_id"])
    op.create_index("ix_invoice_payments_payment_datetime", "invoice_payments", ["payment_datetime"])
    op.create_index("ix_invoice_payments_payment_mode_id", "invoice_payments", ["payment_mode_id"])

    op.create_table(
        "invoice_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('draft', 'issued', 'paid', 'partial_paid', 'credit', 'cancelled', 'returned')",
            name="ck_invoice_status_history_from",
        ),
        sa.CheckConstraint(
            "to_status IN ('draft', 'issued', 'paid', 'partial_paid', 'credit', 'cancelled', 'returned')",
            name="ck_invoice_status_history_to",
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_status_history_changed_at", "invoice_status_history", ["changed_at"])
    op.create_index("ix_invoice_status_history_invoice_id", "invoice_status_history", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_status_history_invoice_id", table_name="invoice_status_history")
    op.drop_index("ix_invoice_status_history_changed_at", table_name="invoice_status_history")
    op.drop_table("invoice_status_history")
    op.drop_index("ix_invoice_payments_payment_mode_id", table_name="invoice_payments")
    op.drop_index("ix_invoice_payments_payment_datetime", table_name="invoice_payments")
    op.drop_index("ix_invoice_payments_invoice_id", table_name="invoice_payments")
    op.drop_table("invoice_payments")
    op.drop_index("ix_invoice_taxes_tax_type", table_name="invoice_taxes")
    op.drop_index("ix_invoice_taxes_invoice_item_id", table_name="invoice_taxes")
    op.drop_index("ix_invoice_taxes_invoice_id", table_name="invoice_taxes")
    op.drop_table("invoice_taxes")
    op.drop_index("ix_invoice_items_product_id", table_name="invoice_items")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_sale_id", table_name="invoices")
    op.drop_index("ix_invoices_payment_status", table_name="invoices")
    op.drop_index("ix_invoices_invoice_date", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_branch_id", table_name="invoices")
    op.drop_table("invoices")
