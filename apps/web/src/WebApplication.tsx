"use client";
import PortalApp from "./ui/PortalApp";
import { AuthProvider } from "./ui/auth/AuthContext";
import { CustomerMenuEntry } from "./ui/public/CustomerMenuEntry";
export default function WebApplication() {
  return window.location.pathname.startsWith("/order/") ? (
    <CustomerMenuEntry />
  ) : (
    <AuthProvider>
      <PortalApp />
    </AuthProvider>
  );
}
