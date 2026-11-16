import type { ClientSession, Db, Filter } from "mongodb";
import { businessDate, inBusinessRange, shiftDate } from "../businessDates";
import type { Row } from "./db";
import { HttpError, requireValue } from "./errors";
import { decimal, scaled } from "./money";
import { receiptFilter, type ReceiptSource } from "./paymentActivity";
import { dateOnly, excludedSalesStatuses, invoiceInstant } from "./query";
import { allow, managers, scoped } from "./security";

const scopeColumns = "company_id,venture,branch_id,branch";
const layouts = {
  sales: `${scopeColumns},period_start_ist,period_end_ist,invoice_count,billed_revenue,retail_line_revenue,outstanding,gross_collections,refunds,net_collections`,
  consolidated: `${scopeColumns},period_start_ist,period_end_ist,invoice_count,billed_revenue,retail_line_revenue,outstanding,gross_collections,refunds,net_collections`,
  invoices: `${scopeColumns},invoice_id,invoice_number,business_date_ist,invoice_date,issued_at,invoice_status,payment_status,refund_status,reversal_id,invoice_type,grand_total,paid_amount,balance_due,operator_id`,
  payments: `${scopeColumns},payment_id,source,invoice_id,invoice_number,business_date_ist,payment_datetime,collection_kind,payment_status,mode_type,amount,counted_collection,corrected_at,operator_id,transaction_reference`,
  reversals: `${scopeColumns},event_type,event_id,invoice_id,invoice_number,payment_id,reversal_id,business_date_ist,timestamp,status,refund_status,mode_type,amount,actual_refund,operator_id,transaction_reference`,
  expenses: `${scopeColumns},expense_id,business_date_ist,created_at,status,category,description,vendor,payment_mode,amount,posted_amount,cash_outflow,source_type,source_id,operator_id,voided_at`,
  inventory: `${scopeColumns},inventory_id,product_id,sku,product_name,quantity_on_hand,reserved,on_order,last_updated_at,snapshot_date_ist`,
  movements: `${scopeColumns},movement_id,product_id,business_date_ist,created_at,movement_type,quantity_change,unit_cost,line_total,reference_type,reference_id,operator_id`,
  "stock-feeds": `${scopeColumns},stock_feed_id,business_date_ist,created_at,status,supplier_id,supplier_name,expense_id,payment_mode,total_amount,item_count,operator_id,transaction_reference`,
  purchases: `${scopeColumns},purchase_order_id,po_number,business_date_ist,created_at,status,supplier_id,supplier_name,total_amount,total_quantity_ordered,total_quantity_received,operator_id`,
  "supplier-payments": `${scopeColumns},expense_id,business_date_ist,created_at,status,vendor,payment_mode,amount,posted_paid_amount,cash_outflow,source_type,source_id,operator_id,transaction_reference`,
  closings: `${scopeColumns},closing_id,business_date_ist,status,opening_cash,cash_receipts,non_cash_receipts,cash_refunds,non_cash_refunds,cash_operating_expenses,cash_supplier_payments,cash_outflows,expected_cash,counted_cash,variance,opened_by,submitted_by,closed_by,reopened_by,opened_at,submitted_at,closed_at,reopened_at`,
  employees: `${scopeColumns},period_start_ist,period_end_ist,employee_id,invoice_count,billed_revenue,gross_collections,refunds,net_collections`,
} as const;
type Kind = keyof typeof layouts;
export type Range = { start: string; end: string };
export type ExportScope = { company: Row; branchId: number | null; branches: Map<number, string> };
export type SnapshotScope = ExportScope & { session: ClientSession };
type Cadence = "daily" | "weekly" | "monthly" | "period";
type CsvRow = Record<string, unknown>;

function queryId(value: string | null) {
  if (!value) return null;
  const id = Number(value);
  requireValue(/^\d+$/.test(value) && Number.isSafeInteger(id) && id > 0, "Invalid venture or branch identifier.");
  return id;
}

function getRange(params: URLSearchParams): Range {
  const today = businessDate();
  const month = today.slice(0, 8) + "01";
  const yesterday = shiftDate(today, -1);
  const lastMonthEnd = shiftDate(month, -1);
  const presets: Record<string, [string, string]> = {
    today: [today, today], yesterday: [yesterday, yesterday], this_month: [month, today],
    last_month: [lastMonthEnd.slice(0, 8) + "01", lastMonthEnd],
  };
  const preset = params.get("preset");
  if (preset && preset !== "custom") {
    requireValue(Object.hasOwn(presets, preset) && !params.has("start_date") && !params.has("end_date"), "Choose a date preset or a custom range.");
    const [start, end] = presets[preset];
    return { start, end };
  }
  const end = dateOnly(params.get("end_date") ?? today);
  const start = dateOnly(params.get("start_date") ?? shiftDate(end, -29));
  requireValue(start <= end, "Start date must precede end date.");
  return { start, end };
}

