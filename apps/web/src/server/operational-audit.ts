import type { Db, Filter } from "mongodb";
import { businessDate, BUSINESS_TIMEZONE, DAY_MS, shiftDate } from "../businessDates";
import type { Row } from "./db";
import { HttpError, requireValue } from "./errors";
import { dateOnly, invoiceInstant } from "./query";
import { allow } from "./security";

const groups = {
  employees: "Employees",
  billing: "Sales and billing",
  cancellations: "Invoice cancellations",
  refunds: "Refunds and payment corrections",
  inventory: "Inventory and stock feeds",
  expenses: "Expenses",
  purchasing: "Suppliers and purchasing",
  closing: "Daily Closing",
  security: "Security and configuration",
  other: "Other",
} as const;

type Category = keyof typeof groups;
const entityLabels: Record<string, string> = {
  user: "Employee", invoice: "Invoice", invoice_payment: "Invoice payment", customer_payment: "Customer payment",
  inventory: "Inventory", stock_movement: "Stock movement", stock_intake: "Stock feed", products: "Product",
  expense: "Expense", suppliers: "Supplier", purchase_order: "Purchase order", business_day_closure: "Daily Closing",
  security_account: "Account security", business_profile: "Business profile", invoice_sequence: "Invoice sequence",
  payment_modes: "Payment mode", tax_rates: "Tax rate", tax_operation: "Tax configuration", cafe_order: "Café order",
};
const actions: Record<string, string> = {
  employee_create: "Employee created", employee_update: "Employee updated", employee_activate: "Employee activated",
  employee_deactivate: "Employee deactivated", employee_role_change: "Employee role changed",
  employee_password_reset: "Password reset started", employee_password_set: "Employee password set", gst_activated: "GST activated",
  create: "Created", update: "Updated", activate: "Activated", deactivate: "Deactivated",
  role_changed: "Role changed", password_reset: "Password reset started", password_set: "Password set",
  issue: "Invoice issued", draft_create: "Draft created", record_payment: "Payment recorded", void: "Voided",
  cancel: "Cancelled", cancel_draft: "Draft cancelled", record_refund: "Refund recorded", payment_not_received: "Payment corrected",
  adjust: "Stock adjusted", receive: "Received", approve: "Approved", open: "Opened", submit: "Submitted",
  close: "Closed", reopen: "Reopened", purge: "Purged", mfa_enabled: "MFA enabled", mfa_disabled: "MFA disabled",
};
const rules: { category: Category; entities: string[]; only?: string[]; except?: string[] }[] = [
  { category: "employees", entities: ["user"] },
  { category: "cancellations", entities: ["invoice"], only: ["void", "cancel", "cancel_draft"] },
  { category: "refunds", entities: ["invoice_payment"], only: ["record_refund", "payment_not_received"] },
  { category: "billing", entities: ["invoice"], except: ["void", "cancel", "cancel_draft"] },
  { category: "billing", entities: ["invoice_payment"], except: ["record_refund", "payment_not_received"] },
  { category: "billing", entities: ["customer_payment", "cafe_order"] },
  { category: "inventory", entities: ["inventory", "stock_movement", "stock_intake", "products"] },
  { category: "expenses", entities: ["expense"] },
  { category: "purchasing", entities: ["suppliers", "purchase_order"] },
  { category: "closing", entities: ["business_day_closure"] },
  { category: "security", entities: ["security_account", "business_profile", "invoice_sequence", "payment_modes", "tax_rates", "tax_operation"] },
];
const matchesRule = (r: typeof rules[number]): Filter<Row> => ({
  entity_type: { $in: r.entities },
  ...(r.only ? { action: { $in: r.only } } : r.except ? { action: { $nin: r.except } } : {}),
});
const columns = ["timestamp_ist", "actor", "action", "category", "venture", "branch", "record", "reference", "outcome"] as const;
// Read only the fields needed for the screen; raw audit details and names of arbitrary keys never leave the server.
const projection = {
  _id: 0, id: 1, created_at: 1, actor_id: 1, actor_name: 1, company_id: 1, branch_id: 1,
  entity_type: 1, entity_id: 1, action: 1, record_reference: 1, outcome: 1,
  "details.branch_id": 1, "details.reversal_id": 1, "details.refund_id": 1,
};
const displayText = (value: unknown) => typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, 120) : "";
const positiveId = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
const referenceCode = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$/;
const isoUtc = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/;
const isoInstant = (value: unknown): value is string => typeof value === "string" && isoUtc.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value;
const clock = new Intl.DateTimeFormat("en-IN", { timeZone: BUSINESS_TIMEZONE, dateStyle: "medium", timeStyle: "medium" });

