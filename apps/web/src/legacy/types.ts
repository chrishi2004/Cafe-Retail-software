export type UserRole = "admin" | "store_manager" | "staff" | "analyst";

export type AuthUser = {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  branch_id: number | null;
  is_active: boolean;
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
};

export type ApiErrorResponse = {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: unknown;
};

export type RouteKey =
  | "overview"
  | "products"
  | "customers"
  | "pos"
  | "sales"
  | "inventory"
  | "low-stock"
  | "purchase-orders"
  | "suppliers"
  | "categories"
  | "branches"
  | "forecasting"
  | "ai-assistant"
  | "power-bi"
  | "settings";

export type PageAction = {
  label: string;
  tone: "primary" | "secondary";
};

export type PageMetric = {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "blue" | "amber" | "rose" | "slate";
};

export type TableColumn = {
  key: string;
  label: string;
};

export type TableRow = Record<string, string>;

export type Category = {
  id: number;
  name: string;
  description: string | null;
};

export type Supplier = {
  id: number;
  name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  payment_terms: string | null;
  lead_time_days: number;
  is_active: boolean;
};

export type Branch = {
  id: number;
  name: string;
  address: string | null;
  city: string | null;
  manager_name: string | null;
  is_active: boolean;
};

export type ProductItemType = "goods" | "service";

export type Product = {
  id: number;
  sku: string;
  name: string;
  description: string | null;
  category_id: number;
  category_name: string;
  supplier_id: number;
  supplier_name: string;
  gst_rate_id: number | null;
  gst_rate_name: string | null;
  gst_rate_percent: string | null;
  unit_cost: string;
  selling_price: string;
  hsn_sac_code: string | null;
  cess_rate_percent: string;
  primary_barcode: string | null;
  unit_of_measure: string;
  mrp: string | null;
  brand: string | null;
  manufacturer: string | null;
  item_type: ProductItemType;
  batch_tracking_enabled: boolean;
  serial_tracking_enabled: boolean;
  expiry_tracking_enabled: boolean;
  reorder_threshold: string;
  target_stock_level: string;
  total_quantity_on_hand: string;
  stock_status: string;
  is_active: boolean;
};

export type ProductPayload = Omit<
  Product,
  | "id"
  | "category_name"
  | "supplier_name"
  | "gst_rate_name"
  | "gst_rate_percent"
  | "total_quantity_on_hand"
  | "stock_status"
>;
export type SupplierPayload = Omit<Supplier, "id">;
export type CategoryPayload = Omit<Category, "id">;
export type BranchPayload = Omit<Branch, "id">;

export type CustomerAddressType = "billing" | "shipping";
export type CustomerLedgerEntryType = "opening_balance" | "invoice" | "payment" | "credit_note" | "adjustment";

export type CustomerAddress = {
  id: number;
  address_type: CustomerAddressType;
  recipient_name: string | null;
  phone: string | null;
  address: string;
  city: string | null;
  state: string | null;
  state_code: string | null;
  pincode: string | null;
  gstin: string | null;
  is_default: boolean;
};

export type Customer = {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  gstin: string | null;
  billing_address: string | null;
  shipping_address: string | null;
  city: string | null;
  state: string | null;
  state_code: string | null;
  pincode: string | null;
  branch_id: number | null;
  branch_name: string | null;
  company_id: number | null;
  credit_limit: string;
  opening_balance: string;
  outstanding_balance: string;
  available_credit: string;
  is_active: boolean;
  addresses: CustomerAddress[];
  created_at: string;
  updated_at: string;
};

export type CustomerPayload = Omit<
  Customer,
  "id" | "branch_name" | "outstanding_balance" | "available_credit" | "addresses" | "created_at" | "updated_at"
>;

