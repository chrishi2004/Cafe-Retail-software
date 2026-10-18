import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { CreditCard, Edit3, Plus, ReceiptText, RotateCw, Search } from "lucide-react";

import { ApiError } from "../api/client";
import {
  createCustomer,
  createCustomerPayment,
  deactivateCustomer,
  getCustomer,
  getCustomerLedger,
  listCustomerOutstanding,
  listCustomers,
  updateCustomer,
} from "../api/customers";
import { listBranches } from "../api/masterData";
import { listPaymentModes } from "../api/businessSettings";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Customer,
  CustomerLedgerEntry,
  CustomerOutstanding,
  CustomerPaymentPayload,
  CustomerPayload,
  PaymentMode,
} from "../types";
import { formatCurrency, formatStatus } from "../utils/format";

const emptyCustomerForm: CustomerPayload = {
  name: "",
  phone: "",
  email: "",
  gstin: "",
  billing_address: "",
  shipping_address: "",
  city: "",
  state: "",
  state_code: "",
  pincode: "",
  branch_id: null,
  company_id: null,
  credit_limit: "0.00",
  opening_balance: "0.00",
  is_active: true,
};

const emptyPaymentForm: CustomerPaymentPayload = {
  amount: "0.00",
  branch_id: null,
  payment_mode_id: null,
  reference_number: "",
  notes: "",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the request. Check that the backend is running.";
}

