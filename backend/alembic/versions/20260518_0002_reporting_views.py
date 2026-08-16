"""add power bi reporting views

Revision ID: 20260518_0002
Revises: 20260518_0001
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260518_0002"
down_revision: str | None = "20260518_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW vw_sales_summary AS
        SELECT
            DATE(s.sale_datetime) AS sale_date,
            b.id AS branch_id,
            b.name AS branch_name,
            COALESCE(SUM(si.line_total), 0) AS revenue,
            COALESCE(SUM((si.unit_price - p.unit_cost) * si.quantity - si.discount_amount), 0) AS gross_profit,
            COALESCE(SUM(si.quantity), 0) AS units_sold,
            COUNT(DISTINCT s.id) AS transaction_count,
            COALESCE(SUM(si.line_total) / NULLIF(COUNT(DISTINCT s.id), 0), 0) AS average_order_value
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        JOIN products p ON p.id = si.product_id
        JOIN branches b ON b.id = s.branch_id
        GROUP BY DATE(s.sale_datetime), b.id, b.name
        """
    )

    op.execute(
        """
        CREATE VIEW vw_sales_by_product AS
        SELECT
            p.id AS product_id,
            p.sku AS product_sku,
            p.name AS product_name,
            c.id AS category_id,
            c.name AS category_name,
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            b.id AS branch_id,
            b.name AS branch_name,
            COALESCE(SUM(si.quantity), 0) AS units_sold,
            COALESCE(SUM(si.line_total), 0) AS revenue,
            COALESCE(SUM((si.unit_price - p.unit_cost) * si.quantity - si.discount_amount), 0) AS gross_profit
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN products p ON p.id = si.product_id
        JOIN categories c ON c.id = p.category_id
        JOIN suppliers sp ON sp.id = p.supplier_id
        JOIN branches b ON b.id = s.branch_id
        GROUP BY p.id, p.sku, p.name, c.id, c.name, sp.id, sp.name, b.id, b.name
        """
    )

    op.execute(
        """
        CREATE VIEW vw_sales_by_category AS
        SELECT
            c.id AS category_id,
            c.name AS category_name,
            b.id AS branch_id,
            b.name AS branch_name,
            COALESCE(SUM(si.quantity), 0) AS units_sold,
            COALESCE(SUM(si.line_total), 0) AS revenue,
            COALESCE(SUM((si.unit_price - p.unit_cost) * si.quantity - si.discount_amount), 0) AS gross_profit,
            COUNT(DISTINCT p.id) AS product_count
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN products p ON p.id = si.product_id
        JOIN categories c ON c.id = p.category_id
        JOIN branches b ON b.id = s.branch_id
        GROUP BY c.id, c.name, b.id, b.name
        """
    )

    op.execute(
        """
        CREATE VIEW vw_inventory_health AS
        SELECT
            i.id AS inventory_id,
            b.id AS branch_id,
            b.name AS branch_name,
            p.id AS product_id,
            p.sku AS product_sku,
            p.name AS product_name,
            c.id AS category_id,
            c.name AS category_name,
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            i.quantity_on_hand,
            i.quantity_reserved,
            i.quantity_on_order,
            p.reorder_threshold,
            p.target_stock_level,
            p.unit_cost,
            i.quantity_on_hand * p.unit_cost AS stock_value,
            CASE
                WHEN i.quantity_on_hand <= 0 THEN 'Out of stock'
                WHEN i.quantity_on_hand <= p.reorder_threshold THEN 'Low stock'
                WHEN p.target_stock_level > 0 AND i.quantity_on_hand > p.target_stock_level * 1.25 THEN 'Overstocked'
                ELSE 'Healthy'
            END AS stock_status,
            CASE WHEN i.quantity_on_hand <= p.reorder_threshold THEN 1 ELSE 0 END AS is_low_stock,
            CASE WHEN p.is_active THEN 1 ELSE 0 END AS product_active,
            i.last_updated_at
        FROM inventory i
        JOIN products p ON p.id = i.product_id
        JOIN categories c ON c.id = p.category_id
        JOIN suppliers sp ON sp.id = p.supplier_id
        JOIN branches b ON b.id = i.branch_id
        """
    )

    op.execute(
        """
        CREATE VIEW vw_low_stock AS
        SELECT
            i.id AS inventory_id,
            b.id AS branch_id,
            b.name AS branch_name,
            p.id AS product_id,
            p.sku AS product_sku,
            p.name AS product_name,
            c.id AS category_id,
            c.name AS category_name,
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            i.quantity_on_hand,
            i.quantity_on_order,
            p.reorder_threshold,
            p.target_stock_level,
            p.unit_cost,
            i.quantity_on_hand * p.unit_cost AS stock_value,
            i.last_updated_at
        FROM inventory i
        JOIN products p ON p.id = i.product_id
        JOIN categories c ON c.id = p.category_id
        JOIN suppliers sp ON sp.id = p.supplier_id
        JOIN branches b ON b.id = i.branch_id
        WHERE i.quantity_on_hand <= p.reorder_threshold
        """
    )

    op.execute(
        """
        CREATE VIEW vw_purchase_order_status AS
        SELECT
            po.status,
            b.id AS branch_id,
            b.name AS branch_name,
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            COUNT(po.id) AS purchase_order_count,
            COALESCE(SUM(po.total_amount), 0) AS total_amount,
            MIN(po.order_date) AS first_order_date,
            MAX(po.order_date) AS latest_order_date
        FROM purchase_orders po
        JOIN branches b ON b.id = po.branch_id
        JOIN suppliers sp ON sp.id = po.supplier_id
        GROUP BY po.status, b.id, b.name, sp.id, sp.name
        """
    )

    op.execute(
        """
        CREATE VIEW vw_supplier_performance AS
        WITH product_rollup AS (
            SELECT supplier_id, COUNT(*) AS product_count
            FROM products
            GROUP BY supplier_id
        ),
        order_rollup AS (
            SELECT
                supplier_id,
                COUNT(*) AS purchase_order_count,
                COALESCE(SUM(total_amount), 0) AS total_order_value,
                COALESCE(SUM(
                    CASE
                        WHEN status IN ('draft', 'pending_approval', 'approved', 'ordered', 'partially_received')
                        THEN total_amount
                        ELSE 0
                    END
                ), 0) AS open_order_value
            FROM purchase_orders
            GROUP BY supplier_id
        ),
        receiving_rollup AS (
            SELECT
                po.supplier_id,
                COALESCE(SUM(poi.quantity_ordered), 0) AS total_quantity_ordered,
                COALESCE(SUM(poi.quantity_received), 0) AS total_quantity_received
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            GROUP BY po.supplier_id
        )
        SELECT
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            sp.lead_time_days,
            COALESCE(pr.product_count, 0) AS product_count,
            COALESCE(orr.purchase_order_count, 0) AS purchase_order_count,
            COALESCE(orr.total_order_value, 0) AS total_order_value,
            COALESCE(orr.open_order_value, 0) AS open_order_value,
            COALESCE(rr.total_quantity_ordered, 0) AS total_quantity_ordered,
            COALESCE(rr.total_quantity_received, 0) AS total_quantity_received
        FROM suppliers sp
        LEFT JOIN product_rollup pr ON pr.supplier_id = sp.id
        LEFT JOIN order_rollup orr ON orr.supplier_id = sp.id
        LEFT JOIN receiving_rollup rr ON rr.supplier_id = sp.id
        """
    )

    op.execute(
        """
        CREATE VIEW vw_forecast_summary AS
        SELECT
            f.id AS forecast_id,
            f.created_at,
            f.forecast_type,
            CASE
                WHEN f.product_id IS NOT NULL THEN 'product'
                WHEN f.category_id IS NOT NULL THEN 'category'
                WHEN f.branch_id IS NOT NULL THEN 'branch'
                ELSE 'overall'
            END AS scope_type,
            COALESCE(p.name, c.name, b.name, 'Overall business') AS scope_name,
            b.id AS branch_id,
            b.name AS branch_name,
            c.id AS category_id,
            c.name AS category_name,
            p.id AS product_id,
            p.name AS product_name,
            f.forecast_start_date,
            f.forecast_end_date,
            f.forecast_value,
            f.confidence_low,
            f.confidence_high,
            f.model_name
        FROM forecasts f
        LEFT JOIN products p ON p.id = f.product_id
        LEFT JOIN categories c ON c.id = f.category_id
        LEFT JOIN branches b ON b.id = f.branch_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_forecast_summary")
    op.execute("DROP VIEW IF EXISTS vw_supplier_performance")
    op.execute("DROP VIEW IF EXISTS vw_purchase_order_status")
    op.execute("DROP VIEW IF EXISTS vw_low_stock")
    op.execute("DROP VIEW IF EXISTS vw_inventory_health")
    op.execute("DROP VIEW IF EXISTS vw_sales_by_category")
    op.execute("DROP VIEW IF EXISTS vw_sales_by_product")
    op.execute("DROP VIEW IF EXISTS vw_sales_summary")
