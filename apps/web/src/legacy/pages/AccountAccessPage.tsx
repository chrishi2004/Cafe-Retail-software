import { useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "../api/client";
import { claimEmployeePassword } from "../api/employees";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import { defaultPathForUser } from "../portalRouting";

export function PasswordSetupPage() {
  const [code] = useState(() => window.location.hash.slice(1));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [complete, setComplete] = useState(false);
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(window.history.state, "", window.location.pathname);
  }, []);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== form.get("confirm")) { setError("The passwords do not match."); return; }
    setSaving(true); setError("");
    try { await claimEmployeePassword(code, password); setComplete(true); }
    catch (err) { setError((err as Error).message); }
    finally { setSaving(false); }
  };
  return <main className="login-shell"><section className="panel page-stack">
    <h1>Set employee password</h1>
    {error && <ErrorState message={error} />}
    {complete ? <p role="status">Password saved. Sign in with your own email and new password.</p> :
      !code ? <p>Open the private setup link from your administrator.</p> :
        <form className="page-stack" onSubmit={submit}>
          <label>New password<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={256} required /></label>
          <label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" minLength={12} maxLength={256} required /></label>
          <button type="submit" className="action-button primary" disabled={saving}>Set password</button>
        </form>}
    <a href="/login">Back to sign in</a>
  </section></main>;
}

type Enrollment = { secret: string; recovery_codes: string[]; provisioning_uri: string };

export function AccountSecurityPage() {
  const { status, token, user, logout } = useAuth();
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const start = async () => {
    setBusy(true); setError("");
    try { setEnrollment(await apiRequest<Enrollment>("/auth/mfa/enroll", { method: "POST" }, token)); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const confirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await apiRequest("/auth/mfa/confirm", { method: "POST", body: JSON.stringify({ totp_code: String(form.get("code")).trim() }) }, token);
      setComplete(true);
      setEnrollment(null);
      await logout();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  return <main className="login-shell"><section className="panel page-stack">
    <h1>Account security</h1>
    {error && <ErrorState message={error} />}
    {complete ? <p role="status">MFA is enabled. Sign in again using a fresh authenticator code.</p> :
      status === "checking" ? <LoadingState label="Checking session" /> :
        !token ? <p>Sign in to manage your authenticator.</p> :
          user?.mfa_enabled ? <p>Authenticator verification is already enabled.</p> :
            !enrollment ? <button className="action-button primary" type="button" disabled={busy} onClick={() => void start()}>Enable authenticator</button> :
              <form className="page-stack" onSubmit={confirm}>
                <p>Add a time-based account in your authenticator app using this setup key. Save the recovery codes somewhere private before continuing.</p>
                <label>Authenticator setup key<input readOnly value={enrollment.secret} onFocus={(e) => e.currentTarget.select()} /></label>
                <label>Recovery codes<textarea readOnly value={enrollment.recovery_codes.join("\n")} rows={8} /></label>
                <label>Authenticator code<input name="code" autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" required /></label>
                <button className="action-button primary" type="submit" disabled={busy}>Confirm authenticator</button>
              </form>}
    <a href={token && user ? defaultPathForUser(user) : "/login"}>{token && user ? "Back to workspace" : "Back to sign in"}</a>
  </section></main>;
}
