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
import { cafeReport, range } from "./reports";
import { closing } from "./closing";
import { HttpError, pending, requireValue } from "./errors";
import { businessDate, decimal, scaled } from "./money";
const json = (data: unknown, status = 200) =>
  Response.json(data, { status, headers: { "Cache-Control": "no-store" } });
async function boundedBody(request:Request) {
 const reader=request.body?.getReader(); if(!reader)return '';
 const chunks:Uint8Array[]=[];let size=0;
 try { while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
  if(size>65536){await reader.cancel();throw new HttpError(413,'payload_too_large','Request body exceeds 64 KiB.');}
  chunks.push(value);
 } } finally { reader.releaseLock(); }
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
          recovery_code: z.string().optional(),
        })
        .parse(body);
      return json(await login(db, credentials));
    }
    // Public QR endpoints cannot fall through into financial/catalog handlers.
    if (route.startsWith("public/") || route.startsWith("cloud/"))
      pending("Public/cloud coordination API");
    const user = await currentUser(db, request);
    if (route === "auth/me" && method === "GET")
      return json(await publicUser(db, user));
    if (route === "auth/logout" && method === "POST") {
      await db
        .collection("users")
        .updateOne({ id: user.id }, { $inc: { token_version: 1 } });
      return json({ message: "Logged out." });
    }
    if (route.startsWith("auth/"))
      pending("Step-up, MFA management and account-administration API");
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
          .find({ company_id: company.id })
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
    const scope = await scoped(db, user, request);
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
        source_type: "cafe_takeaway",
      });
      if (!invoice)
        throw new HttpError(404, "not_found", "Invoice unavailable.");
      return json(receipt(invoice));
    }
    if (route === "cafe/billing/invoices" && method === "GET") {
      const { start, end } = range(url);
      const rows = await db
        .collection<Row>("invoices")
        .find({ ...scope.filter, source_type: "cafe_takeaway" })
        .sort({ id: -1 })
        .limit(500)
        .toArray();
      const items = rows
        .filter(
          (i) =>
            businessDate(new Date(i.invoice_date)) >= start &&
            businessDate(new Date(i.invoice_date)) <= end,
        )
        .map((i) => ({
          invoice_id: i.id,
          invoice_number: i.invoice_number,
          branch_id: i.branch_id,
          branch_name: i.branch_name,
          issued_at: i.issued_at,
          grand_total: i.grand_total,
          paid_amount: i.paid_amount,
          balance_due: i.balance_due,
          payment_status: i.payment_status,
          invoice_status: i.status,
          source_type: i.source_type,
          source_id: i.source_id,
        }));
      return json({ items, total: items.length, limit: 500, offset: 0 });
    }
    if (route === "invoices" && method === "GET")
      return json(
        await db
          .collection("invoices")
          .find(scope.filter)
          .sort({ id: -1 })
          .limit(500)
          .toArray(),
      );
    const invoiceMatch = route.match(/^invoices\/(\d+)$/);
    if (invoiceMatch && method === "GET") {
      const row = await db
        .collection("invoices")
        .findOne({ ...scope.filter, id: Number(invoiceMatch[1]) });
      if (!row) throw new HttpError(404, "not_found", "Invoice unavailable.");
      return json(row);
    }
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
          gst_rate: "0.00",
        });
      }
      return json(result.slice(0, 50));
    }
    if (
      ["inventory", "inventory/low-stock"].includes(route) &&
      method === "GET"
    ) {
      const rows = await inventoryRows(
        db,
        scope,
        url.searchParams.has("branch_id")
          ? Number(url.searchParams.get("branch_id"))
          : undefined,
      );
      return json(
        route.endsWith("low-stock") ? rows.filter((r) => r.is_low_stock) : rows,
      );
    }
    if (route === "inventory/adjustments" && method === "POST") {
      const result = await adjust(scope, body);
      const rows = await inventoryRows(db, scope, Number(body.branch_id));
      return json({
        ...result,
        inventory: rows.find((r) => r.product_id === Number(body.product_id)),
      });
    }
    if (route === "inventory/movements" && method === "GET")
      return json(
        await db
          .collection("stock_movements")
          .find(scope.filter)
          .sort({ id: -1 })
          .limit(500)
          .toArray(),
      );
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
    pending(`API ${method} /api/${route}`);
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
