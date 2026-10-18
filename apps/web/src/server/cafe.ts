import { randomUUID } from "node:crypto";
import type { Db, ClientSession } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, sellers, managers } from "./security";
import { authorizedBranch } from "./billing";
import {
  requiredRow,
  transaction,
  insertRow,
  now,
  queryScope,
  audit,
} from "./query";
import { scaled, decimal, businessDate } from "./money";
import { HttpError, requireValue } from "./errors";
import { writableDay } from "./financial";
export const eligible = ["accepted", "served", "bill_requested"];
export function cafeOnly(scope: Scope) {
  if (scope.company.business_type !== "cafe")
    throw new HttpError(403, "forbidden", "Cafe venture required.");
}
export function version(row: Row, expected: unknown) {
  if (Number(expected) !== row.version)
    throw new HttpError(
      409,
      "version_conflict",
      "This record changed. Refresh before retrying.",
    );
}
export async function createOrder(
  db: Db,
  scope: Scope,
  body: Row,
  session: ClientSession,
  source = "order_taker",
) {
  cafeOnly(scope);
  let tableSession: Row | null = null;
  if (body.table_session_public_id)
    tableSession = await requiredRow(
      db,
      "table_sessions",
      {
        ...scope.filter,
        public_id: body.table_session_public_id,
        status: "open",
      },
      session,
    );
  requireValue(
    ["dine_in", "takeaway", "counter"].includes(body.order_type),
    "Invalid order type.",
  );
  if (body.order_type === "dine_in")
    requireValue(tableSession, "Open a table session first.");
  const branch = await authorizedBranch(
    db,
    scope,
    tableSession?.branch_id ?? body.branch_id ?? scope.user.branch_id,
    session,
  );
  await writableDay(db, scope, branch.id, session);
  requireValue(
    Array.isArray(body.items) &&
      body.items.length > 0 &&
      body.items.length <= 25,
    "Order requires 1–25 items.",
  );
  requireValue(
    String(body.customer_notes ?? "").length <= 500,
    "Notes too long.",
  );
  const items = [];
  let total = 0;
  for (const input of body.items) {
    requireValue(
      input &&
        typeof input === "object" &&
        Object.keys(input).every((k) =>
          ["menu_item_public_id", "quantity", "notes"].includes(k),
        ),
      "Invalid order line.",
    );
    requireValue(
      Number.isInteger(input.quantity) &&
        input.quantity >= 1 &&
        input.quantity <= 20,
      "Quantity must be an integer from 1–20.",
    );
    requireValue(String(input.notes ?? "").length <= 300, "Notes too long.");
    const item = await requiredRow(
      db,
      "menu_items",
      {
        company_id: scope.company.id,
        public_id: String(input.menu_item_public_id),
        is_active: true,
        available: true,
        $or: [{ branch_id: branch.id }, { branch_id: null }],
      },
      session,
    );
    const value = scaled(item.selling_price) * input.quantity;
    total += value;
    items.push({
      id: items.length + 1,
      menu_item_public_id: item.public_id,
      menu_item_id: item.id,
      product_id: item.product_id ?? null,
      name: item.name,
      quantity: input.quantity,
      unit_price: item.selling_price,
      line_total: decimal(value),
      status: "placed",
      preparation_area: item.preparation_area ?? "none",
      notes: input.notes ?? null,
    });
  }
  const order = await insertRow(
    db,
    "cafe_orders",
    {
      company_id: scope.company.id,
      branch_id: branch.id,
      public_id: randomUUID(),
      table_session_public_id: tableSession?.public_id ?? null,
      table_id: tableSession?.table_id ?? null,
      table_code: tableSession?.table_code ?? null,
      order_type: body.order_type,
      source_channel: source,
      status: "placed",
      subtotal: decimal(total),
      discount_total: "0.00",
      estimated_total: decimal(total),
      items,
      customer_notes: body.customer_notes ?? null,
      created_by: source === "qr_customer" ? null : scope.user.id,
      accepted_by: null,
      version: 1,
      placed_at: now(),
      accepted_at: null,
      served_at: null,
      cancelled_at: null,
      billed_invoice_id: null,
    },
    session,
  );
  order.order_number = `ORD-${String(order.id).padStart(6, "0")}`;
  await db
    .collection("cafe_orders")
    .updateOne(
      { id: order.id },
      { $set: { order_number: order.order_number } },
      { session },
    );
  if (tableSession)
    await db
      .collection("table_sessions")
      .updateOne(
        { id: tableSession.id },
        { $inc: { version: 1 } },
        { session },
      );
  return order;
}
export async function requestSessionBill(
  db: Db,
  scope: Scope,
  row: Row,
  expected: unknown,
  session: ClientSession,
) {
  version(row, expected);
  requireValue(row.status === "open", "Session is not open.");
  const orders = await db
    .collection<Row>("cafe_orders")
    .find(
      {
        company_id: scope.company.id,
        table_session_public_id: row.public_id,
        status: { $nin: ["rejected", "cancelled", "closed", "billed"] },
      },
      { session },
    )
    .toArray();
  requireValue(
    orders.length > 0 && orders.every((o) => eligible.includes(o.status)),
    "Finish or reject all pending orders before requesting the bill.",
  );
  await db
    .collection("table_sessions")
    .updateOne(
      { id: row.id },
      {
        $set: { status: "bill_requested", bill_requested_at: now() },
        $inc: { version: 1 },
      },
      { session },
    );
  await db
    .collection("cafe_tables")
    .updateOne(
      { id: row.table_id, company_id: scope.company.id },
      { $set: { active_session_status: "bill_requested" } },
      { session },
    );
  await db
    .collection("cafe_orders")
    .updateMany(
      { id: { $in: orders.map((o) => o.id) }, company_id: scope.company.id },
      { $set: { status: "bill_requested" }, $inc: { version: 1 } },
      { session },
    );
  return {
    public_id: row.public_id,
    status: "bill_requested",
    bill_requested_at: now(),
    version: row.version + 1,
    affected_order_public_ids: orders.map((o) => o.public_id),
  };
}
export async function cafeRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  if (!route.startsWith("cafe/") || route.startsWith("cafe/billing/"))
    return undefined;
  cafeOnly(scope);
  const orderMatch = route.match(
    /^cafe\/orders(?:\/([^/]+)(?:\/(accept|reject|start-preparing|mark-ready|serve|request-bill|cancel))?)?$/,
  );
  if (orderMatch || route === "cafe/kitchen/orders") {
    const kitchen = route === "cafe/kitchen/orders";
    allow(scope.user, [...sellers, "kitchen"]);
    const publicId = orderMatch?.[1],
      action = orderMatch?.[2];
    if (method === "GET") {
      const filter = await queryScope(db, scope, url);
      if (publicId)
        return requiredRow(db, "cafe_orders", {
          ...filter,
          public_id: publicId,
        });
      if (kitchen) filter.status = { $in: ["accepted", "preparing", "ready"] };
      for (const [param, field] of [
        ["status", "status"],
        ["source", "source_channel"],
        ["table_id", "table_id"],
      ])
        if (url.searchParams.has(param))
          filter[field] = param.endsWith("_id")
            ? Number(url.searchParams.get(param))
            : url.searchParams.get(param);
      const rows = (
        await db
          .collection<Row>("cafe_orders")
          .find(filter)
          .sort({ id: kitchen ? 1 : -1 })
          .toArray()
      ).filter(
        (row) =>
          (!url.searchParams.has("business_date") ||
            businessDate(new Date(row.placed_at ?? row.created_at)) ===
              url.searchParams.get("business_date")) &&
          (url.searchParams.get("unbilled_only") !== "true" ||
            !row.billed_invoice_id) &&
          (url.searchParams.get("open_only") !== "true" ||
            !["cancelled", "rejected", "closed"].includes(row.status)) &&
          (!url.searchParams.has("preparation_area") ||
            row.items.some(
              (i: Row) =>
                i.preparation_area === url.searchParams.get("preparation_area"),
            )),
      );
      return kitchen
        ? rows.map((r) => ({
            public_id: r.public_id,
            order_number: r.order_number,
            table_reference: r.table_code,
            source_channel: r.source_channel,
            status: r.status,
            version: r.version,
            age_seconds: Math.max(
              0,
              Math.floor(
                (Date.now() - Date.parse(r.placed_at ?? r.created_at)) / 1000,
              ),
            ),
            items: r.items.filter(
              (i: Row) =>
                i.preparation_area !== "none" &&
                (!url.searchParams.has("preparation_area") ||
                  i.preparation_area ===
                    url.searchParams.get("preparation_area")),
            ),
          }))
        : rows;
    }
    if (method === "POST" && !publicId)
      return transaction((db, session) =>
        createOrder(
          db,
          scope,
          body,
          session,
          scope.user.role === "staff" ? "billing_counter" : "order_taker",
        ),
      );
    if (method === "POST" && action)
      return transaction(async (db, session) => {
        const row = await requiredRow(
          db,
          "cafe_orders",
          { ...scope.filter, public_id: publicId },
          session,
        );
        version(row, body.expected_version);
        const transitions: Record<string, [string[], string]> = {
          accept: [["placed"], "accepted"],
          reject: [["placed"], "rejected"],
          "start-preparing": [["accepted"], "preparing"],
          "mark-ready": [["preparing"], "ready"],
          serve: [["accepted", "ready"], "served"],
          "request-bill": [["accepted", "served"], "bill_requested"],
          cancel: [
            ["placed", "accepted", "preparing", "ready", "served"],
            "cancelled",
          ],
        };
        const transition = transitions[action];
        requireValue(
          transition[0].includes(row.status),
          "Order is not in the required state.",
        );
        if (["start-preparing", "mark-ready"].includes(action))
          allow(scope.user, [...managers, "kitchen"]);
        else allow(scope.user, sellers);
        if (["cancel", "reject"].includes(action))
          requireValue(
            String(body.reason ?? "").trim().length >= 3,
            "Reason required.",
          );
        if (action === "cancel" && row.status !== "placed")
          allow(scope.user, managers);
        requireValue(
          !row.billed_invoice_id,
          "Billed orders cannot be changed.",
        );
        const values = {
          status: transition[1],
          items: row.items.map((i: Row) => ({
            ...i,
            status:
              action === "accept"
                ? "accepted"
                : action === "serve"
                  ? "served"
                  : ["reject", "cancel"].includes(action)
                    ? transition[1]
                    : i.status,
          })),
          updated_at: now(),
          ...(action === "accept"
            ? { accepted_by: scope.user.id, accepted_at: now() }
            : {}),
          ...(action === "serve" ? { served_at: now() } : {}),
          ...(["cancel", "reject"].includes(action)
            ? { cancelled_at: now(), reason: body.reason }
            : {}),
        };
        await db
          .collection("cafe_orders")
          .updateOne(
            { id: row.id },
            { $set: values, $inc: { version: 1 } },
            { session },
          );
        await audit(
          db,
          scope,
          action,
          "cafe_order",
          row.id,
          { reason: body.reason ?? null },
          session,
        );
        return { ...row, ...values, version: row.version + 1 };
      });
  }
  const sessionMatch = route.match(
    /^cafe\/table-sessions(?:\/([^/]+)(?:\/(close|request-bill))?)?$/,
  );
  if (sessionMatch) {
    allow(scope.user, sellers);
    const publicId = sessionMatch[1],
      action = sessionMatch[2];
    if (method === "GET" && publicId)
      return requiredRow(db, "table_sessions", {
        ...scope.filter,
        public_id: publicId,
      });
    if (method === "POST" && !publicId)
      return transaction(async (db, session) => {
        const table = await requiredRow(
          db,
          "cafe_tables",
          { ...scope.filter, id: Number(body.table_id), is_active: true },
          session,
        );
        await writableDay(db, scope, table.branch_id, session);
        requireValue(
          !table.active_session_public_id,
          "Table already has an active session.",
        );
        const row = await insertRow(
          db,
          "table_sessions",
          {
            company_id: scope.company.id,
            branch_id: table.branch_id,
            table_id: table.id,
            table_code: table.table_code,
            public_id: randomUUID(),
            session_type: "dine_in",
            status: "open",
            opened_by: scope.user.id,
            opened_at: now(),
            closed_by: null,
            closed_at: null,
            bill_requested_at: null,
            version: 1,
          },
          session,
        );
        await db
          .collection("cafe_tables")
          .updateOne(
            { id: table.id },
            {
              $set: {
                active_session_public_id: row.public_id,
                active_session_status: "open",
              },
              $inc: { version: 1 },
            },
            { session },
          );
        return row;
      });
    if (method === "POST" && publicId)
      return transaction(async (db, session) => {
        const row = await requiredRow(
          db,
          "table_sessions",
          { ...scope.filter, public_id: publicId },
          session,
        );
        if (action === "request-bill")
          return requestSessionBill(
            db,
            scope,
            row,
            body.expected_version,
            session,
          );
        if (action === "close") {
          version(row, body.expected_version);
          requireValue(
            ["open", "bill_requested", "billed"].includes(row.status),
            "Session already closed.",
          );
          const orders = await db
            .collection<Row>("cafe_orders")
            .find(
              {
                company_id: scope.company.id,
                table_session_public_id: row.public_id,
                status: { $nin: ["cancelled", "rejected", "closed"] },
              },
              { session },
            )
            .toArray();
          requireValue(
            orders.length === 0,
            "Settle or cancel all orders before closing this session.",
          );
          const values = {
            status: body.cancel ? "cancelled" : "closed",
            closed_by: scope.user.id,
            closed_at: now(),
            updated_at: now(),
          };
          await db
            .collection("table_sessions")
            .updateOne(
              { id: row.id },
              { $set: values, $inc: { version: 1 } },
              { session },
            );
          await db
            .collection("cafe_tables")
            .updateOne(
              { id: row.table_id, company_id: scope.company.id },
              {
                $set: {
                  active_session_public_id: null,
                  active_session_status: null,
                },
                $inc: { version: 1 },
              },
              { session },
            );
          return { ...row, ...values, version: row.version + 1 };
        }
      });
  }
  const active = route.match(/^cafe\/tables\/(\d+)\/active-session$/);
  if (active && method === "GET") {
    const table = await requiredRow(db, "cafe_tables", {
      ...scope.filter,
      id: Number(active[1]),
    });
    return table.active_session_public_id
      ? requiredRow(db, "table_sessions", {
          ...scope.filter,
          public_id: table.active_session_public_id,
        })
      : null;
  }
  const availability = route.match(/^cafe\/menu\/items\/(\d+)\/availability$/);
  if (availability && method === "PATCH") {
    allow(scope.user, [...managers, "kitchen"]);
    requireValue(
      typeof body.available === "boolean",
      "Availability must be true or false.",
    );
    return transaction(async (db, session) => {
      const row = await requiredRow(
        db,
        "menu_items",
        {
          company_id: scope.company.id,
          id: Number(availability[1]),
          ...(scope.user.branch_id
            ? {
                $or: [{ branch_id: scope.user.branch_id }, { branch_id: null }],
              }
            : {}),
        },
        session,
      );
      if (body.expected_version != null) version(row, body.expected_version);
      await db
        .collection("menu_items")
        .updateOne(
          { id: row.id },
          {
            $set: { available: body.available, updated_at: now() },
            $inc: { version: 1 },
          },
          { session },
        );
      return { ...row, available: body.available, version: row.version + 1 };
    });
  }
  const deactivate = route.match(/^cafe\/tables\/(\d+)\/deactivate$/);
  if (deactivate && method === "POST") {
    allow(scope.user, managers);
    return transaction(async (db, session) => {
      const row = await requiredRow(
        db,
        "cafe_tables",
        { ...scope.filter, id: Number(deactivate[1]) },
        session,
      );
      requireValue(
        !row.active_session_public_id,
        "Close the active session first.",
      );
      await db
        .collection("cafe_tables")
        .updateOne(
          { id: row.id },
          {
            $set: { is_active: false, qr_active: false },
            $inc: { version: 1 },
          },
          { session },
        );
      await db
        .collection("qr_tokens")
        .updateMany(
          { company_id: scope.company.id, table_id: row.id },
          { $set: { revoked_at: now() } },
          { session },
        );
      return { ...row, is_active: false };
    });
  }
  return undefined;
}
