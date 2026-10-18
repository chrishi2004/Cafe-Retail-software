import type { Db, ClientSession } from "mongodb";
import { database, nextId, type Row } from "./db";
import { authorizedBranch } from "./billing";
import { type Scope } from "./security";
import { HttpError, requireValue } from "./errors";
import { businessDate } from "./money";

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
  requireValue(
    /^\d{4}-\d{2}-\d{2}$/.test(text) &&
      !Number.isNaN(Date.parse(text)) &&
      new Date(text).toISOString().slice(0, 10) === text,
    "Use a valid YYYY-MM-DD date.",
  );
  return text;
}
export const shiftDate = (day: string, n: number) =>
  new Date(Date.parse(day) + n * 86400000).toISOString().slice(0, 10);
export function period(url: URL, days = 30) {
  const end = dateOnly(url.searchParams.get("end_date") ?? businessDate());
  const start = dateOnly(
    url.searchParams.get("start_date") ?? shiftDate(end, 1 - days),
  );
  requireValue(start <= end, "Start date must precede end date.");
  const length =
    Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1;
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
  session?: ClientSession,
) {
  await insertRow(
    db,
    "audit_events",
    {
      ...scope.filter,
      actor_id: scope.user.id,
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
