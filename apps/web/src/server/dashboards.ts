import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow } from "./security";
import { inventoryRows } from "./inventory";
import { businessDate, decimal, scaled } from "./money";
import { period, queryScope, signed } from "./query";

const sum = (rows: Record<string, unknown>[], key: string) =>
  rows.reduce((n, r) => n + signed(r[key] ?? "0"), 0);
const percent = (n: number, d: number) =>
  d ? decimal(Math.round((n * 10000) / d)) : null;
const within = (value: unknown, start: string, end: string) => {
  const day = businessDate(new Date(String(value)));
  return day >= start && day <= end;
};
export async function salesRows(
  db: Db,
  scope: Scope,
  url: URL,
  dates?: { start: string; end: string },
): Promise<Row[]> {
  const filter = await queryScope(db, scope, url);
  const p = dates ?? period(url);
  const products = await db
    .collection<Row>("products")
    .find({ company_id: scope.company.id })
    .toArray();
  const categories = await db
    .collection<Row>("categories")
    .find({ company_id: scope.company.id })
    .toArray();
  const pm = new Map(products.map((x) => [x.id, x])),
    cm = new Map(categories.map((x) => [x.id, x]));
  const rows: Row[] = [];
  for (const invoice of await db
    .collection<Row>("invoices")
    .find({ ...filter, status: { $nin: ["draft", "cancelled", "voided"] } })
    .toArray()) {
    if (!within(invoice.invoice_date, p.start, p.end)) continue;
    const items = (invoice.items as Row[])
      .filter((item) => {
        const product = pm.get(item.product_id);
        return ["product_id", "category_id", "supplier_id"].every(
          (key) =>
            !url.searchParams.has(key) ||
            Number(url.searchParams.get(key)) ===
              Number(key === "product_id" ? item.product_id : product?.[key]),
        );
      })
      .map((item) => ({
        ...item,
        product_name: item.product_name_snapshot,
        product_sku: item.sku_snapshot,
        discount_amount: item.discount,
        category_id: pm.get(item.product_id)?.category_id,
        category_name:
          cm.get(pm.get(item.product_id)?.category_id)?.name ?? "Uncategorised",
      }));
    if (!items.length) continue;
    const row: Row = {
      ...invoice,
      sale_number: invoice.invoice_number,
      sale_datetime: invoice.invoice_date,
      total_amount: invoice.grand_total,
      tax_total: decimal(
        sum([invoice], "cgst_total") +
          sum([invoice], "sgst_total") +
          sum([invoice], "igst_total") +
          sum([invoice], "cess_total"),
      ),
      items,
      item_count: items.length,
      units_sold: decimal(sum(items, "quantity")),
      gross_profit: decimal(sum(items, "gross_profit")),
    };
    const search = url.searchParams.get("search")?.toLowerCase();
    if (
      !search ||
      [row.sale_number, ...items.map((i) => i.product_name)].some((x) =>
        String(x).toLowerCase().includes(search),
      )
    )
      rows.push(row);
  }
  return rows.sort(
    (a, b) =>
      String(b.invoice_date).localeCompare(String(a.invoice_date)) ||
      b.id - a.id,
  );
}
function salesKpis(rows: Row[], previous = 0) {
  const items = rows.flatMap((r) => r.items),
    revenue = sum(items, "line_total"),
    profit = sum(items, "gross_profit");
  return {
    revenue: decimal(revenue),
    gross_profit: decimal(profit),
    gross_margin_percent: percent(profit, revenue),
    units_sold: decimal(sum(items, "quantity")),
    transaction_count: rows.length,
    average_order_value: decimal(
      rows.length ? Math.round(revenue / rows.length) : 0,
    ),
    sales_growth_percent: percent(revenue - previous, previous),
    previous_period_revenue: decimal(previous),
  };
}
function grouped<T>(rows: T[], key: (row: T) => string) {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    const k = key(row);
    groups.set(k, [...(groups.get(k) ?? []), row]);
  }
  return groups;
}
export async function salesAnalytics(db: Db, scope: Scope, url: URL) {
  const p = period(url),
    rows = await salesRows(db, scope, url),
    previous = await salesRows(db, scope, url, {
      start: p.previousStart,
      end: p.previousEnd,
    });
  const flat: Row[] = rows.flatMap((row) =>
    (row.items as Row[]).map((item) => ({
      ...item,
      invoice_id: row.id,
      date: businessDate(new Date(row.invoice_date)),
      branch_id: row.branch_id,
      branch_name: row.branch_name,
    })),
  );
  const trend = [...grouped(flat, (r) => r.date)]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => ({
      date,
      revenue: decimal(sum(items, "line_total")),
      gross_profit: decimal(sum(items, "gross_profit")),
      units_sold: decimal(sum(items, "quantity")),
      transaction_count: new Set(items.map((x) => x.invoice_id)).size,
    }));
  const top = [...grouped(flat, (r) => String(r.product_id ?? r.menu_item_id))]
    .map(([, items]) => ({
      product_id: items[0].product_id,
      product_sku: items[0].product_sku,
      product_name: items[0].product_name,
      category_name: items[0].category_name,
      revenue: decimal(sum(items, "line_total")),
      gross_profit: decimal(sum(items, "gross_profit")),
      units_sold: decimal(sum(items, "quantity")),
    }))
    .sort((a, b) => scaled(b.revenue) - scaled(a.revenue));
  return {
    period_start: p.start,
    period_end: p.end,
    previous_period_start: p.previousStart,
    previous_period_end: p.previousEnd,
    summary: salesKpis(
      rows,
      sum(
        previous.flatMap((r) => r.items),
        "line_total",
      ),
    ),
    sales_trend: trend,
    top_products: top.slice(0, 10),
    revenue_by_category: [...grouped(flat, (r) => String(r.category_id))].map(
      ([, items]) => ({
        category_id: items[0].category_id,
        category_name: items[0].category_name,
        revenue: decimal(sum(items, "line_total")),
        gross_profit: decimal(sum(items, "gross_profit")),
        units_sold: decimal(sum(items, "quantity")),
      }),
    ),
    branch_performance: [...grouped(rows, (r) => String(r.branch_id))].map(
      ([, items]) => ({
        branch_id: items[0].branch_id,
        branch_name: items[0].branch_name,
        ...salesKpis(items),
      }),
    ),
  };
}
export async function inventoryAnalytics(db: Db, scope: Scope, url: URL) {
  const p = period(url);
  await queryScope(db, scope, url);
  const rows = (
    await inventoryRows(
      db,
      scope,
      url.searchParams.has("branch_id")
        ? Number(url.searchParams.get("branch_id"))
        : undefined,
    )
  ).filter((r) =>
    ["product_id", "category_id", "supplier_id"].every(
      (k) =>
        !url.searchParams.has(k) ||
        Number(url.searchParams.get(k)) === Number(r[k as keyof typeof r]),
    ),
  );
  const sales = await salesRows(db, scope, url),
    sold = new Set(
      sales.flatMap((s) =>
        (s.items as Row[]).map((i) => `${s.branch_id}:${i.product_id}`),
      ),
    );
  const history = await salesRows(db, scope, url, {
    start: "1970-01-01",
    end: p.end,
  });
  const last = new Map<string, string>();
  for (const sale of history)
    for (const item of sale.items) {
      const key = `${sale.branch_id}:${item.product_id}`;
      if (!last.has(key))
        last.set(key, businessDate(new Date(sale.invoice_date)));
    }
  const low = rows
    .filter((r) => r.is_low_stock)
    .sort(
      (a, b) =>
        scaled(a.quantity_on_hand) - scaled(b.quantity_on_hand) ||
        a.product_name.localeCompare(b.product_name),
    );
  const slow = rows
    .filter(
      (r) =>
        scaled(r.quantity_on_hand) > 0 &&
        !sold.has(`${r.branch_id}:${r.product_id}`),
    )
    .sort((a, b) => scaled(b.stock_value) - scaled(a.stock_value));
  const status = (r: (typeof rows)[number]) =>
    scaled(r.quantity_on_hand) <= 0
      ? "Out of stock"
      : r.is_low_stock
        ? "Low stock"
        : scaled(r.target_stock_level) > 0 &&
            scaled(r.quantity_on_hand) > scaled(r.target_stock_level) * 1.25
          ? "Overstocked"
          : "Healthy";
  return {
    period_start: p.start,
    period_end: p.end,
    summary: {
      current_stock_value: decimal(sum(rows, "stock_value")),
      total_quantity_on_hand: decimal(sum(rows, "quantity_on_hand")),
      low_stock_product_count: low.length,
      slow_moving_stock_count: slow.length,
    },
    inventory_health: [...grouped(rows, status)].map(([status, items]) => ({
      status,
      product_count: items.length,
      quantity_on_hand: decimal(sum(items, "quantity_on_hand")),
      stock_value: decimal(sum(items, "stock_value")),
    })),
    stock_value_by_category: [
      ...grouped(rows, (r) => String(r.category_id)),
    ].map(([, items]) => ({
      category_id: items[0].category_id,
      category_name: items[0].category_name,
      quantity_on_hand: decimal(sum(items, "quantity_on_hand")),
      stock_value: decimal(sum(items, "stock_value")),
      low_stock_count: items.filter((i) => i.is_low_stock).length,
    })),
    low_stock_items: low.slice(0, 20),
    slow_moving_stock: slow
      .slice(0, 20)
      .map((r) => ({
        ...r,
        last_sale_date: last.get(`${r.branch_id}:${r.product_id}`) ?? null,
      })),
  };
}
export async function purchaseAnalytics(db: Db, scope: Scope, url: URL) {
  const p = period(url),
    filter = await queryScope(db, scope, url);
  const rows = (
    await db
      .collection<Row>("purchase_orders")
      .find(filter)
      .sort({ order_date: -1, id: -1 })
      .toArray()
  ).filter(
    (r) =>
      String(r.order_date).slice(0, 10) >= p.start &&
      String(r.order_date).slice(0, 10) <= p.end &&
      (!url.searchParams.has("supplier_id") ||
        r.supplier_id === Number(url.searchParams.get("supplier_id"))),
  );
  const open = rows.filter(
    (r) => !["received", "cancelled", "draft"].includes(r.status),
  );
  const bucket = (items: Row[]) => ({
    count: items.length,
    total_amount: decimal(sum(items, "total_amount")),
  });
  return {
    period_start: p.start,
    period_end: p.end,
    summary: {
      pending_purchase_orders: open.length,
      pending_approval_count: rows.filter(
        (r) => r.status === "pending_approval",
      ).length,
      approved_count: rows.filter((r) => r.status === "approved").length,
      ordered_count: rows.filter((r) =>
        ["ordered", "partially_received"].includes(r.status),
      ).length,
      overdue_count: open.filter(
        (r) =>
          r.expected_delivery_date && r.expected_delivery_date < businessDate(),
      ).length,
      total_open_order_value: decimal(sum(open, "total_amount")),
    },
    by_status: [...grouped(rows, (r) => r.status)].map(([status, items]) => ({
      status,
      ...bucket(items),
    })),
    by_supplier: [...grouped(rows, (r) => String(r.supplier_id))].map(
      ([, items]) => ({
        supplier_id: items[0].supplier_id,
        supplier_name: items[0].supplier_name,
        ...bucket(items),
      }),
    ),
    branch_performance: [...grouped(rows, (r) => String(r.branch_id))].map(
      ([, items]) => ({
        branch_id: items[0].branch_id,
        branch_name: items[0].branch_name,
        ...bucket(items),
      }),
    ),
    recent_orders: rows.slice(0, 10),
  };
}
export async function dashboard(db: Db, scope: Scope, url: URL, kind: string) {
  allow(scope.user, [
    "super_admin",
    "admin",
    "store_manager",
    "staff",
    "analyst",
  ]);
  if (kind === "inventory") return inventoryAnalytics(db, scope, url);
  if (kind === "sales") return salesAnalytics(db, scope, url);
  if (kind === "purchase-orders") return purchaseAnalytics(db, scope, url);
  const sales = await salesAnalytics(db, scope, url),
    inventory = await inventoryAnalytics(db, scope, url),
    purchase = await purchaseAnalytics(db, scope, url);
  const { summary, ...rest } = sales;
  return {
    ...rest,
    kpis: {
      sales: summary,
      inventory: inventory.summary,
      purchase_orders: purchase.summary,
      top_selling_product: sales.top_products[0] ?? null,
    },
    inventory_health: inventory.inventory_health,
    low_stock_items: inventory.low_stock_items,
  };
}
export async function salesSummary(db: Db, scope: Scope, url: URL) {
  const rows = await salesRows(db, scope, url);
  return {
    ...salesKpis(rows),
    discount_total: decimal(sum(rows, "discount_total")),
    tax_total: decimal(sum(rows, "tax_total")),
  };
}
