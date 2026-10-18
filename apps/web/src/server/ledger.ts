import type { Db, ClientSession } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, sellers } from "./security";
import { requiredRow, insertRow, transaction, now, queryScope } from "./query";
import { scaled, decimal } from "./money";
import { requireValue, HttpError } from "./errors";
import { authorizedBranch } from "./billing";
export async function scopedCustomer(
  db: Db,
  scope: Scope,
  id: unknown,
  session?: ClientSession,
) {
  const row = await requiredRow(
    db,
    "customers",
    {
      company_id: scope.company.id,
      id: Number(id),
      is_active: true,
      ...(scope.user.branch_id
        ? { $or: [{ branch_id: scope.user.branch_id }, { branch_id: null }] }
        : {}),
    },
    session,
  );
  return row;
}
export async function postLedger(
  db: Db,
  scope: Scope,
  customer: Row,
  debit: number,
  credit: number,
  type: string,
  referenceType: string,
  referenceId: number,
  branchId: number,
  session: ClientSession,
  reason?: string,
) {
  const current = await requiredRow(
    db,
    "customers",
    { id: customer.id, company_id: scope.company.id },
    session,
  );
  const balance =
    (current.outstanding_scaled ?? scaled(current.opening_balance ?? "0")) +
    debit -
    credit;
  await db
    .collection("customers")
    .updateOne(
      { id: current.id, company_id: scope.company.id },
      {
        $set: {
          outstanding_scaled: balance,
          outstanding_balance: decimal(balance),
          available_credit: decimal(
            scaled(current.credit_limit ?? "0") - balance,
          ),
          updated_at: now(),
        },
      },
      { session },
    );
  return insertRow(
    db,
    "customer_ledger",
    {
      company_id: scope.company.id,
      branch_id: branchId,
      customer_id: customer.id,
      entry_type: type,
      debit: decimal(debit),
      credit: decimal(credit),
      running_balance: decimal(balance),
      reference_type: referenceType,
      reference_id: referenceId,
      reason: reason ?? null,
      notes: null,
      created_by: scope.user.id,
      created_by_name: scope.user.name,
      entry_datetime: now(),
    },
    session,
  );
}
export async function customerRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  allow(scope.user, [...sellers, "analyst"]);
  if (route === "customer-ledger/outstanding" && method === "GET") {
    await queryScope(db, scope, url);
    const rows = await db
      .collection<Row>("customers")
      .find({
        company_id: scope.company.id,
        ...(scope.user.branch_id
          ? { $or: [{ branch_id: scope.user.branch_id }, { branch_id: null }] }
          : {}),
      })
      .toArray();
    return rows
      .filter(
        (c) =>
          !url.searchParams.has("branch_id") ||
          c.branch_id === Number(url.searchParams.get("branch_id")),
      )
      .map((c) => ({
        customer_id: c.id,
        customer_name: c.name,
        phone: c.phone ?? null,
        gstin: c.gstin ?? null,
        branch_id: c.branch_id ?? null,
        branch_name: c.branch_name ?? null,
        credit_limit: c.credit_limit ?? "0.00",
        outstanding_balance: decimal(
          c.outstanding_scaled ?? scaled(c.opening_balance ?? "0"),
        ),
        available_credit: decimal(
          scaled(c.credit_limit ?? "0") - (c.outstanding_scaled ?? 0),
        ),
        is_over_credit_limit:
          (c.outstanding_scaled ?? 0) > scaled(c.credit_limit ?? "0"),
        is_active: c.is_active,
      }))
      .filter(
        (c) =>
          url.searchParams.get("include_zero") === "true" ||
          c.outstanding_balance !== "0.00",
      );
  }
  const match = route.match(/^customers\/(\d+)\/(ledger|payments)$/);
  if (!match) return undefined;
  const customer = await scopedCustomer(db, scope, match[1]);
  if (match[2] === "ledger" && method === "GET") {
    const rows = await db
      .collection<Row>("customer_ledger")
      .find({ customer_id: customer.id, company_id: scope.company.id })
      .sort({ id: 1 })
      .toArray();
    let balance = scaled(customer.opening_balance ?? "0");
    const opening = balance
      ? [
          {
            id: 0,
            customer_id: customer.id,
            branch_id: customer.branch_id,
            entry_type: "opening_balance",
            debit: decimal(balance),
            credit: "0.00",
            running_balance: decimal(balance),
            entry_datetime: customer.created_at,
            created_at: customer.created_at,
            reference_type: "customer",
            reference_id: customer.id,
          },
        ]
      : [];
    return [
      ...opening,
      ...rows.map((row) => {
        balance += scaled(row.debit) - scaled(row.credit);
        return { ...row, running_balance: decimal(balance) };
      }),
    ];
  }
  if (match[2] === "payments" && method === "POST") {
    allow(scope.user, sellers);
    return transaction(async (db, session) => {
      const c = await scopedCustomer(db, scope, customer.id, session),
        branch = await authorizedBranch(
          db,
          scope,
          body.branch_id ?? c.branch_id,
          session,
        );
      const amount = scaled(body.amount);
      requireValue(amount > 0, "Payment must be positive.");
      const mode = await requiredRow(
        db,
        "payment_modes",
        {
          company_id: scope.company.id,
          id: Number(body.payment_mode_id),
          is_active: true,
        },
        session,
      );
      requireValue(mode.mode_type !== "credit", "Credit is not a collection.");
      if (mode.requires_reference)
        requireValue(
          String(body.reference_number ?? "").trim(),
          "Reference is required.",
        );
      const payment = await insertRow(
        db,
        "customer_payments",
        {
          company_id: scope.company.id,
          branch_id: branch.id,
          branch_name: branch.name,
          customer_id: c.id,
          payment_mode_id: mode.id,
          payment_mode_name: mode.name,
          mode_name: mode.name,
          mode_type: mode.mode_type,
          amount: decimal(amount),
          payment_datetime: now(),
          reference_number: body.reference_number ?? null,
          notes: body.notes ?? null,
          received_by: scope.user.id,
          received_by_name: scope.user.name,
        },
        session,
      );
      const entry = await postLedger(
        db,
        scope,
        c,
        0,
        amount,
        "payment",
        "customer_payment",
        payment.id,
        branch.id,
        session,
      );
      await db
        .collection("customer_payments")
        .updateOne(
          { id: payment.id },
          { $set: { ledger_entry_id: entry.id } },
          { session },
        );
      return {
        ...payment,
        ledger_entry_id: entry.id,
        outstanding_balance: entry.running_balance,
      };
    });
  }
  throw new HttpError(
    405,
    "method_not_allowed",
    "Customer operation unavailable.",
  );
}