export type CustomerLedgerEntry = {
  id: number;
  customer_id: number;
  branch_id: number | null;
  branch_name: string | null;
  entry_type: CustomerLedgerEntryType;
  debit: string;
  credit: string;
  running_balance: string;
  reference_type: string | null;
  reference_id: number | null;
  reason: string | null;
  notes: string | null;
  created_by: number | null;
  created_by_name: string | null;
  entry_datetime: string;
  created_at: string;
};

export type CustomerPaymentPayload = {
  amount: string;
  branch_id?: number | null;
  payment_mode_id?: number | null;
  payment_datetime?: string | null;
  reference_number?: string | null;
  notes?: string | null;
};

export type CustomerPayment = {
  id: number;
  customer_id: number;
  branch_id: number | null;
  branch_name: string | null;
  payment_mode_id: number | null;
  payment_mode_name: string | null;
  amount: string;
  payment_datetime: string;
  reference_number: string | null;
  notes: string | null;
  received_by: number | null;
  received_by_name: string | null;
  ledger_entry_id: number | null;
  outstanding_balance: string;
  created_at: string;
};

export type CustomerOutstanding = {
  customer_id: number;
  customer_name: string;
  phone: string | null;
  gstin: string | null;
  branch_id: number | null;
  branch_name: string | null;
  credit_limit: string;
  outstanding_balance: string;
  available_credit: string;
  is_over_credit_limit: boolean;
  is_active: boolean;
};

export type InvoiceType = "gst" | "non_gst";
export type InvoiceStatus = "draft" | "issued" | "paid" | "partial_paid" | "credit" | "cancelled" | "returned";
export type InvoicePaymentStatus = "unpaid" | "paid" | "partial_paid" | "credit";
export type InvoiceTaxType = "cgst" | "sgst" | "igst" | "cess";

export type POSProductSearchResult = {
  product_id: number;
  sku: string;
  name: string;
  primary_barcode: string | null;
  hsn_sac_code: string | null;
  gst_rate: string;
  cess_rate_percent: string;
  unit_of_measure: string;
  mrp: string | null;
  selling_price: string;
  unit_cost: string;
  branch_id: number | null;
  branch_name: string | null;
  quantity_on_hand: string;
  is_active: boolean;
};

export type POSInvoiceItemPayload = {
  product_id: number;
  quantity: string;
  unit_price?: string | null;
  discount: string;
};

export type POSPaymentPayload = {
  payment_mode_id?: number | null;
  amount: string;
  payment_datetime?: string | null;
  reference_number?: string | null;
  notes?: string | null;
};

export type POSQuotePayload = {
  branch_id: number;
  customer_id?: number | null;
  invoice_type: InvoiceType;
  place_of_supply_state?: string | null;
  place_of_supply_state_code?: string | null;
  invoice_date?: string | null;
  items: POSInvoiceItemPayload[];
};

export type POSCheckoutPayload = POSQuotePayload & {
  payments: POSPaymentPayload[];
};

export type InvoiceQuoteItem = {
  product_id: number;
  product_name: string;
  sku: string;
  barcode: string | null;
  hsn_sac_code: string | null;
  quantity: string;
  unit_price: string;
  mrp: string | null;
  discount: string;
  taxable_value: string;
  gst_rate: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  line_total: string;
  gross_profit: string;
  quantity_on_hand: string;
};

export type InvoiceQuote = {
  branch_id: number;
  customer_id: number | null;
  invoice_type: InvoiceType;
  place_of_supply_state: string | null;
  place_of_supply_state_code: string | null;
  subtotal: string;
  discount_total: string;
  taxable_total: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  round_off: string;
  grand_total: string;
  paid_amount: string;
  balance_due: string;
  items: InvoiceQuoteItem[];
};

export type InvoiceTax = {
  id: number;
  invoice_id: number;
  invoice_item_id: number | null;
  tax_type: InvoiceTaxType;
  tax_rate: string;
  taxable_value: string;
  tax_amount: string;
};

