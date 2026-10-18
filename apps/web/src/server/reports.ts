import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow } from "./security";
import { businessDate, decimal, scaled } from "./money";
import { queryScope, period, signed } from "./query";
export function range(url: URL) {
  const p = period(url, 1);
  return { start: p.start, end: p.end };
}
const inRange = (value: unknown, start: string, end: string) => {
  if (!value) return false;
  const day = businessDate(new Date(String(value)));
  return day >= start && day <= end;
};
export async function cafeReport(db: Db, scope: Scope, url: URL) {
  const { start, end } = range(url),
    filter = await queryScope(db, scope, url);
  let invoices = (
    await db.collection<Row>("invoices").find(filter).toArray()
  ).filter((i) => i.status !== "draft" && inRange(i.invoice_date, start, end));
  let orders = (
    await db.collection<Row>("cafe_orders").find(filter).toArray()
  ).filter((o) => inRange(o.placed_at ?? o.created_at, start, end));
  const sessions = (
    await db.collection<Row>("table_sessions").find(filter).toArray()
  ).filter((s) => inRange(s.opened_at, start, end));
  const eligibleIds = new Set<number>();
  const itemFilter = (item: Row) =>
    !url.searchParams.has("menu_item_id") ||
    Number(item.menu_item_id) === Number(url.searchParams.get("menu_item_id"));
  for (const param of ["status", "source_channel"])
    if (url.searchParams.has(param))
      orders = orders.filter((o) => o[param] === url.searchParams.get(param));
  if (url.searchParams.has("table_id"))
    orders = orders.filter(
      (o) => o.table_id === Number(url.searchParams.get("table_id")),
    );
  if (url.searchParams.has("menu_category_id")) {
    const ids = new Set(
      (
        await db
          .collection<Row>("menu_items")
          .find({
            company_id: scope.company.id,
            category_id: Number(url.searchParams.get("menu_category_id")),
          })
          .toArray()
      ).map((i) => i.public_id),
    );
    orders = orders.filter((o) =>
      o.items.some((i: Row) => ids.has(i.menu_item_public_id)),
    );
  }
  if (url.searchParams.has("menu_item_id"))
    orders = orders.filter((o) => o.items.some(itemFilter));
  const hasOrderFilter = [
    "status",
    "source_channel",
    "table_id",
    "menu_category_id",
    "menu_item_id",
  ].some((p) => url.searchParams.has(p));
  if (hasOrderFilter) {
    for (const o of orders)
      if (o.billed_invoice_id) eligibleIds.add(o.billed_invoice_id);
    invoices = invoices.filter((i) => eligibleIds.has(i.id));
  }
  let payments = (
    await db.collection<Row>("invoice_payments").find(filter).toArray()
  ).filter(
    (p) => !p.is_credit_marker && inRange(p.payment_datetime, start, end),
  );
  if (hasOrderFilter)
    payments = payments.filter((p) => eligibleIds.has(p.invoice_id));
  const mode = url.searchParams.get("payment_mode");
  if (mode) {
    payments = payments.filter(
      (p) =>
        p.mode_name === mode ||
        String(p.payment_mode_id) === mode ||
        p.mode_type === mode,
    );
    const ids = new Set(payments.map((p) => p.invoice_id));
    invoices = invoices.filter((i) => ids.has(i.id));
  }
  let billed = 0,
    outstanding = 0,
    voidValue = 0,
    collected = 0;
  const mix: Record<string, string> = {
      Cash: "0.00",
      UPI: "0.00",
      Card: "0.00",
    },
    channels: Record<string, string> = {},
    top = new Map<string, Row>();
  for (const invoice of invoices) {
    if (["cancelled", "returned"].includes(invoice.status)) {
      voidValue += scaled(invoice.grand_total);
      continue;
    }
    billed += scaled(invoice.grand_total);
    outstanding += scaled(invoice.balance_due);
    for (const item of invoice.items) {
      if (!itemFilter(item)) continue;
      const key = String(item.menu_item_id ?? item.product_id),
        old = top.get(key);
      top.set(key, {
        id: item.menu_item_id ?? item.product_id,
        menu_item_id: item.menu_item_id ?? item.product_id,
        item_name: item.product_name_snapshot,
        units_sold: decimal(
          scaled(old?.units_sold ?? "0") + scaled(item.quantity),
        ),
        ordered_value: decimal(
          scaled(old?.ordered_value ?? "0") + scaled(item.line_total),
        ),
      });
    }
  }
  for (const payment of payments) {
    collected += scaled(payment.amount);
    mix[payment.mode_name] = decimal(
      scaled(mix[payment.mode_name] ?? "0") + scaled(payment.amount),
    );
  }
  let ordered = 0,
    cancelled = 0;
  for (const order of orders) {
    const value = scaled(order.estimated_total ?? order.total_amount ?? "0");
    ordered += value;
    if (["cancelled", "rejected"].includes(order.status)) cancelled += value;
    channels[order.source_channel] = decimal(
      scaled(channels[order.source_channel] ?? "0") + value,
    );
  }
  const items = [...top.values()].sort(
    (a, b) => scaled(b.units_sold) - scaled(a.units_sold),
  );
  const closed = sessions.filter((s) => s.closed_at),
    minutes = closed.reduce(
      (n, s) => n + (Date.parse(s.closed_at) - Date.parse(s.opened_at)) / 60000,
      0,
    ),
    count = invoices.filter(
      (i) => !["cancelled", "returned"].includes(i.status),
    ).length;
  return {
    scope: "venture",
    venture: scope.company.business_type,
    period_start: start,
    period_end: end,
    kpis: {
      order_count:
        scope.company.business_type === "cafe" ? orders.length : count,
      ordered_value: decimal(
        scope.company.business_type === "cafe" ? ordered : billed,
      ),
      billed_revenue: decimal(billed + voidValue),
      net_billed_revenue: decimal(billed),
      collections: decimal(collected),
      outstanding: decimal(outstanding),
      cancelled_value: decimal(cancelled),
      void_value: decimal(voidValue),
      average_bill_value: decimal(count ? Math.round(billed / count) : 0),
      open_unbilled_sessions: sessions.filter((s) =>
        ["open", "bill_requested"].includes(s.status),
      ).length,
    },
    top_items: items,
    top_selling_items: items,
    source_channel_mix: channels,
    payment_mode_mix: mix,
    table_turnover: {
      session_count: sessions.length,
      closed_session_count: closed.length,
      average_duration_minutes: closed.length
        ? decimal(Math.round((minutes * 100) / closed.length))
        : null,
    },
  };
}
export async function consolidated(db: Db, user: Row, url: URL) {
  allow(user, ["super_admin"]);
  const ventures = await db
    .collection<Row>("companies")
    .find({ business_group_id: user.business_group_id, is_active: true })
    .toArray();
  const reports = [];
  for (const company of ventures)
    reports.push({
      company,
      report: await cafeReport(
        db,
        { user, company, filter: { company_id: company.id } },
        url,
      ),
    });
  const { start, end } = range(url),
    kpis: Record<string, string | number> = {};
  const money = [
    "ordered_value",
    "billed_revenue",
    "net_billed_revenue",
    "collections",
    "outstanding",
    "cancelled_value",
    "void_value",
  ];
  for (const key of money)
    kpis[key] = decimal(
      reports.reduce(
        (n, r) => n + signed(r.report.kpis[key as keyof typeof r.report.kpis]),
        0,
      ),
    );
  kpis.order_count = reports.reduce((n, r) => n + r.report.kpis.order_count, 0);
  kpis.open_unbilled_sessions = reports.reduce(
    (n, r) => n + r.report.kpis.open_unbilled_sessions,
    0,
  );
  kpis.average_bill_value = decimal(
    kpis.order_count
      ? Math.round(scaled(kpis.net_billed_revenue) / Number(kpis.order_count))
      : 0,
  );
  const payment_mode_mix: Record<string, string> = {},
    source_channel_mix: Record<string, string> = {};
  for (const { report } of reports)
    for (const [key, value] of Object.entries(report.payment_mode_mix))
      payment_mode_mix[key] = decimal(
        scaled(payment_mode_mix[key] ?? "0") + scaled(value),
      );
  return {
    scope: "group",
    venture: "consolidated",
    period_start: start,
    period_end: end,
    kpis,
    top_items: [],
    top_selling_items: [],
    payment_mode_mix,
    source_channel_mix,
    table_turnover: {
      session_count: reports.reduce(
        (n, r) => n + r.report.table_turnover.session_count,
        0,
      ),
      closed_session_count: reports.reduce(
        (n, r) => n + r.report.table_turnover.closed_session_count,
        0,
      ),
      average_duration_minutes: null,
    },
    venture_summaries: reports.map(({ company, report }) => ({
      company_id: company.id,
      company_name: company.name,
      venture: company.business_type,
      billed_revenue: report.kpis.billed_revenue,
      net_billed_revenue: report.kpis.net_billed_revenue,
      collections: report.kpis.collections,
      outstanding: report.kpis.outstanding,
    })),
  };
}
