import { randomBytes } from "node:crypto";
import type { Db } from "mongodb";
import type { Row } from "./db";
import {
  allow,
  accountActive,
  publicUser,
  hashPassword,
  verifyPassword,
  encrypt,
  decrypt,
  digest,
  verifiedTotpStep,
} from "./security";
import { HttpError, requireValue } from "./errors";
import { insertRow, transaction, now } from "./query";
export function enrollment(email: string) {
  const secret = Array.from(
    randomBytes(32),
    (n) => "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n % 32],
  ).join("");
  const recovery_codes = Array.from({ length: 8 }, () =>
    randomBytes(16).toString("hex"),
  );
  return {
    secret,
    recovery_codes,
    provisioning_uri: `otpauth://totp/${encodeURIComponent("Kalpvriksh:" + email)}?secret=${secret}&issuer=Kalpvriksh&digits=6&period=30`,
  };
}
export function requireStepUp(user: Row) {
  if (
    !user.last_step_up_at ||
    Date.now() - Date.parse(user.last_step_up_at) > 5 * 60000
  )
    throw new HttpError(
      403,
      "step_up_required",
      "Re-enter credentials before this sensitive action.",
    );
}
export async function authActions(
  db: Db,
  user: Row,
  route: string,
  method: string,
  body: Row,
) {
  if (route === "auth/admin-check" && method === "GET") {
    allow(user, ["super_admin", "admin"]);
    return { message: "Admin access granted." };
  }
  if (route === "auth/branch-scope" && method === "GET")
    return {
      all_branches: !user.branch_id,
      branch_ids: user.branch_id ? [user.branch_id] : [],
    };
  if (
    ["auth/step-up", "governance/step-up"].includes(route) &&
    method === "POST"
  ) {
    if (
      !(await verifyPassword(String(body.password ?? ""), user.password_hash))
    )
      throw new HttpError(401, "unauthorized", "Invalid credentials.");
    if (user.mfa_enabled) {
      const step = verifiedTotpStep(
        decrypt(user.mfa_secret_encrypted),
        String(body.totp_code ?? ""),
      );
      if (step === null)
        throw new HttpError(
          401,
          "unauthorized",
          "A current authenticator code is required.",
        );
    }
    await db
      .collection("users")
      .updateOne({ id: user.id }, { $set: { last_step_up_at: now() } });
    return { message: "Step-up authentication completed." };
  }
  if (route === "auth/mfa/enroll" && method === "POST") {
    requireValue(!user.mfa_enabled, "MFA is already enabled.");
    const values = enrollment(user.email);
    await db
      .collection("users")
      .updateOne(
        { id: user.id, mfa_enabled: { $ne: true } },
        {
          $set: {
            mfa_pending_encrypted: encrypt(values.secret),
            mfa_pending_recovery_hashes: values.recovery_codes.map(digest),
            mfa_pending_expires_at: new Date(
              Date.now() + 15 * 60000,
            ).toISOString(),
          },
        },
      );
    return values;
  }
  if (route === "auth/mfa/confirm" && method === "POST") {
    requireValue(
      !user.mfa_enabled &&
        user.mfa_pending_encrypted &&
        Date.parse(user.mfa_pending_expires_at) > Date.now(),
      "Start a fresh MFA enrollment.",
    );
    const step = verifiedTotpStep(
      decrypt(user.mfa_pending_encrypted),
      String(body.totp_code ?? ""),
    );
    requireValue(step !== null, "Invalid authenticator code.");
    const updated = await db
      .collection("users")
      .updateOne(
        {
          id: user.id,
          mfa_pending_encrypted: user.mfa_pending_encrypted,
          mfa_enabled: { $ne: true },
        },
        {
          $set: {
            mfa_enabled: true,
            mfa_secret_encrypted: user.mfa_pending_encrypted,
            mfa_recovery_hashes: user.mfa_pending_recovery_hashes,
            last_totp_step: step,
          },
          $unset: {
            mfa_pending_encrypted: "",
            mfa_pending_recovery_hashes: "",
            mfa_pending_expires_at: "",
          },
          $inc: { token_version: 1 },
        },
      );
    requireValue(updated.modifiedCount === 1, "Enrollment changed. Retry.");
    return { message: "MFA enabled. Sign in again." };
  }
  if (route === "auth/mfa/disable" && method === "POST") {
    requireValue(
      !["super_admin", "admin"].includes(user.role),
      "Privileged accounts must retain MFA. Use the trusted reset command to replace a lost authenticator.",
    );
    requireValue(
      user.mfa_enabled &&
        (await verifyPassword(String(body.password ?? ""), user.password_hash)),
      "Invalid credentials.",
    );
    const step = verifiedTotpStep(
      decrypt(user.mfa_secret_encrypted),
      String(body.totp_code ?? ""),
    );
    requireValue(step !== null, "Invalid authenticator code.");
    await db
      .collection("users")
      .updateOne(
        { id: user.id },
        {
          $set: { mfa_enabled: false },
          $unset: {
            mfa_secret_encrypted: "",
            mfa_recovery_hashes: "",
            last_totp_step: "",
          },
          $inc: { token_version: 1 },
        },
      );
    return { message: "MFA disabled. Sign in again." };
  }
  return undefined;
}
export async function ventureUsers(
  db: Db,
  user: Row,
  route: string,
  method: string,
  body: Row,
) {
  const match = route.match(/^venture-users(?:\/(\d+))?$/);
  if (!match || method === "GET") return undefined;
  allow(user, ["super_admin"]);
  requireStepUp(user);
  requireValue(
    (method === "POST" && !match[1]) || (method === "PUT" && match[1]),
    "Unsupported user operation.",
  );
  return transaction(async (db, session) => {
    const existing = match[1]
      ? await db
          .collection<Row>("users")
          .findOne(
            { id: Number(match[1]), business_group_id: user.business_group_id },
            { session },
          )
      : null;
    if (match[1] && !existing)
      throw new HttpError(404, "not_found", "User unavailable.");
    const values: Row = {
      id: existing?.id ?? 0,
      business_group_id: user.business_group_id,
      name: existing?.name ?? String(body.name ?? "").trim(),
      email:
        existing?.email ??
        String(body.email ?? "")
          .toLowerCase()
          .trim(),
      role: body.role,
      company_id: body.company_id ?? null,
      branch_id: body.branch_id ?? null,
      is_active: body.is_active !== false,
    };
    requireValue(
      values.name.length >= 2 &&
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email),
      "Valid name and email required.",
    );
    requireValue(
      !["admin", "super_admin"].includes(values.role) ||
        !!existing?.mfa_enabled,
      "Privileged users must first enroll MFA as a non-privileged user.",
    );
    if (values.id === user.id)
      requireValue(
        values.role === "super_admin" && values.is_active,
        "Cannot remove your own owner access.",
      );
    await accountActive(db, values);
    if (existing) {
      await db
        .collection("users")
        .updateOne(
          { id: existing.id, business_group_id: user.business_group_id },
          { $set: values, $inc: { token_version: 1 } },
          { session },
        );
      return publicUser(db, { ...existing, ...values });
    }
    const created = await insertRow(
      db,
      "users",
      {
        ...values,
        password_hash: await hashPassword(String(body.password ?? "")),
        mfa_enabled: false,
        token_version: 1,
      },
      session,
    );
    return publicUser(db, created);
  });
}
