import type { AuthUser as LegacyAuthUser, UserRole as LegacyUserRole } from "../types";

export type BusinessType = "retail" | "cafe";

export type ServerUserRole =
  | LegacyUserRole
  | "super_admin"
  | "order_taker"
  | "kitchen";

export const SERVER_ROLE_LABELS: Record<ServerUserRole, string> = {
  super_admin: "Business Owner",
  admin: "Venture Admin",
  store_manager: "Store Manager",
  staff: "Staff",
  analyst: "Analyst",
  order_taker: "Order Taker",
  kitchen: "Kitchen",
};

export type ServerAuthUser = {
  id: number;
  business_group_id: number;
  company_id: number | null;
  company_name: string | null;
  company_slug: string | null;
  company_business_type: BusinessType | null;
  name: string;
  email: string;
  role: ServerUserRole;
  branch_id: number | null;
  permissions: string[];
  is_active: boolean;
  mfa_enabled: boolean;
};

export type AuthUser = Omit<LegacyAuthUser, "role"> & {
  business_group_id: number;
  company_id: number | null;
  company_name: string | null;
  company_slug: string | null;
  company_business_type: BusinessType | null;
  permissions: string[];
  mfa_enabled: boolean;
  /** Authoritative backend role used by the P3 portal router. */
  server_role: ServerUserRole;
  /** Compatibility role used only inside the existing Retail operational pages. */
  role: LegacyUserRole;
};

export type ServerLoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: ServerAuthUser;
};

export type LoginResponse = Omit<ServerLoginResponse, "user"> & {
  user: AuthUser;
};

export function legacyShellRole(role: ServerUserRole): LegacyUserRole {
  if (role === "super_admin") return "admin";
  if (role === "order_taker" || role === "kitchen") return "staff";
  return role;
}

export function normalizeAuthUser(user: ServerAuthUser): AuthUser {
  return {
    ...user,
    server_role: user.role,
    role: legacyShellRole(user.role),
  };
}
