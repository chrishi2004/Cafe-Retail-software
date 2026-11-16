import { randomBytes } from "node:crypto";
import type { ClientSession, Db, Filter } from "mongodb";
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
  setSessionControl,
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
const STEP_UP_MS = 5 * 60_000;

function stepUpExpiry(user: Row) {
  if (!user.session_fingerprint) return null;
  const expiry = Date.parse(user.last_step_up_at) + STEP_UP_MS;
  return expiry > Date.now() ? expiry : null;
}

export function requireStepUp(user: Row) {
  if (!stepUpExpiry(user))
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
  if (route === "governance/step-up" && method === "GET") {
    allow(user, ["super_admin", "admin"]);
    const expiry = stepUpExpiry(user);
    return { remaining_ms: expiry ? Math.max(0, expiry - Date.now()) : 0 };
  }
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
    await setSessionControl(db, user, { verified_at: now() });
    return { message: "Step-up authentication completed.", remaining_ms: STEP_UP_MS };
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
    await transaction(async (db, session) => {
      const updated = await db.collection("users").updateOne(
        {
          id: user.id,
          token_version: user.token_version,
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
        { session },
      );
      requireValue(updated.modifiedCount === 1, "Enrollment changed. Retry.");
      await employeeAudit(db, user, user, "mfa_enabled", {}, session, "security_account");
    });
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
    await transaction(async (db, session) => {
      const updated = await db.collection("users").updateOne(
        { id: user.id, token_version: user.token_version, mfa_enabled: true, mfa_secret_encrypted: user.mfa_secret_encrypted },
        {
          $set: { mfa_enabled: false },
          $unset: {
            mfa_secret_encrypted: "",
            mfa_recovery_hashes: "",
            last_totp_step: "",
          },
          $inc: { token_version: 1 },
        },
        { session },
      );
      requireValue(updated.modifiedCount === 1, "Account security changed. Retry.");
      await employeeAudit(db, user, user, "mfa_disabled", {}, session, "security_account");
    });
    return { message: "MFA disabled. Sign in again." };
  }
  return undefined;
}
const workforceRoles = ["store_manager", "staff", "order_taker", "kitchen", "analyst"];
const branchRoles = ["staff", "order_taker", "kitchen"];
const employeeManagers = ["super_admin", "admin", "store_manager"];

function assignableRoles(actor: Row) {
  if (actor.role === "super_admin") return ["admin", ...workforceRoles];
  return actor.role === "admin" ? workforceRoles : branchRoles;
}

function employeeScope(actor: Row): Filter<Row> {
  return {
    business_group_id: actor.business_group_id,
    ...(actor.role === "super_admin" ? {} : {
      company_id: actor.company_id,
      role: { $in: assignableRoles(actor) },
    }),
    ...(actor.role === "store_manager" ? { branch_id: actor.branch_id } : {}),
  };
}

function canManage(actor: Row, target: Row) {
  return actor.id !== target.id && assignableRoles(actor).includes(target.role);
}

async function employeeView(db: Db, actor: Row, target: Row) {
  return {
    ...await publicUser(db, target),
    last_login_at: target.last_login_at ?? null,
    password_setup_required: target.password_setup_required === true,
    can_manage: canManage(actor, target),
  };
}

function optionalId(value: unknown, label: string) {
  requireValue(value === null || (Number.isSafeInteger(value) && Number(value) > 0), `Choose a valid ${label}.`);
  return value as number | null;
}

function setupCredential() {
  const code = randomBytes(32).toString("base64url");
  const expires = new Date(Date.now() + 60 * 60_000);
  return {
    setup: { code, expires_at: expires.toISOString() },
    fields: { password_setup_hash: digest(code), password_setup_expires_at: expires, password_setup_required: true },
  };
}

async function employeeAudit(db: Db, actor: Row, target: Row, action: string, details: object, session: ClientSession, entity = "user") {
  await insertRow(db, "audit_events", {
    business_group_id: actor.business_group_id,
    company_id: target.company_id, branch_id: target.branch_id,
    actor_id: actor.id, actor_name: actor.name, outcome: "recorded", action, entity_type: entity, entity_id: target.id, details,
  }, session);
}

