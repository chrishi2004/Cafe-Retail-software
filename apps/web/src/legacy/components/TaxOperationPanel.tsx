import { type FormEvent, useEffect, useState } from "react";
import { AlertTriangle, BadgeCheck, KeyRound, ReceiptText, ShieldCheck } from "lucide-react";

import { apiRequest, ApiError } from "../api/client";
import {
  activateGstOperation,
  getTaxOperation,
  type CustomerDetailsOnBill,
  type TaxOperation,
  updateTaxOperationSettings,
} from "../api/taxOperation";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "./ui";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Could not load tax-operation controls.";
}

function tomorrowIso(): string {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  return value.toISOString().slice(0, 10);
}

export function TaxOperationPanel() {
  const { token, user } = useAuth();
  const [state, setState] = useState<TaxOperation | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(tomorrowIso());
  const [confirmation, setConfirmation] = useState("");
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [customerDetails, setCustomerDetails] = useState<CustomerDetailsOnBill>("basic");

  const isOwner = user?.server_role === "super_admin";

  async function load() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getTaxOperation(token);
      setState(result);
      setCustomerDetails(result.customer_details_on_bill);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function saveRegistrationState(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !state || !isOwner) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await updateTaxOperationSettings(token, {
        tax_registration_status: state.gst_registration_configured ? "registered" : "unregistered",
        customer_details_on_bill: customerDetails,
        b2b_gst_enabled: state.b2b_gst_enabled,
        include_customer_in_gst_reports: state.include_customer_in_gst_reports,
        registration_id: state.gst_registration_id,
        registration_active: Boolean(state.gst_registration_id && state.gst_registration_configured),
      });
      setState(result);
      setSuccess(
        result.tax_registration_status === "registered"
          ? "Registration state prepared. GST billing is still disabled until the separate activation gate passes."
          : "Venture remains safely unregistered and Non-GST.",
      );
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function activate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !state || !isOwner) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest(
        "/auth/step-up",
        { method: "POST", body: JSON.stringify({ password }) },
        token,
      );
      const result = await activateGstOperation(token, {
        effective_from: effectiveFrom,
        acknowledge_professional_review: reviewConfirmed,
        confirmation,
      });
      setState(result);
      setPassword("");
      setConfirmation("");
      setReviewConfirmed(false);
      setSuccess(`GST operation scheduled from ${result.gst_effective_from}. Historical Non-GST bills are unchanged.`);
    } catch (activateError) {
      setError(errorMessage(activateError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState label="Loading tax operation status" />;
  if (!state) return <ErrorState message={error ?? "Tax operation status is unavailable."} />;

  return (
    <article className="panel wide" aria-labelledby="tax-operation-title">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Authoritative tax operation</p>
          <h3 id="tax-operation-title">{state.company_name}</h3>
        </div>
        {state.default_tax_mode === "gst" ? <BadgeCheck aria-hidden="true" size={22} /> : <ShieldCheck aria-hidden="true" size={22} />}
      </div>

      <div className="metric-grid" aria-label="Tax operation state">
        <article className="metric-card green">
          <p>Billing mode</p>
          <strong>{state.default_tax_mode === "gst" ? "GST" : "Non-GST"}</strong>
          <span>{state.gst_effective_from ? `Effective ${state.gst_effective_from}` : "No GST effective date"}</span>
        </article>
        <article className="metric-card blue">
          <p>Registration</p>
          <strong>{state.tax_registration_status === "registered" ? "Registered" : "Unregistered"}</strong>
          <span>{state.gstin_masked ?? "No GSTIN configured"}</span>
        </article>
        <article className="metric-card amber">
          <p>GST activation</p>
          <strong>{state.can_activate_gst ? "Ready" : "Blocked"}</strong>
          <span>{state.gst_registration_active ? "Registration active" : "Reference metadata only"}</span>
        </article>
      </div>

      <div className="state-panel">
        <AlertTriangle aria-hidden="true" size={20} />
        <p>{state.compliance_notice}</p>
      </div>

      {state.missing_activation_prerequisites.length ? (
        <div className="state-panel">
          <ReceiptText aria-hidden="true" size={20} />
          <div>
            <strong>Activation prerequisites still missing</strong>
            <ul>
              {state.missing_activation_prerequisites.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </div>
      ) : null}

      {error ? <ErrorState message={error} /> : null}
      {success ? <div className="state-panel success"><BadgeCheck aria-hidden="true" size={20} /><p>{success}</p></div> : null}

      {isOwner ? (
        <div className="dashboard-grid">
          <form className="master-form panel" onSubmit={saveRegistrationState}>
            <div className="panel-header">
              <div><p className="eyebrow">Super Admin only</p><h3>Registration readiness</h3></div>
              <ShieldCheck aria-hidden="true" size={20} />
            </div>
            <label>
              Customer details on bill
              <select value={customerDetails} onChange={(event) => setCustomerDetails(event.target.value as CustomerDetailsOnBill)} disabled={saving}>
                <option value="hidden">Hidden</option>
                <option value="basic">Basic</option>
                <option value="full">Full</option>
              </select>
            </label>
            <p className="page-description">
              This prepares a configured GST registration for validation. It does not activate GST billing.
            </p>
            <button className="action-button secondary" type="submit" disabled={saving || !state.gst_registration_configured}>
              Prepare registration state
            </button>
          </form>

          <form className="master-form panel" onSubmit={activate}>
            <div className="panel-header">
              <div><p className="eyebrow">Effective-dated change</p><h3>Activate GST operation</h3></div>
              <KeyRound aria-hidden="true" size={20} />
            </div>
            <label>
              Effective from
              <input type="date" min={new Date().toISOString().slice(0, 10)} value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} disabled={saving} />
            </label>
            <label>
              Re-enter password for step-up
              <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={saving} />
            </label>
            <label>
              Confirmation
              <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="ACTIVATE GST" disabled={saving} />
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={reviewConfirmed} onChange={(event) => setReviewConfirmed(event.target.checked)} disabled={saving} />
              I confirm independent CA/GST review has been completed.
            </label>
            <button className="action-button primary" type="submit" disabled={saving || !state.can_activate_gst || !password || confirmation.trim().toUpperCase() !== "ACTIVATE GST" || !reviewConfirmed}>
              Activate from selected date
            </button>
          </form>
        </div>
      ) : (
        <p className="page-description">Tax operation is view-only for this account. GST activation is restricted to Super Admin.</p>
      )}
    </article>
  );
}
