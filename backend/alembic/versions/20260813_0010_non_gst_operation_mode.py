"""add non-GST-default venture tax operation mode

Revision ID: 20260813_0010
Revises: 20260811_0009
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0010"
down_revision: str | None = "20260811_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_profiles",
        sa.Column("tax_registration_status", sa.String(length=20), nullable=False, server_default="unregistered"),
    )
    op.add_column("business_profiles", sa.Column("gst_effective_from", sa.Date(), nullable=True))
    op.add_column(
        "business_profiles",
        sa.Column("customer_details_on_bill", sa.String(length=20), nullable=False, server_default="basic"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("b2b_gst_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "business_profiles",
        sa.Column("include_customer_in_gst_reports", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_business_profiles_tax_registration_status",
        "business_profiles",
        "tax_registration_status IN ('unregistered', 'registered')",
    )
    op.create_check_constraint(
        "ck_business_profiles_customer_details_on_bill",
        "business_profiles",
        "customer_details_on_bill IN ('hidden', 'basic', 'full')",
    )

    op.add_column(
        "gst_registrations",
        sa.Column("reference_only", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # P4 deliberately changes current operation to Non-GST. Product HSN/rate
    # metadata and reference registrations remain intact for future activation.
    op.execute("UPDATE business_profiles SET default_tax_mode = 'non_gst', tax_registration_status = 'unregistered', gst_effective_from = NULL, b2b_gst_enabled = false, include_customer_in_gst_reports = false")
    op.execute("UPDATE gst_registrations SET is_active = false, reference_only = true")

    # P1 creates the Cafe Company before P4, but legacy/demo databases may not
    # yet have a BusinessProfile for it. Create a safe unregistered profile for
    # every active Company missing one.
    op.execute(
        sa.text(
            """
            INSERT INTO business_profiles (
                company_id, legal_name, trade_name, pan, email, phone, address,
                city, state, state_code, pincode, default_tax_mode,
                default_currency, terms_and_conditions, tax_registration_status,
                gst_effective_from, customer_details_on_bill, b2b_gst_enabled,
                include_customer_in_gst_reports, created_at, updated_at
            )
            SELECT
                c.id, c.legal_name, c.trade_name, c.pan, NULL, NULL, NULL,
                NULL, NULL, NULL, NULL, 'non_gst', c.default_currency,
                NULL, 'unregistered', NULL, 'basic', false, false, now(), now()
            FROM companies c
            WHERE c.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM business_profiles bp WHERE bp.company_id = c.id
              )
            """
        )
    )

    # Non-GST is usable immediately for both ventures. Billing still uses the
    # existing shared sequence/template engine rather than a Cafe-only fork.
    op.execute(
        sa.text(
            """
            INSERT INTO invoice_sequences (
                company_id, branch_id, invoice_type, fiscal_year, prefix, suffix,
                next_number, padding, reset_rule, is_active, created_at, updated_at
            )
            SELECT c.id, NULL, 'non_gst_invoice', '2026-2027',
                   CASE WHEN c.business_type = 'cafe' THEN 'CAFE-BILL-2026-' ELSE 'BILL-2026-' END,
                   NULL, 1, 5, 'fiscal_year', true, now(), now()
            FROM companies c
            WHERE c.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM invoice_sequences s
                  WHERE s.company_id = c.id
                    AND s.branch_id IS NULL
                    AND s.invoice_type = 'non_gst_invoice'
                    AND s.fiscal_year = '2026-2027'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO print_templates (
                company_id, name, template_type, is_default, is_active,
                settings_json, created_at, updated_at
            )
            SELECT c.id, 'Default Non-GST Invoice', 'non_gst_invoice', true, true,
                   '{"show_gstin": false, "show_applied_tax": false}'::json,
                   now(), now()
            FROM companies c
            WHERE c.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM print_templates p
                  WHERE p.company_id = c.id
                    AND p.template_type = 'non_gst_invoice'
                    AND p.name = 'Default Non-GST Invoice'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM print_templates WHERE template_type = 'non_gst_invoice' AND name = 'Default Non-GST Invoice'")
    op.execute("DELETE FROM invoice_sequences WHERE invoice_type = 'non_gst_invoice' AND fiscal_year = '2026-2027' AND prefix IN ('BILL-2026-', 'CAFE-BILL-2026-')")
    op.drop_column("gst_registrations", "reference_only")
    op.drop_constraint("ck_business_profiles_customer_details_on_bill", "business_profiles", type_="check")
    op.drop_constraint("ck_business_profiles_tax_registration_status", "business_profiles", type_="check")
    op.drop_column("business_profiles", "include_customer_in_gst_reports")
    op.drop_column("business_profiles", "b2b_gst_enabled")
    op.drop_column("business_profiles", "customer_details_on_bill")
    op.drop_column("business_profiles", "gst_effective_from")
    op.drop_column("business_profiles", "tax_registration_status")
