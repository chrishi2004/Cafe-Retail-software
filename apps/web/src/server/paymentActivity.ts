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
  const receipts = (await db.collection<Row>("invoice_payments").find({
    ...filter, is_credit_marker: { $ne: true }, receipt_corrected_at: null,
  }, { session }).toArray()).filter((p) => inBusinessRange(p.payment_datetime, start, end));
  if (customerPayments)
    receipts.push(...(await db.collection<Row>("customer_payments").find(
      filter, { session },
    ).toArray()).filter((p) => inBusinessRange(p.payment_datetime, start, end)));
  // Old voids suppressed the receipt without recording a refund. Legacy
  // voided_at markers are audit evidence only, so receipts remain included.
  const refunds = await db.collection<Row>("invoice_refunds").find({
    ...filter, refund_date: { $gte: start, $lte: end },
  }, { session }).toArray();
  return { receipts, refunds };
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
