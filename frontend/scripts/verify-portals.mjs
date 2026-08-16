import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const entryShim = read("src/App.ts");
const main = read("src/main.tsx");
const portalRoot = read("src/PortalRoot.tsx");
const routing = read("src/portalRouting.ts");
const cafePortal = read("src/portals/CafePortal.tsx");
const billingPage = read("src/pages/CafeBillingPage.tsx");
const superPortal = read("src/portals/SuperAdminPortal.tsx");

const assertions = [
  [entryShim.includes('export { default } from "./PortalRoot"'), "extensionless App entry must route to PortalRoot"],
  [portalRoot.includes('import("./App.tsx")'), "PortalRoot must preserve the original Retail App.tsx"],
  [routing.includes('"super-admin"') && routing.includes('"retail"') && routing.includes('"cafe"'), "all authenticated portal kinds must exist"],
  [routing.includes('user.company_business_type === "cafe"'), "Cafe portal selection must derive from server venture type"],
  [routing.includes('portal === "super-admin"') && routing.includes("return false"), "normal users must be blocked from Super Admin portal"],
  [routing.includes('user.company_business_type === "retail"'), "Retail portal access must derive from server venture type"],
  [routing.includes('role === "kitchen"') && routing.includes('["kitchen"]'), "Kitchen role must have preparation-only navigation"],
  [routing.includes('role === "order_taker"') && routing.includes('["orders", "pos", "billing"]'), "P8 Order Taker must have Live Orders, New Order and Billing navigation"],
  [main.includes('window.location.pathname.startsWith("/order/")') && main.includes("<CustomerMenuEntry />"), "public QR route must remain separate from authenticated portals"],
  [cafePortal.includes("CafeLiveOrdersPage") && cafePortal.includes("CafeNewOrderPage") && cafePortal.includes("CafeKitchenPage"), "P7 operational Cafe pages must remain wired"],
  [cafePortal.includes("CafeBillingPage") && cafePortal.includes('active === "billing"'), "P8 must activate the Cafe billing workspace"],
  [billingPage.includes("Idempotency-Key") === false && billingPage.includes("checkoutKey"), "P8 UI must keep checkout idempotency state rather than expose a free-form key"],
  [billingPage.includes("quoteCafeTableSession") && billingPage.includes("quoteCafeOrder"), "P8 billing totals must come from backend quote endpoints"],
  [billingPage.includes("window.print()"), "P8 must provide a browser-printable receipt action"],
  [superPortal.includes("activeVentureStorage.set"), "Super Admin venture selector must set explicit backend venture scope"],
];

for (const [passed, message] of assertions) {
  if (!passed) {
    console.error(`Portal verification failed: ${message}`);
    process.exit(1);
  }
}

console.log(`Portal verification passed: ${assertions.length} checks.`);
