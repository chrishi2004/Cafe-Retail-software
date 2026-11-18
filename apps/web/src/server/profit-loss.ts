import type { Db } from "mongodb";
import { DAY_MS, shiftDate } from "../businessDates";
import type { Row } from "./db";
import { isStockOrSupplierExpense } from "./expenses";
import { HttpError, requireValue } from "./errors";
import { day, exportScopes, linkedLookup, scan, streamCsv, type ExportScope, type Range, type SnapshotScope } from "./historical-exports";
import { decimal, scaled } from "./money";
import { emptyPaymentBreakdown, paymentBucket, receiptFilter, type ReceiptSource } from "./paymentActivity";
import { excludedSalesStatuses, period, signed } from "./query";
import { allow } from "./security";

const headers = { "Cache-Control": "private, no-store" };
const taxFields = ["cgst_total", "sgst_total", "igst_total", "cess_total"] as const;
const receiptSources: ReceiptSource[] = ["invoice_payments", "customer_payments"];
const sum = (numbers: number[]) => numbers.reduce((total, value) => total + value, 0);
const counters = () => ({
  gross_billed_sales: 0, cancelled_sales: 0, net_billed_sales: 0, net_recognized_sales: 0, recorded_sales_tax: 0,
  recorded_cogs: 0, operating_expenses: 0, stock_purchases: 0, cash_operating_expenses: 0, cash_supplier_outflows: 0,
  outstanding_invoice_credit: 0, issued_invoices: 0, reversed_invoices: 0, active_invoices: 0, excluded_drafts: 0,
  recorded_cost_lines: 0, inferred_cost_lines: 0, missing_cost_lines: 0, cafe_lines_without_recipe_cost: 0,
  missing_tax_records: 0, invalid_billing_records: 0, unpriced_stock_receipts: 0,
});
type Counters = ReturnType<typeof counters>;
type PaymentAmounts = ReturnType<typeof emptyPaymentBreakdown>;
type Trend = Pick<Counters, "net_recognized_sales" | "operating_expenses" | "stock_purchases">;
const emptyTrend = (): Trend => ({ net_recognized_sales: 0, operating_expenses: 0, stock_purchases: 0 });
const fresh = () => ({
  totals: counters(), receipts: emptyPaymentBreakdown(), refunds: emptyPaymentBreakdown(),
  expenses: new Map<string, number>(), trend: new Map<string, Trend>(),
});
type Accumulator = ReturnType<typeof fresh>;

function amount(value: unknown) {
  return (typeof value === "number" || typeof value === "string") && /^\d{1,9}(\.\d{1,2})?$/.test(String(value)) ? scaled(value) : null;
}
function optionalSigned(value: unknown) {
  return (typeof value === "number" || typeof value === "string") && /^-?\d{1,9}(\.\d{1,2})?$/.test(String(value)) ? signed(value) : null;
}

function recordedCost(item: Record<string, unknown>) {
  const explicit = amount(item.recorded_cogs);
  if (explicit !== null) return { value: explicit, inferred: false };
  // Historical checkout stored gross profit as taxable line value less the cost
  // captured at checkout. A zero difference is indistinguishable from missing cost.
  const taxable = amount(item.taxable_value);
  const historicalMargin = optionalSigned(item.gross_profit);
  if (taxable === null || historicalMargin === null || historicalMargin >= taxable) return null;
  return { value: taxable - historicalMargin, inferred: true };
}

function revenue(invoice: Row, total: number) {
  if (invoice.invoice_type === "non_gst") return total;
  const taxes = taxFields.map(field => amount(invoice[field]));
  if (taxes.every(tax => tax !== null)) {
    const net = total - sum(taxes);
    return net >= 0 ? net : null;
  }
  const taxable = amount(invoice.taxable_total);
  const rounding = optionalSigned(invoice.round_off) ?? 0;
  return taxable !== null && taxable + rounding >= 0 && taxable + rounding <= total ? taxable + rounding : null;
}

function addTrend(report: Accumulator, date: string, monthly: boolean, metric: keyof Trend, value: number) {
  const key = monthly ? date.slice(0, 8) + "01" : date;
  const point = report.trend.get(key) ?? emptyTrend();
  point[metric] += value;
  report.trend.set(key, point);
}

