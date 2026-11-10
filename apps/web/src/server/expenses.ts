import type { ClientSession, Db } from "mongodb";

import { authorizedBranch } from "./billing";
import { type Row } from "./db";
import { HttpError, requireValue } from "./errors";
import { writableDay } from "./financial";
import { businessDate, decimal, scaled } from "./money";
import {
  audit,
  dateOnly,
  insertRow,
  now,
  period,
  queryScope,
  requiredRow,
  transaction,
} from "./query";
import { allow, managers, type Scope } from "./security";

export const EXPENSE_CATEGORIES = [
  "maintenance",
  "utilities",
  "rent",
  "wages",
  "cleaning",
  "repairs",
  "transport",
  "marketing",
  "licenses",
  "stock_purchase",
  "miscellaneous",
] as const;

const PAYMENT_MODES = [
  "cash",
  "upi",
  "card",
  "bank_transfer",
  "credit",
  "other",
] as const;

function boundedText(value: unknown, max: number, label: string, required = false) {
  const text = String(value ?? "").trim();
  requireValue(!required || text.length > 0, `${label} is required.`);
  requireValue(text.length <= max, `${label} is too long.`);
  return text || null;
}

export async function insertExpenseRecord(
  db: Db,
  scope: Scope,
  input: Row,
  session: ClientSession,
  options: { checkWritableDay?: boolean } = {},
) {
  const branch = await authorizedBranch(db, scope, Number(input.branch_id), session);
  const expenseDate = dateOnly(input.expense_date ?? businessDate());
  if (options.checkWritableDay !== false)
    await writableDay(db, scope, branch.id, session, expenseDate);

  const amount = scaled(input.amount);
  requireValue(amount > 0, "Expense amount must be greater than zero.");

  const category = String(input.category ?? "").trim();
  requireValue(
    EXPENSE_CATEGORIES.includes(category as (typeof EXPENSE_CATEGORIES)[number]),
    "Choose a valid expense category.",
  );
  const paymentMode = String(input.payment_mode ?? "").trim();
  requireValue(
    PAYMENT_MODES.includes(paymentMode as (typeof PAYMENT_MODES)[number]),
    "Choose a valid expense payment mode.",
  );

  const row = await insertRow(
    db,
    "expenses",
    {
      company_id: scope.company.id,
      branch_id: branch.id,
      branch_name: branch.name,
      expense_date: expenseDate,
      category,
      description: boundedText(input.description, 240, "Description", true),
      amount: decimal(amount),
      payment_mode: paymentMode,
      vendor_name: boundedText(input.vendor_name, 160, "Vendor"),
      reference_number: boundedText(input.reference_number, 160, "Reference"),
      notes: boundedText(input.notes, 1000, "Notes"),
      status: "posted",
      source_type: input.source_type ?? "manual",
      source_id: input.source_id ?? null,
      created_by: scope.user.id,
      created_by_name: scope.user.name,
      voided_by: null,
      voided_by_name: null,
      voided_at: null,
      void_reason: null,
    },
    session,
  );
  await audit(db, scope, "create", "expense", row.id, { category, branch_id: branch.id }, session);
  return row;
}

async function expenseFilter(db: Db, scope: Scope, url: URL) {
  const filter = await queryScope(db, scope, url);
  const { start, end } = period(url, 30);
  filter.expense_date = { $gte: start, $lte: end };
  for (const field of ["category", "payment_mode", "status"])
    if (url.searchParams.get(field)) filter[field] = url.searchParams.get(field);
  return filter;
}

export async function expensesRoutes(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  if (!route.startsWith("expenses")) return undefined;
  allow(scope.user, [...managers, "analyst"]);

  if (route === "expenses" && method === "GET") {
    const filter = await expenseFilter(db, scope, url);
    return db.collection<Row>("expenses").find(filter).sort({ expense_date: -1, id: -1 }).limit(1000).toArray();
  }

  if (route === "expenses/summary" && method === "GET") {
    const filter = await expenseFilter(db, scope, url);
    const rows = await db.collection<Row>("expenses").find({ ...filter, status: { $ne: "voided" } }).toArray();
    let total = 0, cash = 0, nonCash = 0, stockPurchases = 0;
    const byCategory: Record<string, string> = {};
    const categoryTotals = new Map<string, number>();
    for (const row of rows) {
      const amount = scaled(row.amount);
      total += amount;
      if (row.payment_mode === "cash") cash += amount;
      else nonCash += amount;
      if (row.category === "stock_purchase") stockPurchases += amount;
      categoryTotals.set(row.category, (categoryTotals.get(row.category) ?? 0) + amount);
    }
    for (const [category, amount] of categoryTotals) byCategory[category] = decimal(amount);
    return {
      total_expenses: decimal(total),
      cash_expenses: decimal(cash),
      non_cash_expenses: decimal(nonCash),
      stock_purchase_expenses: decimal(stockPurchases),
      expense_count: rows.length,
      by_category: byCategory,
    };
  }

  if (route === "expenses" && method === "POST") {
    allow(scope.user, managers);
    return transaction((txDb, session) => insertExpenseRecord(txDb, scope, body, session));
  }

  const match = route.match(/^expenses\/(\d+)\/void$/);
  if (match && method === "POST") {
    allow(scope.user, managers);
    return transaction(async (txDb, session) => {
      const row = await requiredRow(
        txDb,
        "expenses",
        { ...scope.filter, id: Number(match[1]) },
        session,
      );
      requireValue(row.status === "posted", "Only a posted expense can be voided.");
      requireValue(row.source_type !== "stock_intake", "Linked stock-purchase expenses must be corrected from the stock transaction.");
      await writableDay(txDb, scope, row.branch_id, session, row.expense_date);
      const reason = boundedText(body.reason, 500, "Void reason", true);
      const values = {
        status: "voided",
        void_reason: reason,
        voided_by: scope.user.id,
        voided_by_name: scope.user.name,
        voided_at: now(),
        updated_at: now(),
      };
      await txDb.collection("expenses").updateOne(
        { id: row.id, company_id: scope.company.id, status: "posted" },
        { $set: values },
        { session },
      );
      await audit(txDb, scope, "void", "expense", row.id, { reason }, session);
      return { ...row, ...values };
    });
  }

  throw new HttpError(405, "method_not_allowed", "Expense operation unavailable.");
}