export type InvoiceItem = {
  id: number;
  product_id: number;
  product_name_snapshot: string;
  sku_snapshot: string;
  hsn_sac_code: string | null;
  quantity: string;
  unit_price: string;
  mrp: string | null;
  discount: string;
  taxable_value: string;
  gst_rate: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  line_total: string;
  gross_profit: string;
  taxes: InvoiceTax[];
};

export type InvoicePayment = {
  id: number;
  invoice_id: number;
  payment_mode_id: number | null;
  payment_mode_name: string | null;
  amount: string;
  payment_datetime: string;
  reference_number: string | null;
  notes: string | null;
  received_by: number | null;
  received_by_name: string | null;
  is_credit_marker: boolean;
  created_at: string;
};

export type Invoice = {
  id: number;
  invoice_number: string;
  branch_id: number;
  branch_name: string;
  customer_id: number | null;
  customer_name: string | null;
  sale_id: number | null;
  invoice_type: InvoiceType;
  place_of_supply_state: string | null;
  place_of_supply_state_code: string | null;
  invoice_date: string;
  status: InvoiceStatus;
  payment_status: InvoicePaymentStatus;
  subtotal: string;
  discount_total: string;
  taxable_total: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  round_off: string;
  grand_total: string;
  paid_amount: string;
  balance_due: string;
  created_by: number;
  created_by_name: string;
  created_at: string;
  issued_at: string | null;
  items: InvoiceItem[];
  taxes: InvoiceTax[];
  payments: InvoicePayment[];
  status_history: Array<{
    id: number;
    invoice_id: number;
    from_status: InvoiceStatus | null;
    to_status: InvoiceStatus;
    changed_by: number | null;
    changed_by_name: string | null;
    notes: string | null;
    changed_at: string;
  }>;
};

export type TaxMode = "gst" | "non_gst";
export type PaymentModeType =
  | "cash"
  | "upi"
  | "card"
  | "bank_transfer"
  | "wallet"
  | "cheque"
  | "credit"
  | "other";
export type InvoiceSequenceType =
  | "gst_invoice"
  | "non_gst_invoice"
  | "credit_note"
  | "purchase_bill";
export type InvoiceSequenceResetRule = "never" | "fiscal_year" | "calendar_year" | "monthly";

export type BusinessProfile = {
  company_id: number;
  business_profile_id: number;
  gst_registration_id: number | null;
  company_code: string;
  legal_name: string;
  trade_name: string | null;
  pan: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  state_code: string | null;
  pincode: string | null;
  gstin: string | null;
  default_tax_mode: TaxMode;
  default_currency: string;
  terms_and_conditions: string | null;
  created_at: string;
  updated_at: string;
};

export type BusinessProfilePayload = Omit<
  BusinessProfile,
  "company_id" | "business_profile_id" | "gst_registration_id" | "created_at" | "updated_at"
>;

export type TaxRate = {
  id: number;
  name: string;
  rate_percent: string;
  cess_percent: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TaxRatePayload = Omit<TaxRate, "id" | "created_at" | "updated_at">;

export type PaymentMode = {
  id: number;
  company_id: number;
  name: string;
  mode_type: PaymentModeType;
  requires_reference: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type PaymentModePayload = Omit<PaymentMode, "id" | "company_id" | "created_at" | "updated_at"> & {
  company_id?: number | null;
};

export type InvoiceSequence = {
  id: number;
  company_id: number;
  branch_id: number | null;
  invoice_type: InvoiceSequenceType;
  fiscal_year: string;
  prefix: string;
  suffix: string | null;
  next_number: number;
  padding: number;
  reset_rule: InvoiceSequenceResetRule;
  is_active: boolean;
  last_generated_at: string | null;
  preview_next_number: string;
  created_at: string;
  updated_at: string;
};

export type InvoiceSequencePayload = Omit<
  InvoiceSequence,
  "id" | "company_id" | "last_generated_at" | "preview_next_number" | "created_at" | "updated_at"
> & {
  company_id?: number | null;
};

export type InventoryItem = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  category_id: number;
  category_name: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  quantity_on_hand: string;
  quantity_reserved: string;
  quantity_on_order: string;
  reorder_threshold: string;
  target_stock_level: string;
  unit_cost: string;
  stock_value: string;
  is_low_stock: boolean;
  last_updated_at: string;
};

export type ProductInventoryDetail = {
  product_id: number;
  product_sku: string;
  product_name: string;
  category_name: string;
  supplier_name: string;
  total_quantity_on_hand: string;
  total_stock_value: string;
  is_low_stock_any_branch: boolean;
  inventory: InventoryItem[];
};

export type StockMovementType =
  | "sale"
  | "purchase_received"
  | "manual_adjustment"
  | "return"
  | "transfer";

export type StockMovement = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  branch_id: number;
  branch_name: string;
  movement_type: StockMovementType;
  quantity_change: string;
  reason: string | null;
  reference_type: string | null;
  reference_id: number | null;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
};

