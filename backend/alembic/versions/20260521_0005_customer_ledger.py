"""add customer management and customer ledger

Revision ID: 20260521_0005
Revises: 20260521_0004
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0005"
down_revision: str | None = "20260521_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("state_code", sa.String(length=2), nullable=True),
        sa.Column("pincode", sa.String(length=12), nullable=True),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("credit_limit >= 0", name="ck_customers_credit_limit_non_negative"),
        sa.CheckConstraint("opening_balance >= 0", name="ck_customers_opening_balance_non_negative"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("gstin"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index("ix_customers_branch_id", "customers", ["branch_id"])
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_phone", "customers", ["phone"])
    op.create_index("ix_customers_gstin", "customers", ["gstin"])

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("address_type", sa.String(length=20), nullable=False),
        sa.Column("recipient_name", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("state_code", sa.String(length=2), nullable=True),
        sa.Column("pincode", sa.String(length=12), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("address_type IN ('billing', 'shipping')", name="ck_customer_addresses_type"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "address_type", "is_default", name="uq_customer_addresses_default_type"),
    )
    op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"])
    op.create_index("ix_customer_addresses_type", "customer_addresses", ["address_type"])

    op.create_table(
        "customer_ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("entry_type", sa.String(length=30), nullable=False),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reference_type", sa.String(length=80), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("entry_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('opening_balance', 'invoice', 'payment', 'credit_note', 'adjustment')",
            name="ck_customer_ledger_entry_type",
        ),
        sa.CheckConstraint("debit >= 0", name="ck_customer_ledger_debit_non_negative"),
        sa.CheckConstraint("credit >= 0", name="ck_customer_ledger_credit_non_negative"),
        sa.CheckConstraint("debit > 0 OR credit > 0", name="ck_customer_ledger_has_amount"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_ledger_entries_customer_id", "customer_ledger_entries", ["customer_id"])
    op.create_index("ix_customer_ledger_entries_branch_id", "customer_ledger_entries", ["branch_id"])
    op.create_index("ix_customer_ledger_entries_entry_type", "customer_ledger_entries", ["entry_type"])
    op.create_index("ix_customer_ledger_entries_entry_datetime", "customer_ledger_entries", ["entry_datetime"])

    op.create_table(
        "customer_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("payment_mode_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_by", sa.Integer(), nullable=True),
        sa.Column("ledger_entry_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_customer_payments_amount_positive"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["customer_ledger_entries.id"]),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_payments_customer_id", "customer_payments", ["customer_id"])
    op.create_index("ix_customer_payments_branch_id", "customer_payments", ["branch_id"])
    op.create_index("ix_customer_payments_payment_datetime", "customer_payments", ["payment_datetime"])


def downgrade() -> None:
    op.drop_index("ix_customer_payments_payment_datetime", table_name="customer_payments")
    op.drop_index("ix_customer_payments_branch_id", table_name="customer_payments")
    op.drop_index("ix_customer_payments_customer_id", table_name="customer_payments")
    op.drop_table("customer_payments")
    op.drop_index("ix_customer_ledger_entries_entry_datetime", table_name="customer_ledger_entries")
    op.drop_index("ix_customer_ledger_entries_entry_type", table_name="customer_ledger_entries")
    op.drop_index("ix_customer_ledger_entries_branch_id", table_name="customer_ledger_entries")
    op.drop_index("ix_customer_ledger_entries_customer_id", table_name="customer_ledger_entries")
    op.drop_table("customer_ledger_entries")
    op.drop_index("ix_customer_addresses_type", table_name="customer_addresses")
    op.drop_index("ix_customer_addresses_customer_id", table_name="customer_addresses")
    op.drop_table("customer_addresses")
    op.drop_index("ix_customers_gstin", table_name="customers")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_index("ix_customers_branch_id", table_name="customers")
    op.drop_index("ix_customers_company_id", table_name="customers")
    op.drop_table("customers")
