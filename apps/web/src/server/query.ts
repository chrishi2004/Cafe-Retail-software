import type { Db, ClientSession } from "mongodb";
import { database, nextId, type Row } from "./db";
import { authorizedBranch } from "./billing";
import { type Scope } from "./security";
import { HttpError, requireValue } from "./errors";
import { businessDate, DAY_MS, KOLKATA_OFFSET, isCalendarDate, shiftDate } from "../businessDates";
export { shiftDate } from "../businessDates";

export const now = () => new Date().toISOString();
export const signed = (value: unknown) => {
  const text = String(value ?? "0");
  const n = Number(text);
  requireValue(
    /^-?\d+(\.\d{1,2})?$/.test(text) && Number.isFinite(n),
    "Invalid decimal.",
  );
  return Math.round(n * 100);
};
export function dateOnly(value: unknown) {
  const text = String(value ?? "");
  requireValue(isCalendarDate(text), "Use a valid YYYY-MM-DD date.");
  return text;
}
export function invoiceInstant(value: unknown, fallback = new Date()) {
  if (value == null) return fallback;
  const text = typeof value === "string" ? value : "";
  // Date-only and offsetless input is a Kolkata date/time. Explicit offsets
  // (including the UTC timestamps sent by the POS) identify an absolute instant.
  const match = /^(\d{4}-\d{2}-\d{2})(?:T((?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,3})?)?)(Z|[+-]\d{2}:\d{2})?)?$/i.exec(text);
  requireValue(match && isCalendarDate(match[1]), "Invalid invoice date.");
  const instant = new Date(`${match[1]}T${match[2] ?? "00:00:00"}${match[3] ?? KOLKATA_OFFSET}`);
  requireValue(Number.isFinite(instant.getTime()), "Invalid invoice date.");
  return instant;
}

export function dateBounds(url: URL, defaultDay: string | null = null) {
  const from = url.searchParams.get("start_date");
  const to = url.searchParams.get("end_date");
  const start = from !== null ? dateOnly(from) : to === null ? defaultDay : null;
  const end = to !== null ? dateOnly(to) : from === null ? defaultDay : null;
  requireValue(!start || !end || start <= end, "Start date must precede end date.");
  return { start, end };
}
export function period(url: URL, days = 30) {
  const end = dateOnly(url.searchParams.get("end_date") ?? businessDate());
  const start = dateOnly(
    url.searchParams.get("start_date") ?? shiftDate(end, 1 - days),
  );
  requireValue(start <= end, "Start date must precede end date.");
  const length =
    Math.round((Date.parse(end) - Date.parse(start)) / DAY_MS) + 1;
  requireValue(length <= 3660, "Date range cannot exceed ten years.");
  return {
    start,
    end,
    previousStart: shiftDate(start, -length),
    previousEnd: shiftDate(start, -1),
  };
}
export async function queryScope(db: Db, scope: Scope, url: URL) {
  const filter = { ...scope.filter };
  if (url.searchParams.has("branch_id")) {
    const branch = await authorizedBranch(
      db,
      scope,
      url.searchParams.get("branch_id"),
    );
    filter.branch_id = branch.id;
  }
  return filter;
}
export async function requiredRow(
  db: Db,
  collection: string,
  filter: Record<string, unknown>,
  session?: ClientSession,
): Promise<Row> {
  const row = await db.collection<Row>(collection).findOne(filter, { session });
  if (!row) throw new HttpError(404, "not_found", "Record unavailable.");
  return row;
}
export async function transaction<T>(
  fn: (db: Db, session: ClientSession) => Promise<T>,
) {
  const { db, client } = await database();
  const session = client.startSession();
  try {
    return await session.withTransaction(() => fn(db, session), {
      readConcern: { level: "snapshot" },
      writeConcern: { w: "majority" },
      maxCommitTimeMS: 10000,
    });
  } finally {
    await session.endSession();
  }
}
export async function insertRow(
  db: Db,
  name: string,
  values: Record<string, unknown>,
  session?: ClientSession,
) {
  const row: Row = {
    ...values,
    id: await nextId(db, name, session),
    created_at: now(),
    updated_at: now(),
  };
  await db.collection<Row>(name).insertOne(row, { session });
  return row;
}
export async function audit(
  db: Db,
  scope: Scope,
  action: string,
  entity: string,
  id: number,
  details: Record<string, unknown>,
  session: ClientSession,
  context: { branchId?: number; reference?: string } = {},
) {
  await insertRow(
    db,
    "audit_events",
    {
      ...scope.filter,
      business_group_id: scope.user.business_group_id,
      branch_id: context.branchId ?? details.branch_id ?? scope.filter.branch_id ?? null,
      actor_id: scope.user.id,
      actor_name: scope.user.name,
      outcome: "recorded",
      ...(context.reference ? { record_reference: context.reference } : {}),
      action,
      entity_type: entity,
      entity_id: id,
      details,
    },
    session,
  );
}
export function csv(rows: Record<string, unknown>[], filename: string) {
  const columns = [
    ...new Set(
      rows.flatMap((row) =>
        Object.keys(row).filter(
          (k) => k !== "_id" && typeof row[k] !== "object",
        ),
      ),
    ),
  ];
  const escape = (value: unknown) => {
    let text = String(value ?? "");
    if (/^[=+@-]/.test(text) && !/^-?\d+(\.\d+)?$/.test(text))
      text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  return new Response(
    [
      columns.map(escape).join(","),
      ...rows.map((row) => columns.map((k) => escape(row[k])).join(",")),
    ].join("\r\n"),
    {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename=${filename}.csv`,
        "Cache-Control": "no-store",
      },
    },
  );
}