function addInvoice(report: Accumulator, invoice: Row, date: string, businessType: string, monthly: boolean) {
  const t = report.totals;
  // A cancelled draft has never contributed to billed revenue.
  if (invoice.status === "draft" || String(invoice.invoice_number ?? "").startsWith("DRAFT-")) {
    t.excluded_drafts++;
    return;
  }
  t.issued_invoices++;
  const total = amount(invoice.grand_total);
  if (total === null) { t.invalid_billing_records++; return; }
  t.gross_billed_sales += total;
  if (excludedSalesStatuses.includes(invoice.status)) {
    t.reversed_invoices++;
    t.cancelled_sales += total;
    return;
  }
  t.active_invoices++;
  t.net_billed_sales += total;
  const net = revenue(invoice, total);
  if (net === null) t.missing_tax_records++;
  else {
    t.net_recognized_sales += net;
    t.recorded_sales_tax += total - net;
    addTrend(report, date, monthly, "net_recognized_sales", net);
  }
  t.outstanding_invoice_credit += amount(invoice.balance_due) ?? 0;
  if (!Array.isArray(invoice.items) || !invoice.items.length) {
    t.missing_cost_lines++;
    return;
  }
  for (const item of invoice.items) {
    const cost = item && typeof item === "object" ? recordedCost(item) : null;
    if (cost !== null) {
      t.recorded_cogs += cost.value;
      if (cost.inferred) t.inferred_cost_lines++;
      else t.recorded_cost_lines++;
    }
    if (businessType === "cafe" && !(item?.recipe_cost_recorded && cost)) t.cafe_lines_without_recipe_cost++;
    if (!cost) t.missing_cost_lines++;
  }
}

function merge(reports: Accumulator[]): Accumulator {
  const combined = fresh();
  for (const report of reports) {
    for (const key of Object.keys(report.totals) as (keyof Counters)[]) combined.totals[key] += report.totals[key];
    for (const mode of Object.keys(report.receipts) as (keyof PaymentAmounts)[]) {
      combined.receipts[mode] += report.receipts[mode];
      combined.refunds[mode] += report.refunds[mode];
    }
    for (const [category, value] of report.expenses) combined.expenses.set(category, (combined.expenses.get(category) ?? 0) + value);
    for (const [date, point] of report.trend) {
      const target = combined.trend.get(date) ?? emptyTrend();
      for (const key of Object.keys(point) as (keyof Trend)[]) target[key] += point[key];
      combined.trend.set(date, target);
    }
  }
  return combined;
}

