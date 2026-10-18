"""Persistent production installation marker; no business rows are seeded."""
from alembic import op
import sqlalchemy as sa
revision = '20261018_0020'
down_revision = '20260821_0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('production_installations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('installation_id', sa.String(36), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('id = 1', name='singleton'))


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT 1 FROM production_installations LIMIT 1')).first():
        raise RuntimeError('Refusing to remove the production installation marker.')
    op.drop_table('production_installations')
