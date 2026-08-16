import type { AuthUser, ServerUserRole } from "./auth/types";

export type PortalKind = "super-admin" | "retail" | "cafe";

export function portalFromPath(pathname: string): PortalKind | null {
  if (pathname === "/super-admin" || pathname.startsWith("/super-admin/")) return "super-admin";
  if (pathname === "/retail" || pathname.startsWith("/retail/")) return "retail";
  if (pathname === "/cafe" || pathname.startsWith("/cafe/")) return "cafe";
  return null;
}

export function defaultPortal(user: AuthUser): PortalKind {
  if (user.server_role === "super_admin") return "super-admin";
  return user.company_business_type === "cafe" ? "cafe" : "retail";
}

export function canEnterPortal(user: AuthUser, portal: PortalKind): boolean {
  if (user.server_role === "super_admin") return true;
  if (portal === "super-admin") return false;
  if (portal === "cafe") return user.company_business_type === "cafe";
  return user.company_business_type === "retail";
}

export function defaultPathForUser(user: AuthUser): string {
  const portal = defaultPortal(user);
  if (portal === "super-admin") return "/super-admin/ventures";
  if (portal === "retail") return "/retail/overview";
  if (user.server_role === "kitchen") return "/cafe/kitchen";
  if (user.server_role === "order_taker") return "/cafe/orders";
  return "/cafe/dashboard";
}

export function allowedCafeSections(role: ServerUserRole): string[] {
  if (role === "kitchen") return ["kitchen"];
  if (role === "order_taker") return ["orders", "pos", "billing"];
  if (role === "analyst") return ["dashboard", "reports"];
  if (role === "staff") return ["orders", "pos", "tables"];
  if (role === "store_manager") return ["dashboard", "orders", "pos", "tables", "menu", "billing", "reports"];
  return ["dashboard", "orders", "pos", "tables", "menu", "billing", "reports", "staff", "settings"];
}

export function safePathForUser(user: AuthUser, pathname: string): string {
  const requestedPortal = portalFromPath(pathname);
  if (!requestedPortal || !canEnterPortal(user, requestedPortal)) return defaultPathForUser(user);

  if (requestedPortal === "cafe" && user.server_role !== "super_admin") {
    const section = pathname.split("/").filter(Boolean)[1] ?? "dashboard";
    if (!allowedCafeSections(user.server_role).includes(section)) return defaultPathForUser(user);
  }
  return pathname;
}
