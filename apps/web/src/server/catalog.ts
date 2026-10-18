import { randomUUID } from "node:crypto";
import { type Db } from "mongodb";
import { nextId, type Row } from "./db";
import { allow, managers, type Scope } from "./security";
import { HttpError, requireValue } from "./errors";
import { decimal, scaled } from "./money";
const resources: Record<
  string,
  { collection: string; fields: string[]; defaults: Record<string, unknown> }
> = {
  products: {
    collection: "products",
    fields: [
      "name",
      "sku",
      "category_id",
      "supplier_id",
      "selling_price",
      "unit_cost",
      "mrp",
      "primary_barcode",
      "barcode",
      "reorder_threshold",
      "target_stock_level",
      "unit",
      "description",
    ],
    defaults: {
      selling_price: "0.00",
      unit_cost: "0.00",
      reorder_threshold: "0.00",
      target_stock_level: "0.00",
      unit: "piece",
      primary_barcode: null,
    },
  },
  categories: {
    collection: "categories",
    fields: ["name", "description"],
    defaults: {},
  },
  suppliers: {
    collection: "suppliers",
    fields: [
      "name",
      "contact_name",
      "phone",
      "email",
      "address",
      "city",
      "state",
      "gstin",
      "lead_time_days",
    ],
    defaults: { lead_time_days: 0 },
  },
  branches: {
    collection: "branches",
    fields: ["name", "address", "city", "manager_name"],
    defaults: {},
  },
  customers: {
    collection: "customers",
    fields: [
      "name",
      "branch_id",
      "phone",
      "email",
      "gstin",
      "billing_address",
      "shipping_address",
      "city",
      "state",
      "state_code",
      "pincode",
    ],
    defaults: { credit_limit: "0.00", opening_balance: "0.00" },
  },
  "payment-modes": {
    collection: "payment_modes",
    fields: ["name", "mode_type", "requires_reference"],
    defaults: { requires_reference: false },
  },
  "cafe/menu/categories": {
    collection: "menu_categories",
    fields: ["name", "branch_id", "display_order"],
    defaults: { branch_id: null, display_order: 0 },
  },
  "cafe/menu/items": {
    collection: "menu_items",
    fields: [
      "name",
      "branch_id",
      "category_id",
      "product_id",
      "description",
      "image_reference",
      "selling_price",
      "preparation_area",
      "available",
      "display_order",
    ],
    defaults: {
      branch_id: null,
      product_id: null,
      description: null,
      image_reference: null,
      preparation_area: "none",
      available: true,
      display_order: 0,
    },
  },
  "cafe/tables": {
    collection: "cafe_tables",
    fields: ["table_code", "display_name", "branch_id", "capacity", "area"],
    defaults: {
      capacity: null,
      area: null,
      active_session_public_id: null,
      active_session_status: null,
      qr_active: false,
      qr_public_reference: null,
    },
  },
};
export function resourceNames() {
  return Object.keys(resources);
}
export async function catalog(
  db: Db,
  scope: Scope,
  resource: string,
  id: string | undefined,
  method: string,
  body: Row,
  url: URL,
) {
  const config = resources[resource];
  if (!config) return undefined;
  if (resource.startsWith("cafe/") && scope.company.business_type !== "cafe")
    throw new HttpError(403, "forbidden", "Cafe venture required.");
  const collection = db.collection<Row>(config.collection);
  const filter: Record<string, unknown> = { company_id: scope.company.id };
  if (resource === "branches" && scope.user.branch_id)
    filter.id = scope.user.branch_id;
  else if (
    ["menu_items", "menu_categories", "cafe_tables", "customers"].includes(
      config.collection,
    ) &&
    scope.user.branch_id
  )
    filter.$or = [{ branch_id: scope.user.branch_id }, { branch_id: null }];
  if (id) {
    requireValue(/^\d+$/.test(id), "Invalid record identifier.");
    if (filter.id && Number(id) !== filter.id)
      throw new HttpError(404, "not_found", "Record unavailable.");
    filter.id = Number(id);
  }
  if (method === "GET") {
    if (!url.searchParams.has("include_inactive"))
      filter.is_active = { $ne: false };
    const search = url.searchParams.get("search") ?? url.searchParams.get("q");
    if (search) {
      const escaped = search
        .slice(0, 100)
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      filter.$and = [
        {
          $or: [
            { name: { $regex: escaped, $options: "i" } },
            { sku: { $regex: escaped, $options: "i" } },
            { primary_barcode: search },
          ],
        },
      ];
    }
    if (id) {
      const row = await collection.findOne(filter);
      if (!row) throw new HttpError(404, "not_found", "Record unavailable.");
      return row;
    }
    const rows = await collection.find(filter).limit(500).toArray();
    return rows;
  }
  allow(scope.user, managers);
  if (!["POST", "PUT", "PATCH"].includes(method))
    throw new HttpError(405, "method_not_allowed", "Method unavailable.");
  if (body.company_id != null && body.company_id !== scope.company.id)
    throw new HttpError(403, "forbidden", "Cannot assign another company.");
  if (body.opening_balance && scaled(body.opening_balance) !== 0)
    throw new HttpError(
      501,
      "migration_pending",
      "Customer opening ledger parity is pending.",
    );
  const values: Record<string, unknown> = {};
  for (const field of config.fields)
    if (body[field] !== undefined) values[field] = body[field];
  for (const [field, value] of Object.entries(values))
    requireValue(
      value === null ||
        (["string", "number", "boolean"].includes(typeof value) &&
          String(value).length <= 1000),
      `Invalid ${field}.`,
    );
  for (const field of ["category_id", "supplier_id", "product_id", "branch_id"])
    if (values[field] != null) {
      requireValue(
        Number.isSafeInteger(Number(values[field])) &&
          Number(values[field]) > 0,
        `Invalid ${field}.`,
      );
      values[field] = Number(values[field]);
    }
  if (body.is_active !== undefined) values.is_active = !!body.is_active;
  if (values.branch_id != null) {
    const branch = await db.collection("branches").findOne({
      id: Number(values.branch_id),
      company_id: scope.company.id,
      is_active: true,
    });
    if (!branch || (scope.user.branch_id && scope.user.branch_id !== branch.id))
      throw new HttpError(404, "not_found", "Branch unavailable.");
  }
  for (const [field, table] of [
    [
      "category_id",
      resource === "cafe/menu/items" ? "menu_categories" : "categories",
    ],
    ["supplier_id", "suppliers"],
    ["product_id", "products"],
  ])
    if (
      values[field] != null &&
      !(await db.collection(table).findOne({
        id: Number(values[field]),
        company_id: scope.company.id,
        is_active: true,
      }))
    )
      throw new HttpError(404, "not_found", `${field} unavailable.`);
  for (const field of [
    "selling_price",
    "unit_cost",
    "mrp",
    "reorder_threshold",
    "target_stock_level",
  ])
    if (values[field] != null) values[field] = decimal(scaled(values[field]));
  if (resource === "payment-modes")
    requireValue(
      ["cash", "upi", "card"].includes(
        String(values.mode_type ?? body.mode_type),
      ),
      "Only Cash, UPI and Card are currently ported.",
    );
  if (method === "POST" && !id) {
    requireValue(
      String(values.name ?? values.display_name ?? "").trim(),
      "Name is required.",
    );
    const now = new Date().toISOString();
    const row: Row = {
      ...config.defaults,
      ...values,
      id: await nextId(db, config.collection),
      company_id: scope.company.id,
      is_active: true,
      public_id: randomUUID(),
      version: 1,
      created_at: now,
      updated_at: now,
    };
    if (
      scope.user.branch_id &&
      ["customers", "menu_items", "menu_categories", "cafe_tables"].includes(
        config.collection,
      )
    )
      row.branch_id = scope.user.branch_id;
    await collection.insertOne(row);
    return row;
  }
  requireValue(id, "Choose a record to update.");
  const row = await collection.findOneAndUpdate(
    filter,
    { $set: { ...values, updated_at: new Date().toISOString() } },
    { returnDocument: "after" },
  );
  if (!row) throw new HttpError(404, "not_found", "Record unavailable.");
  return row;
}
