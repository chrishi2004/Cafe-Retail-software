import {
  MongoClient,
  type ClientSession,
  type Db,
  type Document,
} from "mongodb";
export type Row = Document & { id: number };
let connection: Promise<MongoClient> | undefined;
export function databaseName() {
  const name = process.env.MONGODB_DB;
  if (!name || !/^kalpvriksh_web_[a-z0-9_]+$/.test(name))
    throw new Error(
      "MONGODB_DB must name a separate kalpvriksh_web_* database.",
    );
  return name;
}
export async function database() {
  if (!process.env.MONGODB_URI)
    throw new Error("MONGODB_URI is not configured.");
  if (!connection)
    connection = new MongoClient(process.env.MONGODB_URI, {
      maxPoolSize: 10,
      serverSelectionTimeoutMS: 5000,
    })
      .connect()
      .catch((error) => {
        connection = undefined;
        throw error;
      });
  const client = await connection;
  return { client, db: client.db(databaseName()) };
}
export async function nextId(db: Db, name: string, session?: ClientSession) {
  const counter = await db
    .collection<{ _id: string; value: number }>("counters")
    .findOneAndUpdate(
      { _id: name },
      { $inc: { value: 1 } },
      { upsert: true, returnDocument: "after", session },
    );
  if (!counter) throw new Error("Counter allocation failed.");
  return counter.value;
}
export async function indexes(db: Db) {
  for (const name of [
    "business_groups",
    "companies",
    "branches",
    "users",
    "products",
    "categories",
    "suppliers",
    "customers",
    "payment_modes",
    "invoice_sequences",
    "business_profiles",
    "menu_categories",
    "menu_items",
    "cafe_tables",
    "cafe_orders",
    "inventory",
    "stock_movements",
    "invoices",
    "invoice_payments",
    "business_day_closures",
  ])
    await db.collection(name).createIndex({ id: 1 }, { unique: true });
  await db.collection("users").createIndex({ email: 1 }, { unique: true });
  await db
    .collection("companies")
    .createIndex({ business_group_id: 1, slug: 1 }, { unique: true });
  await db
    .collection("products")
    .createIndex({ company_id: 1, sku: 1 }, { unique: true });
  await db
    .collection("inventory")
    .createIndex(
      { company_id: 1, branch_id: 1, product_id: 1 },
      { unique: true },
    );
  await db
    .collection("invoices")
    .createIndex({ company_id: 1, invoice_number: 1 }, { unique: true });
  await db
    .collection("invoices")
    .createIndex({ company_id: 1, idempotency_key: 1 }, { unique: true });
  await db
    .collection("business_day_closures")
    .createIndex(
      { company_id: 1, branch_id: 1, business_date: 1 },
      { unique: true },
    );
  await db
    .collection("login_attempts")
    .createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });
}
export async function disconnect() {
  if (connection) {
    await (await connection).close();
    connection = undefined;
  }
}
