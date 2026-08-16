"""add business profile tax payment and invoice settings

Revision ID: 20260521_0003
Revises: 20260518_0002
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0003"
down_revision: str | None = "20260518_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("pan", sa.String(length=20), nullable=True),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "business_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("pan", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("state_code", sa.String(length=2), nullable=True),
        sa.Column("pincode", sa.String(length=12), nullable=True),
        sa.Column("default_tax_mode", sa.String(length=20), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("terms_and_conditions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("default_tax_mode IN ('gst', 'non_gst')", name="ck_business_profiles_default_tax_mode"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_business_profiles_company_id", "business_profiles", ["company_id"])

    op.create_table(
        "gst_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("pincode", sa.String(length=12), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gstin"),
    )
    op.create_index("ix_gst_registrations_branch_id", "gst_registrations", ["branch_id"])
    op.create_index("ix_gst_registrations_company_id", "gst_registrations", ["company_id"])

    op.create_table(
        "tax_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("cess_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "invoice_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("invoice_type", sa.String(length=40), nullable=False),
        sa.Column("fiscal_year", sa.String(length=20), nullable=False),
        sa.Column("prefix", sa.String(length=30), nullable=False),
        sa.Column("suffix", sa.String(length=30), nullable=True),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.Column("padding", sa.Integer(), nullable=False),
        sa.Column("reset_rule", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "invoice_type IN ('gst_invoice', 'non_gst_invoice', 'credit_note', 'purchase_bill')",
            name="ck_invoice_sequences_invoice_type",
        ),
        sa.CheckConstraint(
            "reset_rule IN ('never', 'fiscal_year', 'calendar_year', 'monthly')",
            name="ck_invoice_sequences_reset_rule",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "branch_id",
            "invoice_type",
            "fiscal_year",
            name="uq_invoice_sequences_scope_type_year",
        ),
    )
    op.create_index("ix_invoice_sequences_branch_id", "invoice_sequences", ["branch_id"])
    op.create_index("ix_invoice_sequences_company_id", "invoice_sequences", ["company_id"])
    op.create_index("ix_invoice_sequences_invoice_type", "invoice_sequences", ["invoice_type"])

    op.create_table(
        "payment_modes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mode_type", sa.String(length=30), nullable=False),
        sa.Column("requires_reference", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "mode_type IN ('cash', 'upi', 'card', 'bank_transfer', 'wallet', 'cheque', 'credit', 'other')",
            name="ck_payment_modes_mode_type",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_payment_modes_company_name"),
    )
    op.create_index("ix_payment_modes_company_id", "payment_modes", ["company_id"])
    op.create_index("ix_payment_modes_mode_type", "payment_modes", ["mode_type"])

    op.create_table(
        "print_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("template_type", sa.String(length=40), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "template_type IN ('a4_gst_invoice', 'a5_invoice', 'pos_58mm', 'pos_80mm', 'non_gst_invoice', 'credit_note', 'purchase_bill')",
            name="ck_print_templates_template_type",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "template_type", "name", name="uq_print_templates_company_type_name"),
    )
    op.create_index("ix_print_templates_company_id", "print_templates", ["company_id"])

    op.create_table(
        "fiscal_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_closed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_fiscal_periods_company_name"),
    )
    op.create_index("ix_fiscal_periods_company_id", "fiscal_periods", ["company_id"])
    op.create_index("ix_fiscal_periods_dates", "fiscal_periods", ["start_date", "end_date"])


def downgrade() -> None:
    op.drop_index("ix_fiscal_periods_dates", table_name="fiscal_periods")
    op.drop_index("ix_fiscal_periods_company_id", table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
    op.drop_index("ix_print_templates_company_id", table_name="print_templates")
    op.drop_table("print_templates")
    op.drop_index("ix_payment_modes_mode_type", table_name="payment_modes")
    op.drop_index("ix_payment_modes_company_id", table_name="payment_modes")
    op.drop_table("payment_modes")
    op.drop_index("ix_invoice_sequences_invoice_type", table_name="invoice_sequences")
    op.drop_index("ix_invoice_sequences_company_id", table_name="invoice_sequences")
    op.drop_index("ix_invoice_sequences_branch_id", table_name="invoice_sequences")
    op.drop_table("invoice_sequences")
    op.drop_table("tax_rates")
    op.drop_index("ix_gst_registrations_company_id", table_name="gst_registrations")
    op.drop_index("ix_gst_registrations_branch_id", table_name="gst_registrations")
    op.drop_table("gst_registrations")
    op.drop_index("ix_business_profiles_company_id", table_name="business_profiles")
    op.drop_table("business_profiles")
    op.drop_table("companies")

