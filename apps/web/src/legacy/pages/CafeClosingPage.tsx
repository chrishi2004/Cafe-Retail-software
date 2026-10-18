import { useEffect, useRef, useState } from "react";
import {
  closeClosing,
  createClosing,
  getClosing,
  reopenClosing,
  submitClosing,
  type Closing,
} from "../api/governance";
import { listBranches } from "../api/masterData";
import { apiRequest } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Branch } from "../types";
import { cafeToday } from "../utils/cafeDates";

export function CafeClosingPage({
  title = "Café cash reconciliation",
}: { title?: string } = {}) {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [openingCash, setOpeningCash] = useState("0");
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [countedCash, setCountedCash] = useState("");
  const [closing, setClosing] = useState<Closing | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const today = cafeToday();
  useEffect(() => {
    if (!token) return;
    let active = true;
    listBranches(token)
      .then((rows) => {
        if (active) {
          setBranches(rows);
          setBranchId(rows[0]?.id ?? 0);
          if (!rows.length) setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [token]);
  useEffect(() => {
    if (!token || !branchId) return;
    let active = true;
    setLoading(true);
    setClosing(null);
    setCountedCash("");
    setOpeningCash("0");
    getClosing(token, branchId, today)
      .then((row) => {
        if (active) {
          setClosing(row);
          setCountedCash(row?.counted_cash ?? "");
        }
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, branchId, today]);
  const run = async (action: "open" | "submit" | "close" | "reopen") => {
    if (!token || lock.current || !branchId) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      if (action === "reopen")
        await apiRequest(
          "/auth/step-up",
          {
            method: "POST",
            body: JSON.stringify({ password, totp_code: totpCode }),
          },
          token,
        );
      const row =
        action === "open"
          ? await createClosing(token, {
              branch_id: branchId,
              business_date: today,
              opening_cash: openingCash,
            })
          : action === "reopen" && closing
            ? await reopenClosing(token, closing.id, reason)
            : closing &&
              (action === "submit"
                ? await submitClosing(token, closing.id, countedCash)
                : await closeClosing(token, closing.id));
      if (row) setClosing(row);
      setPassword("");
      setTotpCode("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  const editable = closing && ["open", "reopened"].includes(closing.status);
  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Daily Closing</p>
          <h2>{title}</h2>
          <p>
            {user?.company_name} · {today}
          </p>
        </div>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <label>
        Branch{" "}
        <select
          disabled={busy}
          value={branchId}
          onChange={(e) => {
            setError(null);
            setBranchId(Number(e.target.value));
          }}
        >
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.name}
            </option>
          ))}
        </select>
      </label>
      {loading ? (
        <LoadingState label="Loading business day" />
      ) : !branchId ? (
        <p>No authorized active Café branch is available.</p>
      ) : !closing ? (
        <article className="panel">
          <h3>Open today</h3>
          <label>
            Opening cash
            <input
              type="number"
              min="0"
              step="0.01"
              value={openingCash}
              onChange={(e) => setOpeningCash(e.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={busy || openingCash === "" || Number(openingCash) < 0}
            onClick={() => void run("open")}
          >
            Open business day
          </button>
        </article>
      ) : (
        <>
          <section className="metric-grid">
            {[
              ["Opening cash", closing.opening_cash],
              ["Cash collections", closing.cash_collections],
              ["Expected cash", closing.expected_cash],
              ["Non-cash totals", closing.non_cash_total],
              ["Counted cash", closing.counted_cash ?? "Pending"],
              ["Variance", closing.variance ?? "Pending count"],
            ].map(([label, value]) => (
              <div className="metric-card" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </section>
          <article className="panel">
            <h3>Status: {closing.status}</h3>
            {editable ? (
              <>
                <label>
                  Counted cash
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={countedCash}
                    onChange={(e) => setCountedCash(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  disabled={
                    busy || countedCash === "" || Number(countedCash) < 0
                  }
                  onClick={() => void run("submit")}
                >
                  Submit count
                </button>
                <p>
                  Submitting stops billing for this day until the owner reopens
                  it.
                </p>
              </>
            ) : null}
            {closing.status === "submitted" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void run("close")}
              >
                Close day
              </button>
            ) : null}
            {["submitted", "closed"].includes(closing.status) &&
            ["admin", "super_admin"].includes(user?.server_role ?? "") ? (
              <>
                <label>
                  Correction reason
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    maxLength={500}
                  />
                </label>
                <label>
                  Confirm password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <label>
                  Authenticator code
                  <input
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={totpCode}
                    onChange={(e) =>
                      setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                  />
                </label>
                <button
                  type="button"
                  disabled={
                    busy ||
                    reason.trim().length < 3 ||
                    !password ||
                    totpCode.length !== 6
                  }
                  onClick={() => void run("reopen")}
                >
                  Reopen day
                </button>
              </>
            ) : null}
            {closing.status === "closed" ? (
              <p>Day closed. The recorded count and variance are saved.</p>
            ) : null}
          </article>
        </>
      )}
    </section>
  );
}
