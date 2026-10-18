import { requireStepUp } from "./accounts";
import type { Db } from "mongodb";
import { type Row } from "./db";
import { type Scope, allow, managers } from "./security";
import { requireValue, HttpError } from "./errors";
import {
  transaction,
  requiredRow,
  insertRow,
  audit,
  now,
  dateOnly,
} from "./query";
import { decimal, scaled, businessDate } from "./money";
import { authorizedBranch } from "./billing";
const fields = [
  "legal_name",
  "trade_name",
  "pan",
  "email",
  "phone",
  "address",
  "city",
  "state",
  "state_code",
  "pincode",
  "gstin",
  "default_currency",
  "terms_and_conditions",
];
const gstPattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
export function safeFields(body: Row, names: string[]) {
  const values: Record<string, unknown> = {};
  for (const name of names)
    if (body[name] !== undefined) {
      requireValue(
        body[name] === null ||
          (["string", "boolean", "number"].includes(typeof body[name]) &&
            String(body[name]).length <= 2000),
        `Invalid ${name}.`,
      );
      values[name] = body[name];
    }
  return values;
}
async function taxState(db: Db, scope: Scope) {
  const p = await requiredRow(db, "business_profiles", {
    company_id: scope.company.id,
  });
  const missing = [];
  if (p.tax_registration_status !== "registered")
    missing.push("registered tax status");
  if (!p.registration_active) missing.push("active GST registration");
  if (!gstPattern.test(p.gstin ?? "")) missing.push("GSTIN format");
  if (!p.state_code) missing.push("state code");
  if (
    !(await db
      .collection("invoice_sequences")
      .findOne({
        company_id: scope.company.id,
        invoice_type: "gst_invoice",
        is_active: true,
      }))
  )
    missing.push("active GST invoice sequence");
  return {
    company_id: scope.company.id,
    company_name: scope.company.name,
    tax_registration_status: p.tax_registration_status ?? "unregistered",
    default_tax_mode: p.default_tax_mode ?? "non_gst",
    gst_effective_from: p.gst_effective_from ?? null,
    customer_details_on_bill: p.customer_details_on_bill ?? "basic",
    b2b_gst_enabled: !!p.b2b_gst_enabled,
    include_customer_in_gst_reports: !!p.include_customer_in_gst_reports,
    gst_registration_id: p.gstin ? p.company_id : null,
    gst_registration_configured: !!p.gstin,
    gst_registration_active: !!p.registration_active,
    gstin_masked: p.gstin
      ? `${p.gstin.slice(0, 2)}*********${p.gstin.slice(-4)}`
      : null,
    can_activate_gst: missing.length === 0,
    missing_activation_prerequisites: missing,
    compliance_notice:
      "GST activation requires independent professional review.",
  };
}
export async function settings(
  db: Db,
  scope: Scope,
  route: string,
  method: string,
  body: Row,
  url: URL,
) {
  if (route === "business-profile") {
    if (method === "GET") {
      const profile = await requiredRow(db, "business_profiles", {
        company_id: scope.company.id,
      });
      return {
        ...profile,
        company_code: scope.company.code,
        business_profile_id: profile.id ?? scope.company.id,
        gst_registration_id: profile.gstin ? scope.company.id : null,
      };
    }
    if (method === "PUT") {
      allow(scope.user, ["super_admin", "admin"]);
      requireValue(
        !body.company_id || body.company_id === scope.company.id,
        "Cannot change another venture.",
      );
      const values = safeFields(body, fields);
      if (values.gstin)
        requireValue(gstPattern.test(String(values.gstin)), "Invalid GSTIN.");
      requireValue(
        !values.default_currency || values.default_currency === "INR",
        "Only INR is supported.",
      );
      return transaction(async (db, session) => {
        const current = await requiredRow(
          db,
          "business_profiles",
          { company_id: scope.company.id },
          session,
        );
        if (
          current.default_tax_mode === "gst" &&
          values.gstin !== undefined &&
          values.gstin !== current.gstin
        )
          throw new HttpError(
            409,
            "active_registration",
            "Cannot replace an active GST registration.",
          );
        await db
          .collection("business_profiles")
          .updateOne(
            { company_id: scope.company.id },
            { $set: { ...values, updated_at: now() } },
            { session },
          );
        await audit(
          db,
          scope,
          "update",
          "business_profile",
          scope.company.id,
          {},
          session,
        );
        return { ...current, ...values };
      });
    }
  }
  if (route === "tax-operation" && method === "GET") return taxState(db, scope);
  if (route === "tax-operation/settings" && method === "PUT") {
    allow(scope.user, ["super_admin"]);
    requireValue(
      ["unregistered", "registration_in_progress", "registered"].includes(
        body.tax_registration_status,
      ),
      "Invalid registration status.",
    );
    requireValue(
      ["basic", "full", "hidden"].includes(
        body.customer_details_on_bill ?? "basic",
      ),
      "Invalid bill detail setting.",
    );
    if (body.registration_id != null)
      requireValue(
        Number(body.registration_id) === scope.company.id,
        "Registration belongs to a different venture.",
      );
    const values = safeFields(body, [
      "tax_registration_status",
      "customer_details_on_bill",
      "b2b_gst_enabled",
      "include_customer_in_gst_reports",
      "registration_active",
    ]);
    if (values.tax_registration_status !== "registered") {
      values.default_tax_mode = "non_gst";
      values.gst_effective_from = null;
      values.registration_active = false;
    }
    await db
      .collection("business_profiles")
      .updateOne({ company_id: scope.company.id }, { $set: values });
    return taxState(db, scope);
  }
  if (route === "tax-operation/activate-gst" && method === "POST") {
    allow(scope.user, ["super_admin"]);
    requireStepUp(scope.user);
    requireValue(
      body.acknowledge_professional_review === true &&
        String(body.confirmation).trim().toUpperCase() === "ACTIVATE GST",
      "Professional review acknowledgement and ACTIVATE GST confirmation required.",
    );
    const effective = dateOnly(body.effective_from);
    requireValue(
      effective >= businessDate(),
      "GST activation cannot be backdated.",
    );
    const state = await taxState(db, scope);
    requireValue(
      state.can_activate_gst,
      `Complete prerequisites: ${state.missing_activation_prerequisites.join(", ")}.`,
    );
    await db
      .collection("business_profiles")
      .updateOne(
        { company_id: scope.company.id },
        {
          $set: {
            default_tax_mode: "gst",
            gst_effective_from: effective,
            updated_at: now(),
          },
        },
      );
    return taxState(db, scope);
  }
  const match = route.match(/^invoice-sequences(?:\/(\d+))?$/);
  if (match) {
    const id = match[1] ? Number(match[1]) : undefined;
    const decorate = (r: Row) => ({
      ...r,
      preview_next_number: `${r.prefix}${String(r.next_number).padStart(r.padding ?? 6, "0")}${r.suffix ?? ""}`,
    });
    if (method === "GET")
      return (
        await db
          .collection<Row>("invoice_sequences")
          .find({
            company_id: scope.company.id,
            ...(url.searchParams.get("include_inactive") === "true"
              ? {}
              : { is_active: true }),
            ...(scope.user.branch_id
              ? { branch_id: scope.user.branch_id }
              : {}),
          })
          .toArray()
      ).map(decorate);
    allow(scope.user, ["super_admin", "admin"]);
    requireValue(
      (method === "POST" && !id) || (method === "PUT" && id),
      "Unsupported sequence operation.",
    );
    return transaction(async (db, session) => {
      const old = id
        ? await requiredRow(
            db,
            "invoice_sequences",
            { id, company_id: scope.company.id },
            session,
          )
        : null;
      const values = {
        ...safeFields(body, [
          "prefix",
          "suffix",
          "invoice_type",
          "fiscal_year",
          "padding",
          "next_number",
          "reset_rule",
          "is_active",
        ]),
        branch_id: body.branch_id ?? old?.branch_id,
      };
      if (values.branch_id != null)
        await authorizedBranch(db, scope, values.branch_id, session);
      const next = Number(body.next_number ?? old?.next_number ?? 1),
        padding = Number(body.padding ?? old?.padding ?? 6);
      requireValue(
        Number.isSafeInteger(next) &&
          next >= 1 &&
          Number.isSafeInteger(padding) &&
          padding >= 1 &&
          padding <= 15,
        "Invalid sequence values.",
      );
      requireValue(
        [
          "gst_invoice",
          "non_gst_invoice",
          "credit_note",
          "purchase_bill",
        ].includes(String(body.invoice_type ?? old?.invoice_type)),
        "Invalid sequence type.",
      );
      requireValue(
        ["never", "fiscal_year", "calendar_year", "monthly"].includes(
          String(body.reset_rule ?? old?.reset_rule ?? "never"),
        ),
        "Invalid reset rule.",
      );
      if (old && old.last_generated_at) {
        requireValue(
          next >= old.next_number,
          "Sequence cannot move backwards.",
        );
        for (const field of [
          "prefix",
          "invoice_type",
          "branch_id",
          "reset_rule",
        ])
          requireValue(
            body[field] === undefined || body[field] === old[field],
            "Used sequence identity cannot be changed.",
          );
      }
      const row = old
        ? { ...old, ...values, next_number: next, padding, updated_at: now() }
        : await insertRow(
            db,
            "invoice_sequences",
            {
              ...values,
              company_id: scope.company.id,
              next_number: next,
              padding,
              is_active: body.is_active !== false,
              reset_rule: body.reset_rule ?? "never",
              fiscal_year: body.fiscal_year ?? "continuous",
              last_generated_at: null,
            },
            session,
          );
      if (old)
        await db
          .collection("invoice_sequences")
          .updateOne(
            { id, company_id: scope.company.id },
            {
              $set: {
                ...values,
                next_number: next,
                padding,
                updated_at: now(),
              },
            },
            { session },
          );
      await audit(
        db,
        scope,
        old ? "update" : "create",
        "invoice_sequence",
        row.id,
        {},
        session,
      );
      return decorate(row);
    });
  }
  return undefined;
}
