"use client";
import PortalApp from "./legacy/PortalApp";
import { AuthProvider } from "./legacy/auth/AuthContext";
import { CustomerMenuEntry } from "./legacy/public/CustomerMenuEntry";
export default function MigratedApplication() {
  return window.location.pathname.startsWith("/order/") ? (
    <CustomerMenuEntry />
  ) : (
    <AuthProvider>
      <PortalApp />
    </AuthProvider>
  );
}
