"""add durable local synchronization foundation

Revision ID: 20260811_0007
Revises: 20260521_0006
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260811_0007"
down_revision: str | None = "20260521_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sync_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "revoked", name="sync_device_status", native_enum=False, create_constraint=True),
            server_default="active",
            nullable=False,
        ),
        sa.Column("credential_ref", sa.String(length=255), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("ix_sync_devices_status", "sync_devices", ["status"], unique=False)

    op.create_table(
        "sync_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_device_id", sa.String(length=64), nullable=True),
        sa.Column("business_group_id", sa.String(length=64), nullable=True),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("branch_id", sa.String(length=64), nullable=True),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("causation_id", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "retry", "sent", "dead_letter",
                name="sync_outbox_status", native_enum=False, create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_sync_outbox_status_next_attempt", "sync_outbox", ["status", "next_attempt_at"], unique=False
    )
    op.create_index(
        "ix_sync_outbox_aggregate",
        "sync_outbox",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
        unique=False,
    )
    op.create_index("ix_sync_outbox_correlation_id", "sync_outbox", ["correlation_id"], unique=False)

    op.create_table(
        "sync_inbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_device_id", sa.String(length=64), nullable=True),
        sa.Column("business_group_id", sa.String(length=64), nullable=True),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("branch_id", sa.String(length=64), nullable=True),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("causation_id", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "retry", "blocked", "processed", "dead_letter",
                name="sync_inbox_status", native_enum=False, create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_sync_inbox_status_next_attempt", "sync_inbox", ["status", "next_attempt_at"], unique=False
    )
    op.create_index(
        "ix_sync_inbox_aggregate",
        "sync_inbox",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
        unique=False,
    )
    op.create_index("ix_sync_inbox_correlation_id", "sync_inbox", ["correlation_id"], unique=False)

    op.create_table(
        "sync_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stream_name", sa.String(length=120), nullable=False),
        sa.Column("checkpoint_value", sa.String(length=255), nullable=True),
        sa.Column("last_event_id", sa.String(length=36), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_name"),
    )

    op.create_table(
        "sync_dead_letters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("inbound", "outbound", name="sync_direction", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("event_envelope_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open", "retry_pending", "resolved",
                name="sync_dead_letter_status", native_enum=False, create_constraint=True,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("direction", "event_id", name="uq_sync_dead_letters_direction_event"),
    )
    op.create_index("ix_sync_dead_letters_status", "sync_dead_letters", ["status"], unique=False)
    op.create_index(
        "ix_sync_dead_letters_correlation_id", "sync_dead_letters", ["correlation_id"], unique=False
    )

    op.create_table(
        "sync_aggregate_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("last_applied_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_event_id", sa.String(length=36), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "aggregate_type", "aggregate_id", name="uq_sync_aggregate_versions_aggregate"
        ),
    )
    op.create_index(
        "ix_sync_aggregate_versions_aggregate",
        "sync_aggregate_versions",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sync_aggregate_versions_aggregate", table_name="sync_aggregate_versions")
    op.drop_table("sync_aggregate_versions")

    op.drop_index("ix_sync_dead_letters_correlation_id", table_name="sync_dead_letters")
    op.drop_index("ix_sync_dead_letters_status", table_name="sync_dead_letters")
    op.drop_table("sync_dead_letters")

    op.drop_table("sync_checkpoints")

    op.drop_index("ix_sync_inbox_correlation_id", table_name="sync_inbox")
    op.drop_index("ix_sync_inbox_aggregate", table_name="sync_inbox")
    op.drop_index("ix_sync_inbox_status_next_attempt", table_name="sync_inbox")
    op.drop_table("sync_inbox")

    op.drop_index("ix_sync_outbox_correlation_id", table_name="sync_outbox")
    op.drop_index("ix_sync_outbox_aggregate", table_name="sync_outbox")
    op.drop_index("ix_sync_outbox_status_next_attempt", table_name="sync_outbox")
    op.drop_table("sync_outbox")

    op.drop_index("ix_sync_devices_status", table_name="sync_devices")
    op.drop_table("sync_devices")