async function summarize(db: Db, scope: SnapshotScope, current: Range, prior: Range, monthly: boolean) {
  const currentData = fresh(), priorData = fresh();
  const range = { start: prior.start, end: current.end };
  const target = (date: string) => date >= current.start ? currentData : priorData;
  const fields = "invoice_number,invoice_date,invoice_type,status,grand_total,balance_due,taxable_total,round_off," +
    taxFields.join(",") + ",items.recorded_cogs,items.taxable_value,items.gross_profit,items.recipe_cost_recorded";
  for await (const invoice of scan(db, scope, "invoices", fields, { dates: range, field: "invoice_date", instant: true })) {
    const date = day(invoice.invoice_date)!;
    addInvoice(target(date), invoice, date, scope.company.business_type, monthly);
  }

  // Orphaned reversals supply a gross-and-offset pair for invoices previously
  // removed by the existing cancellation flow. A retained invoice is authoritative.
  const retainedInvoice = linkedLookup(db, scope, "invoices", "id", "status");
  let lastReversedId: number | null = null;
  for await (const row of scan(db, scope, "financial_reversals", "invoice_date,invoice_id,amount", {
    dates: range, field: "invoice_date", instant: true, sortField: "invoice_id",
    where: { reversal_type: "void", "compensation_json.invoice_deleted": true },
  })) {
    const date = day(row.invoice_date)!;
    const t = target(date).totals;
    if (!Number.isSafeInteger(row.invoice_id) || row.invoice_id <= 0) { t.invalid_billing_records++; continue; }
    if (row.invoice_id === lastReversedId) continue;
    lastReversedId = row.invoice_id;
    const existing = await retainedInvoice(row.invoice_id, row.branch_id);
    if (existing) {
      if (!excludedSalesStatuses.includes(existing.status)) t.invalid_billing_records++;
      continue;
    }
    const total = amount(row.amount);
    if (total === null) { t.invalid_billing_records++; continue; }
    t.issued_invoices++;
    t.reversed_invoices++;
    t.gross_billed_sales += total;
    t.cancelled_sales += total;
  }

  for (const source of receiptSources) {
    for await (const row of scan(db, scope, source, "amount,payment_datetime,mode_type", {
      dates: range, field: "payment_datetime", instant: true, where: receiptFilter(source),
    })) target(day(row.payment_datetime)!).receipts[paymentBucket(row.mode_type)] += scaled(row.amount);
  }
  for await (const row of scan(db, scope, "invoice_refunds", "amount,refund_date,mode_type", { dates: range, field: "refund_date" })) {
    target(row.refund_date).refunds[paymentBucket(row.mode_type)] += scaled(row.amount);
  }

  const lookupStockFeed = linkedLookup(db, scope, "stock_intakes", "id", "status");
  const lookupPurchaseOrder = linkedLookup(db, scope, "purchase_orders", "id", "status");
  for await (const row of scan(db, scope, "expenses", "expense_date,amount,category,payment_mode,source_type,source_id", {
    dates: range, field: "expense_date", where: { status: "posted" },
  })) {
    const p = target(row.expense_date);
    const cost = scaled(row.amount);
    const category = typeof row.category === "string" ? row.category : "miscellaneous";
    if (isStockOrSupplierExpense(row.category, row.source_type)) {
      if (row.payment_mode === "cash") p.totals.cash_supplier_outflows += cost;
      if (row.source_type === "supplier_payment") continue;
      if (row.source_type === "stock_intake" && (await lookupStockFeed(row.source_id, row.branch_id))?.status === "posted") continue;
      if (row.source_type === "purchase_order" && await lookupPurchaseOrder(row.source_id, row.branch_id)) continue;
      p.totals.stock_purchases += cost;
      addTrend(p, row.expense_date, monthly, "stock_purchases", cost);
      continue;
    }
    p.totals.operating_expenses += cost;
    if (row.payment_mode === "cash") p.totals.cash_operating_expenses += cost;
    p.expenses.set(category, (p.expenses.get(category) ?? 0) + cost);
    addTrend(p, row.expense_date, monthly, "operating_expenses", cost);
  }

  for await (const row of scan(db, scope, "stock_intakes", "purchase_date,total_amount", {
    dates: range, field: "purchase_date", where: { status: "posted" },
  })) {
    const p = target(row.purchase_date);
    const cost = amount(row.total_amount);
    if (cost === null || cost === 0) { p.totals.unpriced_stock_receipts++; continue; }
    p.totals.stock_purchases += cost;
    addTrend(p, row.purchase_date, monthly, "stock_purchases", cost);
  }

  for await (const row of scan(db, scope, "stock_movements", "created_at,line_total,unit_cost", {
    dates: range, field: "created_at", instant: true, where: { movement_type: "purchase_received", reference_type: "purchase_order" },
  })) {
    const date = day(row.created_at)!;
    const p = target(date);
    const cost = amount(row.line_total);
    if (cost === null || !amount(row.unit_cost)) { p.totals.unpriced_stock_receipts++; continue; }
    p.totals.stock_purchases += cost;
    addTrend(p, date, monthly, "stock_purchases", cost);
  }

  // The customer ledger is shared across branches, so a venture total is
  // defensible; an as-of or cross-branch allocation is not stored.
  let ledgerCredit = 0;
  if (!scope.branchId) {
    for await (const row of scan(db, scope, "customers", "outstanding_scaled,opening_balance")) {
      const balance = Number.isSafeInteger(row.outstanding_scaled) ? row.outstanding_scaled : amount(row.opening_balance) ?? 0;
      ledgerCredit += Math.max(0, balance);
    }
  }
  return { currentData, priorData, ledgerCredit: scope.branchId ? null : ledgerCredit };
}

