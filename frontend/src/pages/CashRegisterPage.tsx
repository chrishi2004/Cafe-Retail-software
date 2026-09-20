import { useState } from "react";
import { addRegisterMovement, closeRegister, countRegister, openRegister, readRegister, type RegisterSummary } from "../api/cashRegister";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

export function CashRegisterPage() {
  const { token } = useAuth();
  const [branchId, setBranchId] = useState("");
  const [openingFloat, setOpeningFloat] = useState("0");
  const [countedCash, setCountedCash] = useState("");
  const [movementType, setMovementType] = useState("cash_out");
  const [movementAmount, setMovementAmount] = useState("");
  const [movementReason, setMovementReason] = useState("");
  const [register, setRegister] = useState<RegisterSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!token) return <LoadingState label="Loading cash register" />;
  const authToken = token;

  async function start() {
    setError(null);
    try { setRegister(await openRegister(authToken, { branch_id: Number(branchId), opening_float: openingFloat })); }
    catch (err) { setError((err as Error).message); }
  }
  async function movement() {
    if (!register) return;
    setError(null);
    try {
      await addRegisterMovement(authToken, register.id, { movement_type: movementType, amount: movementAmount, reason: movementReason, idempotency_key: `ui-${Date.now()}-${Math.random()}` });
      setRegister(await readRegister(authToken, register.id));
      setMovementAmount(""); setMovementReason("");
    } catch (err) { setError((err as Error).message); }
  }
  async function count() {
    if (!register) return;
    setError(null);
    try { setRegister(await countRegister(authToken, register.id, countedCash)); }
    catch (err) { setError((err as Error).message); }
  }
  async function close() {
    if (!register) return;
    setError(null);
    try { setRegister(await closeRegister(authToken, register.id)); }
    catch (err) { setError((err as Error).message); }
  }

  return <section className="page-stack" data-p7-scope="cash-register">
    <div className="page-header"><div><p className="eyebrow">P7 · Cash register</p><h2>Shift drawer reconciliation</h2><p className="page-description">Open one drawer session per branch, record movements, then count and close it.</p></div></div>
    {error && <ErrorState message={error} />}
    {!register ? <article className="panel"><h3>Open register session</h3><label>Branch ID<input value={branchId} onChange={(event) => setBranchId(event.target.value)} inputMode="numeric" /></label><label>Opening float<input value={openingFloat} onChange={(event) => setOpeningFloat(event.target.value)} inputMode="decimal" /></label><button className="logout-button" type="button" onClick={() => void start()}>Open register</button></article> : <>
      <section className="metric-grid"><div className="metric-card blue"><span>Expected cash</span><strong>{register.expected_cash}</strong></div><div className="metric-card amber"><span>Cash sales</span><strong>{register.cash_collections}</strong></div><div className="metric-card rose"><span>Variance</span><strong>{register.variance ?? "Pending count"}</strong></div></section>
      <article className="panel"><h3>Session #{register.id} · {register.status}</h3><p>Modes: {register.mode_totals.map((mode) => `${mode.mode} ${mode.amount}`).join(" · ") || "No payments yet"}</p><label>Movement type<select value={movementType} onChange={(event) => setMovementType(event.target.value)}><option value="cash_in">Cash in</option><option value="cash_out">Cash out</option><option value="expense">Expense</option><option value="adjustment">Adjustment</option></select></label><label>Amount<input value={movementAmount} onChange={(event) => setMovementAmount(event.target.value)} inputMode="decimal" /></label><label>Reason<input value={movementReason} onChange={(event) => setMovementReason(event.target.value)} /></label><button className="logout-button" type="button" onClick={() => void movement()} disabled={register.status !== "open"}>Record movement</button></article>
      <article className="panel"><h3>Count and close</h3><label>Counted cash<input value={countedCash} onChange={(event) => setCountedCash(event.target.value)} inputMode="decimal" /></label><button className="logout-button" type="button" onClick={() => void count()} disabled={register.status !== "open"}>Submit count</button><button className="logout-button" type="button" onClick={() => void close()} disabled={register.status !== "open" || !register.counted_cash}>Close register</button></article>
    </>}
  </section>;
}