export async function exportScopes(db: Db, user: Row, request: Request, params: URLSearchParams, consolidated: boolean, respectVentureHeader = true) {
  allow(user, [...managers, "analyst"]);
  if (consolidated) allow(user, ["super_admin"]);
  const requestedCompany = queryId(params.get("company_id"));
  const requestedBranch = queryId(params.get("branch_id"));
  const header = respectVentureHeader ? queryId(request.headers.get("x-venture-id")) : null;
  let companies: Row[];
  if (user.role === "super_admin") {
    const id = requestedCompany ?? header;
    companies = await db.collection<Row>("companies").find({
      business_group_id: user.business_group_id,
      ...(id ? { id } : consolidated ? { is_active: true } : {}),
    }, { projection: { id: 1, business_type: 1, name: 1 } }).sort({ id: 1 }).toArray();
    if (id && !companies.length) throw new HttpError(403, "forbidden", "Venture is outside your access.");
  } else {
    const scope = await scoped(db, user, request);
    if (requestedCompany && requestedCompany !== scope.company.id) throw new HttpError(403, "forbidden", "Venture is outside your access.");
    companies = [scope.company];
  }
  if (user.branch_id && requestedBranch && requestedBranch !== user.branch_id)
    throw new HttpError(403, "forbidden", "Branch is outside your access.");
  const branchId = requestedBranch ?? user.branch_id ?? null;
  const branches = await db.collection<Row>("branches").find({ company_id: { $in: companies.map(c => c.id) } }, {
    projection: { id: 1, company_id: 1, name: 1 },
  }).toArray();
  const scopes: ExportScope[] = companies.filter(company => !branchId || branches.some(b => b.id === branchId && b.company_id === company.id))
    .map(company => ({ company, branchId, branches: new Map(branches.filter(b => b.company_id === company.id).map(b => [b.id, b.name])) }));
  if (branchId && !scopes.length) throw new HttpError(403, "forbidden", "Branch is outside your access.");
  return scopes;
}

const companyFilter = (scope: ExportScope) => ({ company_id: scope.company.id, ...(scope.branchId ? { branch_id: scope.branchId } : {}) });
const dimensions = (scope: ExportScope, branchId?: number | null) => ({
  company_id: scope.company.id, venture: scope.company.name, branch_id: branchId ?? null, branch: scope.branches.get(branchId ?? -1) ?? null,
});

function dateFields(field: string, range: Range, instant: boolean): Filter<Row> {
  if (!instant) return { [field]: { $gte: range.start, $lte: range.end } };
  // Widen the indexed string bounds one day for old timestamps with an explicit offset.
  // The same IST predicate as the dashboards then applies the exact business dates.
  return { $or: [
    { [field]: { $gte: shiftDate(range.start, -1), $lt: shiftDate(range.end, 2) } },
    { [field]: { $gte: invoiceInstant(range.start), $lt: invoiceInstant(shiftDate(range.end, 1)) } },
  ] };
}

export async function* scan(db: Db, scope: SnapshotScope, table: string, fields: string, options: {
  dates?: Range; field?: string; instant?: boolean; where?: Filter<Row>; sortField?: string;
} = {}) {
  const { dates, field, instant = false, where = {}, sortField = field } = options;
  const projection = Object.fromEntries(["id", "branch_id", ...fields.split(",")].map(key => [key, 1]));
  const filter: Filter<Row> = { ...companyFilter(scope), ...where, ...(dates && field ? dateFields(field, dates, instant) : {}) };
  const cursor = db.collection<Row>(table).find(filter, { projection, batchSize: 128, session: scope.session, allowDiskUse: true })
    .sort(sortField ? { [sortField]: 1, id: 1 } : { id: 1 });
  try {
    for await (const row of cursor) {
      if (dates && field && instant && !inBusinessRange(row[field], dates.start, dates.end)) continue;
      yield row;
    }
  } finally { await cursor.close(); }
}

