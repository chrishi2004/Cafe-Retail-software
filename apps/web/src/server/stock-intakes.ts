import type { Db } from "mongodb";

import { authorizedBranch } from "./billing";
import { type Row } from "./db";
import { requireValue } from "./errors";
import { insertExpenseRecord } from "./expenses";
import { replay, saveReplay, writableDay } from "./financial";
import { businessDate, decimal, multiply, scaled } from "./money";
import { audit, dateOnly, insertRow, queryScope, transaction } from "./query";
import { allow, managers, type Scope } from "./security";

const PAYMENT_MODES = ["cash", "upi", "card", "bank_transfer", "credit", "other"];

function optionalText(value: unknown, max: number, label: string) {
  const text = String(value ?? "").trim();
  requireValue(text.length <= max, `${label} is too long.`);
  return text || null;
}

export async function stockIntakeRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
  key: string | null,
) {
  if (!route.startsWith("cafe/stock-intakes")) return undefined;
  requireValue(scope.company.business_type === "cafe", "Cafe venture required.");
  allow(scope.user, [...managers, "analyst"]);

  if (route === "cafe/stock-intakes" && method === "GET") {
    const filter = await queryScope(db, scope, url);
    if (url.searchParams.get("start_date") || url.searchParams.get("end_date")) {
      const start = dateOnly(url.searchParams.get("start_date") ?? "2000-01-01");
      const end = dateOnly(url.searchParams.get("end_date") ?? businessDate());
      requireValue(start <= end, "Start date must precede end date.");
      filter.purchase_date = { $gte: start, $lte: end };
    }
    return db.collection<Row>("stock_intakes").find(filter).sort({ purchase_date: -1, id: -1 }).limit(500).toArray();
  }

  if (route !== "cafe/stock-intakes" || method !== "POST")
    return undefined;

  allow(scope.user, managers);
  return transaction(async (txDb, session) => {
    const state = await replay(txDb, scope, key, route, body, session);
    if (state.old) return state.old.result as Row;

    const branch = await authorizedBranch(txDb, scope, Number(body.branch_id), session);
    const purchaseDate = dateOnly(body.purchase_date ?? businessDate());
    await writableDay(txDb, scope, branch.id, session, purchaseDate);

    const supplierId = body.supplier_id ? Number(body.supplier_id) : null;
    const supplier = supplierId
      ? await txDb.collection<Row>("suppliers").findOne(
          { id: supplierId, company_id: scope.company.id, is_active: true },
          { session },
        )
      : null;
    requireValue(!supplierId || supplier, "Supplier unavailable.");

    const paymentMode = String(body.payment_mode ?? "cash");
    requireValue(PAYMENT_MODES.includes(paymentMode), "Choose a valid payment mode.");
    requireValue(Array.isArray(body.items) && body.items.length > 0 && body.items.length <= 100, "Stock feed requires 1–100 items.");

    const seen = new Set<number>();
    const items: Row[] = [];
    let total = 0;
    for (const input of body.items as Row[]) {
      const productId = Number(input.product_id);
      requireValue(Number.isSafeInteger(productId) && productId > 0 && !seen.has(productId), "Choose unique valid inventory items.");
      seen.add(productId);
      const product = await txDb.collection<Row>("products").findOne(
        { id: productId, company_id: scope.company.id, is_active: true },
        { session },
      );
      requireValue(product && product.item_type !== "service", "Inventory item unavailable.");
      const quantity = scaled(input.quantity);
      const unitCost = scaled(input.unit_cost ?? product.unit_cost ?? "0");
      requireValue(quantity > 0, "Stock feed quantity must be positive.");
      requireValue(unitCost >= 0, "Unit cost cannot be negative.");
      const lineTotal = multiply(quantity, unitCost);
      total += lineTotal;
      items.push({
        id: items.length + 1,
        product_id: product.id,
        product_name: product.name,
        product_sku: product.sku,
        unit_of_measure: product.unit_of_measure ?? product.unit ?? "unit",
        quantity: decimal(quantity),
        unit_cost: decimal(unitCost),
        line_total: decimal(lineTotal),
      });
    }

    const intake = await insertRow(
      txDb,
      "stock_intakes",
      {
        company_id: scope.company.id,
        branch_id: branch.id,
        branch_name: branch.name,
        purchase_date: purchaseDate,
        supplier_id: supplier?.id ?? null,
        supplier_name: supplier?.name ?? optionalText(body.vendor_name, 160, "Vendor"),
        vendor_name: optionalText(body.vendor_name, 160, "Vendor") ?? supplier?.name ?? null,
        reference_number: optionalText(body.reference_number, 160, "Reference"),
        payment_mode: paymentMode,
        notes: optionalText(body.notes, 1000, "Notes"),
        items,
        item_count: items.length,
        total_amount: decimal(total),
        status: "posted",
        expense_id: null,
        created_by: scope.user.id,
        created_by_name: scope.user.name,
      },
      session,
    );

    for (const item of items) {
      const filter = {
        company_id: scope.company.id,
        branch_id: branch.id,
        product_id: item.product_id,
      };
      const existing = await txDb.collection<Row>("inventory").findOne(filter, { session });
      if (existing)
        await txDb.collection("inventory").updateOne(
          filter,
          { $inc: { quantity_scaled: scaled(item.quantity) }, $set: { last_updated_at: new Date().toISOString() } },
          { session },
        );
      else
        await insertRow(
          txDb,
          "inventory",
          { ...filter, quantity_scaled: scaled(item.quantity), reserved_scaled: 0, on_order_scaled: 0, last_updated_at: new Date().toISOString() },
          session,
        );

      await insertRow(
        txDb,
        "stock_movements",
        {
          ...filter,
          movement_type: "stock_intake",
          quantity_change: item.quantity,
          unit_cost: item.unit_cost,
          line_total: item.line_total,
          reason: "Cafe stock feed",
          reference_type: "stock_intake",
          reference_id: intake.id,
          created_by: scope.user.id,
          created_by_name: scope.user.name,
        },
        session,
      );
    }

    if (body.record_expense !== false && total > 0) {
      const expense = await insertExpenseRecord(
        txDb,
        scope,
        {
          branch_id: branch.id,
          expense_date: purchaseDate,
          category: "stock_purchase",
          description: `Stock feed #${intake.id}`,
          amount: decimal(total),
          payment_mode: paymentMode,
          vendor_name: intake.vendor_name,
          reference_number: intake.reference_number,
          notes: intake.notes,
          source_type: "stock_intake",
          source_id: intake.id,
        } as Row,
        session,
        { checkWritableDay: false },
      );
      intake.expense_id = expense.id;
      await txDb.collection("stock_intakes").updateOne(
        { id: intake.id, company_id: scope.company.id },
        { $set: { expense_id: expense.id, updated_at: new Date().toISOString() } },
        { session },
      );
    }

    await audit(txDb, scope, "create", "stock_intake", intake.id, { branch_id: branch.id, total_amount: intake.total_amount }, session);
    await saveReplay(txDb, state, intake, session);
    return intake;
  });
}
