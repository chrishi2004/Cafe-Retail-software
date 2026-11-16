import { inBusinessRange } from "../businessDates";
import type { ClientSession, Db, Filter } from "mongodb";
import type { Row } from "./db";
import { decimal, scaled } from "./money";

export async function paymentActivity(
  db: Db,
  filter: Filter<Row>,
  start: string,
  end: string,
  { session, customerPayments = false }: { session?: ClientSession; customerPayments?: boolean } = {},
) {
  const invoiceReceipts = (await db.collection<Row>("invoice_payments").find({
    ...filter, is_credit_marker: { $ne: true }, mode_type: { $ne: "credit" }, receipt_corrected_at: null,
  }, { session }).toArray()).filter((p) => inBusinessRange(p.payment_datetime, start, end));
  const customerReceipts = customerPayments
    ? (await db.collection<Row>("customer_payments").find({
        ...filter, mode_type: { $ne: "credit" }, receipt_corrected_at: null,
      }, { session }).toArray()).filter((p) => inBusinessRange(p.payment_datetime, start, end))
    : [];
  // Old voids suppressed the receipt without recording a refund. Legacy
  // voided_at markers are audit evidence only, so receipts remain included.
  const refunds = await db.collection<Row>("invoice_refunds").find({
    ...filter, refund_date: { $gte: start, $lte: end },
  }, { session }).toArray();
  return { receipts: [...invoiceReceipts, ...customerReceipts], invoiceReceipts, customerReceipts, refunds };
}

export function paymentTotals(receipts: Row[], refunds: Row[]) {
  const total = (rows: Row[]) => rows.reduce((sum, row) => sum + scaled(row.amount), 0);
  const gross = total(receipts), refunded = total(refunds);
  return {
    gross_collections: decimal(gross),
    refunds: decimal(refunded),
    collections: decimal(gross - refunded),
  };
}

export function paymentBreakdown(rows: Row[]) {
  const totals = { cash: 0, upi: 0, card: 0, other_electronic: 0, other_non_cash: 0 };
  for (const row of rows) {
    const type: unknown = row.mode_type;
    if (type === "credit") continue;
    const key = type === "cash" || type === "upi" || type === "card" ? type :
      type === "bank_transfer" || type === "wallet" ? "other_electronic" : "other_non_cash";
    totals[key] += scaled(row.amount);
  }
  return totals;
}
