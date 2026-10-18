import { CafeReceiptView } from "./CafeReceipt";
import type { CafeReceipt } from "../api/cafeBilling";
import type { Invoice } from "../types";
type SnapshotInvoice = Invoice & {
  cafe_name?: string;
  gstin?: string | null;
  source_type?: string;
  source_id?: string;
};
export function RetailReceipt({
  invoice,
  reprint = false,
  onDone,
}: {
  invoice: SnapshotInvoice;
  reprint?: boolean;
  onDone: () => void;
}) {
  const receipt: CafeReceipt = {
    invoice_id: invoice.id,
    invoice_number: invoice.invoice_number,
    source_type: "retail",
    source_id: invoice.source_id ?? String(invoice.id),
    cafe_name: invoice.cafe_name ?? "Kalpvriksh Retail",
    branch_name: invoice.branch_name,
    invoice_type: invoice.invoice_type,
    invoice_status: invoice.status,
    payment_status: invoice.payment_status,
    issued_at: invoice.issued_at,
    subtotal: invoice.subtotal,
    discount_total: invoice.discount_total,
    taxable_total: invoice.taxable_total,
    cgst_total: invoice.cgst_total,
    sgst_total: invoice.sgst_total,
    igst_total: invoice.igst_total,
    cess_total: invoice.cess_total,
    round_off: invoice.round_off,
    grand_total: invoice.grand_total,
    paid_amount: invoice.paid_amount,
    balance_due: invoice.balance_due,
    gstin: invoice.gstin ?? null,
    items: invoice.items.map((i) => ({
      name: i.product_name_snapshot,
      sku: i.sku_snapshot,
      quantity: i.quantity,
      unit_price: i.unit_price,
      discount: i.discount,
      line_total: i.line_total,
    })),
    payments: invoice.payments.map((p) => ({
      mode_name: p.payment_mode_name,
      amount: p.amount,
      reference_number: p.reference_number,
      is_credit_marker: p.is_credit_marker,
    })),
  };
  return (
    <CafeReceiptView receipt={receipt} reprint={reprint}>
      <button
        className="action-button secondary"
        type="button"
        onClick={onDone}
      >
        {reprint ? "Close receipt" : "Next customer"}
      </button>
    </CafeReceiptView>
  );
}
