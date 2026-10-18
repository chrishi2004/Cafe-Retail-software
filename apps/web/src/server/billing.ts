import {
  loadCafeBill,
  finalizeCafeBill,
  type BillSource,
} from "./cafe-billing";
import { postLedger, scopedCustomer } from "./ledger";
import { randomUUID } from "node:crypto";
import { type ClientSession, type Db } from "mongodb";
import { database, nextId, type Row } from "./db";
import { HttpError, requireValue } from "./errors";
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
  snapshots?: Row[],
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
  const invoiceDate = body.invoice_date
    ? new Date(body.invoice_date)
    : new Date();
  requireValue(!Number.isNaN(invoiceDate.getTime()), "Invalid invoice date.");
  const activeGST =
    profile.default_tax_mode === "gst" &&
    profile.gst_effective_from &&
    businessDate(invoiceDate) >= profile.gst_effective_from;
  const invoiceType = body.invoice_type ?? (activeGST ? "gst" : "non_gst");
  requireValue(
    ["gst", "non_gst"].includes(invoiceType),
    "Invalid invoice type.",
  );
  requireValue(
    invoiceType === (activeGST ? "gst" : "non_gst"),
    "Invoice tax mode must match effective venture settings.",
  );
  const customer =
    body.customer_id != null
      ? await scopedCustomer(db, scope, body.customer_id, session)
      : null;
  if (customer?.branch_id)
    requireValue(
      customer.branch_id === branch.id,
      "Customer belongs to another branch.",
    );
  const stateCode =
    body.place_of_supply_state_code ??
    customer?.state_code ??
    profile.state_code ??
    null;
  if (activeGST)
    requireValue(
      profile.gstin && profile.state_code && stateCode,
      "GSTIN and state codes are required.",
    );
  const items = [];
  let subtotal = 0,
    discount = 0;
  for (const [itemIndex, input] of body.items.entries()) {
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
    const item =
      snapshots?.[itemIndex] ??
      (cafe
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
          ));
    if (!item) throw new HttpError(404, "not_found", "Cart item unavailable.");
    const quantity = scaled(input.quantity);
    requireValue(quantity > 0, "Quantity must be positive.");
    let unit = scaled(item.selling_price);
    if (input.unit_price != null && scaled(input.unit_price) !== unit) {
      allow(scope.user, managers);
      unit = scaled(input.unit_price);
    }
    const lineDiscount = scaled(input.discount ?? "0");
    if (lineDiscount) allow(scope.user, managers);
    const gross = multiply(unit, quantity);
    requireValue(lineDiscount <= gross, "Discount exceeds line amount.");
    subtotal += gross;
    discount += lineDiscount;
    const productId = cafe ? item.product_id : item.id;
    const linkedProduct =
      cafe && productId
        ? await db
            .collection<Row>("products")
            .findOne(
              { id: productId, company_id: scope.company.id },
              { session },
            )
        : item;
    if (productId && !linkedProduct)
      throw new HttpError(
        409,
        "scope_integrity",
        "Menu product mapping is unavailable.",
      );
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
    const rate =
      activeGST && linkedProduct?.gst_rate_id
        ? await db
            .collection<Row>("tax_rates")
            .findOne(
              {
                id: linkedProduct.gst_rate_id,
                company_id: scope.company.id,
                is_active: true,
              },
              { session },
            )
        : null;
    const gstRate = activeGST ? scaled(rate?.rate_percent ?? "0") : 0;
    const ownCess = scaled(linkedProduct?.cess_rate_percent ?? "0");
    const cessRate = activeGST
      ? ownCess || scaled(rate?.cess_percent ?? "0")
      : 0;
    const taxable = gross - lineDiscount;
    const interstate = String(stateCode) !== String(profile.state_code);
    const cgst = interstate ? 0 : Math.round((taxable * gstRate) / 20000),
      sgst = cgst,
      igst = interstate ? Math.round((taxable * gstRate) / 10000) : 0,
      cess = Math.round((taxable * cessRate) / 10000);
    const taxes: Row[] = [];
    if (activeGST)
      for (const [type, amount, rateValue] of [
        ["cgst", cgst, gstRate / 2],
        ["sgst", sgst, gstRate / 2],
        ["igst", igst, gstRate],
        ["cess", cess, cessRate],
      ] as const)
        if (amount > 0)
          taxes.push({
            id: taxes.length + 1,
            tax_type: type,
            tax_rate: decimal(Math.round(rateValue)),
            taxable_value: decimal(taxable),
            tax_amount: decimal(amount),
          });
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
      gst_rate: decimal(gstRate),
      cgst_total: decimal(cgst),
      sgst_total: decimal(sgst),
      igst_total: decimal(igst),
      cess_total: decimal(cess),
      line_total: decimal(taxable + cgst + sgst + igst + cess),
      tracks_stock: !!productId && linkedProduct?.item_type !== "service",
      taxes,
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
    invoice_type: invoiceType,
    place_of_supply_state:
      body.place_of_supply_state ?? customer?.state ?? profile.state ?? null,
    place_of_supply_state_code: stateCode,
    subtotal: decimal(subtotal),
    discount_total: decimal(discount),
    taxable_total: decimal(subtotal - discount),
    cgst_total: decimal(items.reduce((n, i) => n + scaled(i.cgst_total), 0)),
    sgst_total: decimal(items.reduce((n, i) => n + scaled(i.sgst_total), 0)),
    igst_total: decimal(items.reduce((n, i) => n + scaled(i.igst_total), 0)),
    cess_total: decimal(items.reduce((n, i) => n + scaled(i.cess_total), 0)),
    round_off: "0.00",
    grand_total: decimal(items.reduce((n, i) => n + scaled(i.line_total), 0)),
    paid_amount: "0.00",
    balance_due: decimal(items.reduce((n, i) => n + scaled(i.line_total), 0)),
    items,
  };
}
export async function checkout(
  scope: Scope,
  body: Row,
  key: string | null,
  cafe: boolean,
  draftId?: number,
  source?: BillSource,
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
        if (draftId) {
          const draft = await db
            .collection<Row>("invoices")
            .findOne({ ...scope.filter, id: draftId }, { session });
          requireValue(
            draft?.status === "draft",
            "Only draft invoices can be issued.",
          );
        }
        const sourceData = source
          ? await loadCafeBill(db, scope, source, session)
          : null;
        const workingBody = sourceData ? { ...body, ...sourceData.body } : body;
        const calculated = await quote(
          db,
          scope,
          workingBody,
          cafe,
          session,
          sourceData?.snapshots,
        );
        const branch = await authorizedBranch(
          db,
          scope,
          workingBody.branch_id,
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
              business_date: businessDate(
                body.invoice_date ? new Date(body.invoice_date) : new Date(),
              ),
              status: { $in: ["submitted", "closed"] },
            },
            { session },
          )
        )
          throw new HttpError(409, "day_closed", "The business day is closed.");
        const customer =
          body.customer_id != null
            ? await scopedCustomer(db, scope, body.customer_id, session)
            : null;
        const amount = scaled(calculated.grand_total);
        requireValue(amount > 0, "Invoice total must be positive.");
        const rawPayments = cafe
          ? (body.payments ?? [
              {
                payment_mode_id: body.payment_mode_id,
                amount: calculated.grand_total,
                reference_number: body.reference_number,
              },
            ])
          : body.payments;
        requireValue(
          Array.isArray(rawPayments) &&
            (rawPayments.length > 0 || customer) &&
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
            mode &&
              [
                "cash",
                "upi",
                "card",
                "bank_transfer",
                "wallet",
                "cheque",
                "other",
                "credit",
              ].includes(mode.mode_type),
            "Select a configured collection mode.",
          );
          const value = scaled(raw.amount);
          requireValue(value > 0, "Payment must be positive.");
          if (mode.requires_reference)
            requireValue(
              String(raw.reference_number ?? "").trim(),
              "Payment reference is required.",
            );
          if (mode.mode_type !== "credit") paid += value;
          else requireValue(customer, "Credit requires a customer.");
          payments.push({
            id: await nextId(db, "invoice_payments", session),
            payment_mode_id: mode.id,
            mode_name: mode.name,
            payment_mode_name: mode.name,
            received_by_name: scope.user.name,
            created_at: new Date().toISOString(),
            mode_type: mode.mode_type,
            amount: decimal(value),
            reference_number: raw.reference_number ?? null,
            is_credit_marker: mode.mode_type === "credit",
            notes: raw.notes ?? null,
            received_by: scope.user.id,
            payment_datetime: new Date().toISOString(),
          });
        }
        requireValue(
          paid <= amount,
          "Payments exceed invoice total; enter the collected amount excluding change.",
        );
        if (paid < amount) {
          requireValue(
            customer,
            "A customer is required for credit or partial payment.",
          );
          const outstanding =
            customer.outstanding_scaled ??
            scaled(customer.opening_balance ?? "0");
          requireValue(
            outstanding + amount - paid <= scaled(customer.credit_limit ?? "0"),
            "Customer credit limit exceeded.",
          );
        }
        const requested = new Map<number, number>();
        for (const item of calculated.items)
          if (item.product_id && item.tracks_stock)
            requested.set(
              item.product_id,
              (requested.get(item.product_id) ?? 0) + scaled(item.quantity),
            );
        const id = draftId ?? (await nextId(db, "invoices", session));
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
              branch_id: { $in: [branch.id, null] },
              is_active: true,
              invoice_type:
                calculated.invoice_type === "gst"
                  ? "gst_invoice"
                  : "non_gst_invoice",
            },
            {
              $inc: { next_number: 1 },
              $set: { last_generated_at: new Date().toISOString() },
            },
            {
              session,
              returnDocument: "before",
              sort: { branch_id: -1, id: 1 },
            },
          );
        requireValue(
          sequence,
          "Configure a separate active invoice sequence for this branch.",
        );
        const invoiceNumber = `${sequence.prefix}${String(sequence.next_number).padStart(sequence.padding ?? 5, "0")}${sequence.suffix ?? ""}`;
        for (const item of calculated.items)
          item.taxes = item.taxes.map((t) => ({
            ...t,
            invoice_id: id,
            invoice_item_id: item.id,
          }));
        const seller = await db
          .collection<Row>("business_profiles")
          .findOne({ company_id: scope.company.id }, { session });
        const sourceId = randomUUID();
        const invoice: Row = {
          ...calculated,
          id,
          company_id: scope.company.id,
          invoice_number: invoiceNumber,
          invoice_date: body.invoice_date
            ? new Date(body.invoice_date).toISOString()
            : now,
          created_at: now,
          issued_at: now,
          created_by: scope.user.id,
          created_by_name: scope.user.name,
          branch_name: branch.name,
          customer_name: customer?.name ?? null,
          gstin:
            calculated.invoice_type === "gst" ? (seller?.gstin ?? null) : null,
          seller_profile: {
            legal_name: seller?.legal_name,
            trade_name: seller?.trade_name,
            address: seller?.address,
            phone: seller?.phone,
            state_code: seller?.state_code,
          },
          status: paid === amount ? "paid" : paid ? "partial_paid" : "credit",
          payment_status:
            paid === amount ? "paid" : paid ? "partial_paid" : "credit",
          paid_amount: decimal(paid),
          balance_due: decimal(amount - paid),
          payments,
          taxes: calculated.items.flatMap((i) => i.taxes),
          status_history: [
            {
              id: 1,
              invoice_id: id,
              from_status: null,
              to_status:
                paid === amount ? "paid" : paid ? "partial_paid" : "credit",
              changed_by: scope.user.id,
              changed_by_name: scope.user.name,
              notes: "Issued through atomic checkout.",
              changed_at: now,
            },
          ],
          sale_id: null,
          cafe_name: seller?.trade_name ?? scope.company.name,
          source_type:
            sourceData?.source_type ?? (cafe ? "cafe_takeaway" : "retail"),
          source_id: source?.publicId ?? sourceId,
          idempotency_key: keyHash,
          request_hash: requestHash,
        };
        if (cafe && !source)
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
        if (draftId)
          await db
            .collection("invoices")
            .replaceOne(
              { id: draftId, company_id: scope.company.id },
              invoice,
              { session },
            );
        else await db.collection("invoices").insertOne(invoice, { session });
        if (customer) {
          await postLedger(
            db,
            scope,
            customer,
            amount,
            0,
            "invoice",
            "invoice",
            id,
            branch.id,
            session,
          );
          if (paid)
            await postLedger(
              db,
              scope,
              customer,
              0,
              paid,
              "payment",
              "invoice",
              id,
              branch.id,
              session,
            );
        }
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
        if (source) await finalizeCafeBill(db, scope, invoice, session);
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
    gstin: invoice.gstin ?? null,
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