function present(p: Accumulator) {
  const t = p.totals;
  const costIncomplete = t.missing_cost_lines > 0 || t.cafe_lines_without_recipe_cost > 0;
  const billingIncomplete = t.missing_tax_records > 0 || t.invalid_billing_records > 0;
  const adequatelyCosted = !costIncomplete && !billingIncomplete && t.active_invoices > 0;
  const grossProfit = adequatelyCosted ? t.net_recognized_sales - t.recorded_cogs : null;
  const amountIfKnown = (value: number | null) => value === null ? null : decimal(value);
  const status = billingIncomplete ? "billing_data_incomplete" : costIncomplete ? "cost_data_incomplete" : adequatelyCosted ? "recorded_cost_covered" : "no_sales";
  return {
    gross_billed_sales: decimal(t.gross_billed_sales),
    cancelled_sales_adjustments: decimal(-t.cancelled_sales),
    net_billed_sales: decimal(t.net_billed_sales),
    net_recognized_sales: t.missing_tax_records > 0 || t.invalid_billing_records > 0 ? null : decimal(t.net_recognized_sales),
    recorded_sales_tax: t.missing_tax_records > 0 || t.invalid_billing_records > 0 ? null : decimal(t.recorded_sales_tax),
    recorded_cogs: decimal(t.recorded_cogs),
    gross_profit: amountIfKnown(grossProfit),
    gross_margin_percent: grossProfit === null || !t.net_recognized_sales ? null : decimal(Math.round((grossProfit * 10000) / t.net_recognized_sales)),
    operating_expenses: decimal(t.operating_expenses),
    stock_purchases: decimal(t.stock_purchases),
    operating_result: amountIfKnown(grossProfit === null ? null : grossProfit - t.operating_expenses),
    cash_collections: decimal(p.receipts.cash), upi_collections: decimal(p.receipts.upi), card_collections: decimal(p.receipts.card),
    other_collections: decimal(p.receipts.other_electronic + p.receipts.other_non_cash),
    gross_collections: decimal(sum(Object.values(p.receipts))),
    actual_refunds: decimal(sum(Object.values(p.refunds))),
    actual_cash_refunds: decimal(p.refunds.cash),
    net_collections: decimal(sum(Object.values(p.receipts)) - sum(Object.values(p.refunds))),
    cash_operating_expenses: decimal(t.cash_operating_expenses),
    cash_supplier_outflows: decimal(t.cash_supplier_outflows),
    outstanding_invoice_credit: decimal(t.outstanding_invoice_credit),
    quality: {
      status, issued_invoices: t.issued_invoices, reversed_invoices: t.reversed_invoices, excluded_drafts: t.excluded_drafts,
      recorded_cost_lines: t.recorded_cost_lines, inferred_cost_lines: t.inferred_cost_lines,
      missing_cost_lines: t.missing_cost_lines, cafe_lines_without_recipe_cost: t.cafe_lines_without_recipe_cost,
      missing_tax_records: t.missing_tax_records, invalid_billing_records: t.invalid_billing_records,
      unpriced_stock_receipts: t.unpriced_stock_receipts,
    },
  };
}

function presentTrends(data: Accumulator, range: Range, monthly: boolean) {
  const days: string[] = [];
  for (let date = monthly ? range.start.slice(0, 8) + "01" : range.start; date <= range.end; ) {
    days.push(date);
    date = monthly ? shiftDate(date, 32).slice(0, 8) + "01" : shiftDate(date, 1);
  }
  return days.map(date => {
    const point = data.trend.get(date) ?? emptyTrend();
    return {
      period_ist: date,
      net_recognized_sales: data.totals.missing_tax_records || data.totals.invalid_billing_records ? null : decimal(point.net_recognized_sales),
      operating_expenses: decimal(point.operating_expenses),
      stock_purchases: decimal(point.stock_purchases),
    };
  });
}

async function buildProfitLoss(db: Db, scopes: ExportScope[], dates: ReturnType<typeof period>) {
  const range = { start: dates.start, end: dates.end };
  const priorRange = { start: dates.previousStart, end: dates.previousEnd };
  const monthly = Date.parse(dates.end) - Date.parse(dates.start) >= 92 * DAY_MS;
  const session = db.client.startSession({ snapshot: true });
  try {
    const rows = [];
    for (const scope of scopes) {
      const results = await summarize(db, { ...scope, session }, range, priorRange, monthly);
      rows.push({
        ...results, company_id: scope.company.id, venture: scope.company.name as string,
        branch_id: scope.branchId, branch: scope.branchId ? scope.branches.get(scope.branchId) ?? null : null,
      });
    }
    const current = merge(rows.map(row => row.currentData)), previous = merge(rows.map(row => row.priorData));
    const assignedBranch = rows.length === 1 ? rows[0].branch_id : null;
    return {
      currency: "INR", timezone: "Asia/Kolkata", period: range, previous_period: priorRange,
      scope: {
        company_id: rows.length === 1 ? rows[0].company_id : null,
        venture: rows.length === 1 ? rows[0].venture : "Consolidated",
        branch_id: assignedBranch, branch: rows.length === 1 ? rows[0].branch : null,
      },
      current: present(current), previous: present(previous),
      current_customer_ledger_credit: assignedBranch ? null : decimal(sum(rows.map(row => row.ledgerCredit ?? 0))),
      supplier_payables: null,
      by_venture: rows.map(row => ({
        company_id: row.company_id, venture: row.venture, branch_id: row.branch_id, branch: row.branch,
        current: present(row.currentData), previous: present(row.priorData),
        current_customer_ledger_credit: row.ledgerCredit === null ? null : decimal(row.ledgerCredit),
      })),
      expenses_by_category: [...current.expenses].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([category, amount]) => ({ category, amount: decimal(amount) })),
      trend_interval: monthly ? "month" : "day",
      trend: presentTrends(current, range, monthly),
    };
  } finally { await session.endSession(); }
}

