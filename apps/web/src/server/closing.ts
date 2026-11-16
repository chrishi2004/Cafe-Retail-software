import { paymentActivity, paymentBreakdown } from "./paymentActivity";
import { closingOutflows } from "./expenses";
import { requireStepUp } from "./accounts";
import { audit, csv, dateOnly, requiredRow, signed, transaction } from "./query";
import { nextId, type Row } from "./db";
import { authorizedBranch } from "./billing";
import { allow, digest, managers, type Scope } from "./security";
import { HttpError, requireValue } from "./errors";
import { businessDate, canonical, decimal, scaled } from "./money";
import type { ClientSession, Db } from "mongodb";

const locked = ["submitted", "closed"];
type Modes = ReturnType<typeof paymentBreakdown>;
const modeTotal = (modes: Modes) => modes.cash + modes.upi + modes.card + modes.other_electronic + modes.other_non_cash;
const modeAmounts = (m: Modes) => ({
  cash: decimal(m.cash), upi: decimal(m.upi), card: decimal(m.card), other_electronic: decimal(m.other_electronic),
  other_non_cash: decimal(m.other_non_cash),
});

async function calculateClosing(db: Db, scope: Scope, record: Row, session: ClientSession) {
  const day = record.business_date;
  const { invoiceReceipts, customerReceipts, refunds } = await paymentActivity(
    db, { company_id: scope.company.id, branch_id: record.branch_id }, day, day,
    { session, customerPayments: true },
  );
  const repayments = paymentBreakdown([
    ...customerReceipts, ...invoiceReceipts.filter((p) => p.collection_kind === "invoice_repayment"),
  ]);
  const sales = paymentBreakdown(invoiceReceipts.filter((p) => p.collection_kind !== "invoice_repayment"));
  const returned = paymentBreakdown(refunds);
  const { cashOperating, cashSupplier, nonCash } = await closingOutflows(db, scope, record.branch_id, day, session);
  const cashReceipts = sales.cash + repayments.cash;
  const outflows = cashOperating + cashSupplier;
  return {
    cash_collections: decimal(cashReceipts),
    cash_refunds: decimal(returned.cash),
    non_cash_refunds: decimal(modeTotal(returned) - returned.cash),
    cash_expenses: decimal(outflows),
    non_cash_expenses: decimal(nonCash),
    non_cash_total: decimal(modeTotal(sales) + modeTotal(repayments) - cashReceipts),
    expected_cash: decimal(scaled(record.opening_cash) + cashReceipts - returned.cash - outflows),
    breakdown: {
      sales: modeAmounts(sales),
      repayments: modeAmounts(repayments),
      refunds: modeAmounts(returned),
      cash_operating_expenses: decimal(cashOperating),
      cash_supplier_payments: decimal(cashSupplier),
    },
  };
}

function previewToken(record: Row, totals: Awaited<ReturnType<typeof calculateClosing>>) {
  return digest(canonical([record.company_id, record.branch_id, record.business_date, record.id, record.status, record.updated_at, totals]));
}

export async function readClosing(scope: Scope, url: URL) {
  allow(scope.user, managers);
  const branchId = Number(url.searchParams.get("branch_id"));
  requireValue(Number.isSafeInteger(branchId) && branchId > 0, "Choose a branch.");
  const day = dateOnly(url.searchParams.get("business_date"));
  const exporting = url.searchParams.get("format") === "csv";
  const preview = exporting || url.searchParams.get("preview") === "true";
  return transaction(async (db, session) => {
    if (scope.user.branch_id && scope.user.branch_id !== branchId)
      throw new HttpError(403, "forbidden", "Choose an authorized branch.");
    const branch = await requiredRow(db, "branches", { id: branchId, company_id: scope.company.id }, session);
    const record = await db.collection<Row>("business_day_closures").findOne(
      { ...scope.filter, branch_id: branch.id, business_date: day }, { session },
    );
    if (!record) {
      if (exporting) throw new HttpError(404, "not_found", "No closing was recorded for this date.");
      return null;
    }
    let view: Row = {
      ...record, branch_name: record.branch_name ?? branch.name, company_name: record.company_name ?? scope.company.name,
    };
    if (preview && !locked.includes(record.status)) {
      const totals = await calculateClosing(db, scope, record, session);
      view = { ...view, ...totals, counted_cash: null, variance: null, preview_token: previewToken(record, totals) };
    }
    const operators = ["opened_by", "submitted_by", "closed_by", "reopened_by"];
    const ids = [...new Set(operators.map((key) => view[key]).filter(Number.isSafeInteger))];
    const users = await db.collection<Row>("users").find(
      { business_group_id: scope.user.business_group_id, id: { $in: ids } },
      { session, projection: { id: 1, name: 1 } },
    ).toArray();
    for (const key of operators) view[key + "_name"] ??= users.find((u) => u.id === view[key])?.name ?? null;
    if (!exporting) return view;
    const row: Record<string, unknown> = {
      venture: view.company_name, branch: view.branch_name, business_date_ist: day,
      status: view.status, opening_cash: view.opening_cash,
      cash_sales: view.breakdown?.sales.cash ?? "",
      upi_sales: view.breakdown?.sales.upi ?? "",
      card_sales: view.breakdown?.sales.card ?? "",
      other_electronic_sales: view.breakdown?.sales.other_electronic ?? "",
      other_non_cash_sales: view.breakdown?.sales.other_non_cash ?? "",
      cash_credit_repayments: view.breakdown?.repayments.cash ?? "",
      upi_credit_repayments: view.breakdown?.repayments.upi ?? "",
      card_credit_repayments: view.breakdown?.repayments.card ?? "",
      other_electronic_credit_repayments: view.breakdown?.repayments.other_electronic ?? "",
      other_non_cash_credit_repayments: view.breakdown?.repayments.other_non_cash ?? "",
      total_cash_receipts: view.cash_collections, total_noncash_receipts: view.non_cash_total,
      cash_refunds: view.cash_refunds, noncash_refunds: view.non_cash_refunds ?? "",
      cash_operating_expenses: view.breakdown?.cash_operating_expenses ?? "",
      cash_supplier_payments: view.breakdown?.cash_supplier_payments ?? "",
      total_cash_outflows: view.cash_expenses, noncash_outflows: view.non_cash_expenses ?? "",
      expected_cash: view.expected_cash, counted_cash: view.counted_cash ?? "",
      cash_shortage_or_excess: view.variance ?? "",
      opened_by: view.opened_by_name ?? "", submitted_by: view.submitted_by_name ?? "",
      closed_by: view.closed_by_name ?? "", reopened_by: view.reopened_by_name ?? "",
    };
    return csv([row], `daily-closing-${branchId}-${day}`);
  });
}

