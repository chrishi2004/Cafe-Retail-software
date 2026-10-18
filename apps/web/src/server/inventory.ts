import { type Db } from "mongodb";
import { database, nextId, type Row } from "./db";
import { authorizedBranch } from "./billing";
import { allow, managers, type Scope } from "./security";
import { HttpError, requireValue } from "./errors";
import { decimal, multiply, scaled } from "./money";
export async function inventoryRows(db: Db, scope: Scope, branchId?: number) {
  if (branchId) await authorizedBranch(db, scope, branchId);
  const filter = {
    ...scope.filter,
    ...(branchId ? { branch_id: branchId } : {}),
  };
  const rows = await db.collection<Row>("inventory").find(filter).toArray();
  const [products, branches, categories, suppliers] = await Promise.all([
    db
      .collection<Row>("products")
      .find({ company_id: scope.company.id })
      .toArray(),
    db
      .collection<Row>("branches")
      .find({ company_id: scope.company.id })
      .toArray(),
    db
      .collection<Row>("categories")
      .find({ company_id: scope.company.id })
      .toArray(),
    db
      .collection<Row>("suppliers")
      .find({ company_id: scope.company.id })
      .toArray(),
  ]);
  const pm = new Map(products.map((p) => [p.id, p])),
    bm = new Map(branches.map((b) => [b.id, b])),
    cm = new Map(categories.map((c) => [c.id, c])),
    sm = new Map(suppliers.map((s) => [s.id, s]));
  const result: Row[] = [];
  for (const row of rows) {
    const product = pm.get(row.product_id),
      branch = bm.get(row.branch_id);
    if (!product || !branch)
      throw new HttpError(
        409,
        "scope_integrity",
        "Inventory has an invalid product or branch reference.",
      );
    const category = cm.get(product.category_id),
      supplier = sm.get(product.supplier_id);
    result.push({
      ...row,
      product_id: Number(row.product_id),
      branch_id: Number(row.branch_id),
      product_name: product.name,
      product_sku: product.sku,
      category_id: product.category_id,
      category_name: category?.name ?? "",
      supplier_id: product.supplier_id,
      supplier_name: supplier?.name ?? "",
      branch_name: branch.name,
      quantity_on_hand: decimal(row.quantity_scaled),
      quantity_reserved: decimal(row.reserved_scaled ?? 0),
      quantity_on_order: decimal(row.on_order_scaled ?? 0),
      reorder_threshold: product.reorder_threshold ?? "0.00",
      target_stock_level: product.target_stock_level ?? "0.00",
      unit_cost: product.unit_cost,
      stock_value: decimal(
        multiply(scaled(product.unit_cost), row.quantity_scaled),
      ),
      is_low_stock:
        row.quantity_scaled <= scaled(product.reorder_threshold ?? "0"),
    });
  }
  return result;
}
export async function adjust(scope: Scope, body: Row) {
  allow(scope.user, managers);
  requireValue(
    String(body.reason ?? "").trim().length >= 3,
    "Adjustment reason is required.",
  );
  const raw = String(body.quantity_change);
  const change =
    scaled(raw.replace(/^-/, "") as string) * (raw.startsWith("-") ? -1 : 1);
  requireValue(change !== 0, "Adjustment must be nonzero.");
  const { db, client } = await database();
  const session = client.startSession();
  try {
    return await session.withTransaction(async () => {
      const branch = await authorizedBranch(db, scope, body.branch_id, session);
      const product = await db.collection<Row>("products").findOne(
        {
          id: Number(body.product_id),
          company_id: scope.company.id,
          is_active: true,
        },
        { session },
      );
      if (!product)
        throw new HttpError(404, "not_found", "Product unavailable.");
      const filter = {
        company_id: scope.company.id,
        branch_id: branch.id,
        product_id: product.id,
      };
      let row: Row | null = await db
        .collection<Row>("inventory")
        .findOne(filter, { session });
      if (!row) {
        requireValue(change > 0, "Insufficient stock.");
        row = {
          ...filter,
          id: await nextId(db, "inventory", session),
          quantity_scaled: 0,
        };
        await db.collection("inventory").insertOne(row, { session });
      }
      if (row.quantity_scaled + change < 0)
        throw new HttpError(
          409,
          "insufficient_stock",
          "Adjustment would make stock negative.",
        );
      await db.collection("inventory").updateOne(
        filter,
        {
          $inc: { quantity_scaled: change },
          $set: { last_updated_at: new Date().toISOString() },
        },
        { session },
      );
      const movement = {
        id: await nextId(db, "stock_movements", session),
        ...filter,
        movement_type: "manual_adjustment",
        quantity_change: decimal(change),
        reason: body.reason,
        reference_type: "manual",
        reference_id: null,
        created_by: scope.user.id,
        created_by_name: scope.user.name,
        created_at: new Date().toISOString(),
      };
      await db.collection("stock_movements").insertOne(movement, { session });
      return { movement };
    });
  } finally {
    await session.endSession();
  }
}
