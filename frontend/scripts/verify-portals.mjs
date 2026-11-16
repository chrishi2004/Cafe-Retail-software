import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import ts from "typescript";

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const entryShim = read("src/App.ts");
const main = read("src/main.tsx");
const portalRoot = read("src/PortalRoot.tsx");
const routingSource = read("src/portalRouting.ts");
const { outputText } = ts.transpileModule(routingSource, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const routing = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const cafe = (server_role) => ({ server_role, company_business_type: "cafe" });
const retail = (server_role) => ({ server_role, company_business_type: "retail" });
const cafePortal = read("src/portals/CafePortal.tsx");
const billingPage = read("src/pages/CafeBillingPage.tsx");
const receipt = read("src/components/CafeReceipt.tsx");
const receiptHistory = read("src/pages/CafeReceiptHistoryPage.tsx");
const superPortal = read("src/portals/SuperAdminPortal.tsx");

const assertions = [
  [entryShim.includes('export { default } from "./PortalRoot"'), "extensionless App entry must route to PortalRoot"],
  [portalRoot.includes('import("./App.tsx")'), "PortalRoot must preserve the original Retail App.tsx"],
  [["super-admin", "retail", "cafe"].every((kind) => routing.portalFromPath(`/${kind}/test`) === kind), "all authenticated portal kinds must exist"],
  [routing.defaultPortal(cafe("admin")) === "cafe" && routing.defaultPortal(retail("admin")) === "retail", "default portals must derive from server venture type"],
  [!routing.canEnterPortal(cafe("admin"), "super-admin") && routing.canEnterPortal(cafe("super_admin"), "super-admin"), "only the owner may enter Super Admin"],
  [routing.safePathForUser(cafe("admin"), "/retail/overview") === "/cafe/dashboard" && routing.safePathForUser(retail("admin"), "/cafe/dashboard") === "/retail/overview", "users must not enter the other venture"],
  [routing.defaultPathForUser(cafe("kitchen")) === "/cafe/kitchen" && routing.allowedCafeSections("kitchen").join(",") === "kitchen", "Kitchen role must have preparation-only navigation"],
  [["pos", "orders", "billing", "receipts"].every((section) => routing.safePathForUser(cafe("order_taker"), `/cafe/${section}`) === `/cafe/${section}`), "Order Taker must have counter POS, Live Orders, Billing and Receipt history"],
  [["dashboard", "reports", "settings", "closing", "inventory", "menu"].every((section) => routing.safePathForUser(cafe("order_taker"), `/cafe/${section}`) === "/cafe/pos"), "Order Taker must not enter management pages"],
  [main.includes('window.location.pathname.startsWith("/order/")') && main.includes("<CustomerMenuEntry />"), "public QR route must remain separate from authenticated portals"],
  [cafePortal.includes("CafeLiveOrdersPage") && cafePortal.includes("CafeNewOrderPage") && cafePortal.includes("CafeKitchenPage"), "P7 operational Cafe pages must remain wired"],
  [cafePortal.includes("CafeBillingPage") && cafePortal.includes('active === "billing"'), "P8 must activate the Cafe billing workspace"],
  [billingPage.includes("Idempotency-Key") === false && billingPage.includes("checkoutKey"), "P8 UI must keep checkout idempotency state rather than expose a free-form key"],
  [billingPage.includes("quoteCafeTableSession") && billingPage.includes("quoteCafeOrder"), "P8 billing totals must come from backend quote endpoints"],
  [billingPage.includes("<CafeReceiptView") && receiptHistory.includes("<CafeReceiptView") && receipt.includes("window.print()") && receipt.includes('id="cafe-receipt-print-root"'), "Billing and receipt history must use the shared browser-printable receipt"],
  [![billingPage, receipt].some((source) => source.includes("dangerouslySetInnerHTML")), "Printable receipts must not render invoice data as raw HTML"],
  [superPortal.includes("activeVentureStorage.set"), "Super Admin venture selector must set explicit backend venture scope"],
];

for (const [passed, message] of assertions) {
  if (!passed) {
    console.error(`Portal verification failed: ${message}`);
    process.exit(1);
  }
}

console.log(`Portal verification passed: ${assertions.length} checks.`);
