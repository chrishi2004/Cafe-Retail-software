import { invoiceHistory } from "./history";
import { consistency } from "./consistency";
import { assistant } from "./assistant";
import { forecasts, recommendations } from "./planning";
import { queryScope, requiredRow, transaction, signed } from "./query";
import { governance } from "./governance";
import { publicCafe, qrRoutes } from "./public-cafe";
import { cafeBillingRoutes } from "./cafe-billing";
import { cafeRoutes } from "./cafe";
import { authActions, ventureUsers } from "./accounts";
import { financial } from "./financial";
import { customerRoutes } from "./ledger";
import {
  dashboard,
  salesRows,
  salesAnalytics,
  salesSummary,
} from "./dashboards";
import { purchases } from "./purchasing";
import { settings } from "./settings";
import { csv } from "./query";
import { z } from "zod";
import { database, type Row } from "./db";
import {
  currentUser,
  publicUser,
  login,
  scoped,
  allow,
  managers,
  sellers,
} from "./security";
import { catalog, resourceNames } from "./catalog";
import { checkout, quote, receipt, authorizedBranch } from "./billing";
import { inventoryRows, adjust } from "./inventory";
import { cafeReport, range, consolidated } from "./reports";
import { closing } from "./closing";
import { HttpError, requireValue } from "./errors";
import { businessDate, decimal, scaled } from "./money";
const json = (data: unknown, status = 200) =>
  Response.json(data, { status, headers: { "Cache-Control": "no-store" } });
