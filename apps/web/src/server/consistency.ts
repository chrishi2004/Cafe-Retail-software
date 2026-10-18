import { randomUUID } from "node:crypto";
import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, managers } from "./security";
import { transaction, insertRow, now, requiredRow } from "./query";
import { scaled, decimal } from "./money";
import { HttpError } from "./errors";
export async function consistency(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
) {
  if (!route.startsWith("sync/")) return undefined;
  allow(scope.user, [...managers, "analyst"]);
  const report = await db
    .collection("reconciliations")
    .findOne(scope.filter, { sort: { id: -1 } });
  if (["sync/status", "sync/continuity"].includes(route) && method === "GET")
    return {
      company_id: scope.company.id,
      branch_ids: scope.user.branch_id ? [scope.user.branch_id] : [],
      pending_inbox: 0,
      pending_outbox: 0,
      dead_letters: 0,
      oldest_pending_age_seconds: null,
      last_inbound_sync_at: null,
      last_outbound_sync_at: null,
      local_device_last_seen_at: null,
      continuity_mode:
        report?.status === "attention_required" ? "attention_required" : "live",
      fencing_epoch: 0,
      lease_expires_at: null,
      last_heartbeat_at: null,
      last_cloud_contact_at: now(),
      last_reconciled_at: report?.completed_at ?? null,
      last_queue_drain_at: null,
      reconciliation_status: report?.status ?? null,
      attention_message:
        "Hosted database connected. This web application requires internet; Local Hub synchronization is not used.",
      deployment_mode: "nextjs_atlas",
      local_hub_sync_enabled: false,
    };
  if (route === "sync/reconciliation" && method === "GET") {
    if (!report)
      throw new HttpError(
        404,
        "not_found",
        "No consistency check has been run.",
      );
    return report;
  }
  if (route === "sync/dead-letters" && method === "GET") return [];
  if (/^sync\/dead-letters\/\d+\/retry$/.test(route))
    throw new HttpError(
      410,
      "not_applicable",
      "Local Hub queues are not used by the hosted application.",
    );
  if (route === "sync/reconcile" && method === "POST") {
    allow(scope.user, managers);
    return transaction(async (db, session) => {
      const invoices = await db
          .collection<Row>("invoices")
          .find(scope.filter, { session })
          .toArray(),
        payments = await db
          .collection<Row>("invoice_payments")
          .find(scope.filter, { session })
          .toArray(),
        stock = await db
          .collection<Row>("inventory")
          .find(scope.filter, { session })
          .toArray(),
        orders = await db
          .collection<Row>("cafe_orders")
          .find(scope.filter, { session })
          .toArray();
      const invoiceIssues = [],
        paymentIssues = [],
        stockIssues = [],
        orderIssues = [];
      const ids = new Set(invoices.map((i) => i.id));
      for (const invoice of invoices) {
        if (["draft", "cancelled", "returned"].includes(invoice.status))
          continue;
        if (
          (invoice.items as Row[]).reduce(
            (n, i) => n + scaled(i.line_total),
            0,
          ) !== scaled(invoice.grand_total)
        )
          invoiceIssues.push(invoice.id);
        const paid = payments
          .filter((p) => p.invoice_id === invoice.id && !p.is_credit_marker)
          .reduce((n, p) => n + scaled(p.amount), 0);
        if (
          paid !== scaled(invoice.paid_amount) ||
          paid + scaled(invoice.balance_due) !== scaled(invoice.grand_total)
        )
          paymentIssues.push(invoice.id);
      }
      for (const payment of payments)
        if (!ids.has(payment.invoice_id))
          paymentIssues.push(payment.invoice_id);
      for (const row of stock)
        if (
          !Number.isSafeInteger(row.quantity_scaled) ||
          row.quantity_scaled < 0 ||
          Number(row.on_order_scaled ?? 0) < 0
        )
          stockIssues.push(row.id);
      for (const order of orders)
        if (order.billed_invoice_id && !ids.has(order.billed_invoice_id))
          orderIssues.push(order.id);
      const failed =
        invoiceIssues.length +
        paymentIssues.length +
        stockIssues.length +
        orderIssues.length;
      return insertRow(
        db,
        "reconciliations",
        {
          ...scope.filter,
          reconciliation_reference: randomUUID(),
          scope_key: `company:${scope.company.id}:branch:${scope.user.branch_id ?? "all"}`,
          fencing_epoch: 0,
          status: failed ? "attention_required" : "clean",
          pending_inbox_before: 0,
          pending_outbox_before: 0,
          pending_inbox_after: 0,
          pending_outbox_after: 0,
          order_mismatch_count: orderIssues.length,
          invoice_mismatch_count: invoiceIssues.length,
          payment_mismatch_count: paymentIssues.length,
          stock_mismatch_count: stockIssues.length,
          queue_receipt_mismatch_count: 0,
          closing_mismatch_count: 0,
          dead_letter_count: 0,
          details: {
            mode: "single_atlas_database",
            checked: {
              invoices: invoices.length,
              payments: payments.length,
              stock: stock.length,
              orders: orders.length,
            },
            invoice_issues: invoiceIssues,
            payment_issues: paymentIssues,
            stock_issues: stockIssues,
            order_issues: orderIssues,
            no_financial_data_modified: true,
            closing_check: "not_compared_to_a_second_database",
          },
          started_at: now(),
          completed_at: now(),
        },
        session,
      );
    });
  }
  return undefined;
}
