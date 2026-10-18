import { apiRequest } from "./client";

export type TaxRegistrationStatus = "unregistered" | "registered";
export type TaxOperationMode = "non_gst" | "gst";
export type CustomerDetailsOnBill = "hidden" | "basic" | "full";

export type TaxOperation = {
  company_id: number;
  company_name: string;
  tax_registration_status: TaxRegistrationStatus;
  default_tax_mode: TaxOperationMode;
  gst_effective_from: string | null;
  customer_details_on_bill: CustomerDetailsOnBill;
  b2b_gst_enabled: boolean;
  include_customer_in_gst_reports: boolean;
  gst_registration_id: number | null;
  gst_registration_configured: boolean;
  gst_registration_active: boolean;
  gstin_masked: string | null;
  can_activate_gst: boolean;
  missing_activation_prerequisites: string[];
  compliance_notice: string;
};

export type TaxOperationSettingsPayload = {
  tax_registration_status: TaxRegistrationStatus;
  customer_details_on_bill: CustomerDetailsOnBill;
  b2b_gst_enabled: boolean;
  include_customer_in_gst_reports: boolean;
  registration_id?: number | null;
  registration_active?: boolean;
};

export type GSTActivationPayload = {
  effective_from: string;
  acknowledge_professional_review: boolean;
  confirmation: string;
};

export type CombinedTurnover = {
  business_group_id: number;
  ventures: Array<{
    company_id: number;
    company_name: string;
    business_type: string;
    turnover: string;
  }>;
  combined_turnover: string;
  review_notice: string;
};

export function getTaxOperation(token: string): Promise<TaxOperation> {
  return apiRequest<TaxOperation>("/tax-operation", {}, token);
}

export function updateTaxOperationSettings(token: string, payload: TaxOperationSettingsPayload): Promise<TaxOperation> {
  return apiRequest<TaxOperation>(
    "/tax-operation/settings",
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function activateGstOperation(token: string, payload: GSTActivationPayload): Promise<TaxOperation> {
  return apiRequest<TaxOperation>(
    "/tax-operation/activate-gst",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function getCombinedTurnover(token: string): Promise<CombinedTurnover> {
  return apiRequest<CombinedTurnover>("/tax-operation/combined-turnover", {}, token);
}
