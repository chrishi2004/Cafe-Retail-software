"""Phase 8 item-level sales returns, stock restoration and credit notes.

Revision ID: 20260920_0021
Revises: 20260920_0020
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_0021"
down_revision = "20260920_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("return_number", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"),
        sa.Column("refund_mode", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "return_number", name="uq_sales_returns_company_number"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_sales_returns_company_idempotency"),
        sa.CheckConstraint("total_amount >= 0", name="sales_returns_total_non_negative"),
    )
    op.create_index("ix_sales_returns_company_id", "sales_returns", ["company_id"])
    op.create_index("ix_sales_returns_invoice_id", "sales_returns", ["invoice_id"])
    op.create_index("ix_sales_returns_branch_id", "sales_returns", ["branch_id"])
    op.create_table(
        "sales_return_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_item_id", sa.Integer(), sa.ForeignKey("invoice_items.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("condition", sa.String(32), nullable=False),
        sa.Column("restocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint("quantity > 0", name="sales_return_items_quantity_positive"),
    )
    op.create_index("ix_sales_return_items_return_id", "sales_return_items", ["return_id"])
    op.create_index("ix_sales_return_items_invoice_item_id", "sales_return_items", ["invoice_item_id"])
    op.create_table(
        "credit_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("sales_return_id", sa.Integer(), sa.ForeignKey("sales_returns.id"), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("credit_note_number", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("refund_mode", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "credit_note_number", name="uq_credit_notes_company_number"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_credit_notes_company_idempotency"),
        sa.CheckConstraint("amount >= 0", name="credit_notes_amount_non_negative"),
    )
    op.create_index("ix_credit_notes_company_id", "credit_notes", ["company_id"])
    op.create_index("ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_notes_invoice_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_company_id", table_name="credit_notes")
    op.drop_table("credit_notes")
    op.drop_index("ix_sales_return_items_invoice_item_id", table_name="sales_return_items")
    op.drop_index("ix_sales_return_items_return_id", table_name="sales_return_items")
    op.drop_table("sales_return_items")
    op.drop_index("ix_sales_returns_branch_id", table_name="sales_returns")
    op.drop_index("ix_sales_returns_invoice_id", table_name="sales_returns")
    op.drop_index("ix_sales_returns_company_id", table_name="sales_returns")
    op.drop_table("sales_returns")