function filterId(params: URLSearchParams, key: string) {
  const raw = params.get(key);
  if (!raw) return null;
  const value = Number(raw);
  requireValue(/^\d+$/.test(raw) && positiveId(value), `Invalid ${key.replaceAll("_", " ")}.`);
  return value;
}

function parseCursor(value: string) {
  let cursor: unknown;
  try {
    if (/^[\w-]{1,120}$/.test(value)) cursor = JSON.parse(Buffer.from(value, "base64url").toString());
  } catch { /* Report a single validation error below. */ }
  requireValue(Array.isArray(cursor) && cursor.length === 2 && isoInstant(cursor[0]) && positiveId(cursor[1]), "Invalid audit page cursor.");
  return cursor as [string, number];
}

function csvCell(value: string | null) {
  const text = value ?? "";
  return '"' + (/^[=+@-]/.test(text) ? "'" + text : text).replaceAll('"', '""') + '"';
}

async function auditScope(db: Db, group: number) {
  const companies = await db.collection<Row>("companies").find({ business_group_id: group }, {
    projection: { _id: 0, id: 1, name: 1, business_type: 1 },
  }).sort({ name: 1 }).toArray();
  const [branches, actors] = await Promise.all([
    db.collection<Row>("branches").find({ company_id: { $in: companies.map(c => c.id) } }, {
      projection: { _id: 0, id: 1, name: 1, company_id: 1 },
    }).sort({ name: 1 }).toArray(),
    db.collection<Row>("users").find({ business_group_id: group }, {
      projection: { _id: 0, id: 1, name: 1 },
    }).sort({ name: 1 }).toArray(),
  ]);
  return { companies, branches, actors };
}

const privateHeaders = { "Cache-Control": "private, no-store" };