export async function claimEmployeePassword(db: Db, body: Row) {
  const code = typeof body.code === "string" ? body.code : "";
  const password = typeof body.password === "string" ? body.password : "";
  const invalidLink = () => new HttpError(422, "invalid_setup_link", "This setup link is invalid or expired. Ask your administrator for a new one.");
  if (!/^[\w-]{43}$/.test(code)) throw invalidLink();
  const filter = {
    password_setup_hash: digest(code), is_active: true, password_setup_required: true,
    password_setup_expires_at: { $gt: new Date() },
  };
  if (!await db.collection<Row>("users").findOne(filter, { projection: { id: 1 } })) throw invalidLink();
  const passwordHash = await hashPassword(password);
  return transaction(async (db, session) => {
    const claimed = await db.collection<Row>("users").findOneAndUpdate(
      { ...filter, password_setup_expires_at: { $gt: new Date() } },
      {
        $set: { password_hash: passwordHash, password_setup_required: false, updated_at: now() },
        $unset: { password_setup_hash: "", password_setup_expires_at: "" },
        $inc: { token_version: 1 },
      },
      { session, returnDocument: "after" },
    );
    if (!claimed) throw invalidLink();
    await accountActive(db, claimed, session);
    await employeeAudit(db, claimed, claimed, "employee_password_set", {}, session);
    return { message: "Password saved. Sign in to continue." };
  });
}

