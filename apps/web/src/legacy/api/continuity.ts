import { apiRequest } from "./client";

export type ContinuityMode =
  | "live"
  | "offline_local"
  | "cloud_continuity"
  | "synchronizing"
  | "stale"
  | "attention_required";

export type SyncContinuityStatus = {
  company_id: number | null;
  branch_ids: number[];
  pending_inbox: number;
  pending_outbox: number;
  dead_letters: number;
  oldest_pending_age_seconds: number | null;
  last_inbound_sync_at: string | null;
  last_outbound_sync_at: string | null;
  local_device_last_seen_at: string | null;
  continuity_mode: ContinuityMode | null;
  fencing_epoch: number;
  lease_expires_at: string | null;
  last_heartbeat_at: string | null;
  last_cloud_contact_at: string | null;
  last_reconciled_at: string | null;
  last_queue_drain_at: string | null;
  reconciliation_status: "pending" | "clean" | "attention_required" | null;
  attention_message: string | null;
};

export type ReconciliationReport = {
  reconciliation_reference: string;
  scope_key: string;
  fencing_epoch: number;
  status: "pending" | "clean" | "attention_required";
  pending_inbox_before: number;
  pending_outbox_before: number;
  pending_inbox_after: number;
  pending_outbox_after: number;
  order_mismatch_count: number;
  invoice_mismatch_count: number;
  payment_mismatch_count: number;
  stock_mismatch_count: number;
  queue_receipt_mismatch_count: number;
  closing_mismatch_count: number;
  dead_letter_count: number;
  details: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
};

export type DeadLetter = {
  id: number;
  direction: string;
  event_id: string;
  correlation_id: string;
  error_code: string;
  error_message: string;
  retryable: boolean;
  retry_count: number;
  status: string;
  first_failed_at: string;
  last_failed_at: string;
};

export function getSyncContinuityStatus(token: string): Promise<SyncContinuityStatus> {
  return apiRequest<SyncContinuityStatus>("/sync/status", {}, token);
}

export function getLatestReconciliation(token: string): Promise<ReconciliationReport> {
  return apiRequest<ReconciliationReport>("/sync/reconciliation", {}, token);
}

export function runReconciliation(token: string): Promise<ReconciliationReport> {
  return apiRequest<ReconciliationReport>("/sync/reconcile", { method: "POST" }, token);
}

export function listDeadLetters(token: string): Promise<DeadLetter[]> {
  return apiRequest<DeadLetter[]>("/sync/dead-letters", {}, token);
}

export function retryDeadLetter(token: string, id: number): Promise<{ id: number; event_id: string; status: string; retry_count: number }> {
  return apiRequest(`/sync/dead-letters/${id}/retry`, { method: "POST" }, token);
}
