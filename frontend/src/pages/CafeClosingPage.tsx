import { useState } from "react";

import { closeClosing, createClosing, submitClosing, type Closing } from "../api/governance";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

export function CafeClosingPage() {
  const { token, user } = useAuth();
  const [branchId, setBranchId] = useState("");
  const [openingCash, setOpeningCash] = useState("0");
  const [countedCash, setCountedCash] = useState("");
  const [closing, setClosing] = useState<Closing | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!token) return <LoadingState label="Loading closing controls" />;
  const today = new Date().toISOString().slice(0, 10);
  const start = async () => {
    try { setError(null); setClosing(await createClosing(token, { branch_id: Number(branchId), business_date: today, opening_cash: openingCash })); }
    catch (err) { setError((err as Error).message); }
  };
  const submit = async () => {
    if (!closing) return;
    try { setClosing(await submitClosing(token, closing.id, countedCash)); } catch (err) { setError((err as Error).message); }
  };
  const finish = async () => {
    if (!closing) return;
    try { setClosing(await closeClosing(token, closing.id)); } catch (err) { setError((err as Error).message); }
  };
  return (
    <section className="page-stack" data-p10-scope="cafe-closing">
      <div className="page-header"><div><p className="eyebrow">P10 · Daily closing</p><h2>Cafe cash reconciliation</h2><p className="page-description">Scope: {user?.company_name ?? "active Cafe"} · {today}. Counted cash never changes the source payments.</p></div></div>
      {error ? <ErrorState message={error} /> : null}
      {!closing ? <article className="panel"><h3>Open today</h3><label>Branch ID<input value={branchId} onChange={(e) => setBranchId(e.target.value)} /></label><label>Opening cash<input value={openingCash} onChange={(e) => setOpeningCash(e.target.value)} /></label><button className="logout-button" type="button" onClick={() => void start()}>Open closing</button></article> : <><section className="metric-grid"><div className="metric-card blue"><span>Expected cash</span><strong>{closing.expected_cash}</strong></div><div className="metric-card amber"><span>Non-cash total</span><strong>{closing.non_cash_total}</strong></div><div className="metric-card rose"><span>Variance</span><strong>{closing.variance ?? "Pending count"}</strong></div></section><article className="panel"><h3>Status: {closing.status}</h3><label>Counted cash<input value={countedCash} onChange={(e) => setCountedCash(e.target.value)} /></label><button className="logout-button" type="button" onClick={() => void submit()}>Submit count</button><button className="logout-button" type="button" onClick={() => void finish()}>Close day</button></article></>}
    </section>
  );
}
