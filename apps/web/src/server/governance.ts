import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, managers, digest } from "./security";
import { requireStepUp } from "./accounts";
import { requiredRow, transaction, insertRow, now, audit } from "./query";
import { replay, saveReplay, writableDay } from "./financial";
import { requireValue, HttpError } from "./errors";
import { scaled, decimal, canonical } from "./money";
import { postLedger, scopedCustomer } from "./ledger";
export async function governance(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  key: string | null,
) {
  const voidMatch = route.match(/^governance\/voids\/invoices\/(\d+)$/);
  if (voidMatch && method === "POST") {
    allow(scope.user, managers);
    requireStepUp(scope.user);
    requireValue(
      String(body.reason ?? "").trim().length >= 3,
      "Void reason required.",
    );
    return transaction(async (db, session) => {
      const state = await replay(
        db,
        scope,
        key ?? body.idempotency_key,
        route,
        body,
        session,
      );
      if (state.old) return state.old.result;
      const invoice = await requiredRow(
        db,
        "invoices",
        { ...scope.filter, id: Number(voidMatch[1]) },
        session,
      );
      requireValue(
        !["draft", "cancelled", "returned"].includes(invoice.status),
        "Invoice cannot be voided.",
      );
      await writableDay(db, scope, invoice.branch_id, session);
      const reversal = await insertRow(
        db,
        "financial_reversals",
        {
          company_id: scope.company.id,
          branch_id: invoice.branch_id,
          invoice_id: invoice.id,
          reversal_type: "void",
          amount: invoice.grand_total,
          reason: body.reason,
          idempotency_key: key ?? body.idempotency_key,
          actor_id: scope.user.id,
          compensation_json: {
            payment_amount: invoice.paid_amount,
            stock_compensation_required: true,
          },
          refund_status:
            scaled(invoice.paid_amount) > 0
              ? "manual_refund_required"
              : "not_required",
        },
        session,
      );
      await db
        .collection("invoices")
        .updateOne(
          { id: invoice.id, company_id: scope.company.id },
          {
            $set: {
              status: "cancelled",
              cancelled_at: now(),
              cancellation_reason: body.reason,
              balance_due: "0.00",
            },
          },
          { session },
        );
      if (invoice.customer_id && scaled(invoice.balance_due) > 0)
        await postLedger(
          db,
          scope,
          await scopedCustomer(db, scope, invoice.customer_id, session),
          0,
          scaled(invoice.balance_due),
          "credit_note",
          "financial_reversal",
          reversal.id,
          invoice.branch_id,
          session,
          body.reason,
        );
      await audit(
        db,
        scope,
        "void",
        "invoice",
        invoice.id,
        { reason: body.reason, manual_compensation_required: true },
        session,
      );
      await saveReplay(db, state, reversal, session);
      return reversal;
    });
  }
  const purge = route.match(
    /^governance\/purges(?:\/(\d+)\/(approve|execute))?$/,
  );
  if (!purge || method !== "POST") return undefined;
  allow(scope.user, ["super_admin"]);
  requireValue(
    scope.company.is_demo === true,
    "Only demo-company records can be purged.",
  );
  return transaction(async (db, session) => {
    if (!purge[1]) {
      requireValue(
        body.entity_type === "demo_cafe_order",
        "Only demo_cafe_order is allowlisted.",
      );
      requireValue(
        String(body.reason ?? "").length >= 3 &&
          String(body.backup_reference ?? "").length >= 3,
        "Reason and verified backup reference required.",
      );
      const order = await requiredRow(
        db,
        "cafe_orders",
        { ...scope.filter, id: Number(body.entity_id) },
        session,
      );
      requireValue(
        !order.billed_invoice_id && !order.table_session_public_id,
        "Order has protected dependencies.",
      );
      return insertRow(
        db,
        "purge_requests",
        {
          company_id: scope.company.id,
          branch_id: order.branch_id,
          entity_type: body.entity_type,
          entity_id: order.id,
          reason: body.reason,
          backup_reference: body.backup_reference,
          status: "requested",
          dependency_report: {
            billed: false,
            has_table_session: false,
            order_items: order.items.length,
          },
          requested_by: scope.user.id,
          approved_by: null,
          second_approved_by: null,
          executed_at: null,
          failure_reason: null,
        },
        session,
      );
    }
    requireStepUp(scope.user);
    const row = await requiredRow(
      db,
      "purge_requests",
      { ...scope.filter, id: Number(purge[1]) },
      session,
    );
    if (purge[2] === "approve") {
      requireValue(
        row.status === "requested",
        "Request is not awaiting approval.",
      );
      requireValue(
        row.requested_by !== scope.user.id,
        "Requester cannot approve their own purge.",
      );
      const values = { status: "approved", approved_by: scope.user.id };
      await db
        .collection("purge_requests")
        .updateOne({ id: row.id }, { $set: values }, { session });
      return { ...row, ...values };
    }
    requireValue(
      row.status === "approved" && row.approved_by !== row.requested_by,
      "Independent approval required.",
    );
    requireValue(
      body.typed_confirmation === `PURGE-${row.id}`,
      "Typed confirmation does not match.",
    );
    const order = await requiredRow(
      db,
      "cafe_orders",
      { ...scope.filter, id: row.entity_id },
      session,
    );
    requireValue(
      !order.billed_invoice_id && !order.table_session_public_id,
      "Dependencies changed; purge refused.",
    );
    await insertRow(
      db,
      "record_tombstones",
      {
        company_id: scope.company.id,
        branch_id: order.branch_id,
        entity_type: row.entity_type,
        entity_id: order.id,
        before_hash: digest(canonical(order)),
        evidence_json: order,
        reason: row.reason,
        actor_id: scope.user.id,
      },
      session,
    );
    await db
      .collection("cafe_orders")
      .deleteOne({ id: order.id, company_id: scope.company.id }, { session });
    const values = { status: "completed", executed_at: now() };
    await db
      .collection("purge_requests")
      .updateOne({ id: row.id }, { $set: values }, { session });
    await audit(db, scope, "purge", "cafe_order", order.id, {}, session);
    return { ...row, ...values };
  });
}
