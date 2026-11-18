import { useState } from "react";

import { requestPurge } from "../api/governance";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

export function PurgeReviewPage() {
  const { token } = useAuth();
  const [entityId, setEntityId] = useState("");
  const [reason, setReason] = useState("");
  const [backupReference, setBackupReference] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!token) return <LoadingState label="Loading purge controls" />;
  const submit = async () => {
    try {
      setError(null);
      const row = await requestPurge(token, { entity_type: "demo_cafe_order", entity_id: Number(entityId), reason, backup_reference: backupReference });
      setMessage(`Purge request #${row.id} created. Approval and typed confirmation are still required.`);
    } catch (err) { setError((err as Error).message); }
  };
  return <section className="page-stack" data-p10-scope="purge-review"><div className="page-header"><div><p className="eyebrow">P10 · Controlled purge</p><h2>Exceptional demo-data removal</h2><p className="page-description">This screen never exposes SQL or arbitrary table controls. A verified backup, dependency report, approval, step-up, and typed confirmation are mandatory.</p></div></div>{error ? <ErrorState message={error} /> : null}{message ? <article className="state-panel"><p>{message}</p></article> : null}<article className="panel"><label>Demo Cafe order ID<input value={entityId} onChange={(e) => setEntityId(e.target.value)} /></label><label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} /></label><label>Backup reference<input value={backupReference} onChange={(e) => setBackupReference(e.target.value)} /></label><button className="logout-button" type="button" onClick={() => void submit()}>Request controlled purge</button></article></section>;
}
