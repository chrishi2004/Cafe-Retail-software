import type { Db } from "mongodb";
import type { Row } from "./db";
import type { Scope } from "./security";
import { queryScope, dateOnly } from "./query";
import { businessDate } from "./money";
import { requireValue } from "./errors";
export async function invoiceHistory(
  db: Db,
  scope: Scope,
  url: URL,
  cafe = false,
) {
  const filter = await queryScope(db, scope, url);
  if (cafe)
    filter.source_type = { $in: ["cafe_takeaway", "cafe_table_session"] };
  for (const key of ["status", "payment_status", "invoice_type"])
    if (url.searchParams.has(key)) filter[key] = url.searchParams.get(key);
  if (url.searchParams.has("customer_id"))
    filter.customer_id = Number(url.searchParams.get("customer_id"));
  const start = url.searchParams.get("start_date")
      ? dateOnly(url.searchParams.get("start_date"))
      : cafe
        ? businessDate()
        : null,
    end = url.searchParams.get("end_date")
      ? dateOnly(url.searchParams.get("end_date"))
      : cafe
        ? businessDate()
        : null;
  if (start && end)
    requireValue(start <= end, "Start date must precede end date.");
  const limit = Number(url.searchParams.get("limit") ?? 100),
    offset = Number(url.searchParams.get("offset") ?? 0);
  requireValue(
    Number.isInteger(limit) &&
      limit >= 1 &&
      limit <= 500 &&
      Number.isInteger(offset) &&
      offset >= 0,
    "Invalid history pagination.",
  );
  const search = (url.searchParams.get("search") ?? "").toLowerCase();
  const rows = (
    await db
      .collection<Row>("invoices")
      .find(filter)
      .sort({ invoice_date: -1, id: -1 })
      .toArray()
  ).filter((i) => {
    const day = businessDate(new Date(i.invoice_date));
    return (
      (!start || day >= start) &&
      (!end || day <= end) &&
      (!search ||
        `${i.invoice_number} ${i.customer_name ?? ""}`
          .toLowerCase()
          .includes(search))
    );
  });
  const page = rows.slice(offset, offset + limit);
  return cafe
    ? {
        items: page.map((i) => ({
          invoice_id: i.id,
          invoice_number: i.invoice_number,
          branch_id: i.branch_id,
          branch_name: i.branch_name,
          issued_at: i.issued_at,
          grand_total: i.grand_total,
          paid_amount: i.paid_amount,
          balance_due: i.balance_due,
          payment_status: i.payment_status,
          invoice_status: i.status,
          source_type: i.source_type,
          source_id: i.source_id,
        })),
        total: rows.length,
        limit,
        offset,
      }
    : page;
}
