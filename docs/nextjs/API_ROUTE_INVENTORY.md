# Existing API route inventory

Generated from the preserved FastAPI OpenAPI documents. These are source contracts, not a claim of Next.js parity.

| Runtime | Method | Route | Area | Purpose |
| --- | --- | --- | --- | --- |
| operational | GET | `/api/health` | health | Health Check |
| operational | POST | `/api/public/cafe/qr/{opaque_token}/resolve` | cafe | Resolve Qr Token |
| operational | GET | `/api/public/cafe/sessions/{public_id}/menu` | public-cafe | Read Menu |
| operational | POST | `/api/public/cafe/sessions/{public_id}/orders` | public-cafe | Submit Order |
| operational | GET | `/api/public/cafe/sessions/{public_id}/orders` | public-cafe | Read Orders |
| operational | POST | `/api/public/cafe/sessions/{public_id}/bill-request` | public-cafe | Request Bill |
| operational | POST | `/api/auth/login` | auth | Login |
| operational | POST | `/api/auth/logout` | auth | Logout |
| operational | POST | `/api/auth/step-up` | auth | Step Up Authentication |
| operational | POST | `/api/auth/mfa/enroll` | auth | Enroll Mfa |
| operational | POST | `/api/auth/mfa/confirm` | auth | Confirm Mfa |
| operational | POST | `/api/auth/mfa/disable` | auth | Disable Mfa |
| operational | GET | `/api/auth/me` | auth | Read Current User |
| operational | GET | `/api/auth/admin-check` | auth | Admin Check |
| operational | GET | `/api/auth/branch-scope` | auth | Read Branch Scope |
| operational | GET | `/api/ventures/current` | ventures | Current Venture |
| operational | GET | `/api/ventures` | ventures | List Ventures |
| operational | GET | `/api/venture-users` | ventures | List Venture Users |
| operational | POST | `/api/venture-users` | ventures | Create Venture User |
| operational | PUT | `/api/venture-users/{user_id}` | ventures | Update Venture User Assignment |
| operational | GET | `/api/cafe/orders` | cafe-orders | Read Orders |
| operational | POST | `/api/cafe/orders` | cafe-orders | Add Order |
| operational | GET | `/api/cafe/orders/{public_id}` | cafe-orders | Read Order |
| operational | POST | `/api/cafe/orders/{public_id}/accept` | cafe-orders | Accept Order |
| operational | POST | `/api/cafe/orders/{public_id}/reject` | cafe-orders | Reject Order |
| operational | POST | `/api/cafe/orders/{public_id}/start-preparing` | cafe-orders | Start Preparing |
| operational | POST | `/api/cafe/orders/{public_id}/mark-ready` | cafe-orders | Mark Ready |
| operational | POST | `/api/cafe/orders/{public_id}/serve` | cafe-orders | Serve Order |
| operational | POST | `/api/cafe/orders/{public_id}/request-bill` | cafe-orders | Request Standalone Order Bill |
| operational | POST | `/api/cafe/orders/{public_id}/cancel` | cafe-orders | Cancel Order |
| operational | POST | `/api/cafe/table-sessions/{public_id}/request-bill` | cafe-orders | Request Session Bill |
| operational | GET | `/api/cafe/kitchen/orders` | cafe-orders | Read Kitchen Queue |
| operational | GET | `/api/cafe/billing/table-sessions/{public_id}/quote` | cafe-billing | Read Table Quote |
| operational | POST | `/api/cafe/billing/table-sessions/{public_id}/bill` | cafe-billing | Create Table Bill |
| operational | GET | `/api/cafe/billing/orders/{public_id}/quote` | cafe-billing | Read Order Quote |
| operational | POST | `/api/cafe/billing/orders/{public_id}/bill` | cafe-billing | Create Order Bill |
| operational | GET | `/api/cafe/billing/invoices/{invoice_id}/receipt` | cafe-billing | Read Receipt |
| operational | POST | `/api/cafe/billing/invoices/{invoice_id}/payments` | cafe-billing | Collect Payment |
| operational | POST | `/api/cafe/billing/pos/checkout` | cafe-billing | Checkout Pos |
| operational | GET | `/api/cafe/billing/invoices` | cafe-billing | Read Invoice History |
| operational | GET | `/api/cafe/menu/categories` | cafe | Read Menu Categories |
| operational | POST | `/api/cafe/menu/categories` | cafe | Add Menu Category |
| operational | PUT | `/api/cafe/menu/categories/{category_id}` | cafe | Edit Menu Category |
| operational | GET | `/api/cafe/menu/items` | cafe | Read Menu Items |
| operational | POST | `/api/cafe/menu/items` | cafe | Add Menu Item |
| operational | PUT | `/api/cafe/menu/items/{item_id}` | cafe | Edit Menu Item |
| operational | PATCH | `/api/cafe/menu/items/{item_id}/availability` | cafe | Set Menu Item Availability |
| operational | GET | `/api/cafe/tables` | cafe | Read Cafe Tables |
| operational | POST | `/api/cafe/tables` | cafe | Add Cafe Table |
| operational | PUT | `/api/cafe/tables/{table_id}` | cafe | Edit Cafe Table |
| operational | POST | `/api/cafe/tables/{table_id}/deactivate` | cafe | Deactivate Cafe Table |
| operational | POST | `/api/cafe/tables/{table_id}/qr/rotate` | cafe | Rotate Qr |
| operational | GET | `/api/cafe/tables/{table_id}/qr/status` | cafe | Read Qr Status |
| operational | POST | `/api/cafe/tables/{table_id}/qr/revoke` | cafe | Revoke Qr |
| operational | POST | `/api/cafe/tables/{table_id}/qr/print-data` | cafe | Print Qr Data |
| operational | POST | `/api/cafe/table-sessions` | cafe | Open Session |
| operational | GET | `/api/cafe/table-sessions/{public_id}` | cafe | Read Session |
| operational | GET | `/api/cafe/tables/{table_id}/active-session` | cafe | Read Active Session |
| operational | POST | `/api/cafe/table-sessions/{public_id}/close` | cafe | Close Session |
| operational | POST | `/api/cafe/tables/{table_id}/qr/render` | cafe | Render Table Qr |
| operational | GET | `/api/sync/status` | sync-status | Sync Status |
| operational | GET | `/api/sync/continuity` | hc4-continuity | Continuity State |
| operational | GET | `/api/sync/reconciliation` | hc4-continuity | Read Reconciliation |
| operational | POST | `/api/sync/reconcile` | hc4-continuity | Reconcile |
| operational | GET | `/api/sync/dead-letters` | hc4-continuity | List Dead Letters |
| operational | POST | `/api/sync/dead-letters/{dead_letter_id}/retry` | hc4-continuity | Retry Failed Sync |
| operational | GET | `/api/tax-operation` | tax-operation | Read Tax Operation |
| operational | PUT | `/api/tax-operation/settings` | tax-operation | Update Tax Settings |
| operational | POST | `/api/tax-operation/activate-gst` | tax-operation | Activate Gst |
| operational | GET | `/api/tax-operation/combined-turnover` | tax-operation | Read Combined Turnover |
| operational | GET | `/api/business-profile` | business settings | Read Business Profile |
| operational | PUT | `/api/business-profile` | business settings | Update Business Profile |
| operational | GET | `/api/tax-rates` | business settings | Read Tax Rates |
| operational | POST | `/api/tax-rates` | business settings | Add Tax Rate |
| operational | PUT | `/api/tax-rates/{tax_rate_id}` | business settings | Edit Tax Rate |
| operational | GET | `/api/payment-modes` | business settings | Read Payment Modes |
| operational | POST | `/api/payment-modes` | business settings | Add Payment Mode |
| operational | PUT | `/api/payment-modes/{payment_mode_id}` | business settings | Edit Payment Mode |
| operational | GET | `/api/invoice-sequences` | business settings | Read Invoice Sequences |
| operational | POST | `/api/invoice-sequences` | business settings | Add Invoice Sequence |
| operational | PUT | `/api/invoice-sequences/{sequence_id}` | business settings | Edit Invoice Sequence |
| operational | GET | `/api/categories` | categories | List Categories |
| operational | POST | `/api/categories` | categories | Create Category |
| operational | PUT | `/api/categories/{category_id}` | categories | Update Category |
| operational | GET | `/api/suppliers` | suppliers | List Suppliers |
| operational | POST | `/api/suppliers` | suppliers | Create Supplier |
| operational | GET | `/api/suppliers/{supplier_id}` | suppliers | Get Supplier |
| operational | PUT | `/api/suppliers/{supplier_id}` | suppliers | Update Supplier |
| operational | GET | `/api/branches` | branches | List Branches |
| operational | POST | `/api/branches` | branches | Create Branch |
| operational | PUT | `/api/branches/{branch_id}` | branches | Update Branch |
| operational | GET | `/api/products` | products | List Products |
| operational | POST | `/api/products` | products | Create Product |
| operational | GET | `/api/products/search` | products | Search Products |
| operational | GET | `/api/products/{product_id}` | products | Get Product |
| operational | PUT | `/api/products/{product_id}` | products | Update Product |
| operational | PATCH | `/api/products/{product_id}/deactivate` | products | Deactivate Product |
| operational | GET | `/api/customers` | customers | Read Customers |
| operational | POST | `/api/customers` | customers | Add Customer |
| operational | GET | `/api/customers/{customer_id}` | customers | Read Customer |
| operational | PUT | `/api/customers/{customer_id}` | customers | Edit Customer |
| operational | PATCH | `/api/customers/{customer_id}/deactivate` | customers | Disable Customer |
| operational | GET | `/api/customers/{customer_id}/ledger` | customers | Read Customer Ledger |
| operational | POST | `/api/customers/{customer_id}/payments` | customers | Add Customer Payment |
| operational | GET | `/api/customer-ledger/outstanding` | customers | Read Customer Outstanding |
| operational | GET | `/api/invoices` | invoices | Read Invoices |
| operational | POST | `/api/invoices` | invoices | Add Invoice |
| operational | GET | `/api/invoices/{invoice_id}` | invoices | Read Invoice |
| operational | POST | `/api/invoices/{invoice_id}/issue` | invoices | Issue Draft Invoice |
| operational | POST | `/api/invoices/{invoice_id}/cancel` | invoices | Cancel Draft Invoice |
| operational | POST | `/api/invoices/{invoice_id}/payments` | invoices | Collect Invoice Payment |
| operational | GET | `/api/pos/products/search` | invoices | Search Products For Pos |
| operational | POST | `/api/pos/quote` | invoices | Quote Pos Invoice |
| operational | POST | `/api/pos/checkout` | invoices | Checkout Pos Invoice |
| operational | GET | `/api/inventory` | inventory | List Inventory |
| operational | GET | `/api/inventory/low-stock` | inventory | List Low Stock Inventory |
| operational | POST | `/api/inventory/adjustments` | inventory | Create Stock Adjustment |
| operational | GET | `/api/inventory/movements` | inventory | List Stock Movements |
| operational | GET | `/api/inventory/reorder-recommendations` | inventory | List Reorder Recommendations |
| operational | GET | `/api/inventory/{product_id}` | inventory | Get Product Inventory |
| operational | GET | `/api/sales` | sales | List Sales |
| operational | POST | `/api/sales` | sales | Record Sale |
| operational | GET | `/api/sales/summary` | sales | Get Sales Summary |
| operational | GET | `/api/sales/trends` | sales | Get Sales Trends |
| operational | GET | `/api/sales/{sale_id}` | sales | Get Sale |
| operational | GET | `/api/dashboard/overview` | dashboard | Overview Dashboard |
| operational | GET | `/api/dashboard/sales` | dashboard | Sales Dashboard |
| operational | GET | `/api/dashboard/inventory` | dashboard | Inventory Dashboard |
| operational | GET | `/api/dashboard/purchase-orders` | dashboard | Purchase Orders Dashboard |
| operational | GET | `/api/dashboard/cafe` | dashboard | Cafe Dashboard |
| operational | GET | `/api/dashboard/consolidated` | dashboard | Consolidated Dashboard |
| operational | GET | `/api/purchase-orders` | purchase-orders | List Purchase Orders |
| operational | POST | `/api/purchase-orders` | purchase-orders | Create Manual Purchase Order |
| operational | POST | `/api/purchase-orders/from-recommendations` | purchase-orders | Create From Recommendations |
| operational | GET | `/api/purchase-orders/{purchase_order_id}` | purchase-orders | Get Purchase Order |
| operational | PUT | `/api/purchase-orders/{purchase_order_id}` | purchase-orders | Update Purchase Order Route |
| operational | POST | `/api/purchase-orders/{purchase_order_id}/submit` | purchase-orders | Submit Purchase Order Route |
| operational | POST | `/api/purchase-orders/{purchase_order_id}/approve` | purchase-orders | Approve Purchase Order Route |
| operational | POST | `/api/purchase-orders/{purchase_order_id}/cancel` | purchase-orders | Cancel Purchase Order Route |
| operational | POST | `/api/purchase-orders/{purchase_order_id}/mark-ordered` | purchase-orders | Mark Purchase Order Ordered Route |
| operational | POST | `/api/purchase-orders/{purchase_order_id}/receive` | purchase-orders | Receive Purchase Order Route |
| operational | POST | `/api/forecasts/run` | forecasts | Run Forecast Route |
| operational | GET | `/api/forecasts` | forecasts | List Forecasts |
| operational | GET | `/api/forecasts/products/{product_id}` | forecasts | List Product Forecasts |
| operational | POST | `/api/governance/step-up` | governance | Step Up |
| operational | GET | `/api/governance/closings` | governance | Get Closing |
| operational | POST | `/api/governance/closings` | governance | Create Closing |
| operational | POST | `/api/governance/closings/{closing_id}/submit` | governance | Submit |
| operational | POST | `/api/governance/closings/{closing_id}/close` | governance | Close |
| operational | POST | `/api/governance/closings/{closing_id}/reopen` | governance | Reopen |
| operational | POST | `/api/governance/voids/invoices/{invoice_id}` | governance | Void |
| operational | POST | `/api/governance/purges` | governance | Create Purge |
| operational | POST | `/api/governance/purges/{purge_id}/approve` | governance | Approve |
| operational | POST | `/api/governance/purges/{purge_id}/execute` | governance | Execute |
| operational | GET | `/api/exports/sales` | exports | Export Sales |
| operational | GET | `/api/exports/inventory` | exports | Export Inventory |
| operational | GET | `/api/exports/purchase-orders` | exports | Export Purchase Orders |
| operational | GET | `/api/exports/forecasts` | exports | Export Forecasts |
| operational | GET | `/api/exports/cafe` | exports | Export Cafe |
| operational | GET | `/api/exports/consolidated` | exports | Export Consolidated |
| operational | POST | `/api/ai/chat` | ai | Chat |
| operational | GET | `/api/ai/sessions` | ai | List Ai Sessions |
| operational | GET | `/api/ai/sessions/{session_id}` | ai | Get Ai Session |
| cloud | GET | `/api/health` | health | Health Check |
| cloud | GET | `/api/cloud/readiness` | cloud-gateway | Readiness |
| cloud | POST | `/api/cloud/devices/heartbeat` | cloud-gateway | Heartbeat |
| cloud | POST | `/api/cloud/publications/menu` | cloud-gateway | Publish Menu |
| cloud | GET | `/api/cloud/public/cafe/menu/{publication_id}` | cloud-gateway | Public Menu |
| cloud | POST | `/api/cloud/public/cafe/qr/resolve` | cloud-gateway | Public Qr Resolve |
| cloud | POST | `/api/cloud/public/cafe/orders` | hc3-cloud-orders | Submit Cloud Order |
| cloud | GET | `/api/cloud/public/cafe/orders/{public_id}` | hc3-cloud-orders | Read Cloud Order |
| cloud | POST | `/api/cloud/public/cafe/orders/{public_id}/bill-request` | hc3-cloud-orders | Submit Cloud Bill Request |
| cloud | GET | `/api/cloud/sync/commands` | hc3-cloud-orders | Pull Commands |
| cloud | POST | `/api/cloud/sync/receipts` | hc3-cloud-orders | Push Receipt |
| cloud | POST | `/api/cloud/sync/events` | hc3-cloud-orders | Push Local Event |
| cloud | POST | `/api/cloud/continuity/lease/acquire` | hc4-continuity | Acquire Writer Lease |
| cloud | POST | `/api/cloud/continuity/lease/renew` | hc4-continuity | Renew Writer Lease |
| cloud | POST | `/api/cloud/continuity/references` | hc4-continuity | Create Continuity Reference |
