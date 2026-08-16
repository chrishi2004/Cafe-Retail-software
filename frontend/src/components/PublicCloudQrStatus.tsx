import { useEffect, useState } from "react";

import { resolveCloudQr, type CloudQrResolution } from "../api/cloudClient";

function freshnessLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s old`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m old`;
  return `${Math.floor(minutes / 60)}h old`;
}

export function PublicCloudQrStatus({ token }: { token: string }) {
  const [resolution, setResolution] = useState<CloudQrResolution | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    resolveCloudQr(token)
      .then((value) => {
        if (cancelled) return;
        setResolution(value);
        setState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setResolution(null);
        setState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state === "loading") return <p className="page-description">Checking the latest Cafe snapshot…</p>;
  if (state === "unavailable" || !resolution) {
    return <p className="page-description">This Cafe table reference is unavailable, expired, or not published yet.</p>;
  }

  return (
    <div className="page-stack">
      <p className="page-description">
        {resolution.table_display_name} · {resolution.table_code}
      </p>
      <p className="page-description">
        Cloud snapshot: {freshnessLabel(resolution.stale_age_seconds)}. Customer ordering remains disabled until the P6 gate.
      </p>
    </div>
  );
}