export function day(value: unknown) {
  return (typeof value === "string" && inBusinessRange(value, null, null)) || (value instanceof Date && Number.isFinite(value.getTime()))
    ? businessDate(value as string | Date) : null;
}

function csvCell(value: unknown) {
  if (value === null || value === undefined) return '""';
  let text = value instanceof Date ? value.toISOString() : String(value);
  // Preserve real signed amounts; neutralize formulas even after spaces or invisible leading controls.
  if (!/^-?\d+(\.\d+)?$/.test(text) && (/^[\s\u0000-\u001f\ufeff]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text))) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

export function streamCsv(filename: string, columns: readonly string[], rows: AsyncGenerator<CsvRow>) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) { controller.enqueue(encoder.encode("\uFEFF" + columns.join(",") + "\r\n")); },
    async pull(controller) {
      let chunk = "";
      try {
        do {
          const next = await rows.next();
          if (next.done) {
            if (chunk) controller.enqueue(encoder.encode(chunk));
            controller.close();
            return;
          }
          chunk += columns.map(column => csvCell(next.value[column])).join(",") + "\r\n";
        } while (chunk.length < 48 * 1024);
        controller.enqueue(encoder.encode(chunk));
      } catch (error) {
        await rows.return(undefined);
        controller.error(error);
      }
    },
    async cancel() { await rows.return(undefined); },
  });
  return new Response(stream, { headers: {
    "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    "Content-Disposition": `attachment; filename="${filename}.csv"`,
  } });
}

export function linkedLookup(db: Db, scope: SnapshotScope, table: string, field: string, columns: string) {
  const projection = Object.fromEntries(columns.split(",").map(column => [column, 1]));
  const memo = new Map<string, Row | null>();
  return async (id: unknown, branchId: number) => {
    if (!Number.isSafeInteger(id) || id == null) return null;
    const key = branchId + ":" + id;
    if (memo.has(key)) return memo.get(key) ?? null;
    // Read product metadata at venture level, and financial links at both venture and branch.
    const found = await db.collection<Row>(table).findOne({
      company_id: scope.company.id, ...(table === "products" ? {} : { branch_id: branchId }), [field]: id,
    }, { projection, session: scope.session });
    if (memo.size >= 128) memo.delete(memo.keys().next().value!);
    memo.set(key, found);
    return found;
  };
}


type Totals = { invoices: number; billed: number; lines: number; due: number; gross: number; refunds: number };
const zero = (): Totals => ({ invoices: 0, billed: 0, lines: 0, due: 0, gross: 0, refunds: 0 });
const asMoney = (totals: Totals) => ({
  invoice_count: totals.invoices, billed_revenue: decimal(totals.billed), retail_line_revenue: decimal(totals.lines),
  outstanding: decimal(totals.due), gross_collections: decimal(totals.gross), refunds: decimal(totals.refunds),
  net_collections: decimal(totals.gross - totals.refunds),
});

function bucket(date: string, cadence: Cadence, range: Range): Range {
  if (cadence === "period") return range;
  if (cadence === "daily") return { start: date, end: date };
  if (cadence === "weekly") {
    const weekday = new Date(date).getUTCDay();
    const monday = shiftDate(date, -((weekday + 6) % 7));
    const sunday = shiftDate(monday, 6);
    return { start: monday < range.start ? range.start : monday, end: sunday > range.end ? range.end : sunday };
  }
  const month = date.slice(0, 8) + "01";
  const monthEnd = shiftDate(shiftDate(month, 32).slice(0, 8) + "01", -1);
  return { start: month < range.start ? range.start : month, end: monthEnd > range.end ? range.end : monthEnd };
}

const receiptSources: ReceiptSource[] = ["invoice_payments", "customer_payments"];
const receiptFields = "invoice_id,amount,payment_datetime,mode_type,is_credit_marker,receipt_corrected_at,received_by,created_by,collection_kind,reference_number";
function isReceipt(row: Row) { return row.is_credit_marker !== true && row.mode_type !== "credit" && !row.receipt_corrected_at; }
const reversalFields = "original_invoice_datetime,original_issued_at,original_invoice_type,original_operator_id,original_payment_status,original_balance_due,invoice_id,invoice_number,invoice_date,reversal_type,refund_status,amount,actor_id,created_at,compensation_json.invoice_deleted,compensation_json.payment_amount";
const refundFields = "refund_date,recorded_at,amount,actor_id,reversal_id,payment_id,invoice_id,mode_type,reference_number";