export type StockAdjustmentPayload = {
  product_id: number;
  branch_id: number;
  quantity_change: string;
  reason: string;
};

export type StockAdjustmentResponse = {
  inventory: InventoryItem;
  movement: StockMovement;
};

export type SaleItemPayload = {
  product_id: number;
  quantity: string;
  unit_price?: string;
  discount_amount: string;
};

export type SalePayload = {
  branch_id: number;
  sale_datetime?: string;
  tax_rate: string;
  items: SaleItemPayload[];
};

export type SaleItem = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  line_total: string;
  gross_profit: string;
};

export type SaleListItem = {
  id: number;
  sale_number: string;
  branch_id: number;
  branch_name: string;
  sale_datetime: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total_amount: string;
  gross_profit: string;
  units_sold: string;
  item_count: number;
  created_by: number;
  created_by_name: string;
  created_at: string;
};

export type Sale = SaleListItem & {
  items: SaleItem[];
};

export type SalesSummary = {
  revenue: string;
  gross_profit: string;
  units_sold: string;
  transaction_count: number;
  average_order_value: string;
  discount_total: string;
  tax_total: string;
};

export type SalesTrendPoint = {
  date: string;
  revenue: string;
  gross_profit: string;
  units_sold: string;
  transaction_count: number;
};

export type SalesKpi = {
  revenue: string;
  gross_profit: string;
  gross_margin_percent: string | null;
  units_sold: string;
  transaction_count: number;
  average_order_value: string;
  sales_growth_percent: string | null;
  previous_period_revenue: string;
};

export type InventoryKpi = {
  current_stock_value: string;
  total_quantity_on_hand: string;
  low_stock_product_count: number;
  slow_moving_stock_count: number;
};

export type PurchaseOrderKpi = {
  pending_purchase_orders: number;
  pending_approval_count: number;
  approved_count: number;
  ordered_count: number;
  overdue_count: number;
  total_open_order_value: string;
};

export type DashboardTopProduct = {
  product_id: number;
  product_sku: string;
  product_name: string;
  category_name: string;
  units_sold: string;
  revenue: string;
  gross_profit: string;
};

export type DashboardKpis = {
  sales: SalesKpi;
  inventory: InventoryKpi;
  purchase_orders: PurchaseOrderKpi;
  top_selling_product: DashboardTopProduct | null;
};

export type DashboardSalesTrendPoint = SalesTrendPoint;

export type RevenueByCategoryPoint = {
  category_id: number;
  category_name: string;
  revenue: string;
  gross_profit: string;
  units_sold: string;
};

export type BranchPerformancePoint = {
  branch_id: number;
  branch_name: string;
  revenue: string;
  gross_profit: string;
  units_sold: string;
  transaction_count: number;
};

export type InventoryHealthPoint = {
  status: string;
  product_count: number;
  quantity_on_hand: string;
  stock_value: string;
};

