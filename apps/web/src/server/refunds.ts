import type { Db } from "mongodb";
import type { Row } from "./db";
import { HttpError, requireValue } from "./errors";
import { replay, saveReplay, writableDay } from "./financial";
import { businessDate, decimal, scaled } from "./money";
import { audit, dateOnly, insertRow, now, queryScope, requiredRow, transaction } from "./query";
import { allow, type Scope } from "./security";

const unresolved = ["pending", "partial", "not_processed_by_pos"];

function sumRefunds(refunds: Row[]) {
  return refunds.reduce((sum, row) => sum + scaled(row.amount), 0);
}

export async function refundRoutes(db: Db, scope: Scope, route: string, method: string, body: Row, url: URL, key: string | null) {
  const match = route.match(/^governance\/refunds\/(\d+)\/payments\/(\d+)$/);
  if (route === "governance/refunds" && method === "GET") {
    allow(scope.user, ["super_admin", "admin"]);
    const filter = await queryScope(db, scope, url);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    requireValue(Number.isSafeInteger(offset) && offset >= 0, "Invalid refund page.");
    const pageSize = 25;
    const showAll = url.searchParams.get("history") === "true";
    const reversals = await db.collection<Row>("financial_reversals").find({
      ...filter, reversal_type: "void",
      refund_status: { $in: showAll ? [...unresolved, "refunded", "resolved"] : unresolved },
    }).sort({ id: -1 }).skip(offset).limit(pageSize + 1).toArray();
    const invoiceIds = reversals.slice(0, pageSize).map((row) => row.invoice_id);
    const related = { ...filter, invoice_id: { $in: invoiceIds } };
    const [payments, refunds, legacyInvoices] = await Promise.all([
      db.collection<Row>("invoice_payments").find({ ...related, is_credit_marker: { $ne: true }, mode_type: { $ne: "credit" } }).sort({ id: 1 }).toArray(),
      db.collection<Row>("invoice_refunds").find(related).sort({ id: -1 }).toArray(),
      db.collection<Row>("invoices").find({ ...filter, id: { $in: invoiceIds } }).project({ id: 1, invoice_number: 1 }).toArray(),
    ]);
    return {
      has_more: reversals.length > pageSize,
      page_size: pageSize,
      items: reversals.slice(0, pageSize).map((row) => ({
        id: row.id,
        invoice_number: row.invoice_number ?? legacyInvoices.find((i) => i.id === row.invoice_id)?.invoice_number ?? String(row.invoice_id),
        deleted_at: row.created_at,
        legacy: !row.compensation_json?.invoice_deleted,
        payments: payments.filter((p) => p.invoice_id === row.invoice_id).map((p) => {
          const entries = refunds.filter((r) => r.payment_id === p.id);
          const refunded = sumRefunds(entries);
          return {
            id: p.id, mode: p.mode_name, cash: p.mode_type === "cash",
            received_date: businessDate(p.payment_datetime), amount: p.amount,
            remaining: p.receipt_corrected_at ? "0.00" : decimal(scaled(p.amount) - refunded),
            correction: p.receipt_correction_reason ?? null,
            refunds: entries.map((r) => ({
              id: r.id, amount: r.amount, date: r.refund_date, reference: r.reference_number,
            })),
          };
        }),
      })),
    };
  }
  if (!match || method !== "POST") return undefined;
  allow(scope.user, ["super_admin", "admin"]);
  requireValue(body.confirmed === true, "Confirm what actually happened to the payment.");
  const correction = body.action === "not_received";
  requireValue(correction || body.action === "refund", "Choose a refund or payment correction.");
  const recordedAt = now();
  const today = businessDate(recordedAt);
  return transaction(async (db, session) => {
    const state = await replay(db, scope, key, route, body, session);
    if (state.old) return state.old.result;
    const row = await requiredRow(db, "financial_reversals", {
      ...scope.filter, id: Number(match[1]), reversal_type: "void",
    }, session);
    const related = { company_id: row.company_id, branch_id: row.branch_id, invoice_id: row.invoice_id };
    const payment = await requiredRow(db, "invoice_payments", {
      ...related, id: Number(match[2]), is_credit_marker: { $ne: true }, mode_type: { $ne: "credit" },
    }, session);
    if (payment.receipt_corrected_at)
      throw new HttpError(409, "payment_resolved", "This payment was already corrected.");
    const receivedDate = businessDate(payment.payment_datetime);
    const day = correction ? receivedDate : dateOnly(body.refund_date);
    requireValue(day >= receivedDate && day <= today, "Use the actual refund date, between receipt of payment and today.");
    // This branch write serializes close, refunds, and simultaneous resolutions.
    await writableDay(db, scope, row.branch_id, session, day);
    const receipts = await db.collection<Row>("invoice_payments").find({
      ...related, is_credit_marker: { $ne: true }, mode_type: { $ne: "credit" },
    }, { session }).toArray();
    const refunds: Row[] = await db.collection<Row>("invoice_refunds").find(related, { session }).toArray();
    const refunded = sumRefunds(refunds.filter((entry) => entry.payment_id === payment.id));
    const remaining = scaled(payment.amount) - refunded;
    requireValue(remaining > 0, "This payment has no amount left to refund.");
    let auditDetails: Record<string, unknown>;
    if (correction) {
      const reason = typeof body.reason === "string" ? body.reason.trim() : "";
      requireValue(refunded === 0 && reason.length >= 3 && reason.length <= 250, "Explain why no payment was received. Any recorded refund must be reviewed separately.");
      await db.collection<Row>("invoice_payments").updateOne({ ...related, id: payment.id }, {
        $set: { receipt_corrected_at: recordedAt, receipt_correction_reason: reason, receipt_corrected_by: scope.user.id },
      }, { session });
      payment.receipt_corrected_at = recordedAt;
      auditDetails = { reason, amount: payment.amount, business_date: day };
    } else {
      const amount = scaled(body.amount);
      const reference = typeof body.reference_number === "string" ? body.reference_number.trim() : "";
      requireValue(amount > 0 && amount <= remaining, "Refund must be positive and no more than the remaining amount.");
      requireValue(reference.length <= 100 && (payment.mode_type === "cash" || reference), "Enter the actual refund transaction reference.");
      if (reference && await db.collection("invoice_refunds").findOne({
        company_id: row.company_id, mode_type: payment.mode_type, reference_number: reference,
      }, { session })) throw new HttpError(409, "duplicate_refund_reference", "This refund reference was already recorded.");
      const entry = await insertRow(db, "invoice_refunds", {
        ...related, reversal_id: row.id, payment_id: payment.id,
        amount: decimal(amount), refund_date: day, recorded_at: recordedAt,
        mode_name: payment.mode_name, mode_type: payment.mode_type, payment_mode_id: payment.payment_mode_id,
        reference_number: reference || null, actor_id: scope.user.id,
      }, session);
      refunds.push(entry);
      auditDetails = { refund_id: entry.id, amount: entry.amount, business_date: day };
    }
    const outstanding = receipts.reduce((sum, receipt) => {
      const current = receipt.id === payment.id ? payment : receipt;
      return sum + (current.receipt_corrected_at ? 0 : scaled(current.amount) -
        sumRefunds(refunds.filter((r) => r.payment_id === current.id)));
    }, 0);
    const refund_status = outstanding ? "partial" :
      (correction || receipts.some((p) => p.receipt_corrected_at) ? "resolved" : "refunded");
    await db.collection<Row>("financial_reversals").updateOne({ ...related, id: row.id },
      { $set: { refund_status, updated_at: recordedAt } }, { session });
    await audit(db, scope, correction ? "payment_not_received" : "record_refund", "invoice_payment",
      payment.id, { reversal_id: row.id, ...auditDetails }, session, { branchId: row.branch_id, reference: row.invoice_number });
    const result = { refund_status, remaining: decimal(outstanding) };
    await saveReplay(db, state, result, session);
    return result;
  });
}