export type ProfitLossReport = Awaited<ReturnType<typeof buildProfitLoss>>;
type Metrics = ProfitLossReport["current"];
const metricColumns = [
  "gross_billed_sales", "cancelled_sales_adjustments", "net_billed_sales", "net_recognized_sales", "recorded_sales_tax",
  "recorded_cogs", "gross_profit", "gross_margin_percent", "operating_expenses", "stock_purchases", "operating_result",
  "cash_collections", "upi_collections", "card_collections", "other_collections", "gross_collections",
  "actual_refunds", "actual_cash_refunds", "net_collections", "cash_operating_expenses", "cash_supplier_outflows",
  "outstanding_invoice_credit",
] as const satisfies readonly (keyof Metrics)[];
const qualityColumns = [
  "status", "issued_invoices", "reversed_invoices", "excluded_drafts", "recorded_cost_lines", "inferred_cost_lines", "missing_cost_lines",
  "cafe_lines_without_recipe_cost", "missing_tax_records", "invalid_billing_records", "unpriced_stock_receipts",
] as const satisfies readonly (keyof Metrics["quality"])[];
const csvColumns = [
  "section", "company_id", "venture", "branch_id", "branch", "period_start_ist", "period_end_ist",
  ...metricColumns, "current_customer_ledger_credit", "supplier_payables", ...qualityColumns, "category", "amount",
];

async function* reportCsv(report: ProfitLossReport) {
  const toRow = (section: string, { quality, ...metrics }: Metrics, range: Range, ledger: string | null) => ({
    section, ...metrics, ...quality, period_start_ist: range.start, period_end_ist: range.end,
    current_customer_ledger_credit: ledger, supplier_payables: null,
  });
  yield { ...report.scope, ...toRow("selected_scope", report.current, report.period, report.current_customer_ledger_credit) };
  yield { ...report.scope, ...toRow("previous_period", report.previous, report.previous_period, null) };
  for (const row of report.by_venture) {
    const { current, previous, current_customer_ledger_credit, ...labels } = row;
    yield { ...labels, ...toRow("venture", current, report.period, current_customer_ledger_credit) };
    yield { ...labels, ...toRow("venture_previous", previous, report.previous_period, null) };
  }
  for (const row of report.expenses_by_category)
    yield { ...report.scope, ...row, section: "expense_category", period_start_ist: report.period.start, period_end_ist: report.period.end };
  for (const { period_ist, ...row } of report.trend)
    yield { ...report.scope, ...row, section: "trend", period_start_ist: period_ist };
}

export async function profitLoss(db: Db, user: Row, request: Request, url: URL, route: string) {
  allow(user, ["super_admin"]);
  if (request.method !== "GET") throw new HttpError(405, "method_not_allowed", "Financial reports are read-only.");
  if (route === "financial/profit-loss/options") {
    const scopes = await exportScopes(db, user, request, new URLSearchParams(), false, false);
    return Response.json({
      companies: scopes.map(({ company }) => ({ id: company.id, name: company.name })),
      branches: scopes.flatMap(({ company, branches }) => [...branches.entries()].map(([id, name]) => ({ id, name, company_id: company.id }))),
    }, { headers });
  }
  if (route !== "financial/profit-loss") throw new HttpError(404, "not_found", "Financial report unavailable.");
  const format = url.searchParams.get("format");
  requireValue(!format || format === "csv", "Unknown financial report format.");
  const scopes = await exportScopes(db, user, request, url.searchParams, false, false);
  const report = await buildProfitLoss(db, scopes, period(url));
  return format === "csv"
    ? streamCsv(`profit-loss-${report.period.start}-${report.period.end}`, csvColumns, reportCsv(report))
    : Response.json(report, { headers });
}
