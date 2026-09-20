"""Phase 7 cash register sessions and drawer movements.

Revision ID: 20260920_0020
Revises: 20260821_0019
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_0020"
down_revision = "20260821_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_register_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("opening_float", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("variance", sa.Numeric(14, 2), nullable=True),
        sa.Column("opened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("opening_float >= 0", name="cash_register_opening_float_non_negative"),
    )
    op.create_index("ix_cash_register_sessions_scope_status", "cash_register_sessions", ["company_id", "branch_id", "status"])
    op.create_index(
        "uq_cash_register_sessions_one_open",
        "cash_register_sessions",
        ["company_id", "branch_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
        sqlite_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "cash_register_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("cash_register_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_cash_register_movements_scope_idempotency"),
        sa.CheckConstraint("amount > 0", name="cash_register_movement_amount_positive"),
    )
    op.create_index("ix_cash_register_movements_session", "cash_register_movements", ["session_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_cash_register_movements_session", table_name="cash_register_movements")
    op.drop_table("cash_register_movements")
    op.drop_index("uq_cash_register_sessions_one_open", table_name="cash_register_sessions")
    op.drop_index("ix_cash_register_sessions_scope_status", table_name="cash_register_sessions")
    op.drop_table("cash_register_sessions")
