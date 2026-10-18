import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import type { CafeReceipt as Receipt } from "../api/cafeBilling";
import { CAFE_TIMEZONE } from "../utils/cafeDates";
import "./cafeReceipt.css";

export function receiptTime(value: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
  return new Intl.DateTimeFormat("en-IN", { timeZone: CAFE_TIMEZONE, dateStyle: "medium", timeStyle: "short" }).format(date);
}

const amount = (value: string) => Number(value).toFixed(2);

function ReceiptContent({ receipt, reprint }: { receipt: Receipt; reprint: boolean }) {
  return <article className="cafe-receipt-paper" aria-label={`Receipt ${receipt.invoice_number}`}>
    <header className="cafe-receipt-heading">
      <h2>{receipt.cafe_name}</h2><p>{receipt.branch_name}</p>
      <p>{reprint ? "REPRINT · " : ""}{receipt.invoice_type === "non_gst" ? "Non-GST invoice" : "Invoice"}</p>
    </header>
    <div className="cafe-receipt-meta"><p><strong>Invoice:</strong> {receipt.invoice_number}</p>
      <p><strong>Date:</strong> {receiptTime(receipt.issued_at)} IST</p>
      <p><strong>Status:</strong> {receipt.invoice_status.replace(/_/g, " ")} / {receipt.payment_status.replace(/_/g, " ")}</p>
    </div>
    <table className="cafe-receipt-items"><colgroup><col className="receipt-item-col" /><col className="receipt-qty-col" /><col className="receipt-price-col" /><col className="receipt-total-col" /></colgroup>
      <thead><tr><th>Item</th><th>Qty</th><th>Unit ₹</th><th>Total ₹</th></tr></thead>
      <tbody>{receipt.items.map((item, index) => <tr key={index}><td>{item.name}</td><td>{Number(item.quantity)}</td><td>{amount(item.unit_price)}</td><td>{amount(item.line_total)}</td></tr>)}</tbody>
    </table>
    <dl className="cafe-receipt-totals">
      {Number(receipt.discount_total) !== 0 ? <><dt>Discount</dt><dd>₹{amount(receipt.discount_total)}</dd></> : null}
      {Number(receipt.round_off) !== 0 ? <><dt>Round off</dt><dd>₹{amount(receipt.round_off)}</dd></> : null}
      <dt className="receipt-grand-total">Grand total</dt><dd className="receipt-grand-total">₹{amount(receipt.grand_total)}</dd>
      {receipt.payments.length === 0 ? <><dt>Payment mode</dt><dd>Not recorded</dd></> : null}
      {receipt.payments.map((payment, index) => <div className="receipt-payment-row" key={index}><dt>{payment.mode_name ?? (payment.is_credit_marker ? "Credit" : "Unspecified mode")}{payment.is_credit_marker ? " (credit)" : ""}</dt><dd>₹{amount(payment.amount)}</dd></div>)}
      <dt>Amount paid</dt><dd>₹{amount(receipt.paid_amount)}</dd>
      {Number(receipt.balance_due) !== 0 ? <><dt>Balance due</dt><dd>₹{amount(receipt.balance_due)}</dd></> : null}
    </dl>
  </article>;
}

export function CafeReceiptView({ receipt, reprint = false, children }: { receipt: Receipt; reprint?: boolean; children?: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const prepare = useRef<() => void>(() => {});
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useLayoutEffect(() => {
    const style = document.createElement("style");
    style.dataset.cafeReceiptPage = "true";
    document.head.appendChild(style);
    document.body.classList.add("cafe-receipt-ready");
    const measure = () => {
      if (!root.current) return;
      // Roll length follows the rendered receipt; CSS has no standard automatic page height.
      const paper = root.current.querySelector<HTMLElement>(".cafe-receipt-paper");
      if (!paper) return;
      const heightMm = Math.max(40, Math.ceil(paper.getBoundingClientRect().height * 25.4 / 96) + 10);
      style.textContent = `@page cafe-receipt { size: 80mm ${heightMm}mm; margin: 4mm; }`;
    };
    prepare.current = measure;
    measure();
    window.addEventListener("beforeprint", measure);
    return () => {
      window.removeEventListener("beforeprint", measure);
      style.remove();
      document.body.classList.remove("cafe-receipt-ready");
      prepare.current = () => {};
    };
  }, [receipt, reprint]);

  const print = async () => {
    if (printing) return;
    setPrinting(true); setError(null);
    try { await document.fonts.ready; prepare.current(); window.print(); }
    catch { setError("Printing could not start. Check the selected printer and try again."); }
    finally { setPrinting(false); }
  };

  return <>
    <section className="panel cafe-receipt-preview" aria-live="polite">
      <div className="cafe-receipt-actions"><button className="action-button primary" type="button" disabled={printing} onClick={() => void print()}>{reprint ? "Reprint receipt" : "Print receipt"}</button>{children}</div>
      <ReceiptContent receipt={receipt} reprint={reprint} />
      {error ? <p role="alert">{error}</p> : null}
    </section>
    {createPortal(<div id="cafe-receipt-print-root" ref={root} aria-hidden="true"><ReceiptContent receipt={receipt} reprint={reprint} /></div>, document.body)}
  </>;
}
