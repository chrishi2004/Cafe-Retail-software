"""add HC4 continuity state and reconciliation

Revision ID: 20260814_0016
Revises: 20260814_0015
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260814_0016"
down_revision: str | None = "20260814_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(values: list[str], name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "continuity_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(length=256), nullable=False),
        sa.Column("business_group_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("branch_id", sa.String(length=64), nullable=True),
        sa.Column(
            "mode",
            _enum(
                ["live", "offline_local", "cloud_continuity", "synchronizing", "stale", "attention_required"],
                "continuity_mode",
            ),
            nullable=False,
            server_default="synchronizing",
        ),
        sa.Column("fencing_epoch", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_owner_device_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cloud_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_queue_drain_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_inbox", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_outbox", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dead_letter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attention_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope_key", name="uq_continuity_states_scope_key"),
        sa.CheckConstraint("fencing_epoch >= 0", name="ck_continuity_states_epoch_nonnegative"),
    )
    op.create_index(
        "ix_continuity_states_scope",
        "continuity_states",
        ["business_group_id", "company_id", "branch_id"],
    )
    op.create_index("ix_continuity_states_mode", "continuity_states", ["mode"])

    op.create_table(
        "continuity_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reconciliation_reference", sa.String(length=36), nullable=False),
        sa.Column("scope_key", sa.String(length=256), nullable=False),
        sa.Column("business_group_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("branch_id", sa.String(length=64), nullable=True),
        sa.Column("fencing_epoch", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            _enum(["pending", "clean", "attention_required"], "continuity_reconciliation_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("pending_inbox_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_outbox_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_inbox_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_outbox_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invoice_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stock_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_receipt_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closing_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dead_letter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("reconciliation_reference", name="uq_continuity_reconciliation_reference"),
        sa.CheckConstraint("fencing_epoch >= 0", name="ck_continuity_reconciliations_epoch_nonnegative"),
    )
    op.create_index(
        "ix_continuity_reconciliations_scope",
        "continuity_reconciliations",
        ["business_group_id", "company_id", "branch_id"],
    )
    op.create_index(
        "ix_continuity_reconciliations_status",
        "continuity_reconciliations",
        ["status", "created_at"],
    )

    op.create_table(
        "continuity_transaction_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("continuity_reference", sa.String(length=36), nullable=False),
        sa.Column("scope_key", sa.String(length=256), nullable=False),
        sa.Column("business_group_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("branch_id", sa.String(length=64), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("fencing_epoch", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            _enum(["pending_reconciliation", "reconciled", "rejected"], "continuity_transaction_status"),
            nullable=False,
            server_default="pending_reconciliation",
        ),
        sa.Column("source_device_id", sa.String(length=128), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("local_reference_type", sa.String(length=80), nullable=True),
        sa.Column("local_reference_id", sa.String(length=128), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("continuity_reference", name="uq_continuity_transaction_receipts_reference"),
        sa.CheckConstraint("fencing_epoch >= 0", name="ck_continuity_receipts_epoch_nonnegative"),
    )
    op.create_index(
        "ix_continuity_transaction_receipts_scope",
        "continuity_transaction_receipts",
        ["business_group_id", "company_id", "branch_id"],
    )
    op.create_index(
        "ix_continuity_transaction_receipts_status",
        "continuity_transaction_receipts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_continuity_transaction_receipts_status", table_name="continuity_transaction_receipts")
    op.drop_index("ix_continuity_transaction_receipts_scope", table_name="continuity_transaction_receipts")
    op.drop_table("continuity_transaction_receipts")
    op.drop_index("ix_continuity_reconciliations_status", table_name="continuity_reconciliations")
    op.drop_index("ix_continuity_reconciliations_scope", table_name="continuity_reconciliations")
    op.drop_table("continuity_reconciliations")
    op.drop_index("ix_continuity_states_mode", table_name="continuity_states")
    op.drop_index("ix_continuity_states_scope", table_name="continuity_states")
    op.drop_table("continuity_states")