async function* financialSummary(db: Db, scope: SnapshotScope, range: Range, cadence: Cadence, employee: boolean) {
  const groups = new Map<string, { window: Range; employeeId: number | null; totals: Totals }>();
  const take = (date: string, operator?: number) => {
    const window = bucket(date, cadence, range);
    const employeeId = employee && Number.isSafeInteger(operator) ? operator! : null;
    const key = window.start + ":" + (employeeId ?? "");
    const existing = groups.get(key);
    if (existing) return existing.totals;
    const totals = zero();
    groups.set(key, { window, employeeId, totals });
    return totals;
  };
  if (cadence === "period" && !employee) take(range.start);
  for await (const row of scan(db, scope, "invoices", "invoice_date,grand_total,balance_due,items.line_total,created_by", {
    dates: range, field: "invoice_date", instant: true, where: { status: { $nin: excludedSalesStatuses } },
  })) {
    const totals = take(day(row.invoice_date)!, row.created_by);
    totals.invoices++;
    totals.billed += scaled(row.grand_total ?? "0");
    totals.due += scaled(row.balance_due ?? "0");
    if (scope.company.business_type === "retail")
      for (const line of row.items ?? []) totals.lines += scaled(line.line_total ?? "0");
  }
  for (const table of receiptSources) {
    for await (const row of scan(db, scope, table, receiptFields, {
      dates: range, field: "payment_datetime", instant: true, where: receiptFilter(table),
    })) take(day(row.payment_datetime)!, row.received_by ?? row.created_by).gross += scaled(row.amount);
  }
  for await (const row of scan(db, scope, "invoice_refunds", refundFields, { dates: range, field: "refund_date" }))
    take(row.refund_date, row.actor_id).refunds += scaled(row.amount);
  for (const { window, employeeId, totals } of [...groups.values()].sort((a, b) => a.window.start.localeCompare(b.window.start) || (a.employeeId ?? 0) - (b.employeeId ?? 0))) {
    yield { ...dimensions(scope, scope.branchId), period_start_ist: window.start, period_end_ist: window.end, employee_id: employeeId, ...asMoney(totals) };
  }
}

