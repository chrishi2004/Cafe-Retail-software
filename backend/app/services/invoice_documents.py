from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request
from app.models import (
    BusinessProfile,
    Company,
    GSTRegistration,
    Invoice,
    InvoiceType,
    PrintTemplate,
    PrintTemplateType,
    User,
)
from app.services.invoices import get_invoice_or_404


@dataclass(frozen=True)
class InvoiceDocument:
    invoice: Invoice
    company: Company
    profile: BusinessProfile | None
    registration: GSTRegistration | None
    template_type: PrintTemplateType


def _money(value: Decimal | None) -> str:
    return f"{value or Decimal('0.00'):,.2f}"


def _date(value: datetime | None) -> str:
    return value.astimezone().strftime("%d %b %Y, %I:%M %p") if value else "—"


def _template_for(invoice: Invoice, requested: PrintTemplateType | None) -> PrintTemplateType:
    if requested in {PrintTemplateType.CREDIT_NOTE, PrintTemplateType.PURCHASE_BILL}:
        raise_bad_request("Credit-note and purchase-bill documents are enabled after their accounting workflows are implemented.")
    if requested is not None:
        return requested
    return PrintTemplateType.A4_GST_INVOICE if invoice.invoice_type == InvoiceType.GST else PrintTemplateType.NON_GST_INVOICE


def load_invoice_document(
    db: Session,
    *,
    invoice_id: int,
    user: User,
    template_type: PrintTemplateType | None,
) -> InvoiceDocument:
    invoice = get_invoice_or_404(db, invoice_id, user=user)
    if invoice.status.value == "draft":
        raise_bad_request("Only issued invoices can be printed or downloaded.")
    company = db.get(Company, invoice.company_id)
    if company is None:
        raise_bad_request("Invoice business could not be resolved.")
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company.id))
    registration = db.scalar(
        select(GSTRegistration)
        .where(
            GSTRegistration.company_id == company.id,
            GSTRegistration.is_active.is_(True),
            GSTRegistration.reference_only.is_(False),
        )
        .order_by(GSTRegistration.is_primary.desc(), GSTRegistration.id)
    )
    selected = _template_for(invoice, template_type)
    # A configured template may override layout settings later; the document
    # remains printable with the safe built-in layout when no row exists.
    db.scalar(
        select(PrintTemplate).where(
            PrintTemplate.company_id == company.id,
            PrintTemplate.template_type == selected,
            PrintTemplate.is_active.is_(True),
        )
    )
    return InvoiceDocument(invoice, company, profile, registration, selected)


def _document_title(document: InvoiceDocument) -> str:
    if document.invoice.invoice_type == InvoiceType.GST:
        return "TAX INVOICE"
    return "INVOICE"


def _customer_lines(document: InvoiceDocument) -> list[str]:
    customer = document.invoice.customer
    if customer is None:
        return ["Walk-in customer"]
    details = [customer.name]
    if customer.phone:
        details.append(customer.phone)
    address = ", ".join(value for value in (customer.billing_address, customer.city, customer.state) if value)
    if address:
        details.append(address)
    if customer.gstin and document.invoice.invoice_type == InvoiceType.GST:
        details.append(f"GSTIN: {customer.gstin}")
    return details


