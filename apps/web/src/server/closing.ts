import { database, nextId, type Row } from "./db";
import { authorizedBranch } from "./billing";
import { allow, managers, type Scope } from "./security";
import { HttpError, requireValue, pending } from "./errors";
import { businessDate, decimal, scaled } from "./money";
export async function closing(
  scope: Scope,
  body: Row,
  id?: number,
  action?: string,
) {
  allow(scope.user, managers);
  const { db, client } = await database();
  const session = client.startSession();
  try {
    return await session.withTransaction(async () => {
      let record: Row | null = id
        ? await db
            .collection<Row>("business_day_closures")
            .findOne({ ...scope.filter, id }, { session })
        : null;
      if (id && !record)
        throw new HttpError(404, "not_found", "Closing unavailable.");
      const branch = await authorizedBranch(
        db,
        scope,
        record?.branch_id ?? body.branch_id,
        session,
      );
      await db
        .collection("branches")
        .updateOne(
          { id: branch.id },
          { $inc: { write_version: 1 } },
          { session },
        );
      if (!record) {
        requireValue(
          body.business_date === businessDate(),
          "Only the current business day may be opened.",
        );
        const opening = scaled(body.opening_cash);
        record = {
          id: await nextId(db, "business_day_closures", session),
          company_id: scope.company.id,
          branch_id: branch.id,
          business_date: body.business_date,
          opening_cash: decimal(opening),
          cash_collections: "0.00",
          cash_refunds: "0.00",
          cash_expenses: "0.00",
          expected_cash: decimal(opening),
          counted_cash: null,
          variance: null,
          non_cash_total: "0.00",
          status: "open",
          submitted_by: null,
          closed_by: null,
          reopened_by: null,
          reason: null,
          reopened_reason: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        await db
          .collection("business_day_closures")
          .insertOne(record, { session });
        return record;
      }
      if (action === "reopen")
        pending("Audited closed-day reopening and reconciliation");
      if (action === "submit") {
        requireValue(
          record.status === "open",
          "Only open days can be submitted.",
        );
        let cash = 0,
          nonCash = 0;
        const payments = await db
          .collection("invoice_payments")
          .find(
            { company_id: scope.company.id, branch_id: branch.id },
            { session },
          )
          .toArray();
        for (const payment of payments)
          if (
            businessDate(new Date(payment.payment_datetime)) ===
            record.business_date
          ) {
            if (payment.mode_type === "cash") cash += scaled(payment.amount);
            else nonCash += scaled(payment.amount);
          }
        const counted = scaled(body.counted_cash),
          expected = scaled(record.opening_cash) + cash;
        Object.assign(record, {
          cash_collections: decimal(cash),
          non_cash_total: decimal(nonCash),
          expected_cash: decimal(expected),
          counted_cash: decimal(counted),
          variance: decimal(counted - expected),
          status: "submitted",
          submitted_by: scope.user.id,
        });
      } else if (action === "close") {
        requireValue(
          record.status === "submitted",
          "Submit counted cash before closing.",
        );
        Object.assign(record, { status: "closed", closed_by: scope.user.id });
      } else
        throw new HttpError(
          405,
          "method_not_allowed",
          "Closing action unavailable.",
        );
      record.updated_at = new Date().toISOString();
      await db
        .collection("business_day_closures")
        .replaceOne({ id: record.id }, record, { session });
      return record;
    });
  } finally {
    await session.endSession();
  }
}