export type StockValueByCategoryPoint = {
  category_id: number;
  category_name: string;
  quantity_on_hand: string;
  stock_value: string;
  low_stock_count: number;
};

export type DashboardLowStockRow = {
  product_id: number;
  product_sku: string;
  product_name: string;
  branch_id: number;
  branch_name: string;
  category_name: string;
  supplier_name: string;
  quantity_on_hand: string;
  reorder_threshold: string;
  target_stock_level: string;
  quantity_on_order: string;
  stock_value: string;
};

export type SlowMovingStockRow = {
  product_id: number;
  product_sku: string;
  product_name: string;
  branch_id: number;
  branch_name: string;
  category_name: string;
  supplier_name: string;
  quantity_on_hand: string;
  stock_value: string;
  last_sale_date: string | null;
};

export type OverviewDashboard = {
  period_start: string;
  period_end: string;
  previous_period_start: string;
  previous_period_end: string;
  kpis: DashboardKpis;
  sales_trend: DashboardSalesTrendPoint[];
  revenue_by_category: RevenueByCategoryPoint[];
  top_products: DashboardTopProduct[];
  branch_performance: BranchPerformancePoint[];
  inventory_health: InventoryHealthPoint[];
  low_stock_items: DashboardLowStockRow[];
};

export type SalesDashboard = {
  period_start: string;
  period_end: string;
  previous_period_start: string;
  previous_period_end: string;
  summary: SalesKpi;
  sales_trend: DashboardSalesTrendPoint[];
  revenue_by_category: RevenueByCategoryPoint[];
  top_products: DashboardTopProduct[];
  branch_performance: BranchPerformancePoint[];
};

export type InventoryDashboard = {
  period_start: string;
  period_end: string;
  summary: InventoryKpi;
  inventory_health: InventoryHealthPoint[];
  stock_value_by_category: StockValueByCategoryPoint[];
  low_stock_items: DashboardLowStockRow[];
  slow_moving_stock: SlowMovingStockRow[];
};

export type PurchaseOrderStatusPoint = {
  status: string;
  count: number;
  total_amount: string;
};

export type PurchaseOrderSupplierPoint = {
  supplier_id: number;
  supplier_name: string;
  count: number;
  total_amount: string;
};

export type PurchaseOrderBranchPoint = {
  branch_id: number;
  branch_name: string;
  count: number;
  total_amount: string;
};

export type RecentPurchaseOrder = {
  id: number;
  po_number: string;
  supplier_name: string;
  branch_name: string;
  status: string;
  order_date: string;
  expected_delivery_date: string | null;
  total_amount: string;
};

export type PurchaseOrdersDashboard = {
  period_start: string;
  period_end: string;
  summary: PurchaseOrderKpi;
  by_status: PurchaseOrderStatusPoint[];
  by_supplier: PurchaseOrderSupplierPoint[];
  branch_performance: PurchaseOrderBranchPoint[];
  recent_orders: RecentPurchaseOrder[];
};

export type PurchaseOrderStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "ordered"
  | "partially_received"
  | "received"
  | "cancelled";

export type ReorderPriority = "critical" | "high" | "medium" | "low";

export type ReorderRecommendation = {
  product_id: number;
  product_sku: string;
  product_name: string;
  category_id: number;
  category_name: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  current_stock: string;
  quantity_on_order: string;
  reorder_threshold: string;
  target_stock_level: string;
  average_daily_sales: string;
  supplier_lead_time_days: number;
  expected_demand_during_lead_time: string;
  days_until_stockout: string | null;
  suggested_reorder_quantity: string;
  priority: ReorderPriority;
  unit_cost: string;
  estimated_cost: string;
};

export type PurchaseOrderDraftItemPayload = {
  product_id: number;
  branch_id: number;
  quantity_ordered: string;
};

export type PurchaseOrdersFromRecommendationsPayload = {
  items: PurchaseOrderDraftItemPayload[];
};

