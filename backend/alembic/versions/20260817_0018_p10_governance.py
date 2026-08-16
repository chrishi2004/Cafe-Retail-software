"""P10 daily closing, reversal, and controlled purge governance.

Revision ID: 20260817_0018
Revises: 20260816_0017
"""

from alembic import op
import sqlalchemy as sa

revision = "20260817_0018"
down_revision = "20260816_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True))
    op.create_index("ix_audit_logs_branch_id", "audit_logs", ["branch_id"])
    op.create_table(
        "business_day_closures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("opening_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cash_collections", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cash_refunds", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cash_expenses", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("variance", sa.Numeric(14, 2), nullable=True),
        sa.Column("non_cash_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reopened_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "branch_id", "business_date", name="uq_business_day_closure_scope_date"),
    )
    op.create_index("ix_business_day_closures_company_branch_date", "business_day_closures", ["company_id", "branch_id", "business_date"])
    op.create_index("ix_business_day_closures_status", "business_day_closures", ["status"])

    op.create_table(
        "financial_reversals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("reversal_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("compensation_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_financial_reversals_invoice_id", "financial_reversals", ["invoice_id"])
    op.create_index("ix_financial_reversals_company_branch", "financial_reversals", ["company_id", "branch_id"])

    op.create_table(
        "record_purge_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="requested"),
        sa.Column("dependency_report", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("backup_reference", sa.String(255), nullable=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("second_approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("step_up_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("typed_confirmation", sa.String(160), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_record_purge_requests_scope_status", "record_purge_requests", ["company_id", "branch_id", "status"])
    op.create_index("ix_record_purge_requests_entity", "record_purge_requests", ["entity_type", "entity_id"])

    op.create_table(
        "record_tombstones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("before_hash", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_record_tombstones_scope_entity", "record_tombstones", ["company_id", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_branch_id", table_name="audit_logs")
    op.drop_column("audit_logs", "branch_id")
    op.drop_table("record_tombstones")
    op.drop_table("record_purge_requests")
    op.drop_table("financial_reversals")
    op.drop_table("business_day_closures")
