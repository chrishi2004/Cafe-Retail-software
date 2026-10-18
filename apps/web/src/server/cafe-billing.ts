import type { Db, ClientSession } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, sellers } from "./security";
import { requiredRow } from "./query";
import { eligible, cafeOnly, version } from "./cafe";
import { checkout, quote, receipt } from "./billing";
import { decimal, scaled } from "./money";
import { requireValue } from "./errors";
export type BillSource = {
  kind: "orders" | "table-sessions";
  publicId: string;
  expectedVersion?: number;
};
export async function loadCafeBill(
  db: Db,
  scope: Scope,
  source: BillSource,
  session?: ClientSession,
) {
  cafeOnly(scope);
  allow(scope.user, sellers);
  const table = source.kind === "table-sessions";
  const row = await requiredRow(
    db,
    table ? "table_sessions" : "cafe_orders",
    { ...scope.filter, public_id: source.publicId },
    session,
  );
  if (source.expectedVersion !== undefined)
    version(row, source.expectedVersion);
  requireValue(
    !["closed", "cancelled", "rejected", "billed"].includes(row.status),
    "Source cannot be billed.",
  );
  if (!table)
    requireValue(
      !row.table_session_public_id,
      "Bill a dine-in order through its table session.",
    );
  const orders = table
    ? await db
        .collection<Row>("cafe_orders")
        .find(
          {
            company_id: scope.company.id,
            table_session_public_id: row.public_id,
            status: { $nin: ["rejected", "cancelled"] },
          },
          { session },
        )
        .toArray()
    : [row];
  requireValue(
    orders.length > 0 &&
      orders.every(
        (order) => eligible.includes(order.status) && !order.billed_invoice_id,
      ),
    "Accept or finish all orders before billing.",
  );
  const snapshots: Row[] = orders.flatMap((order) =>
    (order.items as Row[]).map((item) => ({
      ...item,
      id: item.menu_item_id,
      public_id: item.menu_item_public_id,
      selling_price: item.unit_price,
      product_id: item.product_id,
      name: item.name,
      order_public_id: order.public_id,
      order_number: order.order_number,
      source_channel: order.source_channel,
      order_status: order.status,
      order_item_id: item.id,
    })),
  );
  const body: Row = {
    id: 0,
    branch_id: row.branch_id,
    items: snapshots.map((i) => ({
      menu_item_public_id: i.public_id,
      quantity: i.quantity,
      discount: "0",
    })),
  };
  const calculated = await quote(db, scope, body, true, session, snapshots);
  return {
    row,
    orders,
    snapshots,
    body,
    calculated,
    source_type: table ? "cafe_table_session" : "cafe_takeaway",
  };
}
export async function finalizeCafeBill(
  db: Db,
  scope: Scope,
  invoice: Row,
  session: ClientSession,
) {
  const closed = scaled(invoice.balance_due) === 0,
    status = closed ? "closed" : "billed";
  const filter =
    invoice.source_type === "cafe_table_session"
      ? { table_session_public_id: invoice.source_id }
      : { public_id: invoice.source_id };
  await db
    .collection("cafe_orders")
    .updateMany(
      {
        company_id: scope.company.id,
        ...filter,
        status: { $nin: ["cancelled", "rejected"] },
      },
      { $set: { status, billed_invoice_id: invoice.id }, $inc: { version: 1 } },
      { session },
    );
  if (invoice.source_type === "cafe_table_session") {
    const table = await requiredRow(
      db,
      "table_sessions",
      { company_id: scope.company.id, public_id: invoice.source_id },
      session,
    );
    await db
      .collection("table_sessions")
      .updateOne(
        { id: table.id },
        {
          $set: {
            status,
            billed_invoice_id: invoice.id,
            ...(closed
              ? {
                  closed_at: new Date().toISOString(),
                  closed_by: scope.user.id,
                }
              : {}),
          },
          $inc: { version: 1 },
        },
        { session },
      );
    await db
      .collection("cafe_tables")
      .updateOne(
        { id: table.table_id, company_id: scope.company.id },
        {
          $set: {
            active_session_public_id: closed ? null : table.public_id,
            active_session_status: closed ? null : "billed",
          },
          $inc: { version: 1 },
        },
        { session },
      );
  }
}
export async function cafeBillingRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  key: string | null,
) {
  const match = route.match(
    /^cafe\/billing\/(orders|table-sessions)\/([^/]+)\/(quote|bill)$/,
  );
  if (!match) return undefined;
  const source: BillSource = {
    kind: match[1] as BillSource["kind"],
    publicId: match[2],
  };
  if (match[3] === "quote" && method === "GET") {
    const data = await loadCafeBill(db, scope, source);
    return {
      ...data.calculated,
      source_type: data.source_type,
      source_id: source.publicId,
      source_version: data.row.version,
      table_session_public_id:
        source.kind === "table-sessions" ? source.publicId : null,
      table_session_status:
        source.kind === "table-sessions" ? data.row.status : null,
      eligible_items: data.snapshots.map((i, index) => ({
        order_public_id: i.order_public_id,
        order_number: i.order_number,
        source_channel: i.source_channel,
        order_status: i.order_status,
        order_item_id: i.order_item_id,
        menu_item_name: i.name,
        product_id: i.product_id,
        sku: data.calculated.items[index].sku,
        quantity: i.quantity,
        unit_price: i.unit_price,
        discount: "0.00",
        line_total: data.calculated.items[index].line_total,
        billed: false,
        excluded_reason: null,
      })),
      excluded_items: [],
    };
  }
  if (match[3] === "bill" && method === "POST") {
    source.expectedVersion = Number(body.expected_version);
    requireValue(
      Number.isSafeInteger(source.expectedVersion) &&
        source.expectedVersion > 0,
      "Expected source version required.",
    );
    const result = await checkout(scope, body, key, true, undefined, source);
    requireValue(result, "Billing did not complete.");
    return {
      receipt: receipt(result.invoice),
      closed: result.invoice.balance_due === "0.00",
      idempotent_replay: result.replay,
      table_session_status:
        source.kind === "table-sessions"
          ? result.invoice.balance_due === "0.00"
            ? "closed"
            : "billed"
          : null,
      order_status: result.invoice.balance_due === "0.00" ? "closed" : "billed",
    };
  }
  return undefined;
}
