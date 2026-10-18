import { randomUUID } from "node:crypto";
import { type ClientSession, type Db } from "mongodb";
import { database, nextId, type Row } from "./db";
import { HttpError, requireValue, pending } from "./errors";
import { allow, digest, managers, sellers, type Scope } from "./security";
import { businessDate, canonical, decimal, multiply, scaled } from "./money";
export async function authorizedBranch(
  db: Db,
  scope: Scope,
  id: unknown,
  session?: ClientSession,
) {
  const branch = await db
    .collection<Row>("branches")
    .findOne(
      { id: Number(id), company_id: scope.company.id, is_active: true },
      { session },
    );
  if (!branch || (scope.user.branch_id && scope.user.branch_id !== branch.id))
    throw new HttpError(404, "not_found", "Branch unavailable.");
  return branch;
}
export async function quote(
  db: Db,
  scope: Scope,
  body: Row,
  cafe: boolean,
  session?: ClientSession,
) {
  allow(scope.user, sellers);
  const branch = await authorizedBranch(db, scope, body.branch_id, session);
  requireValue(
    Array.isArray(body.items) &&
      body.items.length > 0 &&
      body.items.length <= 100,
    "Cart must contain 1–100 lines.",
  );
  if ((scope.company.business_type === "cafe") !== cafe)
    throw new HttpError(403, "forbidden", "Wrong venture checkout.");
  const profile = await db
    .collection<Row>("business_profiles")
    .findOne({ company_id: scope.company.id }, { session });
  if (!profile)
    throw new HttpError(409, "not_configured", "Business profile is missing.");
  if (body.invoice_type === "gst" || profile.default_tax_mode === "gst")
    pending("GST calculation and statutory invoice parity");
  const items = [];
  let subtotal = 0,
    discount = 0;
  for (const input of body.items) {
    requireValue(
      input && typeof input === "object" && !Array.isArray(input),
      "Invalid cart line.",
    );
    if (cafe)
      requireValue(
        typeof input.menu_item_public_id === "string" &&
          input.menu_item_public_id.length <= 64,
        "Invalid menu identifier.",
      );
    else
      requireValue(
        Number.isSafeInteger(input.product_id) && input.product_id > 0,
        "Invalid product identifier.",
      );
    const item = cafe
      ? await db.collection<Row>("menu_items").findOne(
          {
            company_id: scope.company.id,
            public_id: input.menu_item_public_id,
            is_active: true,
            available: true,
            $or: [{ branch_id: branch.id }, { branch_id: null }],
          },
          { session },
        )
      : await db.collection<Row>("products").findOne(
          {
            company_id: scope.company.id,
            id: Number(input.product_id),
            is_active: true,
          },
          { session },
        );
    if (!item) throw new HttpError(404, "not_found", "Cart item unavailable.");
    const quantity = scaled(input.quantity);
    requireValue(quantity > 0, "Quantity must be positive.");
    const unit = scaled(item.selling_price);
    if (input.unit_price != null && scaled(input.unit_price) !== unit)
      pending("Price override authorization parity");
    const lineDiscount = scaled(input.discount ?? "0");
    if (lineDiscount) allow(scope.user, managers);
    const gross = multiply(unit, quantity);
    requireValue(lineDiscount <= gross, "Discount exceeds line amount.");
    subtotal += gross;
    discount += lineDiscount;
    const productId = cafe ? item.product_id : item.id;
    const linkedProduct = cafe && productId
      ? await db.collection<Row>('products').findOne({id: productId, company_id: scope.company.id}, {session})
      : item;
    if (productId && !linkedProduct) throw new HttpError(409, 'scope_integrity', 'Menu product mapping is unavailable.');
    const inventory = productId
      ? await db.collection("inventory").findOne(
          {
            company_id: scope.company.id,
            branch_id: branch.id,
            product_id: productId,
          },
          { session },
        )
      : null;
    items.push({
      id: items.length + 1,
      product_id: productId ?? null,
      menu_item_public_id: cafe ? item.public_id : null,
      menu_item_id: cafe ? item.id : null,
      product_name: item.name,
      product_name_snapshot: item.name,
      sku: linkedProduct?.sku ?? "",
      sku_snapshot: linkedProduct?.sku ?? "",
      quantity: decimal(quantity),
      unit_price: decimal(unit),
      discount: decimal(lineDiscount),
      taxable_value: decimal(gross - lineDiscount),
      gst_rate: "0.00",
      cgst_total: "0.00",
      sgst_total: "0.00",
      igst_total: "0.00",
      cess_total: "0.00",
      line_total: decimal(gross - lineDiscount),
      gross_profit: decimal(
        gross -
          lineDiscount -
          multiply(scaled(linkedProduct?.unit_cost ?? "0"), quantity),
      ),
      quantity_on_hand: decimal(inventory?.quantity_scaled ?? 0),
      hsn_sac_code: item.hsn_sac_code ?? null,
      mrp: item.mrp ?? null,
    });
  }
  return {
    branch_id: branch.id,
    customer_id: body.customer_id ?? null,
    invoice_type: "non_gst",
    place_of_supply_state: null,
    place_of_supply_state_code: null,
    subtotal: decimal(subtotal),
    discount_total: decimal(discount),
    taxable_total: decimal(subtotal - discount),
    cgst_total: "0.00",
    sgst_total: "0.00",
    igst_total: "0.00",
    cess_total: "0.00",
    round_off: "0.00",
    grand_total: decimal(subtotal - discount),
    paid_amount: "0.00",
    balance_due: decimal(subtotal - discount),
    items,
  };
}
export async function checkout(
  scope: Scope,
  body: Row,
  key: string | null,
  cafe: boolean,
) {
  requireValue(
    key && key.length >= 8 && key.length <= 150,
    "Idempotency-Key must contain 8–150 characters.",
  );
  allow(scope.user, sellers);
  const { db, client } = await database();
  const requestHash = digest(canonical(body));
  const session = client.startSession();
  const keyHash = digest(`${scope.user.id}:${key}`);
  try {
    return await session.withTransaction(
      async () => {
        const existing = await db
          .collection<Row>("invoices")
          .findOne(
            { company_id: scope.company.id, idempotency_key: keyHash },
            { session },
          );
        if (existing) {
          if (existing.request_hash !== requestHash)
            throw new HttpError(
              409,
              "idempotency_conflict",
              "This payment key belongs to a different cart.",
            );
          if (
            scope.user.branch_id &&
            scope.user.branch_id !== existing.branch_id
          )
            throw new HttpError(404, "not_found", "Invoice unavailable.");
          return { invoice: existing, replay: true };
        }
        const calculated = await quote(db, scope, body, cafe, session);
        const branch = await authorizedBranch(
          db,
          scope,
          body.branch_id,
          session,
        );
        // Serialize checkout and closing through the same branch document.
        await db
          .collection("branches")
          .updateOne(
            { id: branch.id },
            { $inc: { write_version: 1 } },
            { session },
          );
        if (
          await db.collection("business_day_closures").findOne(
            {
              company_id: scope.company.id,
              branch_id: branch.id,
              business_date: businessDate(),
              status: { $in: ["submitted", "closed"] },
            },
            { session },
          )
        )
          throw new HttpError(409, "day_closed", "The business day is closed.");
        if (body.customer_id != null) pending('Customer ledger posting and customer-linked checkout');
        const amount = scaled(calculated.grand_total);
        requireValue(amount > 0, "Invoice total must be positive.");
        const rawPayments = cafe
          ? [
              {
                payment_mode_id: body.payment_mode_id,
                amount: calculated.grand_total,
                reference_number: body.reference_number,
              },
            ]
          : body.payments;
        requireValue(
          Array.isArray(rawPayments) &&
            rawPayments.length > 0 &&
            rawPayments.length <= 10,
          "Payment is required.",
        );
        const payments = [];
        let paid = 0;
        for (const raw of rawPayments) {
          const mode = await db.collection<Row>("payment_modes").findOne(
            {
              id: Number(raw.payment_mode_id),
              company_id: scope.company.id,
              is_active: true,
            },
            { session },
          );
          requireValue(
            mode && ["cash", "upi", "card"].includes(mode.mode_type),
            "Select a configured Cash, UPI or Card mode.",
          );
          const value = scaled(raw.amount);
          requireValue(value > 0, "Payment must be positive.");
          if (mode.requires_reference)
            requireValue(
              String(raw.reference_number ?? "").trim(),
              "Payment reference is required.",
            );
          paid += value;
          payments.push({
            id: await nextId(db, "invoice_payments", session),
            payment_mode_id: mode.id,
            mode_name: mode.name,
            mode_type: mode.mode_type,
            amount: decimal(value),
            reference_number: raw.reference_number ?? null,
            is_credit_marker: false,
            notes: raw.notes ?? null,
            received_by: scope.user.id,
            payment_datetime: new Date().toISOString(),
          });
        }
        if (paid !== amount)
          pending("Partial payment, credit and change handling");
        const requested = new Map<number, number>();
        for (const item of calculated.items)
          if (item.product_id)
            requested.set(
              item.product_id,
              (requested.get(item.product_id) ?? 0) + scaled(item.quantity),
            );
        const id = await nextId(db, "invoices", session);
        const now = new Date().toISOString();
        for (const [product, quantity] of requested) {
          const updated = await db.collection("inventory").updateOne(
            {
              company_id: scope.company.id,
              branch_id: branch.id,
              product_id: product,
              quantity_scaled: { $gte: quantity },
            },
            {
              $inc: { quantity_scaled: -quantity },
              $set: { last_updated_at: now },
            },
            { session },
          );
          if (!updated.modifiedCount)
            throw new HttpError(
              409,
              "insufficient_stock",
              "Insufficient available inventory.",
            );
          await db.collection("stock_movements").insertOne(
            {
              id: await nextId(db, "stock_movements", session),
              company_id: scope.company.id,
              branch_id: branch.id,
              product_id: product,
              movement_type: "sale",
              quantity_change: decimal(-quantity),
              created_by: scope.user.id,
              reference_type: "invoice",
              reference_id: id,
              created_at: now,
            },
            { session },
          );
        }
        const sequence = await db
          .collection<Row>("invoice_sequences")
          .findOneAndUpdate(
            {
              company_id: scope.company.id,
              branch_id: branch.id,
              is_active: true,
              invoice_type: "non_gst_invoice",
            },
            { $inc: { next_number: 1 } },
            { session, returnDocument: "before" },
          );
        requireValue(
          sequence,
          "Configure a separate active invoice sequence for this branch.",
        );
        const invoiceNumber = `${sequence.prefix}${String(sequence.next_number).padStart(sequence.padding ?? 5, "0")}${sequence.suffix ?? ""}`;
        const sourceId = randomUUID();
        const invoice: Row = {
          ...calculated,
          id,
          company_id: scope.company.id,
          invoice_number: invoiceNumber,
          invoice_date: now,
          created_at: now,
          issued_at: now,
          created_by: scope.user.id,
          created_by_name: scope.user.name,
          branch_name: branch.name,
          customer_name: null,
          status: "paid",
          payment_status: "paid",
          paid_amount: decimal(paid),
          balance_due: "0.00",
          payments,
          taxes: [],
          status_history: [],
          sale_id: null,
          cafe_name: scope.company.name,
          source_type: cafe ? "cafe_takeaway" : "retail",
          source_id: sourceId,
          idempotency_key: keyHash,
          request_hash: requestHash,
        };
        if (cafe)
          await db.collection("cafe_orders").insertOne(
            {
              id: await nextId(db, "cafe_orders", session),
              public_id: sourceId,
              order_number: invoiceNumber,
              company_id: scope.company.id,
              branch_id: branch.id,
              session_type: body.order_type ?? "counter",
              order_type: body.order_type ?? "counter",
              estimated_total: calculated.grand_total,
              source_channel: "billing_counter",
              status: "closed",
              version: 1,
              items: calculated.items,
              total_amount: calculated.grand_total,
              created_at: now,
              updated_at: now,
              billed_invoice_id: id,
            },
            { session },
          );
        await db.collection("invoices").insertOne(invoice, { session });
        for (const payment of payments)
          await db.collection("invoice_payments").insertOne(
            {
              ...payment,
              invoice_id: id,
              company_id: scope.company.id,
              branch_id: branch.id,
            },
            { session },
          );
        return { invoice, replay: false };
      },
      {
        readConcern: { level: "snapshot" },
        writeConcern: { w: "majority" },
        maxCommitTimeMS: 10000,
      },
    );
  } finally {
    await session.endSession();
  }
}
export function receipt(invoice: Row) {
  return {
    invoice_id: invoice.id,
    invoice_number: invoice.invoice_number,
    source_type: invoice.source_type,
    source_id: invoice.source_id,
    cafe_name: invoice.cafe_name,
    branch_name: invoice.branch_name,
    invoice_type: invoice.invoice_type,
    invoice_status: invoice.status,
    payment_status: invoice.payment_status,
    issued_at: invoice.issued_at,
    subtotal: invoice.subtotal,
    discount_total: invoice.discount_total,
    taxable_total: invoice.taxable_total,
    cgst_total: invoice.cgst_total,
    sgst_total: invoice.sgst_total,
    igst_total: invoice.igst_total,
    cess_total: invoice.cess_total,
    round_off: invoice.round_off,
    grand_total: invoice.grand_total,
    paid_amount: invoice.paid_amount,
    balance_due: invoice.balance_due,
    gstin: null,
    items: invoice.items.map((i: Row) => ({
      name: i.product_name_snapshot,
      sku: i.sku_snapshot,
      quantity: i.quantity,
      unit_price: i.unit_price,
      discount: i.discount,
      line_total: i.line_total,
    })),
    payments: invoice.payments,
  };
}
