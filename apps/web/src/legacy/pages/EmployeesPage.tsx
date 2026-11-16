import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import {
  employeeOptions, listEmployees, resetEmployeePassword, saveEmployee, verifyEmployeeManager,
  type Employee, type EmployeeChanges, type EmployeeOptions,
} from "../api/employees";
import { useAuth } from "../auth/AuthContext";
import { SERVER_ROLE_LABELS, type ServerUserRole } from "../auth/types";
import { ErrorState, LoadingState } from "../components/ui";
import { formatDateTime } from "../utils/format";

type Operation = { kind: "save" | "status" | "reset"; id: number | null; changes?: EmployeeChanges };
const branchRoles = ["store_manager", "staff", "order_taker", "kitchen"];
const statusOf = (employee: Employee) => !employee.is_active ? "Inactive" :
  employee.password_setup_required ? "Setup required" : "Active";

export function EmployeesPage() {
  const { token, user } = useAuth();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [options, setOptions] = useState<EmployeeOptions | null>(null);
  const [edit, setEdit] = useState<"new" | Employee | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [venture, setVenture] = useState(0);
  const [branch, setBranch] = useState(0);
  const [role, setRole] = useState<ServerUserRole>("staff");
  const [companyId, setCompanyId] = useState(0);
  const [branchId, setBranchId] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [setup, setSetup] = useState<{ url: string; expires: string } | null>(null);
  const [verification, setVerification] = useState<Operation | null>(null);
  const [busy, setBusy] = useState(false);
  const operationLock = useRef(false);

  const reload = useCallback(async () => { if (token) setEmployees(await listEmployees(token)); }, [token]);
  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([listEmployees(token), employeeOptions(token)]).then(([rows, choices]) => {
      if (active) { setEmployees(rows); setOptions(choices); }
    }).catch((err: Error) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [token]);

  const selectEdit = (employee: Employee | "new") => {
    setSetup(null); setError(""); setNotice(""); setVerification(null);
    const initial = employee === "new" ? null : employee;
    const company = initial?.company_id ?? user?.company_id ?? options?.ventures[0]?.id ?? 0;
    setCompanyId(company);
    setBranchId(initial?.branch_id ?? user?.branch_id ?? 0);
    setRole(initial?.role ?? "staff");
    setEdit(employee);
  };
  const run = async (operation: Operation, credentials?: { password: string; totp: string }) => {
    if (!token || operationLock.current) return;
    operationLock.current = true; setBusy(true); setError(""); setNotice(""); setSetup(null);
    try {
      if (credentials) await verifyEmployeeManager(token, credentials.password, credentials.totp);
      const result = operation.kind === "reset"
        ? await resetEmployeePassword(token, operation.id!)
        : await saveEmployee(token, operation.id, operation.changes ?? {});
      setVerification(null);
      setEdit(null);
      if (result.setup) setSetup({
        url: `${window.location.origin}/account/setup#${result.setup.code}`, expires: result.setup.expires_at,
      });
      setNotice(operation.kind === "reset" ? "Password setup link created." :
        operation.kind === "status" ? (operation.changes?.is_active ? "Employee activated." : "Employee deactivated. Their sessions were signed out.") :
          operation.id === null ? "Employee added." : "Employee updated.");
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.code === "step_up_required") setVerification(operation);
      else setError((err as Error).message);
    } finally {
      operationLock.current = false; setBusy(false);
    }
  };
  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run({ kind: "save", id: edit === "new" ? null : edit!.id, changes: {
      name: String(form.get("name")), email: String(form.get("email")), role,
      company_id: companyId || null, branch_id: branchId || null,
    }});
  };
  const verify = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!verification) return;
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    void run(verification, { password: String(form.get("password")), totp: String(form.get("totp") ?? "").trim() });
  };
  const editCompany = options?.ventures.find((item) => item.id === companyId);
  const allowedRoles = options?.roles.filter((item) =>
    (editCompany?.type !== "retail" || !["order_taker", "kitchen"].includes(item)) &&
    (item !== "admin" || (edit !== null && edit !== "new" && edit.mfa_enabled)));
  const filtered = employees.filter((employee) =>
    (!status || statusOf(employee) === status) &&
    (!venture || employee.company_id === venture) && (!branch || employee.branch_id === branch) &&
    `${employee.name} ${employee.email} ${SERVER_ROLE_LABELS[employee.role]}`.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <section className="page-stack">
      <div className="page-header"><div><p className="eyebrow">Team access and roles</p><h2>Employees</h2></div>
        <button className="action-button primary" disabled={!options || busy || !!verification} type="button" onClick={() => selectEdit("new")}>Add employee</button>
      </div>
      {error && <ErrorState message={error} />}
      {notice && <p role="status">{notice}</p>}
      {setup && <article className="panel page-stack">
        <h3>Private setup link</h3>
        <p>Give this link directly to the employee. It works once and expires {formatDateTime(setup.expires)}.</p>
        <label>Setup link<input readOnly value={setup.url} autoComplete="off" onFocus={(e) => e.currentTarget.select()} /></label>
        <div className="filter-actions">
          <button type="button" onClick={() => void navigator.clipboard.writeText(setup.url).then(() => setNotice("Setup link copied.")).catch(() => setNotice("Select the link to copy it."))}>Copy link</button>
          <button type="button" onClick={() => setSetup(null)}>Hide link</button>
        </div>
      </article>}
      {verification && <form className="panel page-stack" onSubmit={verify}>
        <h3>Verify your account</h3>
        <label>Your password<input name="password" type="password" autoComplete="current-password" required /></label>
        {user?.mfa_enabled && <label>Authenticator code<input name="totp" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required /></label>}
        <div className="filter-actions"><button className="action-button primary" disabled={busy} type="submit">Verify and continue</button>
          <button disabled={busy} type="button" onClick={() => setVerification(null)}>Back</button></div>
      </form>}
      {edit && options && <form key={edit === "new" ? "new" : edit.id} className="panel page-stack" onSubmit={save}>
        <h3>{edit === "new" ? "Add employee" : "Edit employee"}</h3>
        <fieldset className="filter-bar" disabled={busy || !!verification}>
          <label>Full name<input name="name" defaultValue={edit === "new" ? "" : edit.name} autoComplete="off" minLength={2} maxLength={120} required /></label>
          <label>Email<input name="email" type="email" autoComplete="off" defaultValue={edit === "new" ? "" : edit.email} maxLength={254} required /></label>
          <label>Venture<select aria-label="Venture" required value={companyId || ""} disabled={user?.server_role !== "super_admin"} onChange={(e) => {
            const id = Number(e.target.value); setCompanyId(id); setBranchId(0);
            if (options.ventures.find((c) => c.id === id)?.type === "retail" && ["order_taker", "kitchen"].includes(role)) setRole("staff");
          }}>
            <option value="">Choose venture</option>{options.ventures.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label>Employee role<select value={role} onChange={(e) => {
            const next = e.target.value as ServerUserRole; setRole(next); if (next === "admin") setBranchId(0);
          }}>{allowedRoles?.map((item) => <option key={item} value={item}>{item === "staff" ? "Cashier / Staff" : SERVER_ROLE_LABELS[item]}</option>)}</select></label>
          <label>Assigned branch<select aria-label="Assigned branch" value={branchId || ""} required={branchRoles.includes(role)}
            disabled={role === "admin" || user?.server_role === "store_manager"} onChange={(e) => setBranchId(Number(e.target.value))}>
            <option value="">{branchRoles.includes(role) ? "Choose branch" : "All authorized branches"}</option>
            {options.branches.filter((item) => item.company_id === companyId).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
        </fieldset>
        {user?.server_role === "super_admin" && !allowedRoles?.includes("admin") && <p>To make a Venture Admin, the employee must first enable MFA in Account security.</p>}
        <div className="filter-actions"><button className="action-button primary" disabled={busy || !!verification} type="submit">Save employee</button>
          <button disabled={busy || !!verification} type="button" onClick={() => setEdit(null)}>Cancel</button></div>
      </form>}
      {!options && !error && <LoadingState label="Loading employees" />}
      {options && <>
        <div className="filter-bar">
          <label>Search employees<input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, email or role" /></label>
          <label>Filter status<select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option><option>Active</option><option>Inactive</option><option>Setup required</option>
          </select></label>
          {options.ventures.length > 1 && <label>Filter venture<select value={venture} onChange={(e) => { setVenture(Number(e.target.value)); setBranch(0); }}>
            <option value={0}>All ventures</option>{options.ventures.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>}
          {options.branches.length > 1 && <label>Filter branch<select value={branch} onChange={(e) => setBranch(Number(e.target.value))}>
            <option value={0}>All branches</option>{options.branches.filter((item) => !venture || item.company_id === venture).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>}
        </div>
        {filtered.length ? <div className="panel table-wrap"><table>
          <thead><tr><th>Name</th><th>Role</th><th>Venture / branch</th><th>Status</th><th>Last login (IST)</th><th>Actions</th></tr></thead>
          <tbody>{filtered.map((item) => <tr key={item.id}>
            <td><strong>{item.name}</strong><div>{item.email}</div></td>
            <td>{SERVER_ROLE_LABELS[item.role]}</td>
            <td>{item.company_name ?? "All ventures"}<div>{options.branches.find((b) => b.id === item.branch_id)?.name ?? (item.branch_id ? "Inactive branch" : "All branches")}</div></td>
            <td>{statusOf(item)}</td>
            <td>{item.last_login_at ? formatDateTime(item.last_login_at) : "Not recorded"}</td>
            <td>{item.can_manage && <div className="filter-actions">
              <button type="button" disabled={busy || !!verification} onClick={() => selectEdit(item)}>Edit</button>
              <button type="button" disabled={busy || !!verification} onClick={() => {
                if ((!item.is_active || window.confirm(`Deactivate ${item.name} and sign out all their sessions?`)))
                  void run({ kind: "status", id: item.id, changes: { is_active: !item.is_active } });
              }}>{item.is_active ? "Deactivate" : "Activate"}</button>
              {item.is_active && <button type="button" disabled={busy || !!verification} onClick={() => {
                if (window.confirm(`Reset access for ${item.name}? Existing sessions and their previous password will stop working.`))
                  void run({ kind: "reset", id: item.id });
              }}>{item.password_setup_required ? "New setup link" : "Reset password"}</button>}
            </div>}</td>
          </tr>)}</tbody>
        </table></div> : <p>No employees match these filters.</p>}
      </>}
    </section>
  );
}
