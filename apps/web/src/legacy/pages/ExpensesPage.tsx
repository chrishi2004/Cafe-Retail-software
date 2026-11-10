import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ReceiptIndianRupee, RefreshCw } from "lucide-react";

import {
  createExpense,
  getExpenseSummary,
  listExpenses,
  voidExpense,
  type Expense,
  type ExpenseCategory,
  type ExpenseSummary,
} from "../api/expenses";
import { listBranches } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type { Branch } from "../types";
import { cafeToday } from "../utils/cafeDates";
import { formatCurrency, inputDateDaysAgo } from "../utils/format";

const CATEGORIES: Array<{ value: ExpenseCategory; label: string }> = [
  { value: "maintenance", label: "Maintenance" },
  { value: "utilities", label: "Utilities / Electricity" },
  { value: "rent", label: "Rent" },
  { value: "wages", label: "Wages / Labour" },
  { value: "cleaning", label: "Cleaning" },
  { value: "repairs", label: "Repairs" },
  { value: "transport", label: "Transport" },
  { value: "marketing", label: "Marketing" },
  { value: "licenses", label: "Licences / Fees" },
  { value: "stock_purchase", label: "Stock Purchase" },
  { value: "miscellaneous", label: "Miscellaneous" },
];

const PAYMENT_MODES = [
  ["cash", "Cash"],
  ["upi", "UPI"],
  ["card", "Card"],
  ["bank_transfer", "Bank Transfer"],
  ["credit", "Credit / Pay Later"],
  ["other", "Other"],
] as const;

const categoryLabel = (value: string) =>
  CATEGORIES.find((row) => row.value === value)?.label ?? value.replaceAll("_", " ");