export type PurchaseOrderItemPayload = {
  product_id: number;
  quantity_ordered: string;
  unit_cost?: string | null;
};

export type PurchaseOrderPayload = {
  supplier_id: number;
  branch_id: number;
  order_date?: string | null;
  expected_delivery_date?: string | null;
  items: PurchaseOrderItemPayload[];
};

export type PurchaseOrderReceiveItemPayload = {
  item_id: number;
  quantity_received: string;
};

export type PurchaseOrderReceivePayload = {
  items: PurchaseOrderReceiveItemPayload[];
};

export type PurchaseOrderItem = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  quantity_ordered: string;
  quantity_received: string;
  remaining_quantity: string;
  unit_cost: string;
  line_total: string;
};

export type PurchaseOrderListItem = {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  status: string;
  order_date: string;
  expected_delivery_date: string | null;
  total_amount: string;
  created_by: number;
  created_by_name: string;
  approved_by: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  item_count: number;
  total_quantity_ordered: string;
  total_quantity_received: string;
  created_at: string;
  updated_at: string;
};

export type PurchaseOrder = PurchaseOrderListItem & {
  items: PurchaseOrderItem[];
};

export type PurchaseOrderDraftItem = PurchaseOrderItem;
export type PurchaseOrderDraft = PurchaseOrder;

export type ForecastType = "revenue" | "units" | "demand";
export type ForecastTrend = "increasing" | "decreasing" | "stable";

export type ForecastPoint = {
  date: string;
  value: string;
};

export type ForecastRunPayload = {
  forecast_type: ForecastType;
  horizon_days: 7 | 30 | 90;
  branch_id?: number | null;
  category_id?: number | null;
  product_id?: number | null;
  as_of_date?: string | null;
};

export type ForecastRecord = {
  id: number;
  product_id: number | null;
  product_name: string | null;
  category_id: number | null;
  category_name: string | null;
  branch_id: number | null;
  branch_name: string | null;
  forecast_type: ForecastType;
  forecast_start_date: string;
  forecast_end_date: string;
  forecast_value: string;
  confidence_low: string | null;
  confidence_high: string | null;
  model_name: string;
  created_at: string;
};

export type ForecastRunResult = {
  forecast: ForecastRecord | null;
  forecast_type: ForecastType;
  horizon_days: 7 | 30 | 90;
  branch_id: number | null;
  branch_name: string | null;
  category_id: number | null;
  category_name: string | null;
  product_id: number | null;
  product_name: string | null;
  history_start_date: string | null;
  history_end_date: string | null;
  forecast_start_date: string | null;
  forecast_end_date: string | null;
  forecast_value: string;
  confidence_low: string | null;
  confidence_high: string | null;
  average_daily_value: string;
  trend_label: ForecastTrend;
  trend_percent: string | null;
  model_name: string;
  insufficient_data: boolean;
  message: string;
  historical_points: ForecastPoint[];
  forecast_points: ForecastPoint[];
};

export type ChatSender = "user" | "assistant" | "system";

export type AIToolCall = {
  name: string;
  description: string;
  data: Record<string, unknown>;
};

export type AIChatMessage = {
  id: number;
  session_id: number;
  sender: ChatSender;
  message: string;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
};

export type AIChatSession = {
  id: number;
  user_id: number;
  branch_id: number | null;
  title: string;
  created_at: string;
  updated_at: string;
  last_message: string | null;
};

export type AIChatSessionDetail = AIChatSession & {
  messages: AIChatMessage[];
};

export type AIChatPayload = {
  message: string;
  session_id?: number | null;
};

export type AIChatResponse = {
  session_id: number;
  intent: string;
  response: string;
  tool_calls: AIToolCall[];
  requires_confirmation: boolean;
  suggested_action: string | null;
  user_message: AIChatMessage;
  assistant_message: AIChatMessage;
};
