import {
  randomBytes,
  scrypt as derive,
  timingSafeEqual,
  createHash,
  createHmac,
  createCipheriv,
  createDecipheriv,
} from "node:crypto";
import { promisify } from "node:util";
import { SignJWT, jwtVerify } from "jose";
import { type Db } from "mongodb";
import { type Row } from "./db";
import { HttpError, requireValue } from "./errors";
const scrypt = promisify(derive);
export const managers = ["admin", "super_admin", "store_manager"];
export const sellers = [...managers, "staff", "order_taker"];
export function secret() {
  const value = process.env.AUTH_SECRET;
  if (!value || value.length < 32 || value.startsWith("REPLACE"))
    throw new Error("AUTH_SECRET requires at least 32 random characters.");
  return value;
}
export async function hashPassword(value: string) {
  requireValue(
    value.length >= 12,
    "Password must have at least 12 characters.",
  );
  const salt = randomBytes(16).toString("hex");
  return `scrypt$${salt}$${((await scrypt(value, salt, 64)) as Buffer).toString("hex")}`;
}
export async function verifyPassword(value: string, hash: string) {
  const [algorithm, salt, expected] = hash.split("$");
  if (algorithm !== "scrypt" || !salt || !expected) return false;
  const actual = (await scrypt(value, salt, 64)) as Buffer;
  const wanted = Buffer.from(expected, "hex");
  return wanted.length === actual.length && timingSafeEqual(actual, wanted);
}
export function digest(value: string) {
  return createHash("sha256").update(value).digest("hex");
}
export function encrypt(value: string) {
  const iv = randomBytes(12);
  const c = createCipheriv(
    "aes-256-gcm",
    createHash("sha256").update(secret()).digest(),
    iv,
  );
  return Buffer.concat([
    iv,
    c.update(value),
    c.final(),
    c.getAuthTag(),
  ]).toString("base64");
}
export function decrypt(value: string) {
  const b = Buffer.from(value, "base64");
  const c = createDecipheriv(
    "aes-256-gcm",
    createHash("sha256").update(secret()).digest(),
    b.subarray(0, 12),
  );
  c.setAuthTag(b.subarray(-16));
  return Buffer.concat([c.update(b.subarray(12, -16)), c.final()]).toString();
}
export function totp(key: string, step = Math.floor(Date.now() / 30000)) {
  let bits = "";
  for (const char of key.replace(/=+$/, "").toUpperCase()) {
    const n = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".indexOf(char);
    if (n < 0) throw new Error("Invalid TOTP key.");
    bits += n.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8)
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const h = createHmac("sha1", Buffer.from(bytes)).update(counter).digest();
  const offset = h[19] & 15;
  return ((h.readUInt32BE(offset) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, "0");
}
export function verifiedTotpStep(key: string, code: string) {
  if (!/^\d{6}$/.test(code)) return null;
  const step = Math.floor(Date.now() / 30000);
  for (const candidate of [step - 1, step, step + 1])
    if (timingSafeEqual(Buffer.from(totp(key, candidate)), Buffer.from(code)))
      return candidate;
  return null;
}
export function allow(user: Row, roles: string[]) {
  if (!roles.includes(user.role))
    throw new HttpError(
      403,
      "forbidden",
      "This role cannot perform the action.",
    );
}
export type Scope = {
  user: Row;
  company: Row;
  filter: Record<string, unknown>;
};
export async function accountActive(db: Db, user: Row) {
  if (
    ![
      "super_admin",
      "admin",
      "store_manager",
      "staff",
      "order_taker",
      "kitchen",
      "analyst",
    ].includes(user.role)
  )
    throw new HttpError(401, "unauthorized", "Invalid role assignment.");
  const group = await db
    .collection<Row>("business_groups")
    .findOne({ id: user.business_group_id, is_active: true });
  if (!group)
    throw new HttpError(401, "unauthorized", "Account scope is inactive.");
  if (user.role === "super_admin") {
    if (user.company_id || user.branch_id)
      throw new HttpError(401, "unauthorized", "Invalid owner scope.");
    return;
  }
  const company = await db.collection<Row>("companies").findOne({
    id: user.company_id,
    business_group_id: user.business_group_id,
    is_active: true,
  });
  if (!company)
    throw new HttpError(401, "unauthorized", "Account scope is inactive.");
  if (user.role === "admin" && user.branch_id)
    throw new HttpError(
      401,
      "unauthorized",
      "Company admins cannot be restricted to a branch.",
    );
  if (
    company.business_type === "retail" &&
    ["order_taker", "kitchen"].includes(user.role)
  )
    throw new HttpError(401, "unauthorized", "Invalid Retail role.");
  if (
    ["staff", "store_manager", "order_taker", "kitchen"].includes(user.role) &&
    !user.branch_id
  )
    throw new HttpError(401, "unauthorized", "Branch assignment is required.");
  if (
    user.branch_id &&
    !(await db
      .collection("branches")
      .findOne({ id: user.branch_id, company_id: company.id, is_active: true }))
  )
    throw new HttpError(401, "unauthorized", "Invalid branch scope.");
}
export async function currentUser(db: Db, request: Request) {
  const token = request.headers.get("authorization")?.replace(/^Bearer /, "");
  if (!token) throw new HttpError(401, "unauthorized", "Login is required.");
  let payload;
  try {
    payload = (
      await jwtVerify(token, new TextEncoder().encode(secret()), {
        algorithms: ["HS256"],
        issuer: "kalpvriksh-web",
        audience: "kalpvriksh-web",
      })
    ).payload;
  } catch {
    throw new HttpError(401, "unauthorized", "Session expired.");
  }
  const user = await db.collection<Row>("users").findOne({
    id: Number(payload.sub),
    is_active: true,
    token_version: payload.version,
  });
  if (!user) throw new HttpError(401, "unauthorized", "Session revoked.");
  await accountActive(db, user);
  if (["admin", "super_admin"].includes(user.role) && !user.mfa_enabled)
    throw new HttpError(
      403,
      "mfa_required",
      "Privileged accounts require MFA.",
    );
  return user;
}
export async function scoped(
  db: Db,
  user: Row,
  request: Request,
): Promise<Scope> {
  const header = request.headers.get("x-venture-id");
  let companyId = user.company_id;
  if (user.role === "super_admin") {
    requireValue(
      header && /^\d+$/.test(header),
      "Choose an authorized venture.",
    );
    companyId = Number(header);
  } else if (header && Number(header) !== companyId)
    throw new HttpError(
      403,
      "forbidden",
      "Cannot switch outside your company.",
    );
  const company = await db.collection<Row>("companies").findOne({
    id: companyId,
    business_group_id: user.business_group_id,
    is_active: true,
  });
  if (!company) throw new HttpError(404, "not_found", "Venture unavailable.");
  return {
    user,
    company,
    filter: {
      company_id: company.id,
      ...(user.branch_id ? { branch_id: user.branch_id } : {}),
    },
  };
}
export async function publicUser(db: Db, user: Row) {
  const company = user.company_id
    ? await db.collection("companies").findOne({ id: user.company_id })
    : null;
  return {
    id: user.id,
    business_group_id: user.business_group_id,
    company_id: user.company_id,
    branch_id: user.branch_id,
    name: user.name,
    email: user.email,
    role: user.role,
    is_active: user.is_active,
    mfa_enabled: !!user.mfa_enabled,
    company_name: company?.name ?? null,
    company_slug: company?.slug ?? null,
    company_business_type: company?.business_type ?? null,
    permissions: [],
  };
}
export async function login(db: Db, body: Record<string, unknown>) {
  const email = String(body.email ?? "")
    .trim()
    .toLowerCase();
  const password = String(body.password ?? "");
  requireValue(
    email.length < 256 && password.length <= 256,
    "Invalid credentials.",
  );
  const attempts = db.collection("login_attempts");
  const key = digest(email);
  const gate = await attempts.findOneAndUpdate(
    { _id: key as never },
    {
      $inc: { count: 1 },
      $setOnInsert: { expires_at: new Date(Date.now() + 15 * 60000) },
    },
    { upsert: true, returnDocument: "after" },
  );
  if (gate && gate.expires_at < new Date()) {
    await attempts.deleteOne({ _id: key as never });
  } else if ((gate?.count ?? 0) > 10)
    throw new HttpError(
      429,
      "rate_limited",
      "Too many login attempts. Retry later.",
    );
  const user = await db
    .collection<Row>("users")
    .findOne({ email, is_active: true });
  if (!user || !(await verifyPassword(password, user.password_hash)))
    throw new HttpError(
      401,
      "unauthorized",
      "Email, password or authenticator code is invalid.",
    );
  await accountActive(db, user);
  if (user.mfa_enabled && body.recovery_code) {
    const consumed = await db
      .collection("users")
      .updateOne(
        {
          id: user.id,
          is_active: true,
          mfa_recovery_hashes: digest(String(body.recovery_code)),
        },
        {
          $pull: {
            mfa_recovery_hashes: digest(String(body.recovery_code)),
          } as never,
        },
      );
    if (!consumed.modifiedCount)
      throw new HttpError(
        401,
        "unauthorized",
        "Invalid or already used recovery code.",
      );
  } else if (user.mfa_enabled) {
    const step = verifiedTotpStep(
      decrypt(user.mfa_secret_encrypted),
      String(body.totp_code ?? ""),
    );
    if (step === null)
      throw new HttpError(
        401,
        "unauthorized",
        "Email, password or authenticator code is invalid.",
      );
    const consumed = await db.collection("users").updateOne(
      {
        id: user.id,
        $or: [
          { last_totp_step: { $lt: step } },
          { last_totp_step: { $exists: false } },
        ],
      },
      { $set: { last_totp_step: step } },
    );
    if (!consumed.modifiedCount)
      throw new HttpError(
        401,
        "unauthorized",
        "Use a fresh authenticator code.",
      );
  } else if (["admin", "super_admin"].includes(user.role))
    throw new HttpError(
      403,
      "mfa_required",
      "Privileged accounts require MFA enrollment through the bootstrap console.",
    );
  await attempts.deleteOne({ _id: key as never });
  const expires = new Date(Date.now() + 8 * 3600000);
  const token = await new SignJWT({ version: user.token_version })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("kalpvriksh-web")
    .setAudience("kalpvriksh-web")
    .setSubject(String(user.id))
    .setIssuedAt()
    .setExpirationTime(Math.floor(expires.getTime() / 1000))
    .sign(new TextEncoder().encode(secret()));
  return {
    access_token: token,
    token_type: "bearer",
    expires_at: expires.toISOString(),
    user: await publicUser(db, user),
  };
}
