import type { Db } from "mongodb";
import type { Row } from "./db";
import { type Scope, allow, managers } from "./security";
import { requiredRow, insertRow, now, shiftDate, transaction } from "./query";
import { inventoryAnalytics, dashboard } from "./dashboards";
import { recommendations, forecasts } from "./planning";
import { cafeReport } from "./reports";
import { businessDate } from "./money";
import { requireValue } from "./errors";
export async function assistant(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  if (!route.startsWith("ai/")) return undefined;
  allow(scope.user, [...managers, "analyst"]);
  const filter = {
    company_id: scope.company.id,
    user_id: scope.user.id,
    ...(scope.user.branch_id ? { branch_id: scope.user.branch_id } : {}),
  };
  if (route === "ai/sessions" && method === "GET")
    return db
      .collection("ai_sessions")
      .find(filter)
      .sort({ updated_at: -1 })
      .limit(50)
      .toArray();
  const match = route.match(/^ai\/sessions\/(\d+)$/);
  if (match && method === "GET") {
    const session = await requiredRow(db, "ai_sessions", {
      ...filter,
      id: Number(match[1]),
    });
    return {
      ...session,
      messages: await db
        .collection("ai_messages")
        .find({ company_id: scope.company.id, session_id: session.id })
        .sort({ id: 1 })
        .toArray(),
    };
  }
  if (route !== "ai/chat" || method !== "POST") return undefined;
  const message = String(body.message ?? "").trim();
  requireValue(
    message.length > 0 && message.length <= 2000,
    "Message must contain 1–2000 characters.",
  );
  const text = message.toLowerCase(),
    today = businessDate(),
    query = new URL(url);
  query.searchParams.set("end_date", today);
  query.searchParams.set(
    "start_date",
    text.includes("today") ? today : today.slice(0, 8) + "01",
  );
  if (text.includes("last month")) {
    const end = shiftDate(today.slice(0, 8) + "01", -1);
    query.searchParams.set("start_date", end.slice(0, 8) + "01");
    query.searchParams.set("end_date", end);
  }
  let intent = "unknown",
    response =
      "Ask about sales, low stock, reorder suggestions, top products, branch performance, slow-moving stock, purchase orders or forecasts.",
    requires_confirmation = false,
    suggested_action: string | null = null;
  const tools: {
    name: string;
    description: string;
    data: Record<string, unknown>;
  }[] = [];
  const tool = (name: string, data: Record<string, unknown>) => {
    intent = name;
    tools.push({
      name,
      description: "Scoped database-backed business analytics.",
      data,
    });
  };
  if (/delete|drop table|erase|remove permanently/.test(text)) {
    intent = "forbidden_write_action";
    response = "Business records cannot be deleted through chat.";
    requires_confirmation = true;
    suggested_action = "Write action refused";
  } else if (
    /approve|cancel|receive|adjust stock|update threshold|change threshold|submit purchase|mark ordered|create purchase|create po|place order/.test(
      text,
    )
  ) {
    intent = "confirmation_required";
    response =
      "Use the dedicated operational screen to review and confirm this change. No business records were changed.";
    requires_confirmation = true;
    suggested_action = "Confirm action in a dedicated workflow";
  } else if (
    scope.company.business_type === "cafe" &&
    /cafe|table|menu|billed|collection/.test(text)
  ) {
    const report = await cafeReport(db, scope, query);
    tool("get_cafe_summary", report);
    response = `Billed revenue INR ${report.kpis.billed_revenue}; collections INR ${report.kpis.collections}; outstanding INR ${report.kpis.outstanding}.`;
  } else if (/forecast|next week|demand/.test(text)) {
    const data = await forecasts(
      db,
      scope,
      "forecasts/run",
      "POST",
      {
        id: 0,
        forecast_type: "demand",
        horizon_days: 7,
        branch_id: scope.user.branch_id ?? null,
      },
      query,
    );
    requireValue(data && !Array.isArray(data), "Forecast unavailable.");
    tool("forecast_summary", data);
    response = data.message;
  } else if (/reorder|restock/.test(text)) {
    const items = (await recommendations(db, scope, query)).filter(
      (i) => Number(i.suggested_reorder_quantity) > 0,
    );
    tool("reorder_recommendations", {
      count: items.length,
      items: items.slice(0, 10),
    });
    response = items.length
      ? items
          .slice(0, 5)
          .map(
            (i) =>
              `${i.product_name}: ${i.suggested_reorder_quantity} units (${i.priority})`,
          )
          .join("; ")
      : "No reorder quantities are currently suggested.";
  } else if (/low.?stock|slow.moving|inventory/.test(text)) {
    if (text.includes("slow"))
      query.searchParams.set("start_date", shiftDate(today, -89));
    const data = await inventoryAnalytics(db, scope, query);
    requireValue("low_stock_items" in data, "Inventory analytics unavailable.");
    const items = text.includes("slow")
      ? data.slow_moving_stock
      : data.low_stock_items;
    tool(text.includes("slow") ? "slow_moving_products" : "low_stock_items", {
      summary: data.summary,
      items,
    });
    response = items.length
      ? items
          .slice(0, 5)
          .map(
            (i: Row) =>
              `${i.product_name} at ${i.branch_name}: ${i.quantity_on_hand} units`,
          )
          .join("; ")
      : "No matching inventory rows were found.";
  } else if (/purchase|pending.*order/.test(text)) {
    const data = await dashboard(db, scope, query, "purchase-orders");
    tool("pending_purchase_orders", data);
    response =
      "summary" in data && "pending_purchase_orders" in data.summary
        ? `${data.summary.pending_purchase_orders} open purchase orders; INR ${data.summary.total_open_order_value} open order value.`
        : "No open purchase orders.";
  } else if (/sales|revenue|profit|top|best|branch|sold/.test(text)) {
    const data = await dashboard(db, scope, query, "sales");
    requireValue(
      "summary" in data && "revenue" in data.summary,
      "Sales analytics unavailable.",
    );
    tool("sales_summary", data);
    response = `Revenue INR ${data.summary.revenue}; gross profit INR ${data.summary.gross_profit}; ${data.summary.transaction_count} transactions.`;
    if (/top|best/.test(text) && "top_products" in data)
      response +=
        " Top products: " +
        data.top_products
          .slice(0, 5)
          .map((i) => `${i.product_name} (${i.units_sold} units)`)
          .join("; ");
  }
  return transaction(async (db, session) => {
    const chat = body.session_id
      ? await requiredRow(
          db,
          "ai_sessions",
          { ...filter, id: Number(body.session_id) },
          session,
        )
      : await insertRow(
          db,
          "ai_sessions",
          {
            ...filter,
            branch_id: scope.user.branch_id ?? null,
            title: message.slice(0, 60),
            last_message: null,
          },
          session,
        );
    const user_message = await insertRow(
      db,
      "ai_messages",
      {
        company_id: scope.company.id,
        session_id: chat.id,
        sender: "user",
        message,
        metadata_json: null,
      },
      session,
    );
    const assistant_message = await insertRow(
      db,
      "ai_messages",
      {
        company_id: scope.company.id,
        session_id: chat.id,
        sender: "assistant",
        message: response,
        metadata_json: {
          intent,
          tool_calls: tools,
          provider: "deterministic",
          requires_confirmation,
          suggested_action,
        },
      },
      session,
    );
    await db
      .collection("ai_sessions")
      .updateOne(
        { id: chat.id, company_id: scope.company.id },
        { $set: { updated_at: now(), last_message: response } },
        { session },
      );
    return {
      session_id: chat.id,
      intent,
      response,
      tool_calls: tools,
      requires_confirmation,
      suggested_action,
      user_message,
      assistant_message,
    };
  });
}
