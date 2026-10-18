import { replay, saveReplay } from "./financial";
import type { Db, ClientSession } from "mongodb";
import { type Row } from "./db";
import { type Scope, managers, allow } from "./security";
import { authorizedBranch } from "./billing";
import { decimal, scaled, multiply, businessDate } from "./money";
import { HttpError, requireValue } from "./errors";
import {
  transaction,
  requiredRow,
  insertRow,
  now,
  dateOnly,
  queryScope,
  audit,
} from "./query";
const open = [
  "draft",
  "pending_approval",
  "approved",
  "ordered",
  "partially_received",
];
export async function purchases(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
  key: string | null,
  context?: { db: Db; session: ClientSession },
) {
  allow(scope.user, [...managers, "analyst", "staff"]);
  const match = route.match(
    /^purchase-orders(?:\/(\d+)(?:\/(submit|approve|cancel|mark-ordered|receive))?)?$/,
  );
  if (!match) return undefined;
  const id = match[1] ? Number(match[1]) : undefined,
    action = match[2];
  if (method === "GET") {
    const filter = await queryScope(db, scope, url);
    if (id) return requiredRow(db, "purchase_orders", { ...filter, id });
    for (const field of ["supplier_id", "status"])
      if (url.searchParams.has(field))
        filter[field] = field.endsWith("_id")
          ? Number(url.searchParams.get(field))
          : url.searchParams.get(field);
    const rows = await db
      .collection<Row>("purchase_orders")
      .find(filter)
      .sort({ id: -1 })
      .toArray();
    const search = url.searchParams.get("search")?.toLowerCase();
    return rows
      .filter(
        (r) =>
          !search ||
          `${r.po_number} ${r.supplier_name}`.toLowerCase().includes(search),
      )
      .slice(0, Math.min(500, Number(url.searchParams.get("limit") ?? 100)));
  }
  allow(scope.user, managers);
  requireValue(
    (!id && method === "POST") ||
      (id && ((!action && method === "PUT") || (action && method === "POST"))),
    "Unsupported purchase operation.",
  );
  const work = async (db: Db, session: ClientSession) => {
    const state = key
      ? await replay(db, scope, key, route, body, session)
      : null;
    if (state?.old) return state.old.result as Row;
    let row: Row | null = id
      ? await requiredRow(
          db,
          "purchase_orders",
          { ...scope.filter, id },
          session,
        )
      : null;
    if (!row || !action) {
      if (row && row.status !== "draft")
        throw new HttpError(409, "invalid_state", "Only drafts can be edited.");
      const branch = await authorizedBranch(
        db,
        scope,
        body.branch_id ?? row?.branch_id,
        session,
      );
      const supplier = await requiredRow(
        db,
        "suppliers",
        {
          company_id: scope.company.id,
          id: Number(body.supplier_id ?? row?.supplier_id),
          is_active: true,
        },
        session,
      );
      requireValue(
        Array.isArray(body.items) &&
          body.items.length > 0 &&
          body.items.length <= 100,
        "Purchase requires 1–100 items.",
      );
      const seen = new Set(),
        items = [];
      let total = 0;
      for (const input of body.items) {
        const product = await requiredRow(
          db,
          "products",
          {
            company_id: scope.company.id,
            id: Number(input.product_id),
            is_active: true,
          },
          session,
        );
        requireValue(
          !seen.has(product.id) && product.supplier_id === supplier.id,
          "Items must be unique and belong to the selected supplier.",
        );
        seen.add(product.id);
        const quantity = scaled(input.quantity_ordered),
          cost = scaled(input.unit_cost ?? product.unit_cost);
        requireValue(quantity > 0, "Quantity must be positive.");
        const line = multiply(cost, quantity);
        total += line;
        items.push({
          id: items.length + 1,
          product_id: product.id,
          product_name: product.name,
          product_sku: product.sku,
          quantity_ordered: decimal(quantity),
          quantity_received: "0.00",
          remaining_quantity: decimal(quantity),
          unit_cost: decimal(cost),
          line_total: decimal(line),
        });
      }
      const values = {
        company_id: scope.company.id,
        branch_id: branch.id,
        branch_name: branch.name,
        supplier_id: supplier.id,
        supplier_name: supplier.name,
        order_date: dateOnly(
          body.order_date ?? row?.order_date ?? businessDate(),
        ),
        expected_delivery_date: body.expected_delivery_date
          ? dateOnly(body.expected_delivery_date)
          : null,
        items,
        item_count: items.length,
        total_amount: decimal(total),
        total_quantity_ordered: decimal(
          items.reduce((n, i) => n + scaled(i.quantity_ordered), 0),
        ),
        total_quantity_received: "0.00",
        updated_at: now(),
      };
      if (row) {
        await db
          .collection("purchase_orders")
          .updateOne(
            { id: row.id, company_id: scope.company.id },
            { $set: values },
            { session },
          );
        row = { ...row, ...values };
      } else {
        row = await insertRow(
          db,
          "purchase_orders",
          {
            ...values,
            status: "draft",
            version: 1,
            created_by: scope.user.id,
            created_by_name: scope.user.name,
            approved_by: null,
            approved_by_name: null,
            approved_at: null,
          },
          session,
        );
        row.po_number = `PO-${String(row.id).padStart(6, "0")}`;
        await db
          .collection("purchase_orders")
          .updateOne(
            { id: row.id },
            { $set: { po_number: row.po_number } },
            { session },
          );
      }
    } else {
      const transitions: Record<string, [string[], string]> = {
        submit: [["draft"], "pending_approval"],
        approve: [["pending_approval"], "approved"],
        "mark-ordered": [["approved"], "ordered"],
        cancel: [open, "cancelled"],
        receive: [["ordered", "partially_received"], "received"],
      };
      const transition = transitions[action];
      requireValue(transition, "Invalid action.");
      if (!transition[0].includes(row.status))
        throw new HttpError(
          409,
          "invalid_state",
          "Purchase order is not in the required state.",
        );
      if (
        action === "approve" ||
        (action === "cancel" &&
          !["draft", "pending_approval"].includes(row.status))
      )
        allow(scope.user, ["super_admin", "admin"]);
      const items = row.items as Row[];
      if (action === "receive") {
        requireValue(
          Array.isArray(body.items) &&
            body.items.length > 0 &&
            body.items.length <= items.length,
          "Select items to receive.",
        );
        const seen = new Set();
        for (const input of body.items) {
          requireValue(!seen.has(input.item_id), "Duplicate receiving line.");
          seen.add(input.item_id);
          const item = items.find((i) => i.id === Number(input.item_id));
          requireValue(item, "Purchase item unavailable.");
          const quantity = scaled(input.quantity_received);
          requireValue(
            quantity > 0 && quantity <= scaled(item.remaining_quantity),
            "Receipt exceeds remaining quantity.",
          );
          item.received_now = quantity;
          item.quantity_received = decimal(
            scaled(item.quantity_received) + quantity,
          );
          item.remaining_quantity = decimal(
            scaled(item.remaining_quantity) - quantity,
          );
        }
      }
      for (const item of items) {
        const quantity =
          action === "receive"
            ? (item.received_now ?? 0)
            : scaled(item.remaining_quantity);
        const ordered =
          action === "mark-ordered"
            ? quantity
            : action === "cancel" &&
                ["ordered", "partially_received"].includes(row.status)
              ? -quantity
              : action === "receive"
                ? -quantity
                : 0;
        if (!ordered && action !== "receive") continue;
        if (!quantity) continue;
        const filter = {
          company_id: scope.company.id,
          branch_id: row.branch_id,
          product_id: item.product_id,
        };
        let stock: Row | null = await db
          .collection<Row>("inventory")
          .findOne(filter, { session });
        if (!stock)
          stock = await insertRow(
            db,
            "inventory",
            { ...filter, quantity_scaled: 0, on_order_scaled: 0 },
            session,
          );
        requireValue(
          (stock.on_order_scaled ?? 0) + ordered >= 0,
          "On-order stock is inconsistent.",
        );
        await db
          .collection("inventory")
          .updateOne(
            filter,
            {
              $inc: {
                quantity_scaled: action === "receive" ? quantity : 0,
                on_order_scaled: ordered,
              },
              $set: { last_updated_at: now() },
            },
            { session },
          );
        if (action === "receive")
          await insertRow(
            db,
            "stock_movements",
            {
              ...filter,
              movement_type: "purchase_received",
              quantity_change: decimal(quantity),
              reason: "Purchase receipt",
              reference_type: "purchase_order",
              reference_id: row.id,
              created_by: scope.user.id,
              created_by_name: scope.user.name,
            },
            session,
          );
        delete item.received_now;
      }
      const status =
        action === "receive" &&
        items.some((i) => scaled(i.remaining_quantity) > 0)
          ? "partially_received"
          : transition[1];
      const values = {
        status,
        items,
        total_quantity_received: decimal(
          items.reduce((n, i) => n + scaled(i.quantity_received), 0),
        ),
        updated_at: now(),
        ...(action === "approve"
          ? {
              approved_by: scope.user.id,
              approved_by_name: scope.user.name,
              approved_at: now(),
            }
          : {}),
      };
      await db
        .collection("purchase_orders")
        .updateOne(
          { id: row.id, company_id: scope.company.id },
          { $set: values, $inc: { version: 1 } },
          { session },
        );
      row = { ...row, ...values, version: row.version + 1 };
    }
    await audit(
      db,
      scope,
      action ?? (id ? "update" : "create"),
      "purchase_order",
      row.id,
      {},
      session,
    );
    if (state) await saveReplay(db, state, row, session);
    return row;
  };
  return context ? work(context.db, context.session) : transaction(work);
}
