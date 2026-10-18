import {
  Bot,
  Boxes,
  ChartNoAxesCombined,
  ClipboardList,
  Database,
  LineChart,
  Package,
  PackageSearch,
  ReceiptText,
  Settings,
  ShoppingCart,
  Store,
  Tags,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { RouteKey, UserRole } from "./types";

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  store_manager: "Store Manager",
  staff: "Staff",
  analyst: "Analyst",
};

export type NavItem = {
  key: RouteKey;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
  roles: UserRole[];
};

const allRoles: UserRole[] = ["admin", "store_manager", "staff", "analyst"];
const operationalRoles: UserRole[] = ["admin", "store_manager", "staff"];
const reportingRoles: UserRole[] = ["admin", "store_manager", "analyst"];

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", label: "Overview", icon: ChartNoAxesCombined, roles: allRoles },
  { key: "products", label: "Products", icon: Package, roles: allRoles },
  { key: "customers", label: "Customers", icon: Users, roles: allRoles },
  { key: "pos", label: "POS Billing", shortLabel: "POS", icon: ReceiptText, roles: operationalRoles },
  { key: "sales", label: "Sales Summary", shortLabel: "Sales", icon: LineChart, roles: allRoles },
  { key: "inventory", label: "Inventory", icon: Boxes, roles: allRoles },
  { key: "low-stock", label: "Low Stock and Reorder", shortLabel: "Low Stock", icon: PackageSearch, roles: reportingRoles },
  { key: "purchase-orders", label: "Purchase Orders", shortLabel: "Orders", icon: ClipboardList, roles: reportingRoles },
  { key: "suppliers", label: "Suppliers", icon: Truck, roles: reportingRoles },
  { key: "categories", label: "Categories", icon: Tags, roles: ["admin"] },
  { key: "branches", label: "Branches", icon: Store, roles: ["admin"] },
  { key: "forecasting", label: "Forecasting", icon: ShoppingCart, roles: reportingRoles },
  { key: "ai-assistant", label: "AI Assistant", shortLabel: "AI", icon: Bot, roles: reportingRoles },
  { key: "power-bi", label: "Power BI Reports", shortLabel: "Power BI", icon: Database, roles: ["admin", "analyst"] },
  { key: "settings", label: "Settings", icon: Settings, roles: ["admin"] },
];

export function getVisibleNavItems(role: UserRole): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

export function canAccessRoute(role: UserRole, routeKey: RouteKey): boolean {
  return NAV_ITEMS.some((item) => item.key === routeKey && item.roles.includes(role));
}

export function getDefaultRoute(role: UserRole): RouteKey {
  return getVisibleNavItems(role)[0]?.key ?? "overview";
}

export function canCreateOperationalRecords(role: UserRole): boolean {
  return operationalRoles.includes(role);
}
