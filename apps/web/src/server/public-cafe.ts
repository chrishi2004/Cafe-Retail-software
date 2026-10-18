import { randomBytes, randomUUID } from "node:crypto";
import type { Db } from "mongodb";
import { type Row } from "./db";
import { type Scope, digest, allow, managers } from "./security";
import { requiredRow, transaction, insertRow, now } from "./query";
import { HttpError, requireValue } from "./errors";
import { cafeOnly, createOrder, requestSessionBill } from "./cafe";
import { replay, saveReplay } from "./financial";
const publicOrder = (row: Row) => ({
  public_id: row.public_id,
  order_number: row.order_number,
  status: row.status,
  subtotal: row.subtotal,
  discount_total: row.discount_total,
  estimated_total: row.estimated_total,
  customer_notes: row.customer_notes,
  placed_at: row.placed_at,
  created_at: row.created_at,
  items: row.items.map((i: Row) => ({
    menu_item_public_id: i.menu_item_public_id,
    name: i.name,
    quantity: i.quantity,
    unit_price: i.unit_price,
    line_total: i.line_total,
    status: i.status,
    notes: i.notes,
  })),
  replayed: false,
});
async function resolve(db: Db, token: string) {
  requireValue(token.length >= 20 && token.length <= 1000, "Invalid QR token.");
  const qr = await requiredRow(db, "qr_tokens", {
    token_hash: digest(token),
    revoked_at: null,
  });
  if (Date.parse(qr.expires_at) <= Date.now())
    throw new HttpError(404, "not_found", "QR link expired.");
  const table = await requiredRow(db, "cafe_tables", {
    id: qr.table_id,
    company_id: qr.company_id,
    is_active: true,
    qr_active: true,
  });
  const company = await requiredRow(db, "companies", {
    id: table.company_id,
    is_active: true,
    business_type: "cafe",
  });
  await requiredRow(db, "business_groups", {
    id: company.business_group_id,
    is_active: true,
  });
  const session = await requiredRow(db, "table_sessions", {
    company_id: company.id,
    public_id: table.active_session_public_id,
    status: { $in: ["open", "bill_requested", "billed"] },
  });
  await db
    .collection("qr_tokens")
    .updateOne({ id: qr.id }, { $set: { last_used_at: now() } });
  return { qr, table, company, session };
}
async function guest(db: Db, publicId: string, request: Request) {
  const key = request.headers.get("x-guest-access") ?? "";
  const access = await requiredRow(db, "guest_access", {
    key_hash: digest(key),
    session_public_id: publicId,
  });
  if (Date.parse(access.expires_at) <= Date.now())
    throw new HttpError(401, "guest_expired", "Rescan the table QR.");
  const session = await requiredRow(db, "table_sessions", {
    public_id: publicId,
    company_id: access.company_id,
    status: { $in: ["open", "bill_requested", "billed"] },
  });
  const table = await requiredRow(db, "cafe_tables", {
    id: session.table_id,
    company_id: session.company_id,
    is_active: true,
    qr_active: true,
  });
  const qr = await requiredRow(db, "qr_tokens", {
    id: access.qr_id,
    company_id: session.company_id,
    revoked_at: null,
  });
  if (Date.parse(qr.expires_at) <= Date.now())
    throw new HttpError(401, "guest_expired", "Rescan an active QR.");
  const company = await requiredRow(db, "companies", {
    id: session.company_id,
    is_active: true,
    business_type: "cafe",
  });
  return { session, table, company };
}
const guestScope = (company: Row, session: Row): Scope => ({
  company,
  user: {
    id: 0,
    business_group_id: company.business_group_id,
    company_id: company.id,
    branch_id: session.branch_id,
    role: "staff",
    name: "QR guest",
  },
  filter: { company_id: company.id, branch_id: session.branch_id },
});
async function safeMenu(
  db: Db,
  data: { session: Row; table: Row; company: Row },
) {
  const { session, table, company } = data;
  const categories = await db
    .collection<Row>("menu_categories")
    .find({
      company_id: company.id,
      is_active: true,
      $or: [{ branch_id: session.branch_id }, { branch_id: null }],
    })
    .sort({ display_order: 1 })
    .toArray();
  const cm = new Map(categories.map((c) => [c.id, c.public_id]));
  const items = await db
    .collection<Row>("menu_items")
    .find({
      company_id: company.id,
      is_active: true,
      category_id: { $in: categories.map((c) => c.id) },
      $or: [{ branch_id: session.branch_id }, { branch_id: null }],
    })
    .sort({ display_order: 1 })
    .toArray();
  return {
    cafe_name: company.name,
    table_code: table.table_code,
    table_display_name: table.display_name,
    session_public_id: session.public_id,
    session_status: session.status,
    categories: categories.map((c) => ({
      public_id: c.public_id,
      name: c.name,
      display_order: c.display_order,
    })),
    items: items.map((i) => ({
      public_id: i.public_id,
      category_public_id: cm.get(i.category_id),
      name: i.name,
      description: i.description,
      image_reference: i.image_reference,
      selling_price: i.selling_price,
      preparation_area: i.preparation_area,
      available: i.available,
      display_order: i.display_order,
    })),
  };
}
async function throttle(db: Db, key: string, max: number) {
  const bucket = Math.floor(Date.now() / 60000),
    id = digest(key + ":" + bucket);
  const gate = await db
    .collection("public_limits")
    .findOneAndUpdate(
      { _id: id as never },
      {
        $inc: { count: 1 },
        $setOnInsert: { expires_at: new Date(Date.now() + 120000) },
      },
      { upsert: true, returnDocument: "after" },
    );
  if (gate && gate.count > max)
    throw new HttpError(
      429,
      "rate_limited",
      "Too many requests. Try again shortly.",
    );
}
export async function publicCafe(
  db: Db,
  route: string,
  request: Request,
  body: Row,
) {
  const method = request.method;
  const resolveMatch = route.match(/^public\/cafe\/qr\/([^/]+)\/resolve$/);
  if (resolveMatch && method === "POST") {
    await throttle(db, "resolve:" + digest(resolveMatch[1]), 30);
    const data = await resolve(db, resolveMatch[1]);
    const key = randomBytes(32).toString("base64url"),
      expires = new Date(Date.now() + 4 * 3600000).toISOString();
    await insertRow(db, "guest_access", {
      company_id: data.company.id,
      session_public_id: data.session.public_id,
      qr_id: data.qr.id,
      key_hash: digest(key),
      expires_at: expires,
    });
    return {
      cafe_name: data.company.name,
      table_code: data.table.table_code,
      table_display_name: data.table.display_name,
      session_public_id: data.session.public_id,
      guest_access: key,
      guest_expires_at: expires,
      ordering_enabled: data.session.status === "open",
    };
  }
  const sessionMatch = route.match(
    /^public\/cafe\/sessions\/([^/]+)\/(menu|orders|bill-request)$/,
  );
  if (sessionMatch) {
    const data = await guest(db, sessionMatch[1], request),
      scope = guestScope(data.company, data.session),
      action = sessionMatch[2];
    if (action === "menu" && method === "GET") return safeMenu(db, data);
    if (action === "orders" && method === "GET")
      return {
        ...(await safeMenu(db, data)),
        orders: (
          await db
            .collection<Row>("cafe_orders")
            .find({
              company_id: data.company.id,
              table_session_public_id: data.session.public_id,
            })
            .sort({ id: 1 })
            .toArray()
        ).map(publicOrder),
      };
    if (action === "orders" && method === "POST") {
      requireValue(
        Object.keys(body).every((k) => ["items", "customer_notes"].includes(k)),
        "Only menu items and notes can be submitted.",
      );
      await throttle(db, "orders:" + data.session.public_id, 10);
      return transaction(async (db, session) => {
        const state = await replay(
          db,
          scope,
          request.headers.get("idempotency-key"),
          route,
          body,
          session,
        );
        if (state.old) return { ...state.old.result, replayed: true };
        const order = await createOrder(
          db,
          scope,
          {
            ...body,
            id: 0,
            order_type: "dine_in",
            table_session_public_id: data.session.public_id,
          },
          session,
          "qr_customer",
        );
        const result = publicOrder(order);
        await saveReplay(db, state, result, session);
        return result;
      });
    }
    if (action === "bill-request" && method === "POST")
      return transaction(async (db, session) => {
        const fresh = await requiredRow(
          db,
          "table_sessions",
          { id: data.session.id, company_id: data.company.id },
          session,
        );
        if (fresh.status === "bill_requested")
          return {
            session_public_id: fresh.public_id,
            session_status: fresh.status,
            bill_requested_at: fresh.bill_requested_at,
          };
        const result = await requestSessionBill(
          db,
          scope,
          fresh,
          fresh.version,
          session,
        );
        return {
          session_public_id: result.public_id,
          session_status: result.status,
          bill_requested_at: result.bill_requested_at,
        };
      });
  }
  return undefined;
}
export async function qrRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  origin: string,
) {
  const match = route.match(
    /^cafe\/tables\/(\d+)\/qr\/(rotate|status|revoke|print-data|render)$/,
  );
  if (!match) return undefined;
  cafeOnly(scope);
  allow(scope.user, managers);
  const table = await requiredRow(db, "cafe_tables", {
    ...scope.filter,
    id: Number(match[1]),
    is_active: true,
  });
  const action = match[2];
  if (action === "status" && method === "GET")
    return db
      .collection("qr_tokens")
      .findOne(
        { company_id: scope.company.id, table_id: table.id },
        { projection: { token_hash: 0 }, sort: { id: -1 } },
      );
  if (action === "rotate" && method === "POST")
    return transaction(async (db, session) => {
      const days = Number(body.expires_in_days ?? 365);
      requireValue(
        Number.isInteger(days) && days >= 1 && days <= 3650,
        "Invalid QR expiry.",
      );
      const raw = randomBytes(32).toString("base64url");
      await db
        .collection("qr_tokens")
        .updateMany(
          {
            company_id: scope.company.id,
            table_id: table.id,
            revoked_at: null,
          },
          { $set: { revoked_at: now() } },
          { session },
        );
      const row = await insertRow(
        db,
        "qr_tokens",
        {
          company_id: scope.company.id,
          table_id: table.id,
          public_reference: randomUUID(),
          token_hash: digest(raw),
          token_prefix: raw.slice(0, 6),
          expires_at: new Date(Date.now() + days * 86400000).toISOString(),
          revoked_at: null,
          last_used_at: null,
          active: true,
        },
        session,
      );
      await db
        .collection("cafe_tables")
        .updateOne(
          { id: table.id, company_id: scope.company.id },
          {
            $set: {
              qr_active: true,
              qr_public_reference: row.public_reference,
            },
            $inc: { version: 1 },
          },
          { session },
        );
      return {
        table_code: table.table_code,
        table_display_name: table.display_name,
        public_reference: row.public_reference,
        token_prefix: row.token_prefix,
        expires_at: row.expires_at,
        raw_token: raw,
        qr_svg_data_uri: null,
      };
    });
  if (action === "revoke" && method === "POST")
    return transaction(async (db, session) => {
      const at = now();
      await db
        .collection("qr_tokens")
        .updateMany(
          {
            company_id: scope.company.id,
            table_id: table.id,
            revoked_at: null,
          },
          { $set: { revoked_at: at, active: false } },
          { session },
        );
      await db
        .collection("cafe_tables")
        .updateOne(
          { id: table.id },
          { $set: { qr_active: false }, $inc: { version: 1 } },
          { session },
        );
      return { public_reference: table.qr_public_reference, revoked_at: at };
    });
  if (["print-data", "render"].includes(action) && method === "POST") {
    const qr = await requiredRow(db, "qr_tokens", {
      company_id: scope.company.id,
      table_id: table.id,
      token_hash: digest(String(body.raw_token)),
      revoked_at: null,
    });
    requireValue(Date.parse(qr.expires_at) > Date.now(), "QR expired.");
    const base = String(body.public_base_url ?? "/order");
    requireValue(
      (base.startsWith("/") && !base.startsWith("//")) ||
        /^https?:\/\//.test(base),
      "Use an HTTP(S) URL or relative path.",
    );
    const QRCode = await import("qrcode");
    const svg = await QRCode.toString(
      new URL(
        base.replace(/\/$/, "") + "/" + encodeURIComponent(body.raw_token),
        origin,
      ).href,
      { type: "svg", errorCorrectionLevel: "M" },
    );
    return {
      table_code: table.table_code,
      table_display_name: table.display_name,
      public_reference: qr.public_reference,
      token_prefix: qr.token_prefix,
      expires_at: qr.expires_at,
      qr_svg_data_uri:
        "data:image/svg+xml;base64," + Buffer.from(svg).toString("base64"),
    };
  }
  return undefined;
}
