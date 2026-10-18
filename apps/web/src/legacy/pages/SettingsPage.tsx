import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  KeyRound,
  LockKeyhole,
  Network,
  ReceiptText,
  Save,
  Server,
  Settings2,
  ShieldCheck,
} from "lucide-react";

import {
  createInvoiceSequence,
  createPaymentMode,
  createTaxRate,
  getBusinessProfile,
  listInvoiceSequences,
  listPaymentModes,
  listTaxRates,
  updateBusinessProfile,
  updateInvoiceSequence,
  updatePaymentMode,
  updateTaxRate,
} from "../api/businessSettings";
import { ApiError } from "../api/client";
import { ErrorState, LoadingState, MetricCard } from "../components/ui";
import { useAuth } from "../auth/AuthContext";
import type {
  BusinessProfilePayload,
  InvoiceSequence,
  InvoiceSequencePayload,
  InvoiceSequenceResetRule,
  InvoiceSequenceType,
  PageMetric,
  PaymentMode,
  PaymentModePayload,
  PaymentModeType,
  TaxMode,
  TaxRate,
  TaxRatePayload,
} from "../types";

const settingsMetrics: PageMetric[] = [
  {
    label: "Database",
    value: "Local only",
    detail: "PostgreSQL is not exposed to remote browsers.",
    tone: "blue",
  },
  {
    label: "GST foundation",
    value: "Configurable",
    detail: "Business profile, tax rates, and invoice sequence.",
    tone: "green",
  },
  {
    label: "Payments",
    value: "Modes stored",
    detail: "Cash, UPI, card, bank transfer, and credit setup.",
    tone: "amber",
  },
  {
    label: "Compliance",
    value: "Review needed",
    detail: "GST reports must be checked by a CA before filing.",
    tone: "slate",
  },
];

const checklist = [
  "Change demo admin credentials before sharing a remote URL.",
  "Expose the dashboard/API only; keep database port 5432 private.",
  "Take a fresh local backup before migrations, seed resets, or remote demos.",
  "Use HTTPS, Cloudflare Access, Tailscale ACLs, or ngrok access controls where practical.",
  "Have GST settings and reports reviewed by a CA before any real filing.",
];

const paymentModeTypes: PaymentModeType[] = [
  "cash",
  "upi",
  "card",
  "bank_transfer",
  "wallet",
  "cheque",
  "credit",
  "other",
];

const invoiceTypes: InvoiceSequenceType[] = [
  "gst_invoice",
  "non_gst_invoice",
  "credit_note",
  "purchase_bill",
];

const resetRules: InvoiceSequenceResetRule[] = ["never", "fiscal_year", "calendar_year", "monthly"];

const profileDefaults: BusinessProfilePayload = {
  company_code: "HYBRID_RETAIL",
  legal_name: "",
  trade_name: "",
  pan: "",
  email: "",
  phone: "",
  address: "",
  city: "",
  state: "",
  state_code: "",
  pincode: "",
  gstin: "",
  default_tax_mode: "gst",
  default_currency: "INR",
  terms_and_conditions: "",
};

const taxDefaults: TaxRatePayload = {
  name: "",
  rate_percent: "0.00",
  cess_percent: "0.00",
  description: "",
  is_active: true,
};

const paymentDefaults: PaymentModePayload = {
  name: "",
  mode_type: "cash",
  requires_reference: false,
  display_order: 1,
  is_active: true,
};

const sequenceDefaults: InvoiceSequencePayload = {
  branch_id: null,
  invoice_type: "gst_invoice",
  fiscal_year: "2026-2027",
  prefix: "INV-2026-",
  suffix: "",
  next_number: 1,
  padding: 5,
  reset_rule: "fiscal_year",
  is_active: true,
};

function cleanOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed ? trimmed : null;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the settings request. Check that the backend is running.";
}