async function* financialDetail(db: Db, scope: SnapshotScope, range: Range, kind: "invoices" | "payments" | "reversals") {
  const lookupInvoice = linkedLookup(db, scope, "invoices", "id", "invoice_number");
  const lookupReversal = linkedLookup(db, scope, "financial_reversals", "invoice_id", "invoice_number");
  const invoiceNumber = async (row: Row) =>
    (await lookupInvoice(row.invoice_id, row.branch_id))?.invoice_number ?? (await lookupReversal(row.invoice_id, row.branch_id))?.invoice_number;
  if (kind === "invoices" || kind === "reversals") {
    const fields = "invoice_number,invoice_date,issued_at,status,payment_status,refund_status,invoice_type,grand_total,paid_amount,balance_due,created_by,cancelled_at,voided_at";
    if (kind === "invoices") {
      for await (const row of scan(db, scope, "invoices", fields, { dates: range, field: "invoice_date", instant: true })) {
        yield { ...dimensions(scope, row.branch_id), ...row, invoice_id: row.id, invoice_status: row.status, business_date_ist: day(row.invoice_date), operator_id: row.created_by };
      }
    } else {
      // Some older invoices retain their cancelled/voided status with no independent reversal.
      for await (const row of scan(db, scope, "invoices", fields, { where: { status: { $in: ["cancelled", "voided", "returned"] } } })) {
        const timestamp = row.voided_at ?? row.cancelled_at ?? null;
        if (!inBusinessRange(timestamp ?? row.invoice_date, range.start, range.end)) continue;
        if (await lookupReversal(row.id, row.branch_id)) continue;
        yield {
          ...dimensions(scope, row.branch_id), event_type: "invoice_status", event_id: row.id, invoice_id: row.id, invoice_number: row.invoice_number,
          business_date_ist: day(timestamp ?? row.invoice_date), timestamp, status: row.status, refund_status: row.refund_status, amount: row.grand_total, actual_refund: "0.00",
        };
      }
    }
    for await (const row of scan(db, scope, "financial_reversals", reversalFields, {
      dates: range, field: kind === "invoices" ? "invoice_date" : "created_at", instant: kind === "reversals",
      where: kind === "invoices" ? { "compensation_json.invoice_deleted": true } : {},
    })) {
      const base = { ...dimensions(scope, row.branch_id), invoice_id: row.invoice_id, invoice_number: row.invoice_number, reversal_id: row.id, refund_status: row.refund_status };
      if (kind === "invoices") yield { ...base, business_date_ist: row.invoice_date, invoice_status: "voided",
        invoice_date: row.original_invoice_datetime, issued_at: row.original_issued_at, invoice_type: row.original_invoice_type,
        operator_id: row.original_operator_id, payment_status: row.original_payment_status, balance_due: row.original_balance_due,
        grand_total: row.amount, paid_amount: row.compensation_json?.payment_amount };
      else yield { ...base, event_type: "invoice_reversal", event_id: row.id, business_date_ist: day(row.created_at), timestamp: row.created_at,
        status: row.reversal_type === "void" ? "voided" : row.reversal_type, amount: row.amount, actual_refund: "0.00", operator_id: row.actor_id };
    }
  }
  if (kind === "payments") {
    for (const table of receiptSources)
      for await (const row of scan(db, scope, table, receiptFields, { dates: range, field: "payment_datetime", instant: true })) {
        const counted = isReceipt(row);
        yield { ...dimensions(scope, row.branch_id), ...row, payment_id: row.id, source: table,
          invoice_number: await invoiceNumber(row), business_date_ist: day(row.payment_datetime),
          payment_status: row.receipt_corrected_at ? "not_received" : counted ? "received" : "credit",
          counted_collection: counted ? row.amount : "0.00", corrected_at: row.receipt_corrected_at,
          operator_id: row.received_by ?? row.created_by, transaction_reference: row.reference_number };
      }
  }
  if (kind === "reversals") {
    for await (const row of scan(db, scope, "invoice_refunds", refundFields, { dates: range, field: "refund_date" }))
      yield { ...dimensions(scope, row.branch_id), ...row, invoice_number: await invoiceNumber(row),
        event_type: "refund", event_id: row.id, status: "refunded", business_date_ist: row.refund_date,
        timestamp: row.recorded_at, actual_refund: row.amount, operator_id: row.actor_id, transaction_reference: row.reference_number };
    for await (const row of scan(db, scope, "invoice_payments", receiptFields + ",receipt_corrected_by", {
      dates: range, field: "receipt_corrected_at", instant: true,
    })) yield { ...dimensions(scope, row.branch_id), ...row, invoice_number: await invoiceNumber(row),
      event_type: "payment_correction", event_id: row.id, payment_id: row.id, status: "not_received",
      business_date_ist: day(row.receipt_corrected_at), timestamp: row.receipt_corrected_at, actual_refund: "0.00", operator_id: row.receipt_corrected_by };
  }
}

