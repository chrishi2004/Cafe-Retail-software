"""P9 reporting views for Cafe and consolidated dashboards.

Revision ID: 20260816_0017
Revises: 20260814_0016
"""

from alembic import op

revision = "20260816_0017"
down_revision = "20260814_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cafe_order_summary AS
        SELECT company_id, branch_id, id AS cafe_order_id, order_number,
               order_type, source_channel, status, estimated_total,
               billed_invoice_id, placed_at, cancelled_at
        FROM cafe_orders
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cafe_order_items AS
        SELECT company_id, branch_id, cafe_order_id, menu_item_id,
               menu_item_name_snapshot AS item_name, quantity,
               line_total, item_status, source_channel
        FROM cafe_order_items
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cafe_table_turnover AS
        SELECT company_id, branch_id, table_id, id AS table_session_id,
               status, opened_at, closed_at,
               CASE WHEN closed_at IS NULL THEN NULL
                    ELSE EXTRACT(EPOCH FROM (closed_at - opened_at)) / 60
               END AS duration_minutes
        FROM table_sessions
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cafe_billing_reconciliation AS
        SELECT i.company_id, i.branch_id, i.id AS invoice_id,
               i.source_type, i.source_id, i.status, i.grand_total,
               i.paid_amount, i.balance_due, i.invoice_date
        FROM invoices i
        WHERE i.source_type IN ('cafe_table_session', 'cafe_takeaway')
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cafe_payment_summary AS
        SELECT i.company_id, i.branch_id, i.id AS invoice_id,
               p.payment_mode_id, p.amount, p.payment_datetime,
               p.is_credit_marker
        FROM invoice_payments p
        JOIN invoices i ON i.id = p.invoice_id
        WHERE i.source_type IN ('cafe_table_session', 'cafe_takeaway')
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_venture_sales_summary AS
        SELECT c.business_group_id, i.company_id, c.business_type,
               i.branch_id, COUNT(i.id) AS invoice_count,
               COALESCE(SUM(CASE WHEN i.status IN ('issued','paid','partial_paid','credit')
                                 THEN i.grand_total ELSE 0 END), 0) AS billed_revenue,
               COALESCE(SUM(CASE WHEN i.status IN ('issued','paid','partial_paid','credit')
                                 THEN i.balance_due ELSE 0 END), 0) AS outstanding
        FROM invoices i
        JOIN companies c ON c.id = i.company_id
        GROUP BY c.business_group_id, i.company_id, c.business_type, i.branch_id
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_business_group_turnover AS
        SELECT c.business_group_id,
               COALESCE(SUM(CASE WHEN i.status IN ('issued','paid','partial_paid','credit')
                                 THEN i.grand_total ELSE 0 END), 0) AS billed_revenue
        FROM invoices i
        JOIN companies c ON c.id = i.company_id
        GROUP BY c.business_group_id
        """
    )


def downgrade() -> None:
    for view_name in (
        "vw_business_group_turnover",
        "vw_venture_sales_summary",
        "vw_cafe_payment_summary",
        "vw_cafe_billing_reconciliation",
        "vw_cafe_table_turnover",
        "vw_cafe_order_items",
        "vw_cafe_order_summary",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view_name}")
