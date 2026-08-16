"""complete scoped-record coverage and step-up foundation

Revision ID: 20260811_0009
Revises: 20260811_0008
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0009"
down_revision: str | None = "20260811_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_company_scope(table: str) -> None:
    op.add_column(
        table,
        sa.Column("company_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        f"fk_{table}_company_id_companies",
        table,
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index(f"ix_{table}_company_id", table, ["company_id"], unique=False)


def _drop_company_scope(table: str) -> None:
    op.drop_index(f"ix_{table}_company_id", table_name=table)
    op.drop_constraint(f"fk_{table}_company_id_companies", table, type_="foreignkey")
    op.drop_column(table, "company_id")


def upgrade() -> None:
    _add_company_scope("product_price_history")
    _add_company_scope("inventory_batches")
    _add_company_scope("serial_numbers")

    op.execute(
        sa.text(
            """
            UPDATE product_price_history h
            SET company_id = p.company_id
            FROM products p
            WHERE p.id = h.product_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE inventory_batches b
            SET company_id = p.company_id
            FROM products p
            WHERE p.id = b.product_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE serial_numbers s
            SET company_id = p.company_id
            FROM products p
            WHERE p.id = s.product_id
            """
        )
    )

    op.add_column("users", sa.Column("last_step_up_at", sa.DateTime(timezone=True), nullable=True))

    # Fail rather than retain any batch/serial/cost-history row whose parent
    # venture cannot be proven after the P1 backfill.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM product_price_history h
                    JOIN products p ON p.id = h.product_id
                    WHERE h.company_id <> p.company_id
                ) THEN
                    RAISE EXCEPTION 'P2 validation failed: product price history company mismatch';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM inventory_batches b
                    JOIN products p ON p.id = b.product_id
                    JOIN branches br ON br.id = b.branch_id
                    WHERE b.company_id <> p.company_id OR b.company_id <> br.company_id
                ) THEN
                    RAISE EXCEPTION 'P2 validation failed: inventory batch company mismatch';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM serial_numbers s
                    JOIN products p ON p.id = s.product_id
                    LEFT JOIN branches br ON br.id = s.branch_id
                    WHERE s.company_id <> p.company_id
                       OR (s.branch_id IS NOT NULL AND s.company_id <> br.company_id)
                ) THEN
                    RAISE EXCEPTION 'P2 validation failed: serial number company mismatch';
                END IF;
            END $$
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "last_step_up_at")
    _drop_company_scope("serial_numbers")
    _drop_company_scope("inventory_batches")
    _drop_company_scope("product_price_history")