export function ExpensesPage() {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [rows, setRows] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<ExpenseSummary | null>(null);
  const [branchId, setBranchId] = useState(user?.branch_id ?? 0);
  const [startDate, setStartDate] = useState(() => inputDateDaysAgo(30));
  const [endDate, setEndDate] = useState(() => cafeToday());
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    branch_id: user?.branch_id ?? 0,
    expense_date: cafeToday(),
    category: "maintenance" as ExpenseCategory,
    description: "",
    amount: "",
    payment_mode: "cash",
    vendor_name: "",
    reference_number: "",
    notes: "",
  });

  const canWrite = ["super_admin", "admin", "store_manager"].includes(user?.server_role ?? "");
  const availableBranches = useMemo(() => branches.filter((row) => row.is_active !== false), [branches]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const filters = {
        branchId: branchId || undefined,
        startDate,
        endDate,
        category: category || undefined,
      };
      const [expenseRows, expenseSummary] = await Promise.all([
        listExpenses(token, filters),
        getExpenseSummary(token, filters),
      ]);
      setRows(expenseRows);
      setSummary(expenseSummary);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [branchId, category, endDate, startDate, token]);

  useEffect(() => {
    if (!token) return;
    void listBranches(token, { includeInactive: false })
      .then((branchRows) => {
        setBranches(branchRows);
        const preferred = user?.branch_id ?? branchRows[0]?.id ?? 0;
        setBranchId((current) => current || preferred);
        setForm((current) => ({ ...current, branch_id: current.branch_id || preferred }));
      })
      .catch((err: Error) => setError(err.message));
  }, [token, user?.branch_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canWrite || !form.branch_id) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await createExpense(token, {
        ...form,
        vendor_name: form.vendor_name.trim() || null,
        reference_number: form.reference_number.trim() || null,
        notes: form.notes.trim() || null,
      });
      setSuccess(`Expense #${saved.id} recorded for ${saved.branch_name}.`);
      setForm((current) => ({
        ...current,
        description: "",
        amount: "",
        vendor_name: "",
        reference_number: "",
        notes: "",
      }));
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const runVoid = async (expense: Expense) => {
    if (!token || !canWrite || expense.source_type === "stock_intake") return;
    const reason = window.prompt("Reason for voiding this expense?");
    if (!reason || reason.trim().length < 3) return;
    setSaving(true);
    setError(null);
    try {
      await voidExpense(token, expense.id, reason.trim());
      setSuccess(`Expense #${expense.id} voided.`);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Branch-level cost control</p>
          <h2>Expense management</h2>
          <p className="page-description">
            Record operating costs separately for each shop. Cash expenses are included automatically in Daily Closing reconciliation.
          </p>
        </div>
        <button className="action-button secondary" onClick={() => void load()} type="button">
          <RefreshCw aria-hidden="true" size={16} />
          Refresh
        </button>
      </div>

      {summary ? (
        <section className="metric-grid">
          <MetricCard metric={{ label: "Total Expenses", value: formatCurrency(summary.total_expenses), detail: `${summary.expense_count} posted entries`, tone: "rose" }} />
          <MetricCard metric={{ label: "Cash Outflow", value: formatCurrency(summary.cash_expenses), detail: "Reduces expected cash at closing", tone: "amber" }} />
          <MetricCard metric={{ label: "Non-Cash", value: formatCurrency(summary.non_cash_expenses), detail: "UPI, card, bank, credit and other", tone: "blue" }} />
          <MetricCard metric={{ label: "Stock Purchases", value: formatCurrency(summary.stock_purchase_expenses), detail: "Linked stock-feed purchases", tone: "green" }} />
        </section>
      ) : null}

      <div className="filter-bar dashboard-filter-bar">
        <div className="filter-actions">
          <select aria-label="Expense branch" value={branchId} onChange={(e) => setBranchId(Number(e.target.value))}>
            {!user?.branch_id ? <option value={0}>All accessible branches</option> : null}
            {availableBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
          </select>
          <select aria-label="Expense category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {CATEGORIES.map((row) => <option key={row.value} value={row.value}>{row.label}</option>)}
          </select>
          <label className="date-filter">Start <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
          <label className="date-filter">End <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
        </div>
      </div>

      {error ? <ErrorState message={error} title="Expense action failed" /> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <div className="content-grid expense-grid">
        <article className="panel">
          <div className="panel-header"><div><p className="eyebrow">Ledger</p><h3>Shop expenses</h3></div></div>
          {loading ? <LoadingState label="Loading expenses" /> : null}
          {!loading && rows.length === 0 ? <EmptyState title="No expenses" message="No expense entries match this branch and period." /> : null}
          {!loading && rows.length > 0 ? (
            <div className="table-shell">
              <table>
                <thead><tr><th>Date / Branch</th><th>Category</th><th>Description</th><th>Payment</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                  {rows.map((expense) => (
                    <tr key={expense.id}>
                      <td><strong>{expense.expense_date}</strong><span>{expense.branch_name}</span></td>
                      <td>{categoryLabel(expense.category)}{expense.source_type === "stock_intake" ? <span>Linked stock feed #{expense.source_id}</span> : null}</td>
                      <td><strong>{expense.description}</strong><span>{expense.vendor_name ?? expense.reference_number ?? "No vendor/reference"}</span></td>
                      <td>{expense.payment_mode.replaceAll("_", " ")}</td>
                      <td>{formatCurrency(expense.amount)}</td>
                      <td>{expense.status}{expense.void_reason ? <span>{expense.void_reason}</span> : null}</td>
                      <td>
                        <button
                          className="action-button secondary"
                          disabled={!canWrite || saving || expense.status !== "posted" || expense.source_type === "stock_intake"}
                          onClick={() => void runVoid(expense)}
                          type="button"
                        >
                          {expense.source_type === "stock_intake" ? "Linked" : "Void"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>

        <article className="panel">
          <div className="panel-header"><div><p className="eyebrow">New entry</p><h3>Add expense</h3></div><ReceiptIndianRupee aria-hidden="true" size={20} /></div>
          {!canWrite ? <p className="page-description">Your role has read-only expense access.</p> : (
            <form className="master-form" onSubmit={submit}>
              <label>Shop / branch
                <select value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: Number(e.target.value) })} required>
                  <option value={0}>Select branch</option>
                  {availableBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                </select>
              </label>
              <div className="form-grid two">
                <label>Date <input type="date" value={form.expense_date} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} required /></label>
                <label>Category
                  <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as ExpenseCategory })}>
                    {CATEGORIES.filter((row) => row.value !== "stock_purchase").map((row) => <option key={row.value} value={row.value}>{row.label}</option>)}
                  </select>
                </label>
              </div>
              <label>Description <input maxLength={240} placeholder="AC service, electricity bill, cleaning, repair…" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></label>
              <div className="form-grid two">
                <label>Amount <input min="0.01" step="0.01" type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></label>
                <label>Payment
                  <select value={form.payment_mode} onChange={(e) => setForm({ ...form, payment_mode: e.target.value })}>
                    {PAYMENT_MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
              </div>
              <label>Vendor / paid to <input maxLength={160} value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} /></label>
              <label>Bill / reference <input maxLength={160} value={form.reference_number} onChange={(e) => setForm({ ...form, reference_number: e.target.value })} /></label>
              <label>Notes <textarea maxLength={1000} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
              <button className="action-button primary" disabled={saving || !form.branch_id || !form.description.trim() || Number(form.amount) <= 0} type="submit">
                {saving ? "Saving…" : "Record expense"}
              </button>
            </form>
          )}
        </article>
      </div>
    </section>
  );
}
