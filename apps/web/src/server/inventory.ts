import { audit, insertRow, now, transaction } from "./query";
import { replay, saveReplay, writableDay } from "./financial";
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
export async function moveStock(scope: Scope, body: Row, key: string | null, kind: "transfer" | "waste") {
  allow(scope.user, managers);
  const quantity = scaled(body.quantity);
  const reason = String(body.reason ?? "").trim();
  requireValue(quantity > 0 && reason.length >= 3 && reason.length <= 250, "Enter a positive quantity and a reason (3–250 characters).");
  return transaction(async (db, session) => {
    const state = await replay(db, scope, key, kind, body, session);
    if (state.old) return state.old.result;
    const source = await authorizedBranch(db, scope, Number(body.branch_id), session);
    const destination = kind === "transfer" ? await authorizedBranch(db, scope, Number(body.destination_id), session) : null;
    requireValue(destination?.id !== source.id, "Select a different receiving branch.");
    await writableDay(db, scope, source.id, session);
    if (destination) await writableDay(db, scope, destination.id, session);
    const product = await db.collection<Row>("products").findOne({ company_id: scope.company.id, id: Number(body.product_id), is_active: true }, { session });
    requireValue(product && product.item_type !== "service", "Choose an active inventory product.");
    const filter = { company_id: scope.company.id, branch_id: source.id, product_id: product.id };
    const stock = await db.collection<Row>("inventory").findOne(filter, { session });
    requireValue(stock && stock.quantity_scaled - (stock.reserved_scaled ?? 0) >= quantity, "Insufficient available stock.");
    const stamp = { last_updated_at: now() };
    await db.collection("inventory").updateOne(filter, { $inc: { quantity_scaled: -quantity }, $set: stamp }, { session });
    const details = { ...filter, reason, created_by: scope.user.id, created_by_name: scope.user.name, reference_type: kind, unit_cost: product.unit_cost, line_total: decimal(multiply(scaled(product.unit_cost ?? "0"), quantity)) };
    const out = await insertRow(db, "stock_movements", { ...details, movement_type: destination ? "transfer_out" : "waste", quantity_change: decimal(-quantity), destination_id: destination?.id }, session);
    if (destination) {
      const target = { ...filter, branch_id: destination.id };
      const updated = await db.collection("inventory").updateOne(target, { $inc: { quantity_scaled: quantity }, $set: stamp }, { session });
      if (!updated.matchedCount) await insertRow(db, "inventory", { ...target, quantity_scaled: quantity, reserved_scaled: 0, on_order_scaled: 0, ...stamp }, session);
      await insertRow(db, "stock_movements", { ...details, ...target, movement_type: "transfer_in", reference_id: out.id, quantity_change: decimal(quantity) }, session);
    }
    await audit(db, scope, kind, "stock_movement", out.id, { product_id: product.id, quantity: decimal(quantity), destination_id: destination?.id }, session, { branchId: source.id });
    const result = { movement_id: out.id };
    await saveReplay(db, state, result, session);
    return result;
  });
}

export async function adjust(scope: Scope, body: Row, key: string | null = null) {
  allow(scope.user, managers);
  requireValue(
    String(body.reason ?? "").trim().length >= 3,
    "Adjustment reason is required.",
  );
  const count = body.counted_quantity === undefined ? null : scaled(body.counted_quantity);
  const raw = String(body.quantity_change ?? "0");
  const delta =
    scaled(raw.replace(/^-/, "") as string) * (raw.startsWith("-") ? -1 : 1);
  requireValue(count !== null || delta !== 0, "Adjustment must be nonzero.");
  const { db, client } = await database();
  const session = client.startSession();
  try {
    return await session.withTransaction(async () => {
      const state = count === null ? null : await replay(db, scope, key, "stock_count", body, session);
      if (state?.old) return state.old.result as { movement: Row };
      const branch = await authorizedBranch(db, scope, body.branch_id, session);
      if (count !== null) await writableDay(db, scope, branch.id, session);
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
      const baseline = row?.quantity_scaled ?? 0;
      if (count !== null) {
        requireValue(baseline === scaled(body.expected_quantity), "Stock changed. Reload inventory and recount.");
        requireValue(count >= (row?.reserved_scaled ?? 0), "Count is below reserved stock.");
      }
      const change = count === null ? delta : count - baseline;
      if (!row) {
        requireValue(count !== null || change > 0, "Insufficient stock.");
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
        movement_type: count === null ? "manual_adjustment" : "stock_count",
        ...(count === null ? {} : { counted_quantity: decimal(count), previous_quantity: decimal(baseline) }),
        quantity_change: decimal(change),
        reason: body.reason,
        reference_type: "manual",
        reference_id: null,
        created_by: scope.user.id,
        created_by_name: scope.user.name,
        created_at: new Date().toISOString(),
      };
      await db.collection("stock_movements").insertOne(movement, { session });
      await audit(db, scope, "adjust", "stock_movement", movement.id, {}, session, { branchId: branch.id });
      if (state) await saveReplay(db, state, { movement }, session);
      return { movement };
    });
  } finally {
    await session.endSession();
  }
}
