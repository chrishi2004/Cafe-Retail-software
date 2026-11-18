import type { ServerAuthUser, ServerUserRole } from "../auth/types";
import { apiRequest } from "./client";

export type Employee = ServerAuthUser & {
  last_login_at: string | null;
  password_setup_required: boolean;
  can_manage: boolean;
};
export type EmployeeOptions = {
  roles: ServerUserRole[];
  ventures: Array<{ id: number; name: string; type: "cafe" | "retail" }>;
  branches: Array<{ id: number; name: string; company_id: number }>;
};
export type EmployeeChanges = Partial<Pick<Employee, "name" | "email" | "role" | "company_id" | "branch_id" | "is_active">>;
type Setup = { code: string; expires_at: string };

export const listEmployees = (token: string) => apiRequest<Employee[]>("/venture-users", {}, token);
export const employeeOptions = (token: string) => apiRequest<EmployeeOptions>("/venture-users/options", {}, token);
export const verifyEmployeeManager = (token: string, password: string, totp_code: string) =>
  apiRequest("/auth/step-up", { method: "POST", body: JSON.stringify({ password, totp_code }) }, token);
export const saveEmployee = (token: string, id: number | null, changes: EmployeeChanges) =>
  apiRequest<Employee & { setup?: Setup }>(id === null ? "/venture-users" : `/venture-users/${id}`, {
    method: id === null ? "POST" : "PUT", body: JSON.stringify(changes),
  }, token);
export const resetEmployeePassword = (token: string, id: number) =>
  apiRequest<{ setup: Setup }>(`/venture-users/${id}/password-reset`, { method: "POST" }, token);
export const claimEmployeePassword = (code: string, password: string) =>
  apiRequest("/auth/employee-password", { method: "POST", body: JSON.stringify({ code, password }) });