function cleanOptional(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function CustomersPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canManage = user?.role === "admin" || user?.role === "store_manager";
  const canRecordPayment = user?.role === "admin" || user?.role === "store_manager" || user?.role === "staff";
  const readOnly = user?.role === "analyst";

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [outstandingRows, setOutstandingRows] = useState<CustomerOutstanding[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [paymentModes, setPaymentModes] = useState<PaymentMode[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [ledger, setLedger] = useState<CustomerLedgerEntry[]>([]);
  const [form, setForm] = useState<CustomerPayload>(emptyCustomerForm);
  const [paymentForm, setPaymentForm] = useState<CustomerPaymentPayload>(emptyPaymentForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [branchFilter, setBranchFilter] = useState(0);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [paymentSaving, setPaymentSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const defaultBranchId = useMemo(() => {
    if (user?.role === "admin") {
      return branches[0]?.id ?? null;
    }
    return user?.branch_id ?? branches[0]?.id ?? null;
  }, [branches, user?.branch_id, user?.role]);

  const load = useCallback(async () => {
    if (!token) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [customerRows, outstanding, branchRows, modes] = await Promise.all([
        listCustomers(token, {
          search,
          branchId: branchFilter || undefined,
          includeInactive,
          limit: 250,
        }),
        listCustomerOutstanding(token, { branchId: branchFilter || undefined }),
        listBranches(token, { includeInactive: false }),
        listPaymentModes(token, true),
      ]);
      setCustomers(customerRows);
      setOutstandingRows(outstanding);
      setBranches(branchRows);
      setPaymentModes(modes);
      setForm((current) => ({
        ...current,
        branch_id: current.branch_id ?? (user?.role === "admin" ? branchRows[0]?.id ?? null : user?.branch_id ?? null),
      }));
      setPaymentForm((current) => ({
        ...current,
        branch_id: current.branch_id ?? (user?.role === "admin" ? branchRows[0]?.id ?? null : user?.branch_id ?? null),
      }));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchFilter, includeInactive, search, token, user?.branch_id, user?.role]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setForm({
      ...emptyCustomerForm,
      branch_id: defaultBranchId,
    });
  };

  const loadLedger = async (customer: Customer) => {
    if (!token) {
      return;
    }
    setSelectedCustomer(customer);
    setLedgerLoading(true);
    setError(null);
    try {
      setLedger(await getCustomerLedger(token, customer.id));
      setPaymentForm({
        ...emptyPaymentForm,
        branch_id: customer.branch_id ?? defaultBranchId,
      });
    } catch (ledgerError) {
      setError(errorMessage(ledgerError));
    } finally {
      setLedgerLoading(false);
    }
  };

  const editCustomer = (customer: Customer) => {
    setEditingId(customer.id);
    setForm({
      name: customer.name,
      phone: customer.phone ?? "",
      email: customer.email ?? "",
      gstin: customer.gstin ?? "",
      billing_address: customer.billing_address ?? "",
      shipping_address: customer.shipping_address ?? "",
      city: customer.city ?? "",
      state: customer.state ?? "",
      state_code: customer.state_code ?? "",
      pincode: customer.pincode ?? "",
      branch_id: customer.branch_id,
      company_id: customer.company_id,
      credit_limit: customer.credit_limit,
      opening_balance: customer.opening_balance,
      is_active: customer.is_active,
    });
  };

  const submitCustomer = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canManage) {
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    const payload: CustomerPayload = {
      ...form,
      name: form.name.trim(),
      phone: cleanOptional(form.phone),
      email: cleanOptional(form.email),
      gstin: cleanOptional(form.gstin)?.toUpperCase() ?? null,
      billing_address: cleanOptional(form.billing_address),
      shipping_address: cleanOptional(form.shipping_address),
      city: cleanOptional(form.city),
      state: cleanOptional(form.state),
      state_code: cleanOptional(form.state_code)?.toUpperCase() ?? null,
      pincode: cleanOptional(form.pincode),
      branch_id: form.branch_id || defaultBranchId,
      company_id: form.company_id || null,
    };
    try {
      const saved = editingId
        ? await updateCustomer(token, editingId, payload)
        : await createCustomer(token, payload);
      setSuccess(`${saved.name} saved.`);
      resetForm();
      await load();
      await loadLedger(saved);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const submitPayment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedCustomer || !canRecordPayment) {
      return;
    }
    setPaymentSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payment = await createCustomerPayment(token, selectedCustomer.id, {
        ...paymentForm,
        branch_id: paymentForm.branch_id || selectedCustomer.branch_id || defaultBranchId,
        payment_mode_id: paymentForm.payment_mode_id || null,
        reference_number: cleanOptional(paymentForm.reference_number),
        notes: cleanOptional(paymentForm.notes),
      });
      setSuccess(`Payment recorded. Outstanding is ${formatCurrency(payment.outstanding_balance)}.`);
      setPaymentForm({ ...emptyPaymentForm, branch_id: selectedCustomer.branch_id ?? defaultBranchId });
      await load();
      await loadLedger(await getCustomer(token, selectedCustomer.id));
    } catch (paymentError) {
      setError(errorMessage(paymentError));
    } finally {
      setPaymentSaving(false);
    }
  };

  const handleDeactivate = async (customer: Customer) => {
    if (!token || !canManage) {
      return;
    }
    setError(null);
    setSuccess(null);
    try {
      const deactivated = await deactivateCustomer(token, customer.id);
      setSuccess(`${deactivated.name} deactivated.`);
      await load();
      if (selectedCustomer?.id === customer.id) {
        await loadLedger(deactivated);
      }
    } catch (deactivateError) {
      setError(errorMessage(deactivateError));
    }
  };

  const outstandingTotal = outstandingRows.reduce((total, row) => total + Number(row.outstanding_balance), 0);
  const overLimitCount = outstandingRows.filter((row) => row.is_over_credit_limit).length;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Customer ledger</p>
          <h2>Customer management</h2>
          <p className="page-description">
            Manage GST and non-GST customers, credit limits, payments, and append-only receivable ledger entries.
          </p>
        </div>
        <div className="page-header-side">
          <button className="action-button secondary" onClick={() => void load()} type="button">
            <RotateCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar dashboard-filter-bar">
        <div className="search-shell">
          <Search aria-hidden="true" size={16} />
          <input
            aria-label="Search customers"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, phone, email, GSTIN"
            type="search"
            value={search}
          />
        </div>
        <div className="filter-actions">
          <select
            aria-label="Filter customers by branch"
            onChange={(event) => setBranchFilter(Number(event.target.value))}
            value={branchFilter}
          >
            <option value={0}>All accessible branches</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
          <label className="checkbox-row compact">
            <input
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              type="checkbox"
            />
            <span>Include inactive</span>
          </label>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard metric={{ label: "Customers", value: String(customers.length), detail: "Current filter result", tone: "blue" }} />
        <MetricCard metric={{ label: "Outstanding", value: formatCurrency(outstandingTotal), detail: "Debit minus credit ledger", tone: "amber" }} />
        <MetricCard metric={{ label: "Over Limit", value: String(overLimitCount), detail: "Credit risk accounts", tone: overLimitCount ? "rose" : "green" }} />
        <MetricCard metric={{ label: "Mode", value: readOnly ? "Read only" : "Operational", detail: "Backend role enforced", tone: "slate" }} />
      </section>

      {error ? <ErrorState message={error} title="Customer action failed" /> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <section className="master-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Accounts</p>
              <h3>Customers</h3>
            </div>
          </div>
          {loading ? <LoadingState label="Loading customers" /> : null}
          {!loading && customers.length === 0 ? (
            <EmptyState title="No customers found" message="Create a customer account or adjust the current filter." />
          ) : null}
          {!loading && customers.length > 0 ? (
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Contact</th>
                    <th>Branch</th>
                    <th>Credit</th>
                    <th>Outstanding</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <tr key={customer.id}>
                      <td>
                        <strong>{customer.name}</strong>
                        <span>{customer.gstin ?? "Non-GST / B2C"}</span>
                      </td>
                      <td>
                        <strong>{customer.phone ?? "No phone"}</strong>
                        <span>{customer.email ?? "No email"}</span>
                      </td>
                      <td>{customer.branch_name ?? "Company-wide"}</td>
                      <td>
                        <strong>{formatCurrency(customer.credit_limit)}</strong>
                        <span>{formatCurrency(customer.available_credit)} available</span>
                      </td>
                      <td>{formatCurrency(customer.outstanding_balance)}</td>
                      <td>
                        <span className={customer.is_active ? "status-badge ok" : "status-badge warning"}>
                          {customer.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button onClick={() => void loadLedger(customer)} type="button">
                            <ReceiptText aria-hidden="true" size={14} />
                            Ledger
                          </button>
                          <button disabled={!canManage} onClick={() => editCustomer(customer)} type="button">
                            <Edit3 aria-hidden="true" size={14} />
                            Edit
                          </button>
                          <button disabled={!canManage || !customer.is_active} onClick={() => void handleDeactivate(customer)} type="button">
                            Deactivate
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>

        <aside className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Account setup</p>
              <h3>{editingId ? "Edit customer" : "Create customer"}</h3>
            </div>
          </div>
          {!canManage ? (
            <EmptyState title="Read-only customer accounts" message="You can view customers and ledgers, but account changes are restricted." />
          ) : (
            <form className="master-form" onSubmit={submitCustomer}>
              <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <div className="form-grid two">
                <label>Phone<input value={form.phone ?? ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
                <label>Email<input type="email" value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
                <label>GSTIN<input value={form.gstin ?? ""} onChange={(event) => setForm({ ...form, gstin: event.target.value })} /></label>
                <label>State code<input maxLength={2} value={form.state_code ?? ""} onChange={(event) => setForm({ ...form, state_code: event.target.value })} /></label>
              </div>
              <label>Billing address<textarea value={form.billing_address ?? ""} onChange={(event) => setForm({ ...form, billing_address: event.target.value })} /></label>
              <label>Shipping address<textarea value={form.shipping_address ?? ""} onChange={(event) => setForm({ ...form, shipping_address: event.target.value })} /></label>
              <div className="form-grid two">
                <label>City<input value={form.city ?? ""} onChange={(event) => setForm({ ...form, city: event.target.value })} /></label>
                <label>State<input value={form.state ?? ""} onChange={(event) => setForm({ ...form, state: event.target.value })} /></label>
                <label>Pincode<input value={form.pincode ?? ""} onChange={(event) => setForm({ ...form, pincode: event.target.value })} /></label>
                <label>Branch<select disabled={!isAdmin} value={form.branch_id ?? 0} onChange={(event) => setForm({ ...form, branch_id: Number(event.target.value) || null })}>
                  <option value={0}>Company-wide</option>
                  {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                </select></label>
                <label>Credit limit<input min="0" step="0.01" type="number" value={form.credit_limit} onChange={(event) => setForm({ ...form, credit_limit: event.target.value })} /></label>
                <label>Opening balance<input min="0" step="0.01" type="number" value={form.opening_balance} onChange={(event) => setForm({ ...form, opening_balance: event.target.value })} /></label>
              </div>
              <label className="checkbox-row"><input checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} type="checkbox" /> Active customer</label>
              <div className="form-actions">
                <button className="action-button primary" disabled={saving} type="submit">
                  <Plus aria-hidden="true" size={16} />
                  {saving ? "Saving" : editingId ? "Save changes" : "Create"}
                </button>
                {editingId ? <button className="action-button secondary" onClick={resetForm} type="button">Cancel</button> : null}
              </div>
            </form>
          )}
        </aside>
      </section>

      <section className="master-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Ledger detail</p>
              <h3>{selectedCustomer ? selectedCustomer.name : "Select a customer"}</h3>
            </div>
          </div>
          {ledgerLoading ? <LoadingState label="Loading customer ledger" /> : null}
          {!ledgerLoading && !selectedCustomer ? (
            <EmptyState title="No ledger selected" message="Choose a customer to inspect opening balance, payments, and running balance." />
          ) : null}
          {!ledgerLoading && selectedCustomer ? (
            <div className="detail-stack">
              <div className="detail-list">
                <div><span>Outstanding</span><strong>{formatCurrency(selectedCustomer.outstanding_balance)}</strong></div>
                <div><span>Credit limit</span><strong>{formatCurrency(selectedCustomer.credit_limit)}</strong></div>
                <div><span>Available credit</span><strong>{formatCurrency(selectedCustomer.available_credit)}</strong></div>
              </div>
              {ledger.length === 0 ? (
                <EmptyState title="No ledger entries" message="This customer has no opening balance or payment history yet." />
              ) : (
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr><th>Date</th><th>Type</th><th>Debit</th><th>Credit</th><th>Balance</th><th>Notes</th></tr>
                    </thead>
                    <tbody>
                      {ledger.map((entry) => (
                        <tr key={entry.id}>
                          <td>{formatDateTime(entry.entry_datetime)}</td>
                          <td>{formatStatus(entry.entry_type)}</td>
                          <td>{formatCurrency(entry.debit)}</td>
                          <td>{formatCurrency(entry.credit)}</td>
                          <td>{formatCurrency(entry.running_balance)}</td>
                          <td>{entry.reason ?? entry.notes ?? "Not set"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </article>

        <aside className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Receipt</p>
              <h3>Record payment</h3>
            </div>
          </div>
          {!selectedCustomer ? (
            <EmptyState title="Select a customer" message="Payments are recorded against the selected customer ledger." />
          ) : !canRecordPayment ? (
            <EmptyState title="Payment writes locked" message="This role can inspect customer receivables but cannot record payments." />
          ) : (
            <form className="master-form" onSubmit={submitPayment}>
              <label>Amount<input min="0.01" required step="0.01" type="number" value={paymentForm.amount} onChange={(event) => setPaymentForm({ ...paymentForm, amount: event.target.value })} /></label>
              <label>Payment mode<select value={paymentForm.payment_mode_id ?? 0} onChange={(event) => setPaymentForm({ ...paymentForm, payment_mode_id: Number(event.target.value) || null })}>
                <option value={0}>Not specified</option>
                {paymentModes.map((mode) => <option key={mode.id} value={mode.id}>{mode.name}</option>)}
              </select></label>
              <label>Branch<select disabled={!isAdmin} value={paymentForm.branch_id ?? 0} onChange={(event) => setPaymentForm({ ...paymentForm, branch_id: Number(event.target.value) || null })}>
                <option value={0}>No branch</option>
                {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
              </select></label>
              <label>Reference<input value={paymentForm.reference_number ?? ""} onChange={(event) => setPaymentForm({ ...paymentForm, reference_number: event.target.value })} /></label>
              <label>Notes<textarea value={paymentForm.notes ?? ""} onChange={(event) => setPaymentForm({ ...paymentForm, notes: event.target.value })} /></label>
              <button className="action-button primary" disabled={paymentSaving} type="submit">
                <CreditCard aria-hidden="true" size={16} />
                {paymentSaving ? "Recording" : "Record payment"}
              </button>
            </form>
          )}
        </aside>
      </section>

      <article className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Receivables</p>
            <h3>Outstanding customers</h3>
          </div>
        </div>
        {outstandingRows.length === 0 ? (
          <EmptyState title="No outstanding balances" message="Customer receivables appear after opening balances, credit invoices, or adjustments." />
        ) : (
          <div className="table-shell">
            <table>
              <thead>
                <tr><th>Customer</th><th>Branch</th><th>Credit limit</th><th>Outstanding</th><th>Available</th><th>Risk</th></tr>
              </thead>
              <tbody>
                {outstandingRows.map((row) => (
                  <tr key={row.customer_id}>
                    <td><strong>{row.customer_name}</strong><span>{row.phone ?? row.gstin ?? "No contact"}</span></td>
                    <td>{row.branch_name ?? "Company-wide"}</td>
                    <td>{formatCurrency(row.credit_limit)}</td>
                    <td>{formatCurrency(row.outstanding_balance)}</td>
                    <td>{formatCurrency(row.available_credit)}</td>
                    <td>
                      <span className={row.is_over_credit_limit ? "status-badge warning" : "status-badge ok"}>
                        {row.is_over_credit_limit ? "Over limit" : "Within limit"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </section>
  );
}
