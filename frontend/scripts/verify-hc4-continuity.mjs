import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const page = read("src/pages/CafeContinuityPage.tsx");
const api = read("src/api/continuity.ts");
const portal = read("src/portals/CafePortal.tsx");

const states = ["live", "offline_local", "cloud_continuity", "synchronizing", "stale", "attention_required"];
const assertions = [
  [states.every((state) => page.includes(`${state}:`) || api.includes(`\"${state}\"`)), "all approved HC4 continuity states must be represented"],
  [api.includes('"/sync/status"'), "continuity UI must use server-side sync status"],
  [api.includes('"/sync/reconcile"'), "reconciliation must use the Local Hub API"],
  [api.includes('"/sync/dead-letters"'), "dead-letter visibility must use the scoped Local Hub API"],
  [page.includes("fencing_epoch") || page.includes("fencing epoch") || page.includes("Fencing epoch"), "fencing epoch must be visible"],
  [page.includes("pending_inbox") && page.includes("pending_outbox"), "queue counts must be visible"],
  [page.includes("attention_message"), "attention reason must be visible"],
  [page.includes('server_role === "admin"') && page.includes('server_role === "store_manager"'), "mutating continuity actions must remain role-gated"],
  [portal.includes("CafeContinuityPage") && portal.includes('active === "dashboard"'), "Cafe dashboard must surface HC4 continuity state"],
  [!page.includes("SUPABASE_SERVICE_ROLE_KEY") && !page.includes("SYNC_DEVICE_SECRET"), "continuity UI must contain no server-only credential names"],
];

for (const [passed, message] of assertions) {
  if (!passed) {
    console.error(`HC4 continuity verification failed: ${message}`);
    process.exit(1);
  }
}

console.log(`HC4 continuity verification passed: ${assertions.length} checks.`);
