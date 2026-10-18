"use client";
import dynamic from "next/dynamic";
const Application = dynamic(() => import("./MigratedApplication"), {
  ssr: false,
  loading: () => (
    <main className="login-shell">
      <p role="status">Loading Kalpvriksh…</p>
    </main>
  ),
});
export default function ClientApplication() {
  return <Application />;
}
