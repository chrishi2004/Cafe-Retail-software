import { TaxOperationPanel } from "../components/TaxOperationPanel";
import { SettingsPage } from "./SettingsPage";

export function SettingsWithTaxPage() {
  return (
    <div className="page-stack">
      <TaxOperationPanel />
      <SettingsPage />
    </div>
  );
}
