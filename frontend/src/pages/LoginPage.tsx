import { FormEvent, useState } from "react";
import { LockKeyhole, LogIn, Server } from "lucide-react";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@hybridretail.test");
  const [password, setPassword] = useState("RetailDemo@123");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (loginError) {
      if (loginError instanceof ApiError) {
        setError(loginError.message);
      } else {
        setError("Could not reach the backend API. Check that FastAPI is running.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand">
          <div className="brand-mark">KV</div>
          <div>
            <p className="brand-name">Kalpvrik Business Suite</p>
            <p className="brand-subtitle">Retail and Cafe operations</p>
          </div>
        </div>

        <div className="login-copy">
          <p className="eyebrow">Secure team access</p>
          <h1 id="login-title">Sign in to your workspace</h1>
          <p>
            Owners choose a business after login. Retail and Cafe team members open directly in
            the workspace allowed for their role and branch.
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            autoComplete="email"
            id="email"
            inputMode="email"
            onChange={(event) => setEmail(event.target.value)}
            type="text"
            value={email}
          />

          <label htmlFor="password">Password</label>
          <input
            autoComplete="current-password"
            id="password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />

          {error ? (
            <div className="form-error" role="alert">
              {error}
            </div>
          ) : null}

          <button className="login-button" disabled={isSubmitting} type="submit">
            <LogIn aria-hidden="true" size={18} />
            <span>{isSubmitting ? "Signing in" : "Sign in"}</span>
          </button>
        </form>

        <div className="login-notes" aria-label="Development login notes">
          <div>
            <LockKeyhole aria-hidden="true" size={17} />
            <span>Demo password: RetailDemo@123</span>
          </div>
          <div>
            <Server aria-hidden="true" size={17} />
            <span>API: {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"}</span>
          </div>
        </div>
      </section>
    </main>
  );
}
