import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, managers } from "./security";
import { inventoryRows } from "./inventory";
import { salesRows } from "./dashboards";
import {
  requiredRow,
  insertRow,
  queryScope,
  dateOnly,
  shiftDate,
} from "./query";
import { scaled, decimal, multiply, businessDate } from "./money";
import { requireValue } from "./errors";
export async function recommendations(
  db: Db,
  scope: Scope,
  url: URL,
): Promise<Row[]> {
  await queryScope(db, scope, url);
  const days = Number(url.searchParams.get("lookback_days") ?? 30);
  requireValue(
    Number.isInteger(days) && days >= 1 && days <= 365,
    "Lookback must be 1–365 days.",
  );
  const end = dateOnly(url.searchParams.get("as_of_date") ?? businessDate());
  const sales = await salesRows(db, scope, url, {
    start: shiftDate(end, 1 - days),
    end,
  });
  const velocity = new Map<string, number>();
  for (const sale of sales)
    for (const item of sale.items) {
      const k = `${sale.branch_id}:${item.product_id}`;
      velocity.set(k, (velocity.get(k) ?? 0) + scaled(item.quantity));
    }
  const rows = (
    await inventoryRows(
      db,
      scope,
      url.searchParams.has("branch_id")
        ? Number(url.searchParams.get("branch_id"))
        : undefined,
    )
  ).filter((r) =>
    ["category_id", "supplier_id"].every(
      (k) =>
        !url.searchParams.has(k) || Number(url.searchParams.get(k)) === r[k],
    ),
  );
  const result = [];
  for (const row of rows) {
    const supplier = await requiredRow(db, "suppliers", {
      id: row.supplier_id,
      company_id: scope.company.id,
    });
    const daily = Math.round(
        (velocity.get(`${row.branch_id}:${row.product_id}`) ?? 0) / days,
      ),
      current = scaled(row.quantity_on_hand),
      lead = Number(supplier.lead_time_days ?? 0),
      expected = daily * lead;
    const suggested = Math.max(
      0,
      scaled(row.target_stock_level) -
        current +
        expected -
        scaled(row.quantity_on_order),
    );
    const until =
      current <= 0 ? 0 : daily > 0 ? Math.round((current * 100) / daily) : null;
    const priority =
      current <= 0 || (until !== null && until <= lead * 100)
        ? "critical"
        : current <= scaled(row.reorder_threshold)
          ? "high"
          : scaled(row.reorder_threshold) > 0 &&
              current <= scaled(row.reorder_threshold) * 1.25
            ? "medium"
            : "low";
    result.push({
      ...row,
      current_stock: row.quantity_on_hand,
      average_daily_sales: decimal(daily),
      supplier_lead_time_days: lead,
      expected_demand_during_lead_time: decimal(expected),
      days_until_stockout: until === null ? null : decimal(until),
      suggested_reorder_quantity: decimal(suggested),
      priority,
      estimated_cost: decimal(multiply(scaled(row.unit_cost), suggested)),
    });
  }
  const rank = ["critical", "high", "medium", "low"];
  return result
    .filter(
      (r) =>
        !url.searchParams.has("priority") ||
        r.priority === url.searchParams.get("priority"),
    )
    .sort(
      (a, b) =>
        rank.indexOf(a.priority) - rank.indexOf(b.priority) ||
        scaled(b.estimated_cost) - scaled(a.estimated_cost),
    );
}
export function forecastPoints(
  values: number[],
  horizon: number,
  start: string,
) {
  const window = Math.min(28, Math.max(7, Math.floor(values.length / 3))),
    recent = values.slice(-window),
    previous =
      values.length >= window * 2
        ? values.slice(-window * 2, -window)
        : values.slice(0, -window);
  const mean = (xs: number[]) =>
    xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
  const avg = mean(recent),
    old = previous.length ? mean(previous) : avg,
    adjustment = previous.length ? (avg - old) / previous.length / 2 : 0;
  const points = Array.from({ length: horizon }, (_, i) => ({
    date: shiftDate(start, i),
    value: decimal(Math.round(Math.max(0, avg + adjustment * (i + 1)))),
  }));
  const trend = old ? Math.round(((avg - old) * 10000) / old) : null;
  return {
    forecast_points: points,
    forecast_value: decimal(points.reduce((n, p) => n + scaled(p.value), 0)),
    average_daily_value: decimal(Math.round(avg)),
    trend_label:
      trend === null || Math.abs(trend) < 500
        ? "stable"
        : trend > 0
          ? "increasing"
          : "decreasing",
    trend_percent: trend === null ? null : decimal(trend),
  };
}
export async function forecasts(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  allow(scope.user, [...managers, "analyst"]);
  const productMatch = route.match(/^forecasts\/products\/(\d+)$/);
  if (method === "GET" && (route === "forecasts" || productMatch)) {
    const filter = await queryScope(db, scope, url);
    if (productMatch) {
      await requiredRow(db, "products", {
        company_id: scope.company.id,
        id: Number(productMatch[1]),
      });
      filter.product_id = Number(productMatch[1]);
    }
    for (const k of ["forecast_type", "product_id", "category_id"])
      if (url.searchParams.has(k))
        filter[k] = k.endsWith("_id")
          ? Number(url.searchParams.get(k))
          : url.searchParams.get(k);
    return db
      .collection("forecasts")
      .find(filter)
      .sort({ id: -1 })
      .limit(
        Math.max(1, Math.min(100, Number(url.searchParams.get("limit") ?? 50))),
      )
      .toArray();
  }
  if (route !== "forecasts/run" || method !== "POST") return undefined;
  requireValue(
    ["revenue", "units", "demand"].includes(body.forecast_type) &&
      [7, 30, 90].includes(Number(body.horizon_days)),
    "Invalid forecast metric or horizon.",
  );
  const params = new URL(url);
  for (const k of ["branch_id", "category_id", "product_id"])
    if (body[k] != null) params.searchParams.set(k, String(body[k]));
  await queryScope(db, scope, params);
  const asOf = body.as_of_date ? dateOnly(body.as_of_date) : businessDate(),
    days = Math.max(90, Number(body.horizon_days) * 2),
    start = shiftDate(asOf, 1 - days);
  const history = await salesRows(db, scope, params, { start, end: asOf });
  const totals = new Map<string, number>();
  for (const sale of history) {
    const day = businessDate(new Date(sale.invoice_date));
    for (const item of sale.items)
      totals.set(
        day,
        (totals.get(day) ?? 0) +
          scaled(
            body.forecast_type === "revenue" ? item.line_total : item.quantity,
          ),
      );
  }
  const points = Array.from({ length: days }, (_, i) => ({
    date: shiftDate(start, i),
    value: decimal(totals.get(shiftDate(start, i)) ?? 0),
  }));
  const details: Record<string, unknown> = {
    company_id: scope.company.id,
    branch_id: body.branch_id ?? scope.user.branch_id ?? null,
    branch_name: null,
    category_id: body.category_id ?? null,
    category_name: null,
    product_id: body.product_id ?? null,
    product_name: null,
    forecast_type: body.forecast_type,
    model_name: "moving_average_trend_v1",
  };
  for (const [field, collection] of [
    ["branch", "branches"],
    ["category", "categories"],
    ["product", "products"],
  ])
    if (details[field + "_id"] != null) {
      const row = await requiredRow(db, collection, {
        company_id: scope.company.id,
        id: Number(details[field + "_id"]),
      });
      details[field + "_name"] = row.name;
    }
  const insufficient = [...totals.values()].filter((v) => v > 0).length < 5;
  const base = {
    ...details,
    horizon_days: Number(body.horizon_days),
    history_start_date: start,
    history_end_date: asOf,
    historical_points: points,
    insufficient_data: insufficient,
  };
  if (insufficient)
    return {
      ...base,
      forecast: null,
      forecast_start_date: null,
      forecast_end_date: null,
      forecast_value: "0.00",
      confidence_low: null,
      confidence_high: null,
      average_daily_value: "0.00",
      trend_label: "stable",
      trend_percent: null,
      message:
        "Not enough historical sales data. Need at least 5 active sales days in the selected scope.",
      forecast_points: [],
    };
  const calculated = forecastPoints(
    points.map((p) => scaled(p.value)),
    Number(body.horizon_days),
    shiftDate(asOf, 1),
  );
  const record = await insertRow(db, "forecasts", {
    ...details,
    forecast_start_date: shiftDate(asOf, 1),
    forecast_end_date: shiftDate(asOf, Number(body.horizon_days)),
    forecast_value: calculated.forecast_value,
    confidence_low: decimal(
      Math.round(scaled(calculated.forecast_value) * 0.85),
    ),
    confidence_high: decimal(
      Math.round(scaled(calculated.forecast_value) * 1.15),
    ),
  });
  return {
    ...base,
    ...record,
    ...calculated,
    forecast: record,
    message: `${body.horizon_days}-day ${body.forecast_type} forecast uses the existing moving average and trend model.`,
  };
}