async function boundedBody(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) {
        await reader.cancel();
        throw new HttpError(
          413,
          "payload_too_large",
          "Request body exceeds 64 KiB.",
        );
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  return new TextDecoder().decode(Buffer.concat(chunks));
}
export async function handle(request: Request, path: string[]) {
  try {
    const route = path.join("/"),
      method = request.method,
      url = new URL(request.url);
    if (route === "health") {
      try {
        const { db } = await database();
        await db.command({ ping: 1 });
        return json({
          status: "healthy",
          environment: process.env.NODE_ENV,
          deployment_mode: "nextjs_atlas",
          database: "connected",
          production_parity: false,
        });
      } catch {
        return json(
          {
            status: "unhealthy",
            database: "unavailable",
            production_parity: false,
          },
          503,
        );
      }
    }
    // Parse bounded JSON before any expensive business work. No request body is forwarded.
    let body = {} as Row;
    if (!["GET", "HEAD", "DELETE"].includes(method)) {
      const raw = await boundedBody(request);
      if (Buffer.byteLength(raw) > 65536)
        throw new HttpError(
          413,
          "payload_too_large",
          "Request body exceeds 64 KiB.",
        );
      if (raw) {
        try {
          const value = JSON.parse(raw);
          requireValue(
            value && typeof value === "object" && !Array.isArray(value),
            "JSON object is required.",
          );
          body = value;
        } catch (error) {
          if (error instanceof HttpError) throw error;
          throw new HttpError(422, "invalid_json", "Invalid JSON body.");
        }
      }
    }
    const { db } = await database();
    if (route === "auth/login" && method === "POST") {
      const credentials = z
        .object({
          email: z.email().max(255),
          password: z.string().min(1).max(256),
          totp_code: z.string().optional(),
          recovery_code: z.string().max(128).optional(),
        })
        .parse(body);
      return json(await login(db, credentials));
    }
    if (route.startsWith("public/")) {
      const value = await publicCafe(db, route, request, body);
      if (value !== undefined) return json(value);
    }
    // Public QR endpoints cannot fall through into financial/catalog handlers.
    if (route.startsWith("cloud/"))
      throw new HttpError(
        410,
        "local_hub_gateway_retired",
        "The hosted Next.js application uses /api/public/cafe directly. Local Hub device, lease and synchronization APIs belong to the preserved original application.",
      );
    if (route.startsWith("public/"))
      throw new HttpError(404, "not_found", "Public endpoint unavailable.");
    const user = await currentUser(db, request);
    if (route === "auth/me" && method === "GET")
      return json(await publicUser(db, user));
    if (route === "auth/logout" && method === "POST") {
      await db
        .collection("users")
        .updateOne({ id: user.id }, { $inc: { token_version: 1 } });
      return json({ message: "Logged out." });
    }
    const authResult = await authActions(db, user, route, method, body);
    if (authResult !== undefined) return json(authResult);
    const userResult = await ventureUsers(db, user, route, method, body);
    if (userResult !== undefined) return json(userResult);
    if (route.startsWith("auth/"))
      throw new HttpError(
        404,
        "not_found",
        "Authentication endpoint unavailable.",
      );
    if (route === "ventures" && method === "GET") {
      allow(user, ["super_admin"]);
      return json(
        await db
          .collection("companies")
          .find({ business_group_id: user.business_group_id, is_active: true })
          .toArray(),
      );
    }
    if (route === "venture-users" && method === "GET") {
      allow(user, ["super_admin"]);
      const users = await db
        .collection<Row>("users")
        .find({ business_group_id: user.business_group_id })
        .toArray();
      return json(await Promise.all(users.map((u) => publicUser(db, u))));
    }
    if (route === "tax-operation/combined-turnover" && method === "GET") {
      allow(user, ["super_admin"]);
      const ventures = [];
      let total = 0;
      for (const company of await db
        .collection<Row>("companies")
        .find({ business_group_id: user.business_group_id, is_active: true })
        .toArray()) {
        let value = 0;
        for (const invoice of await db
          .collection("invoices")
          .find({
            company_id: company.id,
            status: { $nin: ["draft", "cancelled", "returned"] },
          })
          .toArray())
          value += scaled(invoice.grand_total);
        total += value;
        ventures.push({
          company_id: company.id,
          company_name: company.name,
          business_type: company.business_type,
          turnover: decimal(value),
        });
      }
      return json({
        business_group_id: user.business_group_id,
        ventures,
        combined_turnover: decimal(total),
        review_notice:
          "Recorded native web invoices only; legacy PostgreSQL history is not imported.",
      });
    }
    if (
      ["dashboard/consolidated", "exports/consolidated"].includes(route) &&
      method === "GET"
    ) {
      const report = await consolidated(db, user, url);
      return route.startsWith("exports/")
        ? csv(report.venture_summaries, "kalpvriksh-consolidated")
        : json(report);
    }
    if (
      user.role === "kitchen" &&
      !/^(cafe\/kitchen\/orders|cafe\/orders\/[^/]+\/(start-preparing|mark-ready)|cafe\/menu\/items\/\d+\/availability)$/.test(
        route,
      )
    )
      throw new HttpError(
        403,
        "forbidden",
        "Kitchen accounts can only access kitchen work.",
      );
    const scope = await scoped(db, user, request);
    if (
      method === "GET" &&
      /^dashboard\/(overview|sales|inventory|purchase-orders)$/.test(route)
    )
      return json(await dashboard(db, scope, url, route.split("/")[1]));
    if (route === "purchase-orders/from-recommendations" && method === "POST") {
      allow(user, managers);
      requireValue(
        Array.isArray(body.items) &&
          body.items.length > 0 &&
          body.items.length <= 100,
        "Select 1–100 reorder lines.",
      );
      return json(
        await transaction(async (db, session) => {
          const groups = new Map<string, Row[]>();
          for (const item of body.items) {
            const product = await requiredRow(
              db,
              "products",
              {
                company_id: scope.company.id,
                id: Number(item.product_id),
                is_active: true,
              },
              session,
            );
            await authorizedBranch(db, scope, item.branch_id, session);
            const key = `${item.branch_id}:${product.supplier_id}`;
            const list = groups.get(key) ?? [];
            list.push({ ...item, supplier_id: product.supplier_id });
            groups.set(key, list);
          }
          const result = [];
          for (const items of groups.values())
            result.push(
              await purchases(
                db,
                scope,
                "purchase-orders",
                "POST",
                {
                  id: 0,
                  branch_id: items[0].branch_id,
                  supplier_id: items[0].supplier_id,
                  items,
                },
                url,
                null,
                { db, session },
              ),
            );
          return result;
        }),
      );
    }
    if (route.startsWith("purchase-orders")) {
      const value = await purchases(
        db,
        scope,
        route,
        method,
        body,
        url,
        request.headers.get("idempotency-key"),
      );
      if (value !== undefined) return json(value);
    }
    if (route === "sales" && method === "POST") {
      allow(user, sellers);
      requireValue(
        scaled(body.tax_rate ?? "0") === 0,
        "Use GST POS checkout for taxed sales; manual tax-rate overrides are disabled.",
      );
      const items = Array.isArray(body.items)
        ? body.items.map((i: Row) => ({
            product_id: i.product_id,
            quantity: i.quantity,
            unit_price: i.unit_price,
            discount: i.discount_amount ?? "0",
          }))
        : [];
      const payload = {
        id: 0,
        branch_id: body.branch_id,
        invoice_type: "non_gst",
        invoice_date: body.sale_datetime,
        items,
      } as Row;
      const calculated = await quote(db, scope, payload, false);
      const cash = await db.collection<Row>("payment_modes").findOne({
        company_id: scope.company.id,
        is_active: true,
        mode_type: "cash",
      });
      requireValue(cash, "Configure a Cash payment mode.");
      const result = await checkout(
        scope,
        {
          ...payload,
          payments: [
            { payment_mode_id: cash.id, amount: calculated.grand_total },
          ],
        },
        request.headers.get("idempotency-key"),
        false,
      );
      requireValue(result, "Sale did not complete.");
      return json({
        ...result.invoice,
        sale_number: result.invoice.invoice_number,
        sale_datetime: result.invoice.invoice_date,
        total_amount: result.invoice.grand_total,
        tax_total: decimal(
          scaled(result.invoice.cgst_total) +
            scaled(result.invoice.sgst_total) +
            scaled(result.invoice.igst_total) +
            scaled(result.invoice.cess_total),
        ),
        units_sold: decimal(
          result.invoice.items.reduce(
            (n: number, i: Row) => n + scaled(i.quantity),
            0,
          ),
        ),
        item_count: result.invoice.items.length,
        gross_profit: decimal(
          result.invoice.items.reduce(
            (n: number, i: Row) => n + signed(i.gross_profit),
            0,
          ),
        ),
        items: result.invoice.items.map((i: Row) => ({
          ...i,
          product_sku: i.sku_snapshot,
          product_name: i.product_name_snapshot,
          discount_amount: i.discount,
        })),
      });
    }
    if (method === "GET" && /^sales(?:\/(summary|trends|\d+))?$/.test(route)) {
      allow(user, [...sellers, "analyst"]);
      if (route === "sales/summary")
        return json(await salesSummary(db, scope, url));
      if (route === "sales/trends")
        return json((await salesAnalytics(db, scope, url)).sales_trend);
      const rows = await salesRows(
        db,
        scope,
        url,
        url.searchParams.has("start_date") || url.searchParams.has("end_date")
          ? undefined
          : { start: "1970-01-01", end: businessDate() },
      );
      if (route === "sales")
        return json(
          rows.slice(
            0,
            Math.min(500, Number(url.searchParams.get("limit") ?? 100)),
          ),
        );
      const row = rows.find((r) => r.id === Number(route.split("/")[1]));
      if (!row) throw new HttpError(404, "not_found", "Sale unavailable.");
      return json(row);
    }
    if (
      method === "GET" &&
      [
        "exports/sales",
        "exports/inventory",
        "exports/purchase-orders",
        "exports/forecasts",
      ].includes(route)
    ) {
      allow(user, [...managers, "analyst"]);
      const name = route.split("/")[1];
      const rows =
        name === "forecasts"
          ? await forecasts(db, scope, "forecasts", "GET", body, url)
          : name === "sales"
            ? await salesRows(db, scope, url)
            : name === "inventory"
              ? await inventoryRows(
                  db,
                  scope,
                  url.searchParams.has("branch_id")
                    ? Number(url.searchParams.get("branch_id"))
                    : undefined,
                )
              : await purchases(
                  db,
                  scope,
                  "purchase-orders",
                  "GET",
                  body,
                  url,
                  null,
                );
      requireValue(Array.isArray(rows), "Export rows unavailable.");
      const exportRows =
        name === "sales"
          ? rows.flatMap((row) =>
              (row.items as Row[]).map((item) => ({
                sale_number: row.sale_number,
                sale_datetime: row.sale_datetime,
                branch_id: row.branch_id,
                branch_name: row.branch_name,
                product_id: item.product_id,
                sku: item.product_sku,
                product_name: item.product_name,
                category_name: item.category_name,
                quantity: item.quantity,
                unit_price: item.unit_price,
                discount: item.discount,
                line_total: item.line_total,
                gross_profit: item.gross_profit,
              })),
            )
          : name === "purchase-orders"
            ? rows.flatMap((row) =>
                (row.items as Row[]).map((item) => ({
                  po_number: row.po_number,
                  status: row.status,
                  order_date: row.order_date,
                  branch_name: row.branch_name,
                  supplier_name: row.supplier_name,
                  ...item,
                })),
              )
            : rows;
      return csv(exportRows, name);
    }
    if (
      route.startsWith("customers/") ||
      route === "customer-ledger/outstanding"
    ) {
      const value = await customerRoutes(db, scope, route, method, body, url);
      if (value !== undefined) return json(value);
    }
    if (
      route.startsWith("invoices") ||
      route.startsWith("cafe/billing/invoices/")
    ) {
      const value = await financial(
        db,
        scope,
        route,
        method,
        body,
        request.headers.get("idempotency-key"),
      );
      if (value !== undefined) return json(value);
    }
    const billResult = await cafeBillingRoutes(
      db,
      scope,
      route,
      method,
      body,
      request.headers.get("idempotency-key"),
    );
    if (billResult !== undefined) return json(billResult);
    const qrResult = await qrRoutes(db, scope, route, method, body, url.origin);
    if (qrResult !== undefined) return json(qrResult);
    const cafeResult = await cafeRoutes(db, scope, route, method, body, url);
    if (cafeResult !== undefined) return json(cafeResult);
    const governanceResult = await governance(
      db,
      scope,
      route,
      method,
      body,
      request.headers.get("idempotency-key"),
    );
    if (governanceResult !== undefined) return json(governanceResult);
    if (route.startsWith("ai/")) {
      const value = await assistant(db, scope, route, method, body, url);
      if (value !== undefined) return json(value);
    }
    if (route.startsWith("forecasts")) {
      const value = await forecasts(db, scope, route, method, body, url);
      if (value !== undefined) return json(value);
    }
    if (route === "inventory/reorder-recommendations" && method === "GET")
      return json(await recommendations(db, scope, url));
    const inventoryDetail = route.match(/^inventory\/(\d+)$/);
    if (inventoryDetail && method === "GET") {
      const product = await requiredRow(db, "products", {
        company_id: scope.company.id,
        id: Number(inventoryDetail[1]),
      });
      const rows = (await inventoryRows(db, scope)).filter(
        (r) => r.product_id === product.id,
      );
      return json({
        product_id: product.id,
        product_sku: product.sku,
        product_name: product.name,
        category_name: rows[0]?.category_name ?? "",
        supplier_name: rows[0]?.supplier_name ?? "",
        total_quantity_on_hand: decimal(
          rows.reduce((n, r) => n + scaled(r.quantity_on_hand), 0),
        ),
        total_stock_value: decimal(
          rows.reduce((n, r) => n + scaled(r.stock_value), 0),
        ),
        is_low_stock_any_branch: rows.some((r) => r.is_low_stock),
        inventory: rows,
      });
    }
    const deactivateResource = route.match(
      /^(products|customers)\/(\d+)\/deactivate$/,
    );
    if (deactivateResource && method === "PATCH")
      return json(
        await catalog(
          db,
          scope,
          deactivateResource[1],
          deactivateResource[2],
          "PATCH",
          { id: 0, is_active: false },
          url,
        ),
      );
    const consistencyResult = await consistency(db, scope, route, method);
    if (consistencyResult !== undefined) return json(consistencyResult);
    const settingsResult = await settings(db, scope, route, method, body, url);
    if (settingsResult !== undefined) return json(settingsResult);
    if (route === "ventures/current" && method === "GET")
      return json(scope.company);
    if (route === "business-profile" && method === "GET")
      return json(
        await db
          .collection("business_profiles")
          .findOne({ company_id: scope.company.id }),
      );
    if (route === "invoice-sequences" && method === "GET")
      return json(
        await db
          .collection("invoice_sequences")
          .find({ company_id: scope.company.id })
          .toArray(),
      );
    if (route === "pos/quote" && method === "POST")
      return json(await quote(db, scope, body, false));
    if (
      (route === "pos/checkout" || route === "cafe/billing/pos/checkout") &&
      method === "POST"
    ) {
      const cafe = route.startsWith("cafe/");
      const result = await checkout(
        scope,
        body,
        request.headers.get("idempotency-key"),
        cafe,
      );
      if (!result) throw new Error("Transaction returned no invoice.");
      return json(
        cafe
          ? {
              receipt: receipt(result.invoice),
              closed: true,
              idempotent_replay: result.replay,
              order_status: "closed",
              table_session_status: null,
            }
          : result.invoice,
      );
    }
    if (route.startsWith("invoices") || route.startsWith("cafe/billing/"))
      allow(user, [...sellers, "analyst"]);
    const receiptMatch = route.match(
      /^cafe\/billing\/invoices\/(\d+)\/receipt$/,
    );
    if (receiptMatch && method === "GET") {
      const invoice = await db.collection<Row>("invoices").findOne({
        ...scope.filter,
        id: Number(receiptMatch[1]),
        source_type: { $in: ["cafe_takeaway", "cafe_table_session"] },
      });
      if (!invoice)
        throw new HttpError(404, "not_found", "Invoice unavailable.");
      return json(receipt(invoice));
    }
    if (route === "cafe/billing/invoices" && method === "GET")
      return json(await invoiceHistory(db, scope, url, true));
    if (route === "invoices" && method === "GET")
      return json(await invoiceHistory(db, scope, url));
    const invoiceMatch = route.match(/^invoices\/(\d+)$/);
    if (invoiceMatch && method === "GET") {
      const row = await db
        .collection("invoices")
        .findOne({ ...scope.filter, id: Number(invoiceMatch[1]) });
      if (!row) throw new HttpError(404, "not_found", "Invoice unavailable.");
      return json(row);
    }
    if (route === "products/search" && method === "GET")
      return json(
        await catalog(db, scope, "products", undefined, "GET", body, url),
      );
    if (route === "pos/products/search" && method === "GET") {
      const branch = await authorizedBranch(
        db,
        scope,
        Number(url.searchParams.get("branch_id")),
      );
      const products = (await catalog(
        db,
        scope,
        "products",
        undefined,
        "GET",
        body,
        url,
      )) as Row[];
      const result = [];
      for (const p of products) {
        const stock = await db.collection("inventory").findOne({
          company_id: scope.company.id,
          branch_id: branch.id,
          product_id: p.id,
        });
        result.push({
          ...p,
          product_id: p.id,
          primary_barcode: p.primary_barcode ?? p.barcode ?? null,
          quantity_on_hand: decimal(stock?.quantity_scaled ?? 0),
          available_quantity: decimal(stock?.quantity_scaled ?? 0),
          branch_id: branch.id,
          branch_name: branch.name,
          gst_rate: p.gst_rate_percent ?? "0.00",
        });
      }
      return json(result.slice(0, 50));
    }
    if (
      ["inventory", "inventory/low-stock"].includes(route) &&
      method === "GET"
    ) {
      let rows = await inventoryRows(
        db,
        scope,
        url.searchParams.has("branch_id")
          ? Number(url.searchParams.get("branch_id"))
          : undefined,
      );
      rows = rows.filter(
        (r) =>
          ["category_id", "supplier_id"].every(
            (k) =>
              !url.searchParams.has(k) ||
              Number(url.searchParams.get(k)) === r[k],
          ) &&
          (!url.searchParams.get("search") ||
            `${r.product_name} ${r.product_sku}`
              .toLowerCase()
              .includes(url.searchParams.get("search")!.toLowerCase())),
      );
      return json(
        route.endsWith("low-stock") ? rows.filter((r) => r.is_low_stock) : rows,
      );
    }
    if (route === "inventory/adjustments" && method === "POST") {
      const result = await adjust(scope, body);
      let rows = await inventoryRows(db, scope, Number(body.branch_id));
      return json({
        ...result,
        inventory: rows.find((r) => r.product_id === Number(body.product_id)),
      });
    }
    if (route === "inventory/movements" && method === "GET") {
      const filter = await queryScope(db, scope, url);
      for (const field of ["product_id", "movement_type"])
        if (url.searchParams.has(field))
          filter[field] =
            field === "product_id"
              ? Number(url.searchParams.get(field))
              : url.searchParams.get(field);
      const rows = await db
        .collection<Row>("stock_movements")
        .find(filter)
        .sort({ id: -1 })
        .limit(500)
        .toArray();
      for (const row of rows) {
        const product = await db
          .collection("products")
          .findOne({ id: row.product_id, company_id: scope.company.id });
        const branch = await db
          .collection("branches")
          .findOne({ id: row.branch_id, company_id: scope.company.id });
        row.product_name = product?.name ?? "";
        row.product_sku = product?.sku ?? "";
        row.branch_name = branch?.name ?? "";
      }
      return json(rows);
    }
    if (route === "cafe/orders" && method === "GET") {
      if (scope.company.business_type !== "cafe")
        throw new HttpError(403, "forbidden", "Cafe venture required.");
      return json(
        await db
          .collection("cafe_orders")
          .find(scope.filter)
          .sort({ id: -1 })
          .limit(500)
          .toArray(),
      );
    }
    if (route === "exports/cafe" && method === "GET") {
      if (scope.company.business_type !== "cafe")
        throw new HttpError(403, "forbidden", "Cafe venture required.");
      allow(user, ["super_admin", "admin", "store_manager", "analyst"]);
      const report = await cafeReport(db, scope, url);
      const lines = [
        "metric,value",
        ...Object.entries(report.kpis).map(([key, value]) => `${key},${value}`),
      ];
      return new Response(lines.join("\r\n"), {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": "attachment; filename=kalpvriksh-cafe.csv",
          "Cache-Control": "no-store",
        },
      });
    }
    if (route === "dashboard/cafe" && method === "GET") {
      allow(user, ["super_admin", "admin", "store_manager", "analyst"]);
      if (scope.company.business_type !== "cafe")
        throw new HttpError(403, "forbidden", "Cafe venture required.");
      return json(await cafeReport(db, scope, url));
    }
    if (route === "governance/closings" && method === "GET") {
      allow(user, managers);
      const branch = await authorizedBranch(
        db,
        scope,
        url.searchParams.get("branch_id"),
      );
      return json(
        await db.collection("business_day_closures").findOne({
          ...scope.filter,
          branch_id: branch.id,
          business_date: url.searchParams.get("business_date"),
        }),
      );
    }
    if (route === "governance/closings" && method === "POST")
      return json(await closing(scope, body));
    const closeMatch = route.match(
      /^governance\/closings\/(\d+)\/(submit|close|reopen)$/,
    );
    if (closeMatch && method === "POST")
      return json(
        await closing(scope, body, Number(closeMatch[1]), closeMatch[2]),
      );
    for (const name of resourceNames().sort((a, b) => b.length - a.length)) {
      if (route === name || route.startsWith(name + "/")) {
        const tail = route.slice(name.length).replace(/^\//, "");
        if (!tail || /^\d+$/.test(tail))
          return json(
            await catalog(
              db,
              scope,
              name,
              tail || undefined,
              method,
              body,
              url,
            ),
          );
      }
    }
    throw new HttpError(
      404,
      "not_found",
      `API ${method} /api/${route} is not defined.`,
    );
  } catch (error) {
    if (error instanceof HttpError)
      return json(
        { error: { code: error.code, message: error.message } },
        error.status,
      );
    if (error instanceof z.ZodError)
      return json(
        {
          error: {
            code: "validation_error",
            message: "Request validation failed.",
            details: error.issues,
          },
        },
        422,
      );
    if (
      error &&
      typeof error === "object" &&
      "code" in error &&
      error.code === 11000
    )
      return json(
        {
          error: {
            code: "conflict",
            message:
              "A record with this identity already exists. Retry the original request.",
          },
        },
        409,
      );
    return json(
      {
        error: {
          code: "service_unavailable",
          message:
            "The operation could not complete. Check server configuration and database availability.",
        },
      },
      503,
    );
  }
}
