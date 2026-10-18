import { randomBytes } from "node:crypto";
import { pathToFileURL } from "node:url";
import { z } from "zod";
import { database, disconnect, indexes, nextId, type Row } from "./db";
import { encrypt, hashPassword } from "./security";
export async function bootstrap() {
  const credentials = z
    .object({
      BOOTSTRAP_OWNER_EMAIL: z.email(),
      BOOTSTRAP_OWNER_PASSWORD: z.string().min(12),
      BOOTSTRAP_CAFE_CASHIER_EMAIL: z.email(),
      BOOTSTRAP_CAFE_CASHIER_PASSWORD: z.string().min(12),
      BOOTSTRAP_RETAIL_CASHIER_EMAIL: z.email(),
      BOOTSTRAP_RETAIL_CASHIER_PASSWORD: z.string().min(12),
    })
    .parse(process.env);
  const emails = [
    credentials.BOOTSTRAP_OWNER_EMAIL,
    credentials.BOOTSTRAP_CAFE_CASHIER_EMAIL,
    credentials.BOOTSTRAP_RETAIL_CASHIER_EMAIL,
  ].map((e) => e.toLowerCase());
  if (new Set(emails).size !== 3)
    throw new Error("Each bootstrap user needs a distinct email.");
  const { db, client } = await database();
  for (const collection of await db.listCollections().toArray())
    if (await db.collection(collection.name).countDocuments({}, { limit: 1 }))
      throw new Error(
        "Bootstrap is NEW database only. Existing data will not be changed.",
      );
  await indexes(db);
  const secret = Array.from(
    randomBytes(32),
    (n) => "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n % 32],
  ).join("");
  const session = client.startSession();
  try {
    await session.withTransaction(
      async () => {
        const now = new Date().toISOString();
        await db.collection("business_groups").insertOne(
          {
            id: 1,
            name: "Kalpvriksh Group",
            legal_name: process.env.BOOTSTRAP_LEGAL_NAME ?? "Kalpvriksh Group",
            default_currency: "INR",
            is_active: true,
          },
          { session },
        );
        const add = async (name: string, data: Record<string, unknown>) => {
          const row: Row = {
            id: await nextId(db, name, session),
            ...data,
            created_at: now,
            updated_at: now,
          };
          await db.collection(name).insertOne(row, { session });
          return row;
        };
        await add("users", {
          business_group_id: 1,
          company_id: null,
          branch_id: null,
          name: "Owner",
          email: emails[0],
          role: "super_admin",
          password_hash: await hashPassword(
            credentials.BOOTSTRAP_OWNER_PASSWORD,
          ),
          token_version: 1,
          is_active: true,
          mfa_enabled: true,
          mfa_secret_encrypted: encrypt(secret),
        });
        for (const [index, type] of ["cafe", "retail"].entries()) {
          const name =
            type === "cafe" ? "Kalpvriksh Cafe" : "Kalpvriksh Retail";
          const company = await add("companies", {
            business_group_id: 1,
            business_type: type,
            slug: type,
            code: type.toUpperCase(),
            name,
            legal_name: process.env.BOOTSTRAP_LEGAL_NAME ?? name,
            trade_name: name,
            is_active: true,
            is_demo: false,
          });
          const branch = await add("branches", {
            company_id: company.id,
            name: process.env.BOOTSTRAP_BRANCH_NAME ?? "Main Branch",
            address: "",
            city: "",
            is_active: true,
            write_version: 0,
          });
          await add("business_profiles", {
            company_id: company.id,
            legal_name: company.legal_name,
            trade_name: name,
            tax_registration_status: "unregistered",
            default_tax_mode: "non_gst",
            customer_details_on_bill: "basic",
            b2b_gst_enabled: false,
            include_customer_in_gst_reports: false,
            default_currency: "INR",
          });
          for (const mode of ["Cash", "UPI", "Card"])
            await add("payment_modes", {
              company_id: company.id,
              name: mode,
              mode_type: mode.toLowerCase(),
              requires_reference: false,
              is_active: true,
            });
          await add("invoice_sequences", {
            company_id: company.id,
            branch_id: branch.id,
            invoice_type: "non_gst_invoice",
            fiscal_year: "continuous",
            prefix: type === "cafe" ? "CAFE-" : "RETAIL-",
            suffix: null,
            next_number: 1,
            padding: 6,
            reset_rule: "never",
            is_active: true,
          });
          await add("users", {
            business_group_id: 1,
            company_id: company.id,
            branch_id: branch.id,
            name: `${name} Cashier`,
            email: emails[index + 1],
            role: "staff",
            password_hash: await hashPassword(
              type === "cafe"
                ? credentials.BOOTSTRAP_CAFE_CASHIER_PASSWORD
                : credentials.BOOTSTRAP_RETAIL_CASHIER_PASSWORD,
            ),
            token_version: 1,
            is_active: true,
            mfa_enabled: false,
          });
        }
      },
      { writeConcern: { w: "majority" } },
    );
  } finally {
    await session.endSession();
  }
  return { owner: emails[0], totpSecret: secret };
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  bootstrap()
    .then((result) => {
      console.log(
        "New isolated Kalpvriksh web database configured. No orders, invoices, customers or stock were seeded.",
      );
      console.log("Owner:", result.owner);
      console.log(
        "Add this TIME-BASED manual key to your authenticator and store securely:",
        result.totpSecret,
      );
    })
    .catch(() => {
      console.error(
        "Bootstrap refused or failed. Verify external configuration and that the database is empty.",
      );
      process.exitCode = 1;
    })
    .finally(disconnect);
}