export async function ventureUsers(db: Db, actor: Row, route: string, method: string, body: Row) {
  const match = route.match(/^venture-users(?:\/(options|\d+)(\/password-reset)?)?$/);
  if (!match) return undefined;
  allow(actor, employeeManagers);
  const scope = employeeScope(actor);
  const roles = assignableRoles(actor);
  if (method === "GET" && route === "venture-users/options") {
    const companies = await db.collection<Row>("companies").find({
      business_group_id: actor.business_group_id, is_active: true,
      ...(actor.role !== "super_admin" ? { id: actor.company_id } : {}),
    }).toArray();
    const branches = await db.collection<Row>("branches").find({
      company_id: { $in: companies.map((c) => c.id) }, is_active: true,
      ...(actor.role === "store_manager" ? { id: actor.branch_id } : {}),
    }).toArray();
    return {
      roles,
      ventures: companies.map((c) => ({ id: c.id, name: c.name, type: c.business_type })),
      branches: branches.map((b) => ({ id: b.id, company_id: b.company_id, name: b.name })),
    };
  }
  if (method === "GET" && route === "venture-users") {
    const users = await db.collection<Row>("users").find(scope).sort({ name: 1, id: 1 }).toArray();
    return Promise.all(users.map((user) => employeeView(db, actor, user)));
  }
  const creating = method === "POST" && !match[1];
  const resetting = method === "POST" && !!match[2] && /^\d+$/.test(match[1] ?? "");
  const editing = method === "PUT" && !match[2] && /^\d+$/.test(match[1] ?? "");
  requireValue(creating || editing || resetting, "Unsupported user operation.");
  requireStepUp(actor);

  return transaction(async (txDb, session) => {
    // Write the actor's row so a concurrent scope change or deactivation
    // cannot leave a transaction using revoked management permissions.
    const freshActor = await txDb.collection<Row>("users").findOneAndUpdate(
      { id: actor.id, is_active: true, token_version: actor.token_version },
      { $inc: { staff_management_version: 1 } },
      { session, returnDocument: "after" },
    );
    if (!freshActor) throw new HttpError(401, "unauthorized", "Session changed. Sign in again.");
    await accountActive(txDb, freshActor, session);
    const control = await txDb.collection("auth_session_controls").findOne({ _id: actor.session_fingerprint }, { session });
    if (control?.revoked_at) throw new HttpError(401, "unauthorized", "Session revoked.");

    const existing = creating ? null : await txDb.collection<Row>("users").findOne(
      { ...scope, id: Number(match[1]) }, { session },
    );
    if (!creating && !existing) throw new HttpError(404, "not_found", "User unavailable.");
    if (existing && !canManage(actor, existing))
      throw new HttpError(403, "forbidden", "This account cannot be managed here.");

    if (resetting && existing) {
      requireValue(existing.is_active, "Activate the employee before resetting their password.");
      const credential = setupCredential();
      await txDb.collection<Row>("users").updateOne({ ...scope, id: existing.id }, {
        $set: { ...credential.fields, updated_at: now() }, $inc: { token_version: 1 },
      }, { session });
      await employeeAudit(txDb, actor, existing, "employee_password_reset", {}, session);
      return { setup: credential.setup };
    }

    requireValue(!Object.hasOwn(body, "password"), "Employee passwords must be set through the private setup link.");
    const role = body.role ?? existing?.role;
    requireValue(typeof role === "string" && roles.includes(role), "You cannot assign that role.");
    const name = body.name ?? existing?.name;
    const email = body.email ?? existing?.email;
    const active = body.is_active ?? existing?.is_active ?? true;
    requireValue(typeof name === "string" && name.trim().length >= 2 && name.length <= 120, "Enter a valid name (2–120 characters).");
    requireValue(typeof email === "string" && email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()), "Enter a valid email address.");
    requireValue(typeof active === "boolean", "Choose an active or inactive status.");
    const company = Object.hasOwn(body, "company_id") ? optionalId(body.company_id, "venture") :
      existing?.company_id ?? (actor.role === "super_admin" ? null : actor.company_id);
    const branch = Object.hasOwn(body, "branch_id") ? optionalId(body.branch_id, "branch") :
      existing?.branch_id ?? (actor.role === "store_manager" ? actor.branch_id : null);
    requireValue(company !== null, "Choose a venture.");
    requireValue(actor.role === "super_admin" || actor.company_id === company, "Choose an authorized venture.");
    requireValue(actor.role !== "store_manager" || actor.branch_id === branch, "Choose your assigned branch.");
    requireValue(role !== "admin" || !!existing?.mfa_enabled, "This employee must enroll in MFA with Account security before promotion to Venture Admin.");
    const values: Row = {
      id: existing?.id ?? 0,
      business_group_id: actor.business_group_id,
      name: name.trim(), email: email.trim().toLowerCase(),
      role, company_id: company, branch_id: branch, is_active: active,
    };
    const securityChanged = !!existing && ["role", "company_id", "branch_id", "email", "is_active"]
      .some((key) => (existing[key] ?? null) !== (values[key] ?? null));
    const assignmentChanged = !existing || ["role", "company_id", "branch_id"]
      .some((key) => (existing[key] ?? null) !== (values[key] ?? null));
    if (active || assignmentChanged) {
      try {
        await accountActive(txDb, values, session);
      } catch (error) {
        if (!(error instanceof HttpError)) throw error;
        throw new HttpError(422, "invalid_assignment", error.message);
      }
    }

    if (!existing) {
      requireValue(active, "Create an active employee before issuing a setup link.");
      const credential = setupCredential();
      const created = await insertRow(txDb, "users", {
        ...values, ...credential.fields, mfa_enabled: false, token_version: 1,
      }, session);
      await employeeAudit(txDb, actor, created, "employee_create", { role }, session);
      return { ...await employeeView(txDb, actor, created), setup: credential.setup };
    }

    await txDb.collection<Row>("users").updateOne({ ...scope, id: existing.id }, {
      $set: { ...values, updated_at: now() },
      ...(securityChanged ? { $inc: { token_version: 1 }, $unset: { password_setup_hash: "", password_setup_expires_at: "" } } : {}),
    }, { session });
    const changes = Object.keys(values).filter((key) => (existing[key] ?? null) !== (values[key] ?? null));
    const details = {
      fields: changes, previous_role: existing.role, role: values.role,
      previous_company_id: existing.company_id, previous_branch_id: existing.branch_id,
    };
    await employeeAudit(txDb, actor, values,
      existing.is_active !== active ? (active ? "employee_activate" : "employee_deactivate") :
        existing.role !== role ? "employee_role_change" : "employee_update", details, session);
    if (existing.is_active !== active && existing.role !== role)
      await employeeAudit(txDb, actor, values, "employee_role_change", details, session);
    return employeeView(txDb, actor, { ...existing, ...values });
  });
}