function labelize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function profilePayload(form: BusinessProfilePayload): BusinessProfilePayload {
  return {
    company_code: form.company_code.trim().toUpperCase(),
    legal_name: form.legal_name.trim(),
    trade_name: cleanOptional(form.trade_name),
    pan: cleanOptional(form.pan)?.toUpperCase() ?? null,
    email: cleanOptional(form.email),
    phone: cleanOptional(form.phone),
    address: cleanOptional(form.address),
    city: cleanOptional(form.city),
    state: cleanOptional(form.state),
    state_code: cleanOptional(form.state_code)?.toUpperCase() ?? null,
    pincode: cleanOptional(form.pincode),
    gstin: cleanOptional(form.gstin)?.toUpperCase() ?? null,
    default_tax_mode: form.default_tax_mode,
    default_currency: form.default_currency.trim().toUpperCase() || "INR",
    terms_and_conditions: cleanOptional(form.terms_and_conditions),
  };
}

function taxPayload(form: TaxRatePayload): TaxRatePayload {
  return {
    name: form.name.trim(),
    rate_percent: form.rate_percent,
    cess_percent: form.cess_percent,
    description: cleanOptional(form.description),
    is_active: form.is_active,
  };
}

function paymentPayload(form: PaymentModePayload): PaymentModePayload {
  return {
    name: form.name.trim(),
    mode_type: form.mode_type,
    requires_reference: form.requires_reference,
    display_order: Number(form.display_order) || 0,
    is_active: form.is_active,
  };
}

function sequencePayload(form: InvoiceSequencePayload): InvoiceSequencePayload {
  return {
    branch_id: form.branch_id ?? null,
    invoice_type: form.invoice_type,
    fiscal_year: form.fiscal_year.trim(),
    prefix: form.prefix.trim(),
    suffix: cleanOptional(form.suffix),
    next_number: Number(form.next_number) || 1,
    padding: Number(form.padding) || 5,
    reset_rule: form.reset_rule,
    is_active: form.is_active,
  };
}

