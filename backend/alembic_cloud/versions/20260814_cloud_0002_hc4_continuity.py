"""add HC4 replay protection and lease indexes

Revision ID: 20260814_cloud_0002
Revises: 20260813_cloud_0001
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260814_cloud_0002"
down_revision: str | None = "20260813_cloud_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "continuity_request_nonces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("request_nonce", sa.String(length=64), nullable=False),
        sa.Column("signature_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["coordination.device_registrations.device_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("device_id", "request_nonce", name="uq_continuity_request_nonce_device"),
        schema="coordination",
    )
    op.create_index(
        "ix_continuity_request_nonces_expires_at",
        "continuity_request_nonces",
        ["expires_at"],
        schema="coordination",
    )
    op.create_index(
        "ix_writer_leases_expiry_state",
        "writer_leases",
        ["lease_expires_at", "recovery_state"],
        schema="coordination",
    )
    op.execute("ALTER TABLE coordination.continuity_request_nonces ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Coordination queue/security state is durable. Destructive cloud downgrade
    # remains an explicit operator action, consistent with HC2 policy.
    pass
