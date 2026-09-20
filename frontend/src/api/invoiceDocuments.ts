import { API_BASE_URL, activeVentureStorage, ApiError } from "./client";

export type InvoiceTemplate = "a4_gst_invoice" | "a5_invoice" | "pos_58mm" | "pos_80mm" | "non_gst_invoice";

async function documentResponse(token: string, invoiceId: number, format: "html" | "pdf", template: InvoiceTemplate): Promise<Response> {
  const params = new URLSearchParams({ format, template_type: template });
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const ventureId = activeVentureStorage.get();
  if (ventureId !== null) headers.set("X-Venture-Id", String(ventureId));
  const response = await fetch(`${API_BASE_URL}/invoices/${invoiceId}/document?${params}`, { headers });
  if (!response.ok) {
    let message = "Invoice document could not be generated.";
    try {
      const body = await response.json() as { error?: { message?: string }; detail?: string };
      message = body.error?.message ?? body.detail ?? message;
    } catch {
      // Keep the user-facing error stable when a proxy returns non-JSON content.
    }
    throw new ApiError(message, response.status, "invoice_document_error");
  }
  return response;
}

export async function openInvoicePrintPreview(token: string, invoiceId: number, template: InvoiceTemplate): Promise<void> {
  const popup = window.open("about:blank", "_blank");
  if (!popup) throw new ApiError("Allow pop-ups to print the invoice.", 0, "popup_blocked");
  try {
    const response = await documentResponse(token, invoiceId, "html", template);
    popup.document.open();
    popup.document.write(await response.text());
    popup.document.close();
    popup.focus();
  } catch (error) {
    popup.close();
    throw error;
  }
}

export async function downloadInvoicePdf(token: string, invoiceId: number, template: InvoiceTemplate): Promise<void> {
  const response = await documentResponse(token, invoiceId, "pdf", template);
  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ?? `invoice-${invoiceId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}