export async function closing(scope: Scope, body: Row, id?: number, action?: string) {
  allow(scope.user, managers);
  return transaction(async (db, session) => {
    const col = db.collection<Row>("business_day_closures");
    let record = id === undefined ? null : await requiredRow(db, "business_day_closures", { ...scope.filter, id }, session);
    const branch = await authorizedBranch(db, scope, record?.branch_id ?? body.branch_id, session);
    const filter = { company_id: scope.company.id, branch_id: branch.id };
    const branchScope = { ...scope, filter };
    // All till writes serialize with this branch update. Preview is not a lock;
    // submit must recompute from its own snapshot after acquiring it.
    await db.collection("branches").updateOne(
      { id: branch.id, company_id: scope.company.id }, { $inc: { write_version: 1 } }, { session },
    );
    const at = new Date().toISOString();
    if (!record) {
      const day = dateOnly(body.business_date);
      requireValue(day === businessDate(at), "Only the current business day may be opened.");
      const opening = decimal(scaled(body.opening_cash));
      const existing = await col.findOne({ ...filter, business_date: day }, { session });
      if (existing) {
        if (existing.opening_cash !== opening)
          throw new HttpError(409, "day_exists", "The business day already has a different opening cash amount.");
        return existing;
      }
      record = {
        id: await nextId(db, "business_day_closures", session), ...filter,
        branch_name: branch.name, company_name: scope.company.name,
        business_date: day, opening_cash: opening, cash_collections: "0.00", cash_refunds: "0.00",
        non_cash_refunds: "0.00", cash_expenses: "0.00", non_cash_expenses: "0.00", non_cash_total: "0.00",
        expected_cash: opening, counted_cash: null, variance: null, status: "open",
        opened_by: scope.user.id, opened_by_name: scope.user.name, opened_at: at,
        submitted_by: null, closed_by: null, reopened_by: null, reason: null, reopened_reason: null,
        created_at: at, updated_at: at,
      };
      await col.insertOne(record, { session });
      await audit(db, branchScope, "open", "business_day_closure", record.id, { business_date: day, opening_cash: opening }, session);
      return record;
    }
    if (action === "reopen") {
      allow(scope.user, ["super_admin", "admin"]);
      requireStepUp(scope.user);
      requireValue(locked.includes(record.status), "Only submitted or closed days can reopen.");
      const reason = typeof body.reason === "string" ? body.reason.trim() : "";
      requireValue(reason.length >= 3 && reason.length <= 500, "Enter a reopening reason (3–500 characters).");
      const { _id, ...prior } = record;
      await audit(db, branchScope, "reopen", "business_day_closure", record.id,
        { reason, prior_snapshot: prior }, session);
      Object.assign(record, {
        status: "reopened", reopened_by: scope.user.id, reopened_by_name: scope.user.name,
        reopened_reason: reason, reopened_at: at,
      });
    } else if (action === "submit") {
      const counted = scaled(body.counted_cash);
      if (locked.includes(record.status) && record.counted_cash === decimal(counted)) return record;
      requireValue(["open", "reopened"].includes(record.status), "Only open days can be submitted.");
      const totals = await calculateClosing(db, scope, record, session);
      if (body.preview_token != null && body.preview_token !== previewToken(record, totals))
        throw new HttpError(409, "closing_preview_changed", "Payments or expenses changed. Refresh the preview and review your count before submitting.");
      Object.assign(record, {
        ...totals, counted_cash: decimal(counted), variance: decimal(counted - signed(totals.expected_cash)),
        status: "submitted", submitted_by: scope.user.id, submitted_by_name: scope.user.name, submitted_at: at,
        closed_by: null, closed_by_name: null, closed_at: null,
      });
      await audit(db, branchScope, "submit", "business_day_closure", record.id,
        { business_date: record.business_date, expected_cash: record.expected_cash, counted_cash: record.counted_cash, variance: record.variance }, session);
    } else if (action === "close") {
      if (record.status === "closed") return record;
      requireValue(record.status === "submitted", "Submit counted cash before closing.");
      Object.assign(record, { status: "closed", closed_by: scope.user.id, closed_by_name: scope.user.name, closed_at: at });
      await audit(db, branchScope, "close", "business_day_closure", record.id,
        { business_date: record.business_date }, session);
    } else throw new HttpError(405, "method_not_allowed", "Closing action unavailable.");
    record.updated_at = at;
    await col.replaceOne({ ...filter, id: record.id }, record, { session });
    return record;
  });
}