def render_invoice_html(document: InvoiceDocument) -> str:
    invoice = document.invoice
    profile = document.profile
    registration = document.registration
    lines = []
    for item in sorted(invoice.items, key=lambda row: row.id):
        lines.append(
            "<tr>"
            f"<td>{html.escape(item.product_name_snapshot)}</td>"
            f"<td>{html.escape(item.sku_snapshot)}</td>"
            f"<td class=\"num\">{item.quantity}</td>"
            f"<td class=\"num\">{_money(item.unit_price)}</td>"
            f"<td class=\"num\">{_money(item.discount)}</td>"
            f"<td class=\"num\">{_money(item.line_total)}</td>"
            "</tr>"
        )
    payment_lines = []
    for payment in sorted(invoice.payments, key=lambda row: row.id):
        mode = payment.payment_mode.name if payment.payment_mode else ("Credit" if payment.is_credit_marker else "Payment")
        reference = f" ({html.escape(payment.reference_number)})" if payment.reference_number else ""
        payment_lines.append(f"<li>{html.escape(mode)}{reference}: INR {_money(payment.amount)}</li>")
    seller = profile.trade_name or profile.legal_name if profile else document.company.name
    seller_details = [seller]
    if profile:
        seller_details.extend(value for value in (profile.address, profile.city, profile.state, profile.pincode) if value)
    gstin = registration.gstin if registration else None
    tax_rows = []
    for label, value in (("CGST", invoice.cgst_total), ("SGST", invoice.sgst_total), ("IGST", invoice.igst_total), ("CESS", invoice.cess_total)):
        if value and value > 0:
            tax_rows.append(f"<tr><td>{label}</td><td class=\"num\">INR {_money(value)}</td></tr>")
    terms = profile.terms_and_conditions if profile and profile.terms_and_conditions else "Goods once sold are subject to the business return policy."
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(invoice.invoice_number)}</title>
<style>
@page {{ size: auto; margin: 12mm; }} body {{ font-family: Arial, sans-serif; color: #172033; margin: 0; }}
.sheet {{ max-width: 900px; margin: auto; }} header {{ display: flex; justify-content: space-between; gap: 24px; border-bottom: 2px solid #172033; padding-bottom: 14px; }}
h1 {{ margin: 0 0 6px; font-size: 24px; }} h2 {{ margin: 0; font-size: 18px; }} p {{ margin: 4px 0; }} table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
th, td {{ border: 1px solid #c9ced8; padding: 7px; text-align: left; }} th {{ background: #eef1f5; }} .num {{ text-align: right; white-space: nowrap; }}
.columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 18px; }} .totals {{ margin-left: auto; max-width: 360px; }} .totals td {{ border: 0; padding: 4px; }}
.grand {{ font-size: 18px; font-weight: bold; border-top: 2px solid #172033 !important; }} .muted {{ color: #5b6475; font-size: 12px; }}
@media print {{ .no-print {{ display: none; }} }}
</style></head><body><main class="sheet">
<header><div><h1>{html.escape(seller)}</h1>{''.join(f'<p>{html.escape(value)}</p>' for value in seller_details[1:])}{f'<p>GSTIN: {html.escape(gstin)}</p>' if gstin and invoice.invoice_type == InvoiceType.GST else ''}</div>
<div><h2>{_document_title(document)}</h2><p><strong>No:</strong> {html.escape(invoice.invoice_number)}</p><p><strong>Date:</strong> {_date(invoice.invoice_date)}</p><p><strong>Status:</strong> {html.escape(invoice.status.value)}</p></div></header>
<div class="columns"><section><h2>Bill to</h2>{''.join(f'<p>{html.escape(value)}</p>' for value in _customer_lines(document))}</section><section><h2>Supply</h2><p>{html.escape(invoice.place_of_supply_state or 'Not specified')}</p><p>{html.escape(invoice.place_of_supply_state_code or '')}</p></section></div>
<table><thead><tr><th>Item</th><th>SKU</th><th class="num">Qty</th><th class="num">Unit price</th><th class="num">Discount</th><th class="num">Line total</th></tr></thead><tbody>{''.join(lines)}</tbody></table>
<div class="columns"><section><h2>Payments</h2><ul>{''.join(payment_lines) or '<li>Unpaid / credit</li>'}</ul></section><section><table class="totals"><tr><td>Subtotal</td><td class="num">INR {_money(invoice.subtotal)}</td></tr><tr><td>Discount</td><td class="num">INR {_money(invoice.discount_total)}</td></tr><tr><td>Taxable value</td><td class="num">INR {_money(invoice.taxable_total)}</td></tr>{''.join(tax_rows)}<tr><td>Round off</td><td class="num">INR {_money(invoice.round_off)}</td></tr><tr class="grand"><td>Grand total</td><td class="num">INR {_money(invoice.grand_total)}</td></tr><tr><td>Paid</td><td class="num">INR {_money(invoice.paid_amount)}</td></tr><tr><td>Balance due</td><td class="num">INR {_money(invoice.balance_due)}</td></tr></table></section></div>
<p class="muted"><strong>Terms:</strong> {html.escape(terms)}</p><p class="muted">Generated by Kalpvrik Business Suite. Tax presentation is based on stored invoice values.</p>
</main></body></html>"""


def _pdf_story(document: InvoiceDocument):
    invoice = document.invoice
    profile = document.profile
    registration = document.registration
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("invoice-normal", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10)
    small = ParagraphStyle("invoice-small", parent=normal, fontSize=7, leading=8)
    title = ParagraphStyle("invoice-title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=18)
    seller = profile.trade_name or profile.legal_name if profile else document.company.name
    seller_details = [seller] + ([profile.address, profile.city, profile.state, profile.pincode] if profile else [])
    seller_details = [value for value in seller_details if value]
    header = [[Paragraph(f"<b>{html.escape(seller)}</b><br/>{'<br/>'.join(html.escape(value) for value in seller_details[1:])}", normal),
               Paragraph(f"<b>{_document_title(document)}</b><br/>No: {html.escape(invoice.invoice_number)}<br/>Date: {_date(invoice.invoice_date)}", normal)]]
    items = [[Paragraph("Item", small), Paragraph("Qty", small), Paragraph("Unit", small), Paragraph("Amount", small)]]
    for item in sorted(invoice.items, key=lambda row: row.id):
        items.append([Paragraph(html.escape(item.product_name_snapshot), small), Paragraph(str(item.quantity), small), Paragraph(f"INR {_money(item.unit_price)}", small), Paragraph(f"INR {_money(item.line_total)}", small)])
    summary = [["Subtotal", f"INR {_money(invoice.subtotal)}"], ["Discount", f"INR {_money(invoice.discount_total)}"], ["Taxable", f"INR {_money(invoice.taxable_total)}"], ["CGST", f"INR {_money(invoice.cgst_total)}"], ["SGST", f"INR {_money(invoice.sgst_total)}"], ["IGST", f"INR {_money(invoice.igst_total)}"], ["Grand total", f"INR {_money(invoice.grand_total)}"], ["Paid", f"INR {_money(invoice.paid_amount)}"], ["Balance", f"INR {_money(invoice.balance_due)}"]]
    customer = "<br/>".join(html.escape(value) for value in _customer_lines(document))
    story = [Table(header, colWidths=[None, 58 * mm]), Spacer(1, 5 * mm), Paragraph(f"<b>Bill to</b><br/>{customer}", normal), Spacer(1, 3 * mm), Table(items, colWidths=[None, 14 * mm, 24 * mm, 28 * mm]), Spacer(1, 4 * mm), Table(summary, colWidths=[None, 35 * mm]), Spacer(1, 3 * mm), Paragraph(f"<b>Terms:</b> {html.escape(profile.terms_and_conditions if profile and profile.terms_and_conditions else 'Goods once sold are subject to the business return policy.')}", small)]
    return story


def render_invoice_pdf(document: InvoiceDocument) -> bytes:
    template = document.template_type
    if template == PrintTemplateType.A5_INVOICE:
        page_size = A5
        margins = (8 * mm, 8 * mm, 8 * mm, 8 * mm)
    elif template == PrintTemplateType.POS_58MM:
        page_size = (58 * mm, 220 * mm)
        margins = (4 * mm, 4 * mm, 4 * mm, 4 * mm)
    elif template == PrintTemplateType.POS_80MM:
        page_size = (80 * mm, 260 * mm)
        margins = (5 * mm, 5 * mm, 5 * mm, 5 * mm)
    else:
        page_size = A4
        margins = (12 * mm, 12 * mm, 12 * mm, 12 * mm)
    output = BytesIO()
    document_builder = SimpleDocTemplate(output, pagesize=page_size, rightMargin=margins[0], leftMargin=margins[1], topMargin=margins[2], bottomMargin=margins[3], title=document.invoice.invoice_number, author="Kalpvrik Business Suite")
    document_builder.build(_pdf_story(document))
    return output.getvalue()