export function SettingsPage() {
  const { token, user } = useAuth();
  const [profileForm, setProfileForm] = useState<BusinessProfilePayload>(profileDefaults);
  const [taxForm, setTaxForm] = useState<TaxRatePayload>(taxDefaults);
  const [paymentForm, setPaymentForm] = useState<PaymentModePayload>(paymentDefaults);
  const [sequenceForm, setSequenceForm] = useState<InvoiceSequencePayload>(sequenceDefaults);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [paymentModes, setPaymentModes] = useState<PaymentMode[]>([]);
  const [invoiceSequences, setInvoiceSequences] = useState<InvoiceSequence[]>([]);
  const [editingTaxId, setEditingTaxId] = useState<number | null>(null);
  const [editingPaymentId, setEditingPaymentId] = useState<number | null>(null);
  const [editingSequenceId, setEditingSequenceId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canEdit = user?.role === "admin";

  async function loadSettings() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [profile, taxes, modes, sequences] = await Promise.all([
        getBusinessProfile(token),
        listTaxRates(token, true),
        listPaymentModes(token, true),
        listInvoiceSequences(token, true),
      ]);
      setProfileForm({
        company_code: profile.company_code,
        legal_name: profile.legal_name,
        trade_name: profile.trade_name ?? "",
        pan: profile.pan ?? "",
        email: profile.email ?? "",
        phone: profile.phone ?? "",
        address: profile.address ?? "",
        city: profile.city ?? "",
        state: profile.state ?? "",
        state_code: profile.state_code ?? "",
        pincode: profile.pincode ?? "",
        gstin: profile.gstin ?? "",
        default_tax_mode: profile.default_tax_mode,
        default_currency: profile.default_currency,
        terms_and_conditions: profile.terms_and_conditions ?? "",
      });
      setTaxRates(taxes);
      setPaymentModes(modes);
      setInvoiceSequences(sequences);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, [token]);

  const activeTaxRateCount = useMemo(() => taxRates.filter((rate) => rate.is_active).length, [taxRates]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canEdit) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const profile = await updateBusinessProfile(token, profilePayload(profileForm));
      setProfileForm({
        company_code: profile.company_code,
        legal_name: profile.legal_name,
        trade_name: profile.trade_name ?? "",
        pan: profile.pan ?? "",
        email: profile.email ?? "",
        phone: profile.phone ?? "",
        address: profile.address ?? "",
        city: profile.city ?? "",
        state: profile.state ?? "",
        state_code: profile.state_code ?? "",
        pincode: profile.pincode ?? "",
        gstin: profile.gstin ?? "",
        default_tax_mode: profile.default_tax_mode,
        default_currency: profile.default_currency,
        terms_and_conditions: profile.terms_and_conditions ?? "",
      });
      setSuccess("Business profile saved.");
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function saveTaxRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canEdit) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingTaxId) {
        await updateTaxRate(token, editingTaxId, taxPayload(taxForm));
      } else {
        await createTaxRate(token, taxPayload(taxForm));
      }
      setTaxForm(taxDefaults);
      setEditingTaxId(null);
      setSuccess("Tax rate saved.");
      setTaxRates(await listTaxRates(token, true));
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function savePaymentMode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canEdit) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingPaymentId) {
        await updatePaymentMode(token, editingPaymentId, paymentPayload(paymentForm));
      } else {
        await createPaymentMode(token, paymentPayload(paymentForm));
      }
      setPaymentForm(paymentDefaults);
      setEditingPaymentId(null);
      setSuccess("Payment mode saved.");
      setPaymentModes(await listPaymentModes(token, true));
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function saveInvoiceSequence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canEdit) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingSequenceId) {
        await updateInvoiceSequence(token, editingSequenceId, sequencePayload(sequenceForm));
      } else {
        await createInvoiceSequence(token, sequencePayload(sequenceForm));
      }
      setSequenceForm(sequenceDefaults);
      setEditingSequenceId(null);
      setSuccess("Invoice sequence saved.");
      setInvoiceSequences(await listInvoiceSequences(token, true));
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading business settings" />;
  }

  return (
    <section className="page-stack" aria-labelledby="settings-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Administration</p>
          <h2 id="settings-title">Settings</h2>
          <p className="page-description">
            Configure the local-first business profile, GST foundation, payment modes, invoice
            numbering, and deployment guidance for the expanded retail billing system.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">Admin only</span>
          <a className="action-button secondary" href="/docs/REMOTE_ACCESS.md" rel="noreferrer" target="_blank">
            <ExternalLink aria-hidden="true" size={16} />
            Remote access guide
          </a>
        </div>
      </div>

      <section className="metric-grid" aria-label="Settings status">
        {settingsMetrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      {error ? <ErrorState message={error} /> : null}
      {success ? (
        <div className="state-panel success">
          <Settings2 aria-hidden="true" size={22} />
          <p>{success}</p>
        </div>
      ) : null}

      <section className="dashboard-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Business identity</p>
              <h3>Business Profile</h3>
            </div>
            <ShieldCheck aria-hidden="true" size={20} />
          </div>
          <form className="master-form" onSubmit={saveProfile}>
            <div className="form-grid two">
              <label>
                Company code
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.company_code}
                  onChange={(event) => setProfileForm({ ...profileForm, company_code: event.target.value })}
                />
              </label>
              <label>
                Legal name
                <input
                  disabled={!canEdit || saving}
                  required
                  value={profileForm.legal_name}
                  onChange={(event) => setProfileForm({ ...profileForm, legal_name: event.target.value })}
                />
              </label>
              <label>
                Trade name
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.trade_name ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, trade_name: event.target.value })}
                />
              </label>
              <label>
                GSTIN
                <input
                  disabled={!canEdit || saving}
                  maxLength={15}
                  value={profileForm.gstin ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, gstin: event.target.value })}
                />
              </label>
              <label>
                PAN
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.pan ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, pan: event.target.value })}
                />
              </label>
              <label>
                Default tax mode
                <select
                  disabled={!canEdit || saving}
                  value={profileForm.default_tax_mode}
                  onChange={(event) =>
                    setProfileForm({ ...profileForm, default_tax_mode: event.target.value as TaxMode })
                  }
                >
                  <option value="gst">GST</option>
                  <option value="non_gst">Non-GST</option>
                </select>
              </label>
              <label>
                State
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.state ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, state: event.target.value })}
                />
              </label>
              <label>
                State code
                <input
                  disabled={!canEdit || saving}
                  maxLength={2}
                  value={profileForm.state_code ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, state_code: event.target.value })}
                />
              </label>
              <label>
                Email
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.email ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, email: event.target.value })}
                />
              </label>
              <label>
                Phone
                <input
                  disabled={!canEdit || saving}
                  value={profileForm.phone ?? ""}
                  onChange={(event) => setProfileForm({ ...profileForm, phone: event.target.value })}
                />
              </label>
            </div>
            <label>
              Address
              <textarea
                disabled={!canEdit || saving}
                value={profileForm.address ?? ""}
                onChange={(event) => setProfileForm({ ...profileForm, address: event.target.value })}
              />
            </label>
            <label>
              Terms and conditions
              <textarea
                disabled={!canEdit || saving}
                value={profileForm.terms_and_conditions ?? ""}
                onChange={(event) => setProfileForm({ ...profileForm, terms_and_conditions: event.target.value })}
              />
            </label>
            <div className="form-actions">
              <button className="action-button primary" disabled={!canEdit || saving} type="submit">
                <Save aria-hidden="true" size={16} />
                Save business profile
              </button>
            </div>
          </form>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">GST setup</p>
              <h3>Tax Rates</h3>
            </div>
            <ReceiptText aria-hidden="true" size={20} />
          </div>
          <form className="master-form" onSubmit={saveTaxRate}>
            <div className="form-grid two">
              <label>
                Name
                <input
                  disabled={!canEdit || saving}
                  required
                  value={taxForm.name}
                  onChange={(event) => setTaxForm({ ...taxForm, name: event.target.value })}
                />
              </label>
              <label>
                GST %
                <input
                  disabled={!canEdit || saving}
                  min="0"
                  step="0.01"
                  type="number"
                  value={taxForm.rate_percent}
                  onChange={(event) => setTaxForm({ ...taxForm, rate_percent: event.target.value })}
                />
              </label>
              <label>
                Cess %
                <input
                  disabled={!canEdit || saving}
                  min="0"
                  step="0.01"
                  type="number"
                  value={taxForm.cess_percent}
                  onChange={(event) => setTaxForm({ ...taxForm, cess_percent: event.target.value })}
                />
              </label>
              <label className="checkbox-row compact">
                <input
                  checked={taxForm.is_active}
                  disabled={!canEdit || saving}
                  type="checkbox"
                  onChange={(event) => setTaxForm({ ...taxForm, is_active: event.target.checked })}
                />
                Active
              </label>
            </div>
            <label>
              Description
              <textarea
                disabled={!canEdit || saving}
                value={taxForm.description ?? ""}
                onChange={(event) => setTaxForm({ ...taxForm, description: event.target.value })}
              />
            </label>
            <div className="form-actions">
              <button className="action-button primary" disabled={!canEdit || saving} type="submit">
                {editingTaxId ? "Update tax rate" : "Add tax rate"}
              </button>
              {editingTaxId ? (
                <button
                  className="action-button secondary"
                  type="button"
                  onClick={() => {
                    setEditingTaxId(null);
                    setTaxForm(taxDefaults);
                  }}
                >
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
          <p className="page-description">{activeTaxRateCount} active tax rates configured.</p>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>GST %</th>
                  <th>Cess %</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {taxRates.map((rate) => (
                  <tr key={rate.id}>
                    <td>{rate.name}</td>
                    <td>{rate.rate_percent}</td>
                    <td>{rate.cess_percent}</td>
                    <td>{rate.is_active ? "Active" : "Inactive"}</td>
                    <td>
                      <button
                        className="action-button secondary"
                        disabled={!canEdit || saving}
                        type="button"
                        onClick={() => {
                          setEditingTaxId(rate.id);
                          setTaxForm({
                            name: rate.name,
                            rate_percent: rate.rate_percent,
                            cess_percent: rate.cess_percent,
                            description: rate.description ?? "",
                            is_active: rate.is_active,
                          });
                        }}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Collections</p>
              <h3>Payment Modes</h3>
            </div>
            <Settings2 aria-hidden="true" size={20} />
          </div>
          <form className="master-form" onSubmit={savePaymentMode}>
            <div className="form-grid two">
              <label>
                Name
                <input
                  disabled={!canEdit || saving}
                  required
                  value={paymentForm.name}
                  onChange={(event) => setPaymentForm({ ...paymentForm, name: event.target.value })}
                />
              </label>
              <label>
                Type
                <select
                  disabled={!canEdit || saving}
                  value={paymentForm.mode_type}
                  onChange={(event) =>
                    setPaymentForm({ ...paymentForm, mode_type: event.target.value as PaymentModeType })
                  }
                >
                  {paymentModeTypes.map((type) => (
                    <option key={type} value={type}>
                      {labelize(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Display order
                <input
                  disabled={!canEdit || saving}
                  min="0"
                  type="number"
                  value={paymentForm.display_order}
                  onChange={(event) => setPaymentForm({ ...paymentForm, display_order: Number(event.target.value) })}
                />
              </label>
              <label className="checkbox-row compact">
                <input
                  checked={paymentForm.requires_reference}
                  disabled={!canEdit || saving}
                  type="checkbox"
                  onChange={(event) => setPaymentForm({ ...paymentForm, requires_reference: event.target.checked })}
                />
                Requires reference
              </label>
            </div>
            <label className="checkbox-row compact">
              <input
                checked={paymentForm.is_active}
                disabled={!canEdit || saving}
                type="checkbox"
                onChange={(event) => setPaymentForm({ ...paymentForm, is_active: event.target.checked })}
              />
              Active
            </label>
            <div className="form-actions">
              <button className="action-button primary" disabled={!canEdit || saving} type="submit">
                {editingPaymentId ? "Update payment mode" : "Add payment mode"}
              </button>
              {editingPaymentId ? (
                <button
                  className="action-button secondary"
                  type="button"
                  onClick={() => {
                    setEditingPaymentId(null);
                    setPaymentForm(paymentDefaults);
                  }}
                >
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Reference</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {paymentModes.map((mode) => (
                  <tr key={mode.id}>
                    <td>{mode.name}</td>
                    <td>{labelize(mode.mode_type)}</td>
                    <td>{mode.requires_reference ? "Required" : "Optional"}</td>
                    <td>{mode.is_active ? "Active" : "Inactive"}</td>
                    <td>
                      <button
                        className="action-button secondary"
                        disabled={!canEdit || saving}
                        type="button"
                        onClick={() => {
                          setEditingPaymentId(mode.id);
                          setPaymentForm({
                            name: mode.name,
                            mode_type: mode.mode_type,
                            requires_reference: mode.requires_reference,
                            display_order: mode.display_order,
                            is_active: mode.is_active,
                          });
                        }}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Document numbering</p>
              <h3>Invoice Sequences</h3>
            </div>
            <ReceiptText aria-hidden="true" size={20} />
          </div>
          <form className="master-form" onSubmit={saveInvoiceSequence}>
            <div className="form-grid two">
              <label>
                Invoice type
                <select
                  disabled={!canEdit || saving}
                  value={sequenceForm.invoice_type}
                  onChange={(event) =>
                    setSequenceForm({ ...sequenceForm, invoice_type: event.target.value as InvoiceSequenceType })
                  }
                >
                  {invoiceTypes.map((type) => (
                    <option key={type} value={type}>
                      {labelize(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fiscal year
                <input
                  disabled={!canEdit || saving}
                  required
                  value={sequenceForm.fiscal_year}
                  onChange={(event) => setSequenceForm({ ...sequenceForm, fiscal_year: event.target.value })}
                />
              </label>
              <label>
                Prefix
                <input
                  disabled={!canEdit || saving}
                  required
                  value={sequenceForm.prefix}
                  onChange={(event) => setSequenceForm({ ...sequenceForm, prefix: event.target.value })}
                />
              </label>
              <label>
                Suffix
                <input
                  disabled={!canEdit || saving}
                  value={sequenceForm.suffix ?? ""}
                  onChange={(event) => setSequenceForm({ ...sequenceForm, suffix: event.target.value })}
                />
              </label>
              <label>
                Next number
                <input
                  disabled={!canEdit || saving}
                  min="1"
                  type="number"
                  value={sequenceForm.next_number}
                  onChange={(event) => setSequenceForm({ ...sequenceForm, next_number: Number(event.target.value) })}
                />
              </label>
              <label>
                Padding
                <input
                  disabled={!canEdit || saving}
                  min="1"
                  max="12"
                  type="number"
                  value={sequenceForm.padding}
                  onChange={(event) => setSequenceForm({ ...sequenceForm, padding: Number(event.target.value) })}
                />
              </label>
              <label>
                Reset rule
                <select
                  disabled={!canEdit || saving}
                  value={sequenceForm.reset_rule}
                  onChange={(event) =>
                    setSequenceForm({ ...sequenceForm, reset_rule: event.target.value as InvoiceSequenceResetRule })
                  }
                >
                  {resetRules.map((rule) => (
                    <option key={rule} value={rule}>
                      {labelize(rule)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="checkbox-row compact">
                <input
                  checked={sequenceForm.is_active}
                  disabled={!canEdit || saving}
                  type="checkbox"
                  onChange={(event) => setSequenceForm({ ...sequenceForm, is_active: event.target.checked })}
                />
                Active
              </label>
            </div>
            <div className="form-actions">
              <button className="action-button primary" disabled={!canEdit || saving} type="submit">
                {editingSequenceId ? "Update sequence" : "Add sequence"}
              </button>
              {editingSequenceId ? (
                <button
                  className="action-button secondary"
                  type="button"
                  onClick={() => {
                    setEditingSequenceId(null);
                    setSequenceForm(sequenceDefaults);
                  }}
                >
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Fiscal year</th>
                  <th>Next preview</th>
                  <th>Reset</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {invoiceSequences.map((sequence) => (
                  <tr key={sequence.id}>
                    <td>{labelize(sequence.invoice_type)}</td>
                    <td>{sequence.fiscal_year}</td>
                    <td>{sequence.preview_next_number}</td>
                    <td>{labelize(sequence.reset_rule)}</td>
                    <td>{sequence.is_active ? "Active" : "Inactive"}</td>
                    <td>
                      <button
                        className="action-button secondary"
                        disabled={!canEdit || saving}
                        type="button"
                        onClick={() => {
                          setEditingSequenceId(sequence.id);
                          setSequenceForm({
                            branch_id: sequence.branch_id,
                            invoice_type: sequence.invoice_type,
                            fiscal_year: sequence.fiscal_year,
                            prefix: sequence.prefix,
                            suffix: sequence.suffix ?? "",
                            next_number: sequence.next_number,
                            padding: sequence.padding,
                            reset_rule: sequence.reset_rule,
                            is_active: sequence.is_active,
                          });
                        }}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Print foundation</p>
              <h3>Print Templates</h3>
            </div>
            <ReceiptText aria-hidden="true" size={20} />
          </div>
          <p className="page-description">
            Template records are seeded for A4 GST invoices and 80mm POS receipts. Full print
            preview and PDF rendering arrives in the invoice print phase.
          </p>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Hybrid deployment</p>
              <h3>Remote access documentation</h3>
            </div>
            <Network aria-hidden="true" size={20} />
          </div>
          <div className="settings-link-list">
            <a href="/docs/REMOTE_ACCESS.md" rel="noreferrer" target="_blank">
              <ShieldCheck aria-hidden="true" size={18} />
              <span>
                <strong>Remote access guide</strong>
                <small>Cloudflare Tunnel, Tailscale, ngrok, and security checklist.</small>
              </span>
            </a>
            <a href="/docs/POWER_BI_SETUP.md" rel="noreferrer" target="_blank">
              <Server aria-hidden="true" size={18} />
              <span>
                <strong>Power BI setup guide</strong>
                <small>Local PostgreSQL views, CSV exports, and reporting workflow.</small>
              </span>
            </a>
            <a href="/docs/BACKUP_RESTORE.md" rel="noreferrer" target="_blank">
              <Server aria-hidden="true" size={18} />
              <span>
                <strong>Backup and restore guide</strong>
                <small>PostgreSQL backup scripts, restore commands, and reliability checklist.</small>
              </span>
            </a>
          </div>
        </article>

        <aside className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Security checklist</p>
              <h3>Before sharing a URL</h3>
            </div>
            <LockKeyhole aria-hidden="true" size={20} />
          </div>
          <ul className="settings-checklist">
            {checklist.map((item) => (
              <li key={item}>
                <KeyRound aria-hidden="true" size={16} />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </aside>
      </section>
    </section>
  );
}
