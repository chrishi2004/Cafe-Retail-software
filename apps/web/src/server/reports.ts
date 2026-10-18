import { type Db } from "mongodb";
import { type Scope } from "./security";
import { businessDate, decimal, scaled } from "./money";
import { requireValue } from "./errors";
export function range(url: URL) {
  const start = url.searchParams.get("start_date") ?? businessDate(),
    end = url.searchParams.get("end_date") ?? businessDate();
  requireValue(
    /^\d{4}-\d{2}-\d{2}$/.test(start) &&
      /^\d{4}-\d{2}-\d{2}$/.test(end) &&
      start <= end,
    "Valid ordered dates are required.",
  );
  return { start, end };
}
export async function cafeReport(db: Db, scope: Scope, url: URL) {
  const { start, end } = range(url);
  const invoices = (
    await db.collection("invoices").find(scope.filter).toArray()
  ).filter((i) => {
    const date = businessDate(new Date(i.invoice_date));
    return date >= start && date <= end;
  });
  const payments = (
    await db.collection("invoice_payments").find(scope.filter).toArray()
  ).filter((p) => {
    const date = businessDate(new Date(p.payment_datetime));
    return date >= start && date <= end;
  });
  let billed = 0,
    collected = 0,
    outstanding = 0;
  const mix: Record<string, string> = {
    Cash: "0.00",
    UPI: "0.00",
    Card: "0.00",
  };
  const top = new Map<
    string,
    {
      menu_item_id: number;
      item_name: string;
      units_sold: string;
      ordered_value: string;
    }
  >();
  for (const invoice of invoices) {
    billed += scaled(invoice.grand_total);
    outstanding += scaled(invoice.balance_due);
    for (const item of invoice.items) {
      const key = item.menu_item_public_id ?? String(item.product_id);
      const previous = top.get(key);
      top.set(key, {
        menu_item_id: item.menu_item_id ?? item.product_id,
        item_name: item.product_name_snapshot,
        units_sold: decimal(
          scaled(previous?.units_sold ?? "0") + scaled(item.quantity),
        ),
        ordered_value: decimal(
          scaled(previous?.ordered_value ?? "0") + scaled(item.line_total),
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
  const items = [...top.values()].sort(
    (a, b) => scaled(b.units_sold) - scaled(a.units_sold),
  );
  return {
    scope: "venture",
    venture: scope.company.business_type,
    period_start: start,
    period_end: end,
    kpis: {
      order_count: invoices.length,
      ordered_value: decimal(billed),
      billed_revenue: decimal(billed),
      net_billed_revenue: decimal(billed),
      collections: decimal(collected),
      outstanding: decimal(outstanding),
      cancelled_value: "0.00",
      void_value: "0.00",
      average_bill_value: decimal(
        invoices.length ? Math.round(billed / invoices.length) : 0,
      ),
      open_unbilled_sessions: 0,
    },
    top_items: items,
    top_selling_items: items,
    source_channel_mix: { billing_counter: decimal(billed) },
    payment_mode_mix: mix,
    table_turnover: {
      session_count: 0,
      closed_session_count: 0,
      average_duration_minutes: null,
    },
  };
}