export async function operationalAudit(db: Db, user: Row, route: string, method: string, url: URL) {
  allow(user, ["super_admin"]);
  if (route !== "audit/events" && route !== "audit/options") throw new HttpError(404, "not_found", "Audit endpoint unavailable.");
  if (method !== "GET") throw new HttpError(405, "method_not_allowed", "Audit history is read-only.");
  const group: number = user.business_group_id;
  const { companies, branches, actors } = await auditScope(db, group);
  if (route === "audit/options") return Response.json({
    companies, branches, actors, categories: Object.entries(groups).map(([id, label]) => ({ id, label })),
  }, { headers: privateHeaders });

  const params = url.searchParams;
  const end = dateOnly(params.get("end_date") ?? businessDate());
  const start = dateOnly(params.get("start_date") ?? shiftDate(end, -6));
  requireValue(start <= end && Date.parse(end) - Date.parse(start) < 366 * DAY_MS, "Choose a date range of up to 366 days.");
  const companyId = filterId(params, "company_id");
  const branchId = filterId(params, "branch_id");
  const actorId = filterId(params, "actor_id");
  const category = params.get("category") as Category | null;
  const reference = (params.get("reference") ?? "").trim();
  const limit = filterId(params, "limit") ?? 30;
  const cursor = params.get("cursor");
  const format = params.get("format");
  const exportCsv = format === "csv";
  requireValue(!format || exportCsv, "Unknown audit export format.");
  requireValue(limit <= 100 && (!exportCsv || !cursor), "Invalid audit page size or export cursor.");
  requireValue(!reference || referenceCode.test(reference), "Enter an invoice number or transaction ID.");
  requireValue(!category || Object.hasOwn(groups, category), "Unknown audit category.");
  requireValue(companyId === null || companies.some(c => c.id === companyId), "Choose an authorized venture.");
  const branch = branches.find(b => b.id === branchId);
  requireValue(branchId === null || (branch && (!companyId || branch.company_id === companyId)), "Choose an authorized branch for this venture.");
  requireValue(actorId === null || actors.some(a => a.id === actorId), "Choose an authorized employee.");
  const selectedCompany = companyId ?? branch?.company_id;
  const companyFilter = selectedCompany ? [selectedCompany] : companies.map(c => c.id);
  const filters: Filter<Row>[] = [
    { $or: [
      ...(!selectedCompany ? [{ business_group_id: group, company_id: null }] : []),
      { company_id: { $in: companyFilter }, $or: [{ business_group_id: group }, { business_group_id: { $exists: false } }] },
    ] },
    { created_at: { $gte: invoiceInstant(start).toISOString(), $lt: invoiceInstant(shiftDate(end, 1)).toISOString() } },
  ];
  if (branchId) filters.push({ $or: [{ branch_id: branchId }, { branch_id: null, "details.branch_id": branchId }] });
  if (actorId) filters.push({ actor_id: actorId });
  if (category) filters.push(category === "other" ? { $nor: rules.map(matchesRule) } : { $or: rules.filter(r => r.category === category).map(matchesRule) });
  if (reference) {
    const code = new RegExp(`^${reference.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, "i");
    const id = Number(reference);
    const invoiceQuery = { company_id: { $in: companyFilter }, invoice_number: code };
    const [invoices, reversals] = await Promise.all([
      db.collection<Row>("invoices").find(invoiceQuery, { projection: { _id: 0, id: 1, company_id: 1 } }).toArray(),
      db.collection<Row>("financial_reversals").find(invoiceQuery, { projection: { _id: 0, invoice_id: 1, company_id: 1 } }).toArray(),
    ]);
    const refs: Filter<Row>[] = [{ record_reference: code }];
    for (const row of [...invoices, ...reversals]) {
      const invoiceId = row.invoice_id ?? row.id;
      if (positiveId(invoiceId)) refs.push({ entity_type: "invoice", entity_id: invoiceId, company_id: row.company_id });
    }
    if (/^\d+$/.test(reference) && positiveId(id)) refs.push({ entity_id: id }, { "details.reversal_id": id }, { "details.refund_id": id });
    filters.push({ $or: refs });
  }
  if (cursor) {
    const [timestamp, id] = parseCursor(cursor);
    filters.push({ $or: [{ created_at: { $lt: timestamp } }, { created_at: timestamp, id: { $lt: id } }] });
  }
  const cap = exportCsv ? 5000 : limit;
  const docs = await db.collection<Row>("audit_events").find({ $and: filters }, { projection })
    .sort({ created_at: -1, id: -1 }).limit(cap + 1).toArray();
  requireValue(!exportCsv || docs.length <= cap, "This export exceeds 5,000 events. Choose a shorter date range or add a filter.");
  const companyNames = new Map(companies.map(c => [c.id, displayText(c.name)]));
  const branchById = new Map(branches.map(b => [b.id, b]));
  const actorNames = new Map(actors.map(a => [a.id, displayText(a.name)]));
  const rows = docs.slice(0, cap).map(doc => {
    const type: string = doc.entity_type;
    const action: string = doc.action;
    const category = rules.find(r => r.entities.includes(type) && (!r.only || r.only.includes(action)) && !r.except?.includes(action))?.category ?? "other";
    const recordedBranch = branchById.get(doc.branch_id ?? doc.details?.branch_id);
    const safeReference = typeof doc.record_reference === "string" && referenceCode.test(doc.record_reference) ? doc.record_reference : null;
    const reversalId = doc.details?.reversal_id;
    const refundId = doc.details?.refund_id;
    return {
      id: doc.id,
      timestamp_ist: isoInstant(doc.created_at) ? `${clock.format(new Date(doc.created_at))} IST` : null,
      actor: actorNames.has(doc.actor_id) ? (displayText(doc.actor_name) || actorNames.get(doc.actor_id) || `Employee #${doc.actor_id}`) : null,
      action: Object.hasOwn(actions, action) ? actions[action] : "Recorded action",
      category: groups[category],
      venture: companyNames.get(doc.company_id) ?? null,
      branch: recordedBranch && recordedBranch.company_id === doc.company_id ? displayText(recordedBranch.name) : null,
      record: positiveId(doc.entity_id) ? `${Object.hasOwn(entityLabels, type) ? entityLabels[type] : "Record"} #${doc.entity_id}` : null,
      reference: safeReference ?? (category === "cancellations" && positiveId(reversalId) ? `Reversal #${reversalId}` : category === "refunds" && positiveId(refundId) ? `Refund #${refundId}` : null),
      outcome: doc.outcome === "recorded" ? "Recorded" : null,
    };
  });
  if (exportCsv) return new Response([columns.join(","), ...rows.map(row => columns.map(column => csvCell(row[column])).join(","))].join("\r\n"), {
    headers: { ...privateHeaders, "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": `attachment; filename="operational-audit-${start}-${end}.csv"` },
  });
  const last = docs[cap - 1];
  return Response.json({ rows, next_cursor: docs.length > cap && last ? Buffer.from(JSON.stringify([last.created_at, last.id])).toString("base64url") : null }, { headers: privateHeaders });
}
