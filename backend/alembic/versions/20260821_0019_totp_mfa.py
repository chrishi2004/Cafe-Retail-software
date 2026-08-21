"""Add TOTP MFA state for privileged production access.

Revision ID: 20260821_0019
Revises: 20260817_0018
"""

from alembic import op
import sqlalchemy as sa

revision = "20260821_0019"
down_revision = "20260817_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.String(length=1024), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_hashes", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_enrolled_at")
    op.drop_column("users", "mfa_recovery_hashes")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
