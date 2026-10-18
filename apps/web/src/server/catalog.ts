import { transaction, audit } from "./query";
import { randomUUID } from "node:crypto";
import { type Db, type ClientSession } from "mongodb";
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
      "gst_rate_id",
      "hsn_sac_code",
      "cess_rate_percent",
      "unit_of_measure",
      "brand",
      "manufacturer",
      "item_type",
      "batch_tracking_enabled",
      "serial_tracking_enabled",
      "expiry_tracking_enabled",
    ],
    defaults: {
      hsn_sac_code: null,
      cess_rate_percent: "0.00",
      unit_of_measure: "piece",
      brand: null,
      manufacturer: null,
      item_type: "goods",
      batch_tracking_enabled: false,
      serial_tracking_enabled: false,
      expiry_tracking_enabled: false,
      gst_rate_id: null,
      mrp: null,
      selling_price: "0.00",
      unit_cost: "0.00",
      reorder_threshold: "0.00",
      target_stock_level: "0.00",
      unit: "piece",
      primary_barcode: null,
    },
  },
  "tax-rates": {
    collection: "tax_rates",
    fields: ["name", "rate_percent", "cess_percent", "description"],
    defaults: { rate_percent: "0.00", cess_percent: "0.00", description: null },
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
      "contact_person",
      "payment_terms",
      "phone",
      "email",
      "address",
      "city",
      "state",
      "gstin",
      "lead_time_days",
    ],
    defaults: {
      lead_time_days: 0,
      contact_person: null,
      payment_terms: null,
      email: null,
      phone: null,
      address: null,
    },
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
      "credit_limit",
      "opening_balance",
    ],
    defaults: { credit_limit: "0.00", opening_balance: "0.00" },
  },
  "payment-modes": {
    collection: "payment_modes",
    fields: ["name", "mode_type", "requires_reference", "display_order"],
    defaults: { requires_reference: false, display_order: 0 },
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
  session?: ClientSession,
): Promise<Row | Row[] | undefined> {
  if (method !== "GET" && !session)
    return transaction((db, session) =>
      catalog(db, scope, resource, id, method, body, url, session),
    );
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
    if (url.searchParams.get("include_inactive") !== "true")
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
    if (resource === "products") {
      const [categories, suppliers, rates, stock] = await Promise.all([
        db
          .collection<Row>("categories")
          .find({ company_id: scope.company.id })
          .toArray(),
        db
          .collection<Row>("suppliers")
          .find({ company_id: scope.company.id })
          .toArray(),
        db
          .collection<Row>("tax_rates")
          .find({ company_id: scope.company.id })
          .toArray(),
        db.collection<Row>("inventory").find(scope.filter).toArray(),
      ]);
      const cm = new Map(categories.map((c) => [c.id, c])),
        sm = new Map(suppliers.map((c) => [c.id, c])),
        rm = new Map(rates.map((c) => [c.id, c])),
        totals = new Map<number, number>();
      for (const row of stock)
        totals.set(
          row.product_id,
          (totals.get(row.product_id) ?? 0) + row.quantity_scaled,
        );
      for (const row of rows) {
        const category = cm.get(row.category_id),
          supplier = sm.get(row.supplier_id),
          rate = rm.get(row.gst_rate_id);
        row.category_name = category?.name ?? "";
        row.supplier_name = supplier?.name ?? "";
        row.gst_rate_name = rate?.name ?? null;
        row.gst_rate_percent = rate?.rate_percent ?? null;
        row.total_quantity_on_hand = decimal(totals.get(row.id) ?? 0);
        row.stock_status =
          scaled(row.total_quantity_on_hand) <=
          scaled(row.reorder_threshold ?? "0")
            ? "Low stock"
            : "Healthy";
      }
    }
    if (resource === "customers")
      for (const row of rows) {
        row.outstanding_balance = decimal(
          row.outstanding_scaled ?? scaled(row.opening_balance ?? "0"),
        );
        row.available_credit = decimal(
          scaled(row.credit_limit ?? "0") -
            (row.outstanding_scaled ?? scaled(row.opening_balance ?? "0")),
        );
        row.addresses = row.addresses ?? [];
      }
    return rows;
  }
  allow(scope.user, managers);
  if (!["POST", "PUT", "PATCH"].includes(method))
    throw new HttpError(405, "method_not_allowed", "Method unavailable.");
  if (body.company_id != null && body.company_id !== scope.company.id)
    throw new HttpError(403, "forbidden", "Cannot assign another company.");

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
  for (const field of [
    "category_id",
    "supplier_id",
    "product_id",
    "branch_id",
    "gst_rate_id",
  ])
    if (values[field] != null) {
      requireValue(
        Number.isSafeInteger(Number(values[field])) &&
          Number(values[field]) > 0,
        `Invalid ${field}.`,
      );
      values[field] = Number(values[field]);
    }
  if (body.is_active !== undefined) {
    requireValue(
      typeof body.is_active === "boolean",
      "is_active must be boolean.",
    );
    values.is_active = body.is_active;
  }
  for (const field of [
    "available",
    "requires_reference",
    "batch_tracking_enabled",
    "serial_tracking_enabled",
    "expiry_tracking_enabled",
  ])
    if (values[field] !== undefined)
      requireValue(
        typeof values[field] === "boolean",
        `${field} must be boolean.`,
      );
  if (resource === "products")
    requireValue(
      !values.item_type ||
        ["goods", "service"].includes(String(values.item_type)),
      "Invalid item type.",
    );
  if (resource === "cafe/menu/items")
    requireValue(
      !values.preparation_area ||
        ["kitchen", "beverage", "counter", "none"].includes(
          String(values.preparation_area),
        ),
      "Invalid preparation area.",
    );
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
    ["gst_rate_id", "tax_rates"],
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
    "rate_percent",
    "cess_percent",
    "cess_rate_percent",
    "credit_limit",
    "opening_balance",
  ])
    if (values[field] != null) values[field] = decimal(scaled(values[field]));
  if (resource === "tax-rates")
    for (const field of ["rate_percent", "cess_percent"])
      if (values[field] != null)
        requireValue(
          scaled(values[field]) <= 10000,
          "Tax rates cannot exceed 100 percent.",
        );
  if (resource === "payment-modes")
    requireValue(
      [
        "cash",
        "upi",
        "card",
        "bank_transfer",
        "wallet",
        "cheque",
        "credit",
        "other",
      ].includes(String(values.mode_type ?? body.mode_type)),
      "Invalid payment mode type.",
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
      id: await nextId(db, config.collection, session),
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
    if (resource === "customers") {
      row.outstanding_scaled = scaled(row.opening_balance ?? "0");
      row.outstanding_balance = decimal(row.outstanding_scaled);
      row.available_credit = decimal(
        scaled(row.credit_limit ?? "0") - row.outstanding_scaled,
      );
      row.addresses = ["billing", "shipping"]
        .filter((type) => row[type + "_address"])
        .map((type, index) => ({
          id: index + 1,
          address_type: type,
          address: row[type + "_address"],
          recipient_name: row.name,
          phone: row.phone ?? null,
          city: row.city ?? null,
          state: row.state ?? null,
          state_code: row.state_code ?? null,
          pincode: row.pincode ?? null,
          gstin: row.gstin ?? null,
          is_default: true,
        }));
    }
    await collection.insertOne(row, { session });
    await audit(db, scope, "create", config.collection, row.id, {}, session);
    return row;
  }
  requireValue(id, "Choose a record to update.");
  if (resource === "customers" && values.opening_balance !== undefined) {
    const old = await collection.findOne(filter, { session });
    if (
      old &&
      scaled(values.opening_balance) !== scaled(old.opening_balance ?? "0")
    )
      throw new HttpError(
        409,
        "immutable_opening_balance",
        "Opening balance cannot be edited after customer creation.",
      );
  }
  if (body.expected_version != null)
    filter.version = Number(body.expected_version);
  const row = await collection.findOneAndUpdate(
    filter,
    {
      $set: { ...values, updated_at: new Date().toISOString() },
      $inc: { version: 1 },
    },
    { returnDocument: "after", session },
  );
  if (!row) throw new HttpError(404, "not_found", "Record unavailable.");
  await audit(db, scope, "update", config.collection, row.id, {}, session);
  return row;
}
