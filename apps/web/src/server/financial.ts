import { finalizeCafeBill } from "./cafe-billing";
import { randomUUID } from "node:crypto";
import type { Db, ClientSession } from "mongodb";
import { type Row } from "./db";
import { type Scope, allow, sellers, managers, digest } from "./security";
import { checkout, quote, authorizedBranch, receipt } from "./billing";
import { requiredRow, transaction, insertRow, now, audit } from "./query";
import { postLedger, scopedCustomer } from "./ledger";
import { canonical, scaled, decimal, businessDate } from "./money";
import { HttpError, requireValue } from "./errors";
export async function writableDay(
  db: Db,
  scope: Scope,
  branchId: number,
  session: ClientSession,
  day = businessDate(),
) {
  await authorizedBranch(db, scope, branchId, session);
  await db
    .collection("branches")
    .updateOne(
      { id: branchId, company_id: scope.company.id },
      { $inc: { write_version: 1 } },
      { session },
    );
  if (
    await db
      .collection("business_day_closures")
      .findOne(
        {
          company_id: scope.company.id,
          branch_id: branchId,
          business_date: day,
          status: { $in: ["submitted", "closed"] },
        },
        { session },
      )
  )
    throw new HttpError(409, "day_closed", "Business day is closed.");
}
export async function replay(
  db: Db,
  scope: Scope,
  key: string | null,
  action: string,
  body: unknown,
  session: ClientSession,
) {
  requireValue(
    key && key.length >= 8 && key.length <= 150,
    "Idempotency-Key must contain 8–150 characters.",
  );
  const id = digest(`${scope.company.id}:${scope.user.id}:${action}:${key}`),
    hash = digest(canonical(body));
  const old = await db
    .collection("operation_keys")
    .findOne({ _id: id as never }, { session });
  if (old && old.hash !== hash)
    throw new HttpError(
      409,
      "idempotency_conflict",
      "Key belongs to another request.",
    );
  return { old, id, hash };
}
export async function saveReplay(
  db: Db,
  state: { id: string; hash: string },
  result: unknown,
  session: ClientSession,
) {
  await db
    .collection("operation_keys")
    .insertOne(
      { _id: state.id as never, hash: state.hash, result, created_at: now() },
      { session },
    );
}
export async function financial(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  key: string | null,
) {
  allow(scope.user, [...sellers, "analyst"]);
  if (route === "invoices" && method === "POST") {
    allow(scope.user, sellers);
    return transaction(async (db, session) => {
      const calculated = await quote(db, scope, body, false, session);
      const branch = await authorizedBranch(db, scope, body.branch_id, session);
      return insertRow(
        db,
        "invoices",
        {
          ...calculated,
          company_id: scope.company.id,
          invoice_number: `DRAFT-${randomUUID()}`,
          status: "draft",
          payment_status: "unpaid",
          branch_name: branch.name,
          invoice_date: body.invoice_date ?? now(),
          created_by: scope.user.id,
          created_by_name: scope.user.name,
          customer_name: null,
          payments: [],
          taxes: [],
          status_history: [],
          idempotency_key: `draft:${randomUUID()}`,
          source_type: "retail",
          draft_payload: body,
        },
        session,
      );
    });
  }
  const match = route.match(
    /^(?:invoices|cafe\/billing\/invoices)\/(\d+)\/(payments|issue|cancel)$/,
  );
  if (!match) return undefined;
  allow(scope.user, sellers);
  const id = Number(match[1]),
    action = match[2];
  requireValue(method === "POST", "Use POST for invoice actions.");
  if (action === "issue") {
    const draft = await requiredRow(db, "invoices", { ...scope.filter, id });
    const result = await checkout(
      scope,
      { ...draft.draft_payload, payments: body.payments ?? [] },
      key,
      false,
      id,
    );
    return result?.invoice;
  }
  return transaction(async (db, session) => {
    const invoice = await requiredRow(
      db,
      "invoices",
      { ...scope.filter, id },
      session,
    );
    if (action === "cancel") {
      requireValue(
        invoice.status === "draft",
        "Only a draft can be cancelled. Use audited void for an issued invoice.",
      );
      requireValue(
        String(body.reason ?? "").trim().length >= 3,
        "Cancellation reason required.",
      );
      await db
        .collection("invoices")
        .updateOne(
          { id, company_id: scope.company.id },
          {
            $set: {
              status: "cancelled",
              cancelled_at: now(),
              cancellation_reason: body.reason,
            },
          },
          { session },
        );
      await audit(
        db,
        scope,
        "cancel",
        "invoice",
        id,
        { reason: body.reason },
        session,
      );
      return { ...invoice, status: "cancelled" };
    }
    const state = await replay(db, scope, key, route, body, session);
    if (state.old) return state.old.result;
    requireValue(
      !["draft", "cancelled", "voided", "returned"].includes(invoice.status),
      "Invoice cannot accept payment.",
    );
    await writableDay(db, scope, invoice.branch_id, session);
    const input = route.startsWith("cafe/") ? (body.payment ?? body) : body;
    const amount = scaled(input.amount),
      due = scaled(invoice.balance_due);
    requireValue(
      amount > 0 && amount <= due,
      "Payment must be positive and cannot exceed the balance.",
    );
    const mode = await requiredRow(
      db,
      "payment_modes",
      {
        company_id: scope.company.id,
        id: Number(input.payment_mode_id),
        is_active: true,
      },
      session,
    );
    requireValue(mode.mode_type !== "credit", "Credit is not payment.");
    if (mode.requires_reference)
      requireValue(
        String(input.reference_number ?? "").trim(),
        "Payment reference required.",
      );
    const payment = await insertRow(
      db,
      "invoice_payments",
      {
        company_id: scope.company.id,
        branch_id: invoice.branch_id,
        invoice_id: id,
        payment_mode_id: mode.id,
        payment_mode_name: mode.name,
        mode_name: mode.name,
        mode_type: mode.mode_type,
        amount: decimal(amount),
        reference_number: input.reference_number ?? null,
        notes: input.notes ?? null,
        received_by: scope.user.id,
        received_by_name: scope.user.name,
        is_credit_marker: false,
        payment_datetime: now(),
      },
      session,
    );
    const remaining = due - amount,
      status = remaining ? "partial_paid" : "paid";
    const values = {
      balance_due: decimal(remaining),
      paid_amount: decimal(scaled(invoice.paid_amount) + amount),
      status,
      payment_status: status,
      payments: [...invoice.payments, payment],
      status_history: [
        ...(invoice.status_history ?? []),
        {
          id: (invoice.status_history?.length ?? 0) + 1,
          invoice_id: id,
          from_status: invoice.status,
          to_status: status,
          changed_by: scope.user.id,
          changed_by_name: scope.user.name,
          changed_at: now(),
          notes: "Payment collected.",
        },
      ],
      updated_at: now(),
    };
    await db
      .collection("invoices")
      .updateOne(
        { id, company_id: scope.company.id },
        { $set: values },
        { session },
      );
    if (invoice.customer_id)
      await postLedger(
        db,
        scope,
        await scopedCustomer(db, scope, invoice.customer_id, session),
        0,
        amount,
        "payment",
        "invoice_payment",
        payment.id,
        invoice.branch_id,
        session,
      );
    const updated: Row = { ...invoice, ...values };
    if (updated.source_type?.startsWith("cafe_"))
      await finalizeCafeBill(db, scope, updated, session);
    const result = route.startsWith("cafe/")
      ? {
          receipt: receipt(updated),
          closed: remaining === 0,
          idempotent_replay: false,
          table_session_status:
            invoice.source_type === "cafe_table_session"
              ? remaining
                ? "billed"
                : "closed"
              : null,
          order_status: remaining ? "billed" : "closed",
        }
      : updated;
    await saveReplay(db, state, result, session);
    return result;
  });
}