async function* operationalDetail(db: Db, scope: SnapshotScope, range: Range, kind: Exclude<Kind, "sales" | "consolidated" | "employees" | "invoices" | "payments" | "reversals">) {
  if (kind === "inventory") {
    const product = linkedLookup(db, scope, "products", "id", "sku,name");
    const snapshot = range.start;
    for await (const row of scan(db, scope, "inventory", "product_id,quantity_scaled,reserved_scaled,on_order_scaled,last_updated_at")) {
      const item = await product(row.product_id, row.branch_id);
      yield {
        ...dimensions(scope, row.branch_id), inventory_id: row.id, product_id: row.product_id, sku: item?.sku, product_name: item?.name,
        quantity_on_hand: decimal(row.quantity_scaled ?? 0), reserved: decimal(row.reserved_scaled ?? 0),
        on_order: decimal(row.on_order_scaled ?? 0), last_updated_at: row.last_updated_at, snapshot_date_ist: snapshot,
      };
    }
  } else if (kind === "expenses" || kind === "supplier-payments") {
    for await (const row of scan(db, scope, "expenses",
      "expense_date,created_at,status,category,description,payment_mode,amount,source_type,source_id,created_by,voided_at,vendor_name,reference_number", {
        dates: range, field: "expense_date", where: kind === "supplier-payments" ? { category: "stock_purchase" } : {},
      })) {
      const paid = row.status === "posted" && row.payment_mode !== "credit";
      yield { ...dimensions(scope, row.branch_id), ...row, expense_id: row.id, business_date_ist: row.expense_date,
        posted_amount: row.status === "posted" ? row.amount : "0.00", posted_paid_amount: paid ? row.amount : "0.00",
        cash_outflow: paid && row.payment_mode === "cash" ? row.amount : "0.00", operator_id: row.created_by,
        vendor: row.vendor_name, transaction_reference: row.reference_number };
    }
  } else if (kind === "movements") {
    for await (const row of scan(db, scope, "stock_movements",
      "created_at,product_id,movement_type,quantity_change,unit_cost,line_total,reference_type,reference_id,created_by", {
        dates: range, field: "created_at", instant: true,
      })) yield { ...dimensions(scope, row.branch_id), ...row, movement_id: row.id, business_date_ist: day(row.created_at), operator_id: row.created_by };
  } else if (kind === "stock-feeds") {
    for await (const row of scan(db, scope, "stock_intakes",
      "purchase_date,created_at,status,supplier_id,supplier_name,expense_id,payment_mode,total_amount,item_count,created_by,reference_number", {
        dates: range, field: "purchase_date",
      })) yield { ...dimensions(scope, row.branch_id), ...row, stock_feed_id: row.id, business_date_ist: row.purchase_date,
        operator_id: row.created_by, transaction_reference: row.reference_number };
  } else if (kind === "purchases") {
    for await (const row of scan(db, scope, "purchase_orders",
      "order_date,created_at,po_number,status,supplier_id,supplier_name,total_amount,total_quantity_ordered,total_quantity_received,created_by", {
        dates: range, field: "order_date", instant: true,
      })) yield { ...dimensions(scope, row.branch_id), ...row, purchase_order_id: row.id, business_date_ist: day(row.order_date), operator_id: row.created_by };
  } else {
    const fields = "business_date,status,opening_cash,cash_collections,non_cash_total,cash_refunds,non_cash_refunds,cash_expenses,expected_cash,counted_cash,variance,opened_by,submitted_by,closed_by,reopened_by,opened_at,submitted_at,closed_at,reopened_at,breakdown.cash_operating_expenses,breakdown.cash_supplier_payments";
    for await (const row of scan(db, scope, "business_day_closures", fields, { dates: range, field: "business_date" })) {
      // A reopened or merely open register is not a historical counted-cash snapshot.
      const locked = ["submitted", "closed"].includes(row.status);
      yield { ...dimensions(scope, row.branch_id), ...row, closing_id: row.id, business_date_ist: row.business_date,
        cash_receipts: locked ? row.cash_collections : null, non_cash_receipts: locked ? row.non_cash_total : null,
        cash_refunds: locked ? row.cash_refunds : null, non_cash_refunds: locked ? row.non_cash_refunds : null,
        cash_operating_expenses: locked ? row.breakdown?.cash_operating_expenses : null,
        cash_supplier_payments: locked ? row.breakdown?.cash_supplier_payments : null,
        cash_outflows: locked ? row.cash_expenses : null, expected_cash: locked ? row.expected_cash : null,
        counted_cash: locked ? row.counted_cash : null, variance: locked ? row.variance : null };
    }
  }
}

async function* exportRows(db: Db, scopes: ExportScope[], range: Range, kind: Kind, cadence: Cadence) {
  // A read snapshot keeps each export internally consistent if tills take payments while it runs.
  const session = db.client.startSession({ snapshot: true });
  try {
    for (const selection of scopes) {
      const scope = { ...selection, session };
      if (kind === "sales" || kind === "consolidated" || kind === "employees")
        yield* financialSummary(db, scope, range, cadence, kind === "employees");
      else if (kind === "invoices" || kind === "payments" || kind === "reversals") yield* financialDetail(db, scope, range, kind);
      else yield* operationalDetail(db, scope, range, kind);
    }
  } finally { await session.endSession(); }
}

export async function historicalExports(db: Db, user: Row, request: Request, route: string, url: URL) {
  const kind = route.slice("exports/history/".length) as Kind;
  if (!Object.hasOwn(layouts, kind)) throw new HttpError(404, "not_found", "Historical report unavailable.");
  if (request.method !== "GET") throw new HttpError(405, "method_not_allowed", "Historical exports are read-only.");
  const range = getRange(url.searchParams);
  const cadence = (url.searchParams.get("cadence") ?? (kind === "sales" ? "daily" : "period")) as Cadence;
  requireValue(["daily", "weekly", "monthly", "period"].includes(cadence), "Invalid reporting interval.");
  const scopes = await exportScopes(db, user, request, url.searchParams, kind === "consolidated");
  const effectiveRange = kind === "inventory" ? { start: businessDate(), end: businessDate() } : range;
  return streamCsv(`${kind}-${effectiveRange.start}-${effectiveRange.end}`, layouts[kind].split(","), exportRows(db, scopes, effectiveRange, kind, kind === "employees" ? "period" : cadence));
}
